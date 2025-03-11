from fastapi import FastAPI, WebSocket, Request, UploadFile, File, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import uvicorn
from datetime import timedelta
from colorama import init
from typing import List
import os
from dotenv import load_dotenv
import jwt

from backend.utils.agent.ai import WebSocketManager, FileHandler
from backend.login import LoginUtils, auth_handler, UserRole
from chat import ChatManager, MessageHandler, AIModel, MessageRole, ChatMessage, ChatSession

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