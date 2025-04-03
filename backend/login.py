from fastapi import Depends, HTTPException, status, Request, Response, Header
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from jose import JWTError, jwt, ExpiredSignatureError
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from typing import Optional, Dict, List, Union, Callable
import logging
import json
import traceback

from dbcon import get_db, AuthUtils, User, UserRole

# .env 파일 로드
load_dotenv()

# 환경 변수에서 JWT 시크릿 키 가져오기
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY 환경 변수가 설정되지 않았습니다.")

# JWT 알고리즘
ALGORITHM = "HS256"

# OAuth2 스키마 - tokenUrl을 절대 경로로 변경
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

# 표준 오류 응답 코드
class ErrorCode:
    INVALID_TOKEN = "auth_001"
    EXPIRED_TOKEN = "auth_002"
    INVALID_SIGNATURE = "auth_003"
    TOKEN_REQUIRED = "auth_004"
    PERMISSION_DENIED = "auth_005"
    USER_NOT_FOUND = "auth_006"

# 표준화된 오류 응답 생성
def create_error_response(code: str, message: str, status_code: int = 401) -> JSONResponse:
    """표준화된 오류 응답 생성"""
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "timestamp": datetime.now().isoformat()
        },
        headers={"WWW-Authenticate": "Bearer"}
    )

# JWT 예외 처리 미들웨어
async def jwt_exception_middleware(request: Request, call_next: Callable):
    """JWT 관련 예외를 처리하는 미들웨어"""
    try:
        response = await call_next(request)
        return response
    except ExpiredSignatureError:
        return create_error_response(
            code=ErrorCode.EXPIRED_TOKEN,
            message="토큰이 만료되었습니다. 다시 로그인하세요.",
            status_code=401
        )
    except JWTError:
        return create_error_response(
            code=ErrorCode.INVALID_TOKEN,
            message="유효하지 않은 토큰입니다.",
            status_code=401
        )

