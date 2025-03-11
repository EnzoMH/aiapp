from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

class Database:
    client: AsyncIOMotorClient = None
    
    @classmethod
    def build_connection_string(cls):
        # 로컬 MongoDB 연결 문자열
        host = os.getenv('MONGODB_HOST', 'localhost')
        port = os.getenv('MONGODB_PORT', '27017')
        return f"mongodb://{host}:{port}"
    
    @classmethod
    async def connect_db(cls):
        try:
            connection_string = cls.build_connection_string()
            cls.client = AsyncIOMotorClient(connection_string)
            
            # 데이터베이스 초기화 및 인덱스 생성
            db = cls.get_database()
            await db.users.create_index("username", unique=True)
            await db.users.create_index("email", unique=True)
            
            # 연결 테스트
            await cls.client.admin.command('ping')
            print("로컬 MongoDB에 성공적으로 연결되었습니다!")
            
        except Exception as e:
            print(f"MongoDB 연결 실패: {e}")
            raise e
    
    @classmethod
    async def close_db(cls):
        if cls.client:
            cls.client.close()
            print("MongoDB 연결이 종료되었습니다.")
    
    @classmethod
    def get_database(cls):
        return cls.client[os.getenv('DATABASE_NAME', 'progen_db')]
    
    @classmethod
    def get_user_collection(cls):
        db = cls.get_database()
        return db.users

db = Database()