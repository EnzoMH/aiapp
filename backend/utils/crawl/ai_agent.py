"""
나라장터 AI 에이전트 크롤러 모듈

이 모듈은 Gemini API를 활용하여 나라장터 웹사이트의 입찰공고를 수집하는 AI 에이전트 크롤러를 구현합니다.
웹 페이지 구조가 변경되어도 AI 비전 기술을 활용하여 데이터를 추출할 수 있습니다.
"""

import os
import json
import asyncio
import logging
import time
import base64
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from fastapi import WebSocket
from dotenv import load_dotenv

# Selenium 관련 임포트
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import chromedriver_autoinstaller

# 모델 임포트
from .models import BidBasicInfo, BidDetailInfo, BidItem, AgentStatus

# Gemini API용 설정 로드
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_VISION_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateContent?key={GEMINI_API_KEY}"
GEMINI_TEXT_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"

# 로깅 설정
logger = logging.getLogger(__name__)


class AIAgentCrawler:
    """나라장터 AI 에이전트 크롤러 클래스"""
    
    def __init__(self, headless: bool = True):
        """크롤러 초기화"""
        self.base_url = "https://www.g2b.go.kr"
        self.driver = None
        self.wait = None
        self.headless = headless
        self.results = []
        self.active_connections: List[WebSocket] = []
        self.is_running = False
        self.current_keyword = None
        self.processed_keywords: Set[str] = set()
        self.total_keywords = 0
        self.agent_task = None
    
    def add_connection(self, websocket: WebSocket):
        """웹소켓 연결 추가"""
        if websocket not in self.active_connections:
            self.active_connections.append(websocket)
            logger.info(f"새 AI 에이전트 WebSocket 연결 추가됨 (현재 {len(self.active_connections)}개)")
    
    def remove_connection(self, websocket: WebSocket):
        """웹소켓 연결 제거"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"AI 에이전트 WebSocket 연결 제거됨 (현재 {len(self.active_connections)}개)")
    
    async def send_to_all_clients(self, data: Dict):
        """모든 연결된 클라이언트에 메시지 전송"""
        if not self.active_connections:
            return
        
        for connection in self.active_connections.copy():
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.error(f"클라이언트 메시지 전송 오류: {str(e)}")
                # 오류 발생한 연결은 목록에서 제거
                self.remove_connection(connection)
    
    async def send_status(self, message: str, type_: str = "status"):
        """상태 메시지 전송"""
        await self.send_to_all_clients({
            "type": type_,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })
    
    async def send_error(self, message: str):
        """오류 메시지 전송"""
        await self.send_status(message, type_="error")
    
    async def broadcast_status(self):
        """현재 AI 에이전트 상태 브로드캐스트"""
        status_data = {
            "type": "agent_status",
            "is_running": self.is_running,
            "current_keyword": self.current_keyword,
            "processed_count": len(self.processed_keywords),
            "fallback_mode": True,
            "results_count": len(self.results),
            "timestamp": datetime.now().isoformat()
        }
        
        await self.send_to_all_clients(status_data)
    
    async def initialize(self):
        """크롤러 초기화 및 웹드라이버 설정"""
        try:
            # 웹드라이버 설정
            await self._setup_driver()
            return True
        except Exception as e:
            logger.error(f"AI 에이전트 크롤러 초기화 실패: {str(e)}")
            return False
    
    async def _setup_driver(self):
        """웹드라이버 설정"""
        logger.info("AI 에이전트용 Chrome 웹드라이버 설정 중...")
        
        # ChromeDriver 자동 설치 및 설정
        chrome_ver = chromedriver_autoinstaller.get_chrome_version().split('.')[0]
        try:
            chromedriver_autoinstaller.install(True)
        except Exception as e:
            logger.warning(f"ChromeDriver 자동 설치 실패: {str(e)}. 기본 경로 사용 시도.")
            
        # 크롬 옵션 설정
        chrome_options = Options()
        
        # 헤드리스 모드 설정 (선택적)
        if self.headless:
            chrome_options.add_argument('--headless=new')
            
        # 기타 기본 옵션 설정
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-popup-blocking')
        
        # 최신 크롬 user agent 설정
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        
        # 웹드라이버 초기화
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 10)
            logger.info("AI 에이전트용 Chrome 웹드라이버 초기화 성공")
        except Exception as e:
            logger.error(f"Chrome 웹드라이버 초기화 실패: {str(e)}")
            raise
    
    async def close(self):
        """웹드라이버 종료 및 리소스 정리"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("AI 에이전트 웹드라이버 종료 완료")
            except Exception as e:
                logger.error(f"웹드라이버 종료 중 오류: {str(e)}")
    
    async def start_agent_crawling(self, keywords: List[str], fallback_mode: bool = True) -> Dict:
        """AI 에이전트 크롤링 시작"""
        # 이미 실행 중인 경우
        if self.is_running:
            await self.send_status("이미 AI 에이전트 크롤링이 실행 중입니다.", type_="error")
            return {
                "status": "error",
                "message": "이미 AI 에이전트 크롤링이 실행 중입니다."
            }
        
        # 키워드 유효성 검사
        if not keywords:
            await self.send_status("검색할 키워드가 없습니다.", type_="error")
            return {
                "status": "error",
                "message": "검색할 키워드가 없습니다."
            }
        
        # Gemini API 키 확인
        if not GEMINI_API_KEY:
            await self.send_status("Gemini API 키가 설정되지 않았습니다.", type_="error")
            return {
                "status": "error",
                "message": "Gemini API 키가 설정되지 않았습니다."
            }
        
        # 상태 초기화
        self.is_running = True
        self.current_keyword = None
        self.processed_keywords.clear()
        self.total_keywords = len(keywords)
        self.results.clear()
        
        # 현재 상태 브로드캐스트
        await self.broadcast_status()
        
        # 비동기로 크롤링 실행 (백그라운드 태스크)
        self.agent_task = asyncio.create_task(self._run_agent_crawling(keywords, fallback_mode))
        
        # 성공 응답 반환
        await self.send_status(f"AI 에이전트 크롤링이 시작되었습니다. 키워드 {len(keywords)}개를 처리합니다.", type_="status")
        return {
            "status": "success",
            "message": f"AI 에이전트 크롤링이 시작되었습니다. 키워드 {len(keywords)}개를 처리합니다.",
            "agent_mode": fallback_mode,
            "total_keywords": len(keywords),
            "results_count": 0
        }
    
    def capture_screenshot(self) -> str:
        """현재 화면 스크린샷 캡처 및 base64 인코딩 데이터 반환"""
        screenshot_data = self.driver.get_screenshot_as_base64()
        return screenshot_data
    
    async def query_gemini_vision(self, prompt: str, image_data: str) -> Dict:
        """Gemini Vision API 쿼리 (이미지 + 텍스트)"""
        try:
            # API 요청 데이터 구성
            data = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": "image/jpeg",
                                    "data": image_data
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.4,
                    "topP": 0.95,
                    "topK": 0,
                    "maxOutputTokens": 2048,
                },
                "safetySettings": [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    }
                ]
            }
            
            # API 요청 전송
            response = requests.post(
                GEMINI_VISION_API_URL,
                json=data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                logger.error(f"Gemini Vision API 요청 실패: {response.status_code}, {response.text}")
                return {"error": f"API 요청 실패: {response.status_code}"}
            
            response_data = response.json()
            
            # 응답 데이터 파싱
            if "candidates" in response_data and len(response_data["candidates"]) > 0:
                content = response_data["candidates"][0]["content"]
                if "parts" in content and len(content["parts"]) > 0:
                    result_text = content["parts"][0]["text"]
                    return {"result": result_text}
            
            return {"error": "API 응답 형식 오류"}
        
        except Exception as e:
            logger.error(f"Gemini Vision API 요청 중 오류: {str(e)}")
            return {"error": f"API 요청 중 오류: {str(e)}"}
    
    async def extract_data_from_screenshot(self, prompt: str) -> Dict:
        """스크린샷에서 데이터 추출"""
        try:
            # 스크린샷 캡처
            screenshot_data = self.capture_screenshot()
            
            # Gemini API로 데이터 추출
            result = await self.query_gemini_vision(prompt, screenshot_data)
            
            return result
        except Exception as e:
            logger.error(f"스크린샷에서 데이터 추출 중 오류: {str(e)}")
            return {"error": f"데이터 추출 중 오류: {str(e)}"}

# AI 에이전트 매니저 전역 인스턴스 생성
ai_agent_manager = AIAgentCrawler() 