import httpx
from typing import Optional

class HTTPClient:
    _instance: Optional[httpx.AsyncClient] = None

    @classmethod
    async def get_client(cls) -> httpx.AsyncClient:
        if cls._instance is None:
            cls._instance = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0'
                }
            )
        return cls._instance

    @classmethod
    async def close_client(cls) -> None:
        if cls._instance is not None:
            await cls._instance.aclose()
            cls._instance = None

http_client = HTTPClient()