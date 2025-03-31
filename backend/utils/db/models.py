"""
데이터베이스 모델 정의
"""
from sqlalchemy import Column, String, Float, DateTime, Boolean, ForeignKey, Enum, Text, ARRAY
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
import enum
from passlib.context import CryptContext

from backend.utils.db.connection import Base

# 비밀번호 해싱을 위한 유틸리티
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 사용자 역할 Enum
class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"

# 모델 정의
class User(Base):
    __tablename__ = "users"
    
    user_id = Column(String(50), primary_key=True)
    password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # 관계 정의
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="user", cascade="all, delete-orphan")
    
    def verify_password(self, plain_password):
        """비밀번호 검증 (임시 해결책)"""
        # 현재는 평문 비교 (보안상 좋지 않음)
        return plain_password == self.password
    
    @staticmethod
    def get_password_hash(password):
        """비밀번호 해싱"""
        return pwd_context.hash(password)
    
    def to_dict(self):
        """사용자 정보를 딕셔너리로 변환"""
        return {
            "id": self.user_id,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None
        }

class Session(Base):
    __tablename__ = "sessions"
    
    session_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(50), ForeignKey("users.user_id"))
    model = Column(String(20), nullable=False)
    title = Column(String(100), default="새 대화")  # default 말고 적합한 네이밍 필요. 대화내용에 대해서 요약을 하거나, 사용자의 첫 질문으로 가는 것으로
    system_prompt = Column(Text, default="당신은 도움이 되는 AI 어시스턴트입니다. 사용자의 질문에 대해 정확하고 친절하게 답변하세요.") # 시스템 프롬프트 체계화, 구체화, 모듈화 필요
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow)
    active = Column(Boolean, default=True)
    
    # 관계 정의
    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    
    message_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.session_id"))
    role = Column(String(10), nullable=False)
    content = Column(Text, nullable=False)
    model = Column(String(20), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # 관계 정의
    session = relationship("Session", back_populates="messages")

class Memory(Base):
    __tablename__ = "memories"
    
    memory_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(50), ForeignKey("users.user_id"))
    content = Column(Text, nullable=False)
    keywords = Column(ARRAY(String), default=[])
    importance = Column(Float, default=1.0)
    status = Column(String(10), default="active")
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # 관계 정의
    user = relationship("User", back_populates="memories")