class LoginUtils:
    @staticmethod
    async def verify_user(token: str, db: Session = Depends(get_db)):
        """JWT 토큰 검증 및 사용자 정보 반환"""
        # 로거 가져오기
        logger = logging.getLogger("backend.login")
        logger.debug(f"토큰 검증 시작: {token[:15]}...")
        
        try:
            # 디버깅용 만료 검사 없이 디코딩 시도
            try:
                payload_debug = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
                exp_time = datetime.fromtimestamp(payload_debug.get("exp", 0))
                now = datetime.utcnow()
                
                if "exp" in payload_debug:
                    if exp_time < now:
                        delta = now - exp_time
                        logger.warning(f"토큰 만료됨: {exp_time.isoformat()}, 현재: {now.isoformat()}, 만료 경과: {delta}")
                    else:
                        delta = exp_time - now
                        logger.debug(f"토큰 유효함: {exp_time.isoformat()}, 현재: {now.isoformat()}, 남은 시간: {delta}")
            except Exception as e:
                logger.warning(f"토큰 디버깅 중 오류: {str(e)}")
            
            # 실제 토큰 디코딩 (만료 검사 포함)
            try:
                payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
                logger.debug(f"토큰 페이로드 디코딩 성공")
            except ExpiredSignatureError as exp_error:
                logger.warning(f"토큰 만료 예외: {str(exp_error)}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"code": ErrorCode.EXPIRED_TOKEN, "message": "Token has expired"},
                    headers={"WWW-Authenticate": "Bearer", "X-Error-Code": "TOKEN_EXPIRED"},
                )
            
            user_id = payload.get("sub")
            if user_id is None:
                logger.error("페이로드에 'sub' 필드가 없습니다")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"code": ErrorCode.INVALID_TOKEN, "message": "Invalid token payload"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            logger.debug(f"사용자 ID '{user_id}' 조회 중")
            
            # 사용자 조회
            user = AuthUtils.get_user_by_id(db, user_id)
            if user is None:
                logger.error(f"사용자 ID '{user_id}'를 찾을 수 없습니다")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"code": ErrorCode.USER_NOT_FOUND, "message": "User not found"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # 사용자 정보 반환
            user_dict = user.to_dict()
            logger.debug(f"사용자 '{user_id}' 검증 성공")
            return user_dict
            
        except ExpiredSignatureError:
            logger.error("토큰이 만료되었습니다")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": ErrorCode.EXPIRED_TOKEN, "message": "Token has expired"},
                headers={"WWW-Authenticate": "Bearer", "X-Error-Code": "TOKEN_EXPIRED"},
            )
        except JWTError as e:
            logger.error(f"JWT 토큰 디코딩 오류: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": ErrorCode.INVALID_TOKEN, "message": "Invalid token"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"사용자 검증 중 예외 발생: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "server_error", "message": "Internal server error"},
            )
    
    @staticmethod
    def decode_token_without_verification(token: str) -> Dict:
        """만료된 토큰에서도 페이로드 추출 (갱신용)"""
        logger = logging.getLogger("backend.login")
        
        try:
            # 토큰 형식 간단 검사
            parts = token.split('.')
            if len(parts) != 3:
                logger.error(f"잘못된 JWT 토큰 형식: 부분이 3개가 아님")
                return {}
                
            # 만료 검사 없이 디코딩
            payload = jwt.decode(
                token, 
                JWT_SECRET_KEY, 
                algorithms=[ALGORITHM], 
                options={"verify_exp": False, "verify_signature": True}
            )
            
            # 중요 필드 확인
            if "sub" not in payload:
                logger.warning(f"JWT 페이로드에 'sub' 필드가 없음")
                return {}
                
            logger.debug(f"토큰 페이로드 추출 성공 (검증 없음): sub={payload.get('sub')}, 만료시간={datetime.fromtimestamp(payload.get('exp', 0)).isoformat() if 'exp' in payload else 'None'}")
            return payload
        except jwt.JWTError as e:
            logger.error(f"JWT 토큰 페이로드 추출 오류: {str(e)}")
            return {}
        except Exception as e:
            logger.error(f"토큰 디코딩 중 예외 발생: {str(e)}")
            return {}
    
    @staticmethod
    def create_user_token(user: Dict, expires_delta: Optional[timedelta] = None):
        """사용자 JWT 토큰 생성"""
        logger = logging.getLogger("backend.login")
        
        to_encode = user.copy()
        
        # 'sub' 필드가 없으면 추가 (사용자 ID를 sub 필드에 저장)
        if "sub" not in to_encode and "id" in to_encode:
            to_encode["sub"] = to_encode["id"]
        
        # 만료 시간 설정
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
            logger.debug(f"토큰 만료 시간 설정: {expires_delta} (사용자 지정)")
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
            logger.debug(f"토큰 만료 시간 설정: 15분 (기본값)")
        
        to_encode.update({"exp": expire})
        
        # 디버깅을 위한 로그 추가
        logger.debug(f"토큰 페이로드 생성: sub={to_encode.get('sub')}, exp={expire.isoformat()}")
        
        # 토큰 생성
        encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
        
        # 토큰 확인 테스트
        try:
            decoded = jwt.decode(encoded_jwt, JWT_SECRET_KEY, algorithms=[ALGORITHM])
            logger.debug(f"토큰 검증 성공: sub={decoded.get('sub')}, exp={datetime.fromtimestamp(decoded.get('exp')).isoformat()}")
        except Exception as e:
            logger.error(f"생성된 토큰 검증 실패: {str(e)}")
        
        return {"access_token": encoded_jwt, "token_type": "bearer"}
    
    @staticmethod
    def verify_role(user: Dict, allowed_roles: List[UserRole]):
        """사용자 역할 검증"""
        if user["role"] not in [role.value for role in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": ErrorCode.PERMISSION_DENIED, "message": "Permission denied"}
            )

class UserAuth:
    def __init__(self):
        pass
    
    def authenticate_user(self, username: str, password: str, db: Session = Depends(get_db)):
        """사용자 인증"""
        return AuthUtils.authenticate_user(db, username, password)
    
    def load_users(self, db: Session = Depends(get_db)):
        """모든 사용자 조회"""
        return AuthUtils.get_all_users(db)
    
    def create_user(self, user_id: str, password: str, role: UserRole = UserRole.USER, db: Session = Depends(get_db)):
        """새 사용자 생성"""
        return AuthUtils.create_user(db, user_id, password, role)
    
    def get_user_by_id(self, db: Session, user_id: str):
        """ID로 사용자 조회"""
        user = AuthUtils.get_user_by_id(db, user_id)
        if user:
            return user.to_dict()
        return None

# JWT 토큰 의존성 - 만료된 토큰에 대해 더 명확한 오류 응답 반환
async def get_token_with_error_handling(authorization: str = Header(None)):
    """인증 헤더에서 토큰 추출 및 기본 검증"""
    logger = logging.getLogger("backend.login")
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": ErrorCode.TOKEN_REQUIRED, "message": "Authorization header missing"},
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    scheme, token = authorization.split()
    if scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail={"code": ErrorCode.INVALID_TOKEN, "message": "Invalid authentication scheme"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # 토큰 기본 검증
        jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        return token
    except ExpiredSignatureError:
        logger.warning("토큰 만료 감지")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": ErrorCode.EXPIRED_TOKEN, "message": "Token has expired"},
            headers={"WWW-Authenticate": "Bearer", "X-Error-Code": "TOKEN_EXPIRED"},
        )
    except JWTError as e:
        logger.error(f"토큰 검증 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": ErrorCode.INVALID_TOKEN, "message": "Invalid token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

# 인증 핸들러 인스턴스 생성
auth_handler = UserAuth()