from fastapi import FastAPI, WebSocket, Request, UploadFile, File, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import uvicorn
from datetime import timedelta
from colorama import init
from typing import List, Dict, Any
import os
from dotenv import load_dotenv
import jwt
import asyncio
import json
import argparse
import logging

# 로깅 설정 추가
logging.basicConfig(
    level=logging.INFO,  # 기본 레벨은 INFO로 설정
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("server.log", mode="a", encoding="utf-8")
    ]
)
logger = logging.getLogger("app")  # 애플리케이션 전용 로거 생성

from backend.utils.agent.ai import WebSocketManager, FileHandler
from backend.login import LoginUtils, auth_handler, UserRole
from chat import ChatManager, MessageHandler, AIModel, MessageRole, ChatMessage, ChatSession
from backend.crawl import crawling_state, start_crawling, stop_crawling, get_results

# SQLAlchemy의 Session 클래스 가져오기
from sqlalchemy.orm import Session

# dbcon.py에서 필요한 것들을 가져옵니다
from dbcon import engine, SessionLocal, Base, get_db, test_connection
from docpro import process_file, clean_text

# .env 파일 로드
load_dotenv()

chat_manager = ChatManager()
message_handler = MessageHandler(chat_manager)

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 및 템플릿 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="static")

# 매니저 초기화
ACCESS_TOKEN_EXPIRE_MINUTES = 30
ws_manager = WebSocketManager()
file_handler = FileHandler()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

# CLI 옵션 처리를 위한 인자 파서 추가
def parse_args():
    """명령줄 인수 파싱"""
    parser = argparse.ArgumentParser(description="나라장터 크롤링")
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 로깅 활성화")
    parser.add_argument("--headless", action="store_true", help="헤드리스 모드 사용 (기본값: True)")
    
    return parser.parse_args()

# 현재 사용자 가져오기
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    return await LoginUtils.verify_user(token, db)

# 권한 확인
def require_role(allowed_roles: List[UserRole]):
    async def role_checker(user: dict = Depends(get_current_user)):
        LoginUtils.verify_role(user, allowed_roles)
        return user["role"]
    return role_checker

# 라우트 정의
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/home", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

# 크롤링 페이지 추가
@app.get("/crawl", response_class=HTMLResponse)
async def crawl_page(request: Request):
    return templates.TemplateResponse("crawl.html", {"request": request})

