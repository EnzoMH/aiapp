from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
import pymongo

class Database:
    client: Optional[AsyncIOMotorClient] = None
    
    @classmethod
    async def init_db(cls, mongodb_url: str):
        try:
            # DB 연결
            cls.client = AsyncIOMotorClient(mongodb_url)
            db = cls.client.progen_db
            
            # 필수 필드 인덱스 생성
            await db.users.create_indexes([
                # 식별자 인덱스
                pymongo.IndexModel([("id", pymongo.ASCENDING)], 
                    unique=True,
                    name="idx_user_id"),
                
                # 사용자 정보 인덱스
                pymongo.IndexModel([("username", pymongo.ASCENDING)], 
                    unique=True,
                    name="idx_username"),
                pymongo.IndexModel([("email", pymongo.ASCENDING)], 
                    unique=True,
                    name="idx_email"),
                pymongo.IndexModel([("phone", pymongo.ASCENDING)], 
                    unique=True,
                    name="idx_phone"),
                
                # 상태 및 권한 인덱스
                pymongo.IndexModel([
                    ("role", pymongo.ASCENDING),
                    ("status", pymongo.ASCENDING)
                ], name="idx_role_status"),
                
                # 시간 관련 인덱스
                pymongo.IndexModel([("created_at", pymongo.DESCENDING)],
                    name="idx_created_at"),
                pymongo.IndexModel([("last_login", pymongo.DESCENDING)],
                    sparse=True,
                    name="idx_last_login")
            ])
            
            # 컬렉션 검증 규칙 설정
            await db.command({
                "collMod": "users",
                "validator": {
                    "$jsonSchema": {
                        "bsonType": "object",
                        "required": [
                            "_id", "id", "username", "password", 
                            "email", "phone", "role", "created_at", "status"
                        ],
                        "properties": {
                            "_id": {"bsonType": "objectId"},
                            "id": {
                                "bsonType": "string",
                                "minLength": 4,
                                "maxLength": 30
                            },
                            "username": {
                                "bsonType": "string",
                                "minLength": 2,
                                "maxLength": 30
                            },
                            "password": {"bsonType": "string"},
                            "email": {
                                "bsonType": "string",
                                "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
                            },
                            "phone": {
                                "bsonType": "string",
                                "pattern": "^[0-9]{10,11}$"
                            },
                            "role": {
                                "enum": ["admin", "user"]
                            },
                            "created_at": {"bsonType": "date"},
                            "status": {
                                "enum": ["active", "inactive"]
                            },
                            "profile_image": {"bsonType": ["string", "null"]},
                            "last_login": {"bsonType": ["date", "null"]},
                            "service_preferences": {
                                "bsonType": "object",
                                "properties": {
                                    "theme": {"enum": ["light", "dark"]},
                                    "language": {"enum": ["ko", "en"]},
                                    "email_notifications": {"bsonType": "bool"}
                                }
                            },
                            "notification_settings": {
                                "bsonType": "object",
                                "properties": {
                                    "email": {"bsonType": "bool"},
                                    "sms": {"bsonType": "bool"},
                                    "marketing_agree": {"bsonType": "bool"},
                                    "last_updated": {"bsonType": "date"}
                                }
                            }
                        }
                    }
                },
                "validationLevel": "strict"
            })
            
            print("Database indexes and validation rules created successfully")
            
        except Exception as e:
            print(f"Error initializing database: {e}")
            raise
    
    @classmethod
    async def close_db(cls):
        if cls.client:
            cls.client.close()