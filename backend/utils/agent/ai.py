from datetime import datetime, timedelta
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
import json
from typing import Optional, Dict, List
from enum import Enum
from fastapi import WebSocket, HTTPException, status

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user" 
    GUEST = "guest"

class UserAuth:
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def load_users(self) -> List[Dict]:
        try:
            with open("users.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("users", [])
        except FileNotFoundError:
            return []
    
    def authenticate_user(self, user_id: str, password: str) -> Optional[Dict]:
        users = self.load_users()
        for user in users:
            if user["id"] == user_id and user["password"] == password:
                return user
        return None

    def validate_token(self, token: str) -> Optional[Dict]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            user_id: str = payload.get("sub")
            if user_id is None:
                return None
                
            users = self.load_users()
            user = next((u for u in users if u["id"] == user_id), None)
            return user
        except (ExpiredSignatureError, InvalidTokenError):
            return None

class TokenManager:
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def create_access_token(self, data: Dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)
            
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

class FileHandler:
    def __init__(self, allowed_extensions: List[str] = None, max_size: int = 10 * 1024 * 1024):
        self.allowed_extensions = allowed_extensions or ['.pdf', '.hwp', '.hwpx', '.doc', '.docx']
        self.max_size = max_size  # 10MB default
    
    def validate_file(self, filename: str, filesize: int) -> bool:
        ext = '.' + filename.split('.')[-1].lower()
        if ext not in self.allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file type"
            )
        if filesize > self.max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size too large"
            )
        return True