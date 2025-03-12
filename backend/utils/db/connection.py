"""
데이터베이스 연결 설정
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경 변수에서 데이터베이스 연결 URL 가져오기
PSQL_URL = os.getenv("PSQL_URL")
if not PSQL_URL:
    raise ValueError("PSQL_URL 환경 변수가 설정되지 않았습니다.")

# Engine 생성
engine = create_engine(
    PSQL_URL,
    echo=True,  # SQL 쿼리 로깅 활성화
)

# SessionLocal 클래스 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 클래스 생성
Base = declarative_base()

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