@app.post("/api/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = auth_handler.authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect ID or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return LoginUtils.create_user_token(user, expires_delta)

@app.get("/api/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user

@app.get("/api/admin/users")
async def get_all_users(
    current_role: str = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    return auth_handler.load_users(db)

# WebSocket 엔드포인트
@app.websocket("/chat")
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    # 사용자 인증 처리
    if token:
        try:
            # WebSocket에서는 Depends를 사용할 수 없으므로 직접 세션 생성
            db = SessionLocal()
            try:
                user = await LoginUtils.verify_user(token, db)
                user_id = user["id"]
            finally:
                db.close()
        except:
            await websocket.close(code=1008, reason="인증 실패")
            return
    else:
        # 인증 없이 테스트용 (실제 환경에서는 제거)
        user_id = "anonymous_user"
    
    # 클라이언트 연결
    await chat_manager.connect_client(websocket, user_id)
    
    try:
        # 연결 성공 메시지
        await websocket.send_json({
            "type": "connection_established",
            "data": {"user_id": user_id}
        })
        
        # 메시지 처리 핸들러에 위임
        await message_handler.handle_message(websocket, user_id)
            
    except Exception as e:
        print(f"WebSocket 오류: {str(e)}")
    finally:
        # 연결 종료 시 클라이언트 연결 해제
        chat_manager.disconnect_client(user_id)

# 크롤링 WebSocket 엔드포인트
@app.websocket("/ws")
async def crawl_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    crawling_state.add_connection(websocket)
    
    try:
        # 연결 성공 메시지
        await websocket.send_json({
            "type": "connection_established",
            "message": "WebSocket 연결이 설정되었습니다."
        })
        
        # 현재 상태 전송
        await crawling_state.broadcast_status()
        
        # 메시지 수신 대기
        while True:
            await websocket.receive_text()  # 클라이언트 메시지 수신
            
    except Exception as e:
        print(f"크롤링 WebSocket 오류: {str(e)}")
    finally:
        # 연결 종료 시 제거
        crawling_state.remove_connection(websocket)

# AI 에이전트 WebSocket 엔드포인트
@app.websocket("/ws/agent")
async def agent_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    try:
        # 연결 성공 메시지
        await websocket.send_json({
            "type": "connection_established",
            "message": "AI 에이전트 WebSocket 연결이 설정되었습니다."
        })
        
        # AI 에이전트 기능 사용 불가 메시지
        await websocket.send_json({
            "type": "notice",
            "message": "AI 에이전트 기능은 현재 개발 중입니다."
        })
        
        # 연결 유지 및 메시지 수신 대기
        while True:
            data = await websocket.receive_text()
            logger.debug(f"AI 에이전트 메시지 수신 (무시됨): {data[:100]}")
                
    except Exception as e:
        logger.error(f"AI 에이전트 WebSocket 오류: {str(e)}")
    finally:
        # 연결 종료 시 처리 (필요한 경우 정리 작업 추가)
        logger.info("AI 에이전트 WebSocket 연결 종료")

# 크롤링 API 엔드포인트
@app.post("/api/start")
async def api_start_crawling(request: Dict[str, Any]):
    """크롤링 시작 API"""
    try:
        # Pydantic 모델로 요청 검증
        from backend.utils.crawl.models import CrawlingRequest, CrawlingResponse
        
        # 날짜 처리
        start_date = request.get("startDate", "")
        end_date = request.get("endDate", "")
        
        # 키워드 및 헤드리스 모드 설정
        keywords = request.get("keywords", None)
        headless = parse_args().headless if hasattr(parse_args(), 'headless') else True
        
        # Pydantic 모델로 변환하여 검증
        crawl_request = CrawlingRequest(
            start_date=start_date if not start_date else None,
            end_date=end_date if not end_date else None,
            keywords=keywords if keywords else [],
            headless=headless,
            client_info=request.get("clientInfo", {})
        )
        
        # 요청 로깅
        logger.info(f"크롤링 시작 요청: {crawl_request.json(exclude={'client_info'})}")
        
        # 크롤링 시작
        result = await start_crawling(
            crawl_request.start_date, 
            crawl_request.end_date, 
            crawl_request.keywords, 
            crawl_request.headless
        )
        
        # Pydantic 모델로 응답 반환
        response = CrawlingResponse(
            status=result.get("status", "error"),
            message=result.get("message", "알 수 없는 오류가 발생했습니다."),
            results=result.get("results", []),
            crawling_status=None  # 필요시 상태 추가
        )
        
        return response.dict(exclude_none=True)
    except Exception as e:
        logger.exception(f"크롤링 시작 API 처리 중 예외 발생: {str(e)}")
        return {
            "status": "error",
            "message": f"서버 오류가 발생했습니다: {str(e)}"
        }

@app.post("/api/stop")
async def api_stop_crawling():
    """크롤링 중지 API"""
    try:
        from backend.utils.crawl.models import CrawlingResponse
        
        logger.info("크롤링 중지 요청 수신")
        
        result = stop_crawling()
        
        # Pydantic 모델로 응답 반환
        response = CrawlingResponse(
            status=result.get("status", "error"),
            message=result.get("message", "알 수 없는 오류가 발생했습니다."),
            results=None,
            crawling_status=None
        )
        
        return response.dict(exclude_none=True)
    except Exception as e:
        logger.exception(f"크롤링 중지 API 처리 중 예외 발생: {str(e)}")
        return {
            "status": "error",
            "message": f"서버 오류가 발생했습니다: {str(e)}"
        }

@app.get("/api/crawl-results/")
async def api_get_crawl_results():
    """크롤링 결과 조회 API"""
    try:
        from backend.utils.crawl.models import CrawlingResponse
        
        logger.info("크롤링 결과 조회 요청 수신")
        
        result = get_results()
        
        # Pydantic 모델로 응답 반환
        response = CrawlingResponse(
            status=result.get("status", "error"),
            message=result.get("message", "알 수 없는 오류가 발생했습니다."),
            results=result.get("results", []),
            crawling_status=None
        )
        
        result_count = len(response.results or [])
        logger.info(f"크롤링 결과 조회 성공: {result_count}건")
        
        return response.dict(exclude_none=True)
    except Exception as e:
        logger.exception(f"크롤링 결과 조회 API 처리 중 예외 발생: {str(e)}")
        return {
            "status": "error",
            "message": f"서버 오류가 발생했습니다: {str(e)}",
            "results": []
        }

# 파일 업로드 엔드포인트
@app.post("/mainupload")
async def upload_file(file: UploadFile = File(...)):
    # 파일 유효성 검사
    file_handler.validate_file(file.filename, 0)
    
    try:
        # docpro를 사용하여 파일에서 텍스트 추출
        extracted_text = await process_file(file)
        
        # 텍스트 정리
        cleaned_text = clean_text(extracted_text)
        
        # 텍스트 인코딩 문제 처리
        try:
            # UTF-8로 인코딩 확인
            cleaned_text.encode('utf-8')
        except UnicodeEncodeError:
            # 인코딩 문제가 있는 경우 대체
            cleaned_text = cleaned_text.encode('utf-8', errors='replace').decode('utf-8')
        
        # 텍스트 길이 계산
        text_length = len(cleaned_text)
        
        # 미리보기용 텍스트 (너무 길면 잘라서 반환)
        preview_text = cleaned_text[:1000] + "..." if text_length > 1000 else cleaned_text
        
        return {
            "filename": file.filename,
            "status": "success",
            "text_length": text_length,
            "preview": preview_text,
            "full_text": cleaned_text  # 전체 텍스트 반환 (필요에 따라 제거 가능)
        }
    except HTTPException as e:
        # 이미 HTTPException이면 그대로 전달
        raise e
    except Exception as e:
        # 기타 예외는 500 오류로 변환
        raise HTTPException(
            status_code=500,
            detail=f"파일 처리 중 오류 발생: {str(e)}"
        )

# AI 에이전트 API 엔드포인트
@app.post("/api/agent/start")
async def start_agent_crawling(data: dict):
    """AI 에이전트 크롤링 시작 - 개발 중인 기능"""
    logger.info(f"AI 에이전트 시작 요청 (개발 중): {data}")
    
    return {
        "status": "notice",
        "message": "AI 에이전트 기능은 현재 개발 중입니다.",
        "current_status": "development"
    }

@app.post("/api/agent/stop")
async def stop_agent_crawling():
    """AI 에이전트 크롤링 중지 - 개발 중인 기능"""
    logger.info("AI 에이전트 중지 요청 (개발 중)")
    
    return {
        "status": "notice",
        "message": "AI 에이전트 기능은 현재 개발 중입니다."
    }

@app.get("/api/agent/results")
async def get_agent_results():
    """AI 에이전트 결과 조회 - 개발 중인 기능"""
    logger.info("AI 에이전트 결과 조회 요청 (개발 중)")
    
    return {
        "status": "notice",
        "message": "AI 에이전트 기능은 현재 개발 중입니다.",
        "results": []
    }

# 애플리케이션 시작 시 데이터베이스 연결 테스트
@app.on_event("startup")
async def startup_event():
    test_connection()
    
    # 로깅 레벨 설정 - 항상 DEBUG로 설정
    logging.getLogger().setLevel(logging.DEBUG)
    
    # 크롤링 관련 로거 설정
    for logger_name in ['backend.crawl', 'backend.utils.crawl.crawler', 'backend.utils.crawl.crawler_manager']:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        
        # 기존 핸들러 설정 유지하면서 추가 포맷팅
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setFormatter(logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                ))
    
    logging.debug("애플리케이션이 시작되었습니다. 디버그 모드가 활성화되었습니다.")
    print("애플리케이션이 시작되었습니다.")

# 애플리케이션 종료 시 리소스 정리
@app.on_event("shutdown")
async def shutdown_event():
    print("애플리케이션이 종료되었습니다.")

if __name__ == "__main__":
    init()
    
    # 명령줄 인수 파싱
    args = parse_args()
    
    # 서버 설정
    host = "0.0.0.0"
    port = 8000
    
    # 서버 실행
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=True,
        log_level="info" if not args.verbose else "debug",
        use_colors=True
    )