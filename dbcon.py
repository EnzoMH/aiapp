from sqlalchemy import create_engine, text, Column, String, Float, DateTime, Boolean, ForeignKey, Enum, Text, ARRAY
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus
import uuid
from datetime import datetime
import enum
from passlib.context import CryptContext

# .env 파일 로드
load_dotenv()

# 환경 변수에서 데이터베이스 연결 URL 가져오기
PSQL_URL = os.getenv("PSQL_URL")
if not PSQL_URL:
    # 환경 변수가 없는 경우 기본값 설정 (개발 환경용)
    DB_USER = "postgres"
    DB_PASSWORD = quote_plus("Smh213417!")
    DB_HOST = "localhost"
    DB_PORT = "5432"
    DB_NAME = "progen"
    PSQL_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Engine 생성
engine = create_engine(
    PSQL_URL,
    echo=True,  # SQL 쿼리 로깅 활성화
)

# SessionLocal 클래스 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 클래스 생성
Base = declarative_base()

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
    system_prompt = Column(Text, default="당신은 도움이 되는 AI 어시스턴트입니다. 사용자의 질문에 대해 정확하고 친절하게 답변하세요.")
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

# DB 세션 생성 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 데이터베이스 연결 테스트
def test_connection():
    try:
        with engine.connect() as connection:
            # text() 함수를 사용하여 SQL 문자열을 실행 가능한 객체로 변환
            result = connection.execute(text("SELECT 1"))
            print("데이터베이스 연결 성공!")
            
            # 테이블 확인
            result = connection.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
            tables = [row[0] for row in result]
            print(f"데이터베이스 테이블 목록: {', '.join(tables)}")
            
            # 사용자 데이터 확인
            result = connection.execute(text("SELECT user_id, role FROM users"))
            users = [f"{row[0]} ({row[1]})" for row in result]
            print(f"등록된 사용자: {', '.join(users)}")
            
            return True
    except Exception as e:
        print(f"데이터베이스 연결 실패: {str(e)}")
        return False

# 사용자 인증 관련 유틸리티 함수
class AuthUtils:
    @staticmethod
    def get_user_by_id(db, user_id):
        """사용자 ID로 사용자 조회"""
        return db.query(User).filter(User.user_id == user_id).first()
    
    @staticmethod
    def authenticate_user(db, username, password):
        """사용자 인증"""
        user = db.query(User).filter(User.user_id == username).first()
        if not user:
            return None
        if not user.verify_password(password):
            return None
        
        # 마지막 로그인 시간 업데이트
        user.last_login = datetime.utcnow()
        db.commit()
        
        return user.to_dict()
    
    @staticmethod
    def create_user(db, user_id, password, role=UserRole.USER):
        """새 사용자 생성"""
        hashed_password = User.get_password_hash(password)
        user = User(
            user_id=user_id,
            password=hashed_password,
            role=role
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.to_dict()
    
    @staticmethod
    def get_all_users(db):
        """모든 사용자 조회"""
        users = db.query(User).all()
        return [user.to_dict() for user in users]

if __name__ == "__main__":
    test_connection()