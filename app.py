from fastapi import FastAPI, WebSocket, Request, UploadFile, File, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import uvicorn
from datetime import timedelta, datetime
from colorama import init
from typing import List, Dict, Any
import os
from dotenv import load_dotenv
import jwt
import asyncio
import json
import argparse
import logging
import pandas as pd
from io import BytesIO
import traceback
import sys

# 로깅 설정 강화
logging.basicConfig(
    level=logging.INFO,  # 기본 레벨을 INFO로 변경
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger("app")  # 애플리케이션 전용 로거 생성
logger.setLevel(logging.INFO)  # 앱 로거 레벨을 INFO로 변경

# 추가 로거 설정
fastapi_logger = logging.getLogger("fastapi")
fastapi_logger.setLevel(logging.INFO)
uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.setLevel(logging.INFO)

from backend.utils.agent.ai import FileHandler
from backend.login import LoginUtils, auth_handler, UserRole
from backend.chat import ChatManager, MessageHandler, AIModel, MessageRole, ChatMessage, ChatSession
from backend.crawl import crawling_state, start_crawling, stop_crawling, get_results, get_crawling_status
from backend.websocket_manager import WebSocketManager, ChatWebSocketEndpoint, CrawlWebSocketEndpoint, AgentWebSocketEndpoint

# SQLAlchemy의 Session 클래스 가져오기
from sqlalchemy.orm import Session

# dbcon.py에서 필요한 것들을 가져옵니다
from backend.dbcon import engine, SessionLocal, Base, get_db, test_connection
from backend.docpro import process_file, clean_text

# .env 파일 로드
load_dotenv()

# 디버깅 정보 출력
logger.debug("Python 버전: %s", sys.version)
logger.debug("실행 경로: %s", os.getcwd())
logger.debug("모듈 검색 경로: %s", sys.path)

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
file_handler = FileHandler()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

# 웹소켓 관리자 초기화
websocket_manager = WebSocketManager()

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
    logger.debug("크롤링 페이지 요청 - 클라이언트: %s", request.client.host)
    try:
        response = templates.TemplateResponse("crawl.html", {"request": request})
        logger.debug("크롤링 페이지 응답 생성 - 상태 코드: %s", response.status_code)
        return response
    except Exception as e:
        logger.error("크롤링 페이지 렌더링 중 오류: %s", str(e))
        logger.error("상세 오류: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="페이지 렌더링 중 오류가 발생했습니다.")

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
    # 웹소켓 관리자의 채팅 엔드포인트에 처리 위임
    endpoint = websocket_manager.get_endpoint("/chat")
    await endpoint.handle_client(websocket, token)

# 크롤링 WebSocket 엔드포인트
@app.websocket("/ws")
async def crawl_websocket_endpoint(websocket: WebSocket):
    # 웹소켓 관리자의 크롤링 엔드포인트에 처리 위임
    endpoint = websocket_manager.get_endpoint("/ws")
    await endpoint.handle_client(websocket)

# AI 에이전트 WebSocket 엔드포인트
@app.websocket("/ws/agent")
async def agent_websocket_endpoint(websocket: WebSocket):
    # 웹소켓 관리자의 AI 에이전트 엔드포인트에 처리 위임
    endpoint = websocket_manager.get_endpoint("/ws/agent")
    await endpoint.handle_client(websocket)

# 크롤링 API 엔드포인트
@app.post("/api/start")
async def api_start_crawling(request: Dict[str, Any]):
    """크롤링 시작 API"""
    logger.debug("크롤링 시작 API 호출 - 요청 데이터: %s", request)
    try:
        # Pydantic 모델로 요청 검증
        from backend.utils.crawl.models import CrawlingRequest, CrawlingResponse
        
        # 날짜 처리
        start_date = request.get("startDate", "")
        end_date = request.get("endDate", "")
        
        # 키워드 및 헤드리스 모드 설정
        keywords = request.get("keywords", None)
        logger.debug("크롤링 키워드: %s, 시작일: %s, 종료일: %s", keywords, start_date, end_date)
        
        headless = parse_args().headless if hasattr(parse_args(), 'headless') else True
        
        # Pydantic 모델로 변환하여 검증
        crawl_request = CrawlingRequest(
            start_date=None if not start_date else start_date,
            end_date=None if not end_date else end_date,
            keywords=keywords if keywords else [],
            headless=headless,
            client_info=request.get("clientInfo", {})
        )
        
        # 요청 로깅
        logger.info(f"크롤링 시작 요청: {crawl_request.json(exclude={'client_info'})}")
        
        # 크롤링 시작
        logger.debug("start_crawling 함수 호출 전")
        result = await start_crawling(
            crawl_request.keywords, 
            crawl_request.headless,
            crawl_request.start_date, 
            crawl_request.end_date
        )
        logger.debug("start_crawling 함수 호출 후 - 결과: %s", result)
        
        # Pydantic 모델로 응답 반환
        response = CrawlingResponse(
            status=result.get("status", "error"),
            message=result.get("message", "알 수 없는 오류가 발생했습니다."),
            results=result.get("results", []),
            crawling_status=None  # 필요시 상태 추가
        )
        
        logger.debug("API 응답 생성 완료: %s", response.json())
        return response.dict(exclude_none=True)
    except Exception as e:
        logger.exception(f"크롤링 시작 API 처리 중 예외 발생: {str(e)}")
        logger.error("상세 오류: %s", traceback.format_exc())
        return {
            "status": "error",
            "message": f"서버 오류가 발생했습니다: {str(e)}"
        }

@app.post("/api/stop")
async def api_stop_crawling():
    """크롤링 중지 API"""
    logger.debug("크롤링 중지 API 호출")
    try:
        from backend.utils.crawl.models import CrawlingResponse
        
        logger.info("크롤링 중지 요청 수신")
        
        result = stop_crawling()
        logger.debug("stop_crawling 함수 결과: %s", result)
        
        # Pydantic 모델로 응답 반환
        response = CrawlingResponse(
            status=result.get("status", "error"),
            message=result.get("message", "알 수 없는 오류가 발생했습니다."),
            results=None,
            crawling_status=None
        )
        
        logger.debug("크롤링 중지 API 응답: %s", response.json())
        return response.dict(exclude_none=True)
    except Exception as e:
        logger.exception(f"크롤링 중지 API 처리 중 예외 발생: {str(e)}")
        logger.error("상세 오류: %s", traceback.format_exc())
        return {
            "status": "error",
            "message": f"서버 오류가 발생했습니다: {str(e)}"
        }

@app.get("/api/crawl-results/")
async def api_get_crawl_results():
    """크롤링 결과 조회 API"""
    logger.debug("크롤링 결과 조회 API 호출")
    try:
        from backend.utils.crawl.models import CrawlingResponse
        
        logger.info("크롤링 결과 조회 요청 수신")
        
        result = get_results()
        logger.debug("get_results 함수 결과: %s", result)
        
        # Pydantic 모델로 응답 반환
        response = CrawlingResponse(
            status=result.get("status", "error"),
            message=result.get("message", "알 수 없는 오류가 발생했습니다."),
            results=result.get("results", []),
            crawling_status=None
        )
        
        result_count = len(response.results or [])
        logger.info(f"크롤링 결과 조회 성공: {result_count}건")
        logger.debug("크롤링 결과 조회 API 응답: %s", response.json(exclude={"results"}))
        
        return response.dict(exclude_none=True)
    except Exception as e:
        logger.exception(f"크롤링 결과 조회 API 처리 중 예외 발생: {str(e)}")
        logger.error("상세 오류: %s", traceback.format_exc())
        return {
            "status": "error",
            "message": f"서버 오류가 발생했습니다: {str(e)}",
            "results": []
        }

# 크롤링 상태 확인 API 엔드포인트 추가
@app.get("/api/status")
async def api_get_crawling_status():
    """
    크롤링 상태 확인 API
    
    Returns:
        Dict: 현재 크롤링 상태 정보
    """
    try:
        logger.debug("크롤링 상태 조회 API 호출")
        
        # 크롤링 상태 정보 가져오기
        status_info = get_crawling_status()
        
        # 응답 구성
        response = {
            "status": "success",
            "message": "크롤링 상태 조회 성공",
            "data": status_info.get("data", {}),
            "timestamp": datetime.now().isoformat()
        }
        
        # 결과가 있으면 함께 반환
        if crawling_state.is_running:
            # 실행 중이면 현재까지 수집된 결과 반환
            results = get_results()
            response["results"] = results.get("results", [])
            response["total_items"] = len(results.get("results", []))
        else:
            # 실행 중이 아니면 전체 결과 반환
            results = get_results()
            response["results"] = results.get("results", [])
            response["total_items"] = len(results.get("results", []))
            
        # 응답 반환
        logger.debug(f"크롤링 상태 반환: is_running={crawling_state.is_running}, 결과 수={response.get('total_items', 0)}")
        return response
    
    except Exception as e:
        logger.exception(f"크롤링 상태 조회 중 오류: {str(e)}")
        return {
            "status": "error",
            "message": f"크롤링 상태 조회 중 오류가 발생했습니다: {str(e)}",
            "data": {},
            "timestamp": datetime.now().isoformat()
        }

# 크롤링 결과 다운로드 API 엔드포인트 추가
@app.get("/api/results/download")
async def api_download_results():
    """크롤링 결과 다운로드 API"""
    logger.debug("크롤링 결과 다운로드 API 호출")
    try:
        logger.info("크롤링 결과 다운로드 요청 수신")
        
        # backend.crawl 모듈에서 결과 가져오기
        result = get_results()
        logger.debug("get_results 함수 결과: %s", str(result)[:1000])  # 결과 로그 (일부만)
        
        # 결과 추출
        results = result.get("results", [])
        
        if not results:
            logger.warning("다운로드할 결과가 없음")
            return {
                "status": "error",
                "message": "다운로드할 결과가 없습니다."
            }
        
        # 데이터프레임 생성
        logger.debug("데이터프레임 생성 시작 - 결과 개수: %d", len(results))
        df = pd.DataFrame(results)
        logger.debug("데이터프레임 생성 완료 - 컬럼: %s", df.columns.tolist())
        
        # 엑셀 파일 생성
        output = BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)
        
        # 파일 이름 설정
        filename = f"crawling_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        logger.debug("엑셀 파일 생성 완료 - 파일명: %s", filename)
        
        # 스트리밍 응답으로 파일 전송
        logger.info("엑셀 파일 다운로드 응답 전송 - 파일명: %s", filename)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.exception(f"크롤링 결과 다운로드 API 처리 중 예외 발생: {str(e)}")
        logger.error("상세 오류: %s", traceback.format_exc())
        return {
            "status": "error",
            "message": f"서버 오류가 발생했습니다: {str(e)}"
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
    logger.info("=== 애플리케이션 시작 ===")
    logger.debug("데이터베이스 연결 테스트 시작")
    try:
        test_connection()
        logger.info("데이터베이스 연결 테스트 성공")
    except Exception as e:
        logger.error("데이터베이스 연결 테스트 실패: %s", str(e))
        logger.error("상세 오류: %s", traceback.format_exc())
    
    # 로깅 레벨 설정 - INFO로 변경
    logger.info("로깅 레벨 설정")
    logging.getLogger().setLevel(logging.INFO)
    
    # 크롤링 관련 로거 설정
    logger.info("크롤링 로거 설정")
    for logger_name in ['backend.crawl', 'backend.utils.crawl.crawler', 'backend.utils.crawl.crawler_manager']:
        log = logging.getLogger(logger_name)
        log.setLevel(logging.INFO)
        
        # 기존 핸들러 설정 유지하면서 추가 포맷팅
        for handler in log.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setFormatter(logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                ))
    
    # 웹소켓 엔드포인트 등록
    logger.debug("웹소켓 엔드포인트 등록")
    
    # 채팅 웹소켓 엔드포인트 등록
    chat_endpoint = ChatWebSocketEndpoint(chat_manager, message_handler, LoginUtils, SessionLocal)
    websocket_manager.register_endpoint(chat_endpoint)
    
    # 크롤링 웹소켓 엔드포인트 등록
    crawl_endpoint = CrawlWebSocketEndpoint(crawling_state)
    websocket_manager.register_endpoint(crawl_endpoint)
    
    # AI 에이전트 웹소켓 엔드포인트 등록
    agent_endpoint = AgentWebSocketEndpoint()
    websocket_manager.register_endpoint(agent_endpoint)
    
    logger.debug("애플리케이션 초기화 완료")
    print("애플리케이션이 시작되었습니다.")

# 애플리케이션 종료 시 리소스 정리
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("=== 애플리케이션 종료 ===")
    print("애플리케이션이 종료되었습니다.")

@app.post("/api/search")
async def api_search_bids(request: Request):
    """나라장터 API 검색 엔드포인트"""
    return {
        "success": False,
        "message": "나라장터 API 기능이 비활성화되었습니다. (SERVICE ERROR)",
        "error": "NO_OPENAPI_SERVICE_ERROR",
        "results": []
    }

if __name__ == "__main__":
    init()
    
    # 명령줄 인수 파싱
    args = parse_args()
    logger.debug("명령줄 인수: %s", args)
    
    # 서버 설정
    host = "0.0.0.0"
    port = 8000
    
    # 서버 실행
    logger.info("서버 시작 - 호스트: %s, 포트: %d", host, port)
    try:
        uvicorn.run(
            "app:app",
            host=host,
            port=port,
            reload=True,
            log_level="info",
            use_colors=True
        )
    except Exception as e:
        logger.error("서버 실행 중 오류: %s", str(e))
        logger.error("상세 오류: %s", traceback.format_exc())