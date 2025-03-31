"""
크롤링 설정 관리 모듈

이 모듈은 크롤링 작업에 필요한 구성 설정을 관리합니다.
"""

import os
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class CrawlerConfig(BaseModel):
    """크롤러 설정 모델"""
    base_url: str = "https://www.g2b.go.kr"
    headless: bool = True
    timeout: int = 10
    retry_count: int = 3
    wait_time: float = 1.0
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    screenshot_dir: str = "screenshots"
    results_dir: str = "results"
    debug_mode: bool = False


class AIAgentConfig(BaseModel):
    """AI 에이전트 설정 모델"""
    gemini_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_vision_api_url: str = Field(
        default_factory=lambda: f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateContent?key={os.getenv('GEMINI_API_KEY', '')}"
    )
    gemini_text_api_url: str = Field(
        default_factory=lambda: f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={os.getenv('GEMINI_API_KEY', '')}"
    )
    temperature: float = 0.4
    top_p: float = 0.95
    max_tokens: int = 2048
    parallel_requests: int = 1
    request_delay: float = 0.5


class SearchConfig(BaseModel):
    """검색 설정 모델"""
    default_keywords: List[str] = [
        "소프트웨어", "시스템", "개발", "유지보수", "AI", "인공지능", 
        "클라우드", "빅데이터", "데이터", "IT", "정보화", "플랫폼"
    ]
    max_pages_per_keyword: int = 5
    items_per_page: int = 10


# 전역 설정 인스턴스
crawler_config = CrawlerConfig()
ai_agent_config = AIAgentConfig()
search_config = SearchConfig() 