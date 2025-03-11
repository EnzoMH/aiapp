from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from typing import Optional, Dict, List

from dbcon import get_db, AuthUtils, User, UserRole

# .env 파일 로드
load_dotenv()

# 환경 변수에서 JWT 시크릿 키 가져오기
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY 환경 변수가 설정되지 않았습니다.")

# JWT 알고리즘
ALGORITHM = "HS256"

# OAuth2 스키마
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

class LoginUtils:
    @staticmethod
    async def verify_user(token: str, db: Session = Depends(get_db)):
        """JWT 토큰 검증 및 사용자 정보 반환"""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            # 디버깅 로그 추가
            print(f"검증 중인 토큰: {token[:10]}...")
            
            # 토큰 디코딩
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
            print(f"디코딩된 페이로드: {payload}")
            
            user_id: str = payload.get("sub")
            if user_id is None:
                print("페이로드에 'sub' 필드가 없습니다")
                raise credentials_exception
            
            # 사용자 조회
            user = AuthUtils.get_user_by_id(db, user_id)
            if user is None:
                print(f"사용자 ID '{user_id}'를 찾을 수 없습니다")
                raise credentials_exception
            
            return user.to_dict()
        except JWTError as e:
            print(f"JWT 오류: {str(e)}")
            raise credentials_exception
    
    @staticmethod
    def create_user_token(user: Dict, expires_delta: Optional[timedelta] = None):
        """사용자 JWT 토큰 생성"""
        to_encode = user.copy()
        
        # 'sub' 필드가 없으면 추가 (사용자 ID를 sub 필드에 저장)
        if "sub" not in to_encode and "id" in to_encode:
            to_encode["sub"] = to_encode["id"]
        
        # 만료 시간 설정
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        
        to_encode.update({"exp": expire})
        
        # 디버깅을 위한 로그 추가
        print(f"토큰 페이로드: {to_encode}")
        
        # 토큰 생성
        encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
        return {"access_token": encoded_jwt, "token_type": "bearer"}
    
    @staticmethod
    def verify_role(user: Dict, allowed_roles: List[UserRole]):
        """사용자 역할 검증"""
        if user["role"] not in [role.value for role in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied"
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

# 인증 핸들러 인스턴스 생성
auth_handler = UserAuth()