from fastapi import FastAPI, WebSocket, Request, UploadFile, File, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
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
import json

# login utils import, 로그인 유틸 가져오기
from backend.login import LoginUtils, UserRole
# prop utils import, 문서 유틸 가져오기
from backend.prop import process_file, clean_text
# chat utils import, 채팅 유틸 가져오기
from backend.chat import ChatManager, ChatSession
# Agent utils import, 에이전트 유틸 가져오기
from backend.utils.agent.ai import WebSocketManager, FileHandler
# chat utils import, 채팅 유틸 가져오기
from backend.utils.chat.models import ChatMessage, MessageRole
# chat utils import, 채팅 유틸 가져오기
from backend.utils.chat.ai_models import AIModel
# chat utils import, 채팅 유틸 가져오기
from backend.utils.chat.handlers import MessageHandler
# Session class of SQLAlchemy import, 세션 클래스 가져오기
from sqlalchemy.orm import Session

# DB uils function import, DB 유틸 함수 가져오기
from backend.utils.db import engine, SessionLocal, Base, get_db, test_connection
from backend.dbm import UserManager, SessionManager, MessageManager, MemoryManager

# 크롤링 라우터 import
from backend.crawl import router as crawl_router

# .env 파일 로드
load_dotenv()

from fastapi.responses import JSONResponse
from backend.utils.json_encoder import CustomJSONEncoder



# JWT 설정
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"

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

app.json_encoder = CustomJSONEncoder

# 정적 파일 및 템플릿 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="static")

# 크롤링 라우터 등록
app.include_router(crawl_router, tags=["crawling"])

# 매니저 초기화
ACCESS_TOKEN_EXPIRE_MINUTES = 30
ws_manager = WebSocketManager()
file_handler = FileHandler()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

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

@app.get("/prop", response_class=HTMLResponse) # 현재 html파일은 없음 
async def prop(request: Request):
    return templates.TemplateResponse("prop.html", {"request": request})

@app.get("/crawl", response_class=HTMLResponse)
async def crawl(request: Request):
    return templates.TemplateResponse("crawl.html", {"request": request})

@app.post("/api/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = UserManager.authenticate_user(db, form_data.username, form_data.password)
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

# 수정된 코드
@app.get("/api/admin/users")
async def get_all_users(
    current_role: str = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    return UserManager.get_all_users(db)

@app.websocket("/chat")
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    await websocket.accept()
    db = SessionLocal()
    user_id = None
    
    try:
        # 사용자 인증
        user = await LoginUtils.verify_user(token, db)
        user_id = user["id"]
        
        # 첫 메시지를 받아서 모델 정보 확인
        first_message = await websocket.receive_text()
        message_data = json.loads(first_message)
        model_type = message_data.get("model", "meta")  # 기본값은 meta
        
        # 세션 ID 확인 - 기존 세션이거나 새 세션
        session_id = message_data.get("session_id")
        if session_id:
            # 기존 세션 검증
            session = SessionManager.get_session_by_id(db, session_id)
            if not session or session["user_id"] != user_id:
                # 유효하지 않은 세션 ID - 새로 생성
                session = SessionManager.create_session(db, user_id, model_type)
                session_id = str(session["session_id"])
        else:
            # 세션 생성 (클라이언트 선택 모델 사용)
            session = SessionManager.create_session(db, user_id, model_type)
            session_id = str(session["session_id"])
        
        # 연결 성공 메시지 전송
        await websocket.send_json({
            "type": "connection_established",
            "data": {
                "user_id": user_id,
                "session_id": session_id,
                "model": model_type
            }
        })
        
        # 첫 메시지 처리
        if message_data.get("type") == "message" and message_data.get("content"):
            print(f"첫 메시지 처리 시작: {message_data.get('content')}")
            
            # 첫 메시지 처리 - ChatManager의 process_message 메소드 사용
            response = await chat_manager.process_message(
                user_id=user_id,
                content=message_data.get("content", ""),
                session_id=session_id,
                model=model_type
            )
            print(f"process_message 응답: {response}")
            
            # 응답 내용 확인
            if response and "message" in response and "content" in response["message"]:
                # 실시간 응답 전송 (프론트엔드에서 표시용)
                await websocket.send_json({
                    "type": "assistant",  # 프론트엔드가 기대하는 타입
                    "content": response["message"]["content"],
                    "model": model_type,
                    "session_id": session_id
                })
                
                # 메시지 완료 신호 전송
                await websocket.send_json({
                    "type": "message_complete",
                    "data": {
                        "session_id": session_id
                    }
                })
            else:
                print("응답에 메시지 또는 내용이 없습니다.")
        
        # 클라이언트 연결 등록 (세션 ID도 함께 전달)
        await chat_manager.connect_client(websocket, user_id, session_id)
        
        # 메시지 처리 시작
        await message_handler.handle_message(websocket, user_id, session_id)
            
    except Exception as e:
        print(f"WebSocket 처리 오류: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": f"처리 중 오류가 발생했습니다: {str(e)}"}
            })
        except:
            pass
    finally:
        # 연결 정리
        if user_id:
            chat_manager.disconnect_client(user_id)
        db.close()

# 세션 상태 업데이트 API 추가
@app.post("/api/chat/session/{session_id}/status")
async def update_session_status(
    session_id: str,
    status_data: Dict[str, bool],
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """세션 활성 상태 업데이트"""
    try:
        # 세션 소유자 확인
        session = SessionManager.get_session_by_id(db, session_id)
        if not session or session["user_id"] != current_user["id"]:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # 세션 상태 업데이트
        result = SessionManager.update_session(db, session_id, active=status_data["active"])
        if not result:
            raise HTTPException(status_code=500, detail="Failed to update session")
        
        return {"status": "success"}
    except Exception as e:
        print(f"Error updating session status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 최근 세션 조회 API 추가
@app.get("/api/chat/recent-sessions")
async def get_recent_sessions(
    limit: int = 10,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """사용자의 최근 대화 세션 목록 조회"""
    user_id = current_user["id"]
    chat_manager = ChatManager()
    sessions = await chat_manager.get_recent_sessions(user_id, limit)
    return sessions

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

# 애플리케이션 시작 시 데이터베이스 연결 테스트
@app.on_event("startup")
async def startup_event():
    test_connection()

# 테스트 엔드포인트 추가
@app.get("/api/test-token")
async def test_token(token: str = None):
    if not token:
        return {"status": "error", "message": "토큰이 제공되지 않았습니다"}
    
    try:
        # 토큰 디코딩 시도
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        return {"status": "success", "payload": payload}
    except Exception as e:
        return {"status": "error", "message": f"토큰 디코딩 오류: {str(e)}"}

@app.post("/api/chat/history")
async def save_chat_history(
    chat_history: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """대화 내용 저장"""
    try:
        session = SessionManager.get_session_by_id(db, chat_history["session_id"])
        if not session or session["user_id"] != current_user["id"]:
            raise HTTPException(status_code=404, detail="Session not found")
        
        success = MessageManager.save_chat_session(db, chat_history)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save chat history")
        
        return {"status": "success"}
    except Exception as e:
        print(f"Error saving chat history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/chat/histories")
async def get_chat_histories(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """사용자의 모든 대화 세션 목록 조회"""
    user_id = current_user["id"]
    sessions = SessionManager.get_user_sessions(db, user_id)
    
    # 각 세션별 미리보기 추가
    for session in sessions:
        # 첫 메시지 또는 가장 최근 메시지를 미리보기로 사용
        preview_message = MessageManager.get_session_preview(db, session["session_id"])
        session["preview"] = preview_message.get("content", "새로운 대화") if preview_message else "새로운 대화"
    
    return sessions

@app.get("/api/chat/session/{session_id}")
async def get_chat_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """특정 세션의 대화 내용 조회"""
    # 세션 소유자 확인
    session = SessionManager.get_session_by_id(db, session_id)
    if not session or session["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = MessageManager.get_session_messages(db, session_id)
    return {
        "session_id": session_id,
        "model": session["model"],
        "messages": messages
    }
    
@app.delete("/api/chat/session/{session_id}")
async def delete_chat_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """특정 세션 삭제"""
    # 세션 소유자 확인
    session = SessionManager.get_session_by_id(db, session_id)
    if not session or session["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if SessionManager.delete_session(db, session_id):
        return {"status": "success", "message": "Session deleted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete session")


@app.post("/api/chat/session/{session_id}/title")
async def update_session_title(
    session_id: str,
    title_data: Dict[str, str],
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """세션 제목 업데이트"""
    try:
        # 세션 소유자 확인
        session = SessionManager.get_session_by_id(db, session_id)
        if not session or session["user_id"] != current_user["id"]:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # 세션 제목 업데이트
        result = SessionManager.update_session(db, session_id, title=title_data["title"])
        if not result:
            raise HTTPException(status_code=500, detail="Failed to update session title")
        
        return {"status": "success"}
    except Exception as e:
        print(f"Error updating session title: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 크롤링용 웹소켓 엔드포인트
@app.websocket("/ws")
async def crawling_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = id(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            # 클라이언트로부터의 메시지 처리
            await handle_websocket_message(websocket, data)
    except Exception as e:
        logger.error(f"크롤링 WebSocket 오류: {str(e)}")
    finally:
        pass

# 크롤링 웹소켓 메시지 처리
async def handle_websocket_message(websocket: WebSocket, message: str):
    try:
        data = json.loads(message)
        message_type = data.get("type")
        
        # 크롤링 라우터의 처리 함수 사용
        from backend.crawl import start_crawling, stop_crawling, send_status_update
        
        if message_type == "start_crawling":
            await start_crawling(websocket)
        elif message_type == "stop_crawling":
            await stop_crawling(websocket)
        elif message_type == "get_status":
            await send_status_update(websocket)
            
    except json.JSONDecodeError:
        await websocket.send_json({
            "type": "error",
            "message": "잘못된 JSON 형식입니다."
        })
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": f"처리 중 오류 발생: {str(e)}"
        })

if __name__ == "__main__":
    init()
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        use_colors=True
    )