import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os
from urllib.parse import quote_plus

load_dotenv()

async def test_connection():
    client = None
    try:
        # 비밀번호 URL 인코딩
        password = quote_plus("ksgi02160621!@")
        connection_string = f"mongodb+srv://balderlogin:{password}@balderlogin.6nnh0.mongodb.net/?retryWrites=true&w=majority"
        
        print("연결 시도중...")
        client = AsyncIOMotorClient(connection_string)
        db = client[os.getenv('DATABASE_NAME')]
        await db.command('ping')
        print("MongoDB Atlas에 성공적으로 연결되었습니다!")
        
    except Exception as e:
        print(f"연결 실패: {str(e)}")
    finally:
        if client:
            client.close()

if __name__ == "__main__":
    asyncio.run(test_connection())