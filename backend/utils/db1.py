from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from urllib.parse import quote_plus
import os

load_dotenv()

class Database:
    local_client: AsyncIOMotorClient = None
    atlas_client: AsyncIOMotorClient = None
    current_connection: str = None
    
    @classmethod
    def build_connection_strings(cls):
        # 로컬 MongoDB 연결 문자열
        local_host = os.getenv('LOCAL_MONGODB_HOST', 'localhost')
        local_port = os.getenv('LOCAL_MONGODB_PORT', '27017')
        local_uri = f"mongodb://{local_host}:{local_port}"
        
        # Atlas MongoDB 연결 문자열
        atlas_username = os.getenv('ATLAS_MONGODB_USERNAME')
        atlas_password = quote_plus(os.getenv('ATLAS_MONGODB_PASSWORD'))
        atlas_host = os.getenv('ATLAS_MONGODB_HOST')
        atlas_uri = f"mongodb+srv://{atlas_username}:{atlas_password}@{atlas_host}/?retryWrites=true&w=majority"
        
        return local_uri, atlas_uri
    
    @classmethod
    async def connect_db(cls, connection_type='both'):
        try:
            local_uri, atlas_uri = cls.build_connection_strings()
            
            if connection_type in ['local', 'both']:
                cls.local_client = AsyncIOMotorClient(local_uri)
                # 로컬 DB 연결 테스트
                await cls.local_client.admin.command('ping')
                print("로컬 MongoDB에 성공적으로 연결되었습니다!")
                
                # 로컬 DB 초기 설정
                local_db = cls.local_client[os.getenv('LOCAL_DATABASE_NAME', 'progen_db')]
                await local_db.users.create_index("username", unique=True)
                await local_db.users.create_index("email", unique=True)
            
            if connection_type in ['atlas', 'both']:
                cls.atlas_client = AsyncIOMotorClient(atlas_uri)
                # Atlas DB 연결 테스트
                await cls.atlas_client.admin.command('ping')
                print("Atlas MongoDB에 성공적으로 연결되었습니다!")
                
                # Atlas DB 초기 설정
                atlas_db = cls.atlas_client[os.getenv('ATLAS_DATABASE_NAME', 'progen_db')]
                await atlas_db.users.create_index("username", unique=True)
                await atlas_db.users.create_index("email", unique=True)
            
            # 기본 연결 설정
            cls.current_connection = os.getenv('DEFAULT_MONGODB', 'local')
            
        except Exception as e:
            print(f"MongoDB 연결 실패: {e}")
            raise e
    
    @classmethod
    async def close_db(cls):
        if cls.local_client:
            cls.local_client.close()
            print("로컬 MongoDB 연결이 종료되었습니다.")
        if cls.atlas_client:
            cls.atlas_client.close()
            print("Atlas MongoDB 연결이 종료되었습니다.")
    
    @classmethod
    def switch_connection(cls, connection_type):
        """데이터베이스 연결을 전환합니다."""
        if connection_type in ['local', 'atlas']:
            cls.current_connection = connection_type
            print(f"연결이 {connection_type}으로 전환되었습니다.")
        else:
            raise ValueError("connection_type은 'local' 또는 'atlas'여야 합니다.")
    
    @classmethod
    def get_database(cls):
        if cls.current_connection == 'local':
            return cls.local_client[os.getenv('LOCAL_DATABASE_NAME', 'progen_db')]
        else:
            return cls.atlas_client[os.getenv('ATLAS_DATABASE_NAME', 'progen_db')]
    
    @classmethod
    def get_user_collection(cls):
        db = cls.get_database()
        return db.users

db = Database()