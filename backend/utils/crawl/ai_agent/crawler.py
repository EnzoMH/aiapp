"""
AI 에이전트 크롤러 모듈

이 모듈은 나라장터 크롤링을 위한 AI 기반 크롤러를 구현합니다.
"""

import os
import time
import json
import asyncio
import random
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

# 셀레니움 및 관련 라이브러리
import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

# 내부 모듈
from .api_client import gemini_client
from .crawler_helper import take_screenshot
from .search_processor import SearchResultProcessor
from .detail_extractor import DetailExtractor
from .websocket_manager import WebSocketManager
from ..utils.config import crawler_config, search_config
from ..utils.logger import CrawlLogger
from ..core.models import (
    CrawlResult,
    CrawlStatus,
    CrawlType,
    AgentStatusLevel
)

# 로거 설정
logger = CrawlLogger("ai_agent_crawler", debug=True)


class AIAgentCrawler:
    """AI 에이전트 크롤러 클래스"""
    
    BASE_URL = "https://www.g2b.go.kr"
    SEARCH_URL = "https://www.g2b.go.kr:8101/ep/tbid/tbidList.do?taskClCd=5"
    
    def __init__(
        self, 
        keywords: List[str] = None,
        max_pages_per_keyword: int = None,
        max_details: int = 10,
        result: Optional[CrawlResult] = None,
        headless: bool = None,
        debug_mode: bool = None,
        websocket = None
    ):
        """
        AI 에이전트 크롤러 초기화
        
        Args:
            keywords: 검색할 키워드 목록
            max_pages_per_keyword: 키워드당 최대 페이지 수
            max_details: 상세 정보를 추출할 최대 항목 수
            result: 기존 크롤링 결과 (재개 시 사용)
            headless: 헤드리스 모드 여부
            debug_mode: 디버그 모드 여부
            websocket: 웹소켓 객체
        """
        # 설정 로드
        self.keywords = keywords or search_config.default_keywords
        self.max_pages = max_pages_per_keyword or search_config.max_pages_per_keyword
        self.max_details = max_details
        self.headless = headless if headless is not None else crawler_config.headless
        self.debug_mode = debug_mode if debug_mode is not None else crawler_config.debug_mode
        
        # 크롤링 상태 및 결과
        self.result = result or CrawlResult(
            id=str(uuid.uuid4()),
            crawl_type=CrawlType.AI_AGENT,
            keywords=self.keywords
        )
        
        # 웹소켓 관리자
        self.websocket_manager = WebSocketManager(websocket)
        self.should_stop = False
        
        # 결과 저장 경로
        self.screenshot_dir = Path(crawler_config.screenshot_dir)
        self.results_dir = Path(crawler_config.results_dir)
        
        # 디렉토리 생성
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # 웹드라이버 초기화
        self.driver = None
        self.wait = None
        
        # 진행 상황 초기화
        self.result.update_progress(
            total_keywords=len(self.keywords),
            processed_keywords=0,
            total_pages=len(self.keywords) * self.max_pages,
            processed_pages=0,
            total_items=0,
            collected_items=0
        )
        
        logger.info(f"AI 에이전트 크롤러 초기화 완료 (키워드: {len(self.keywords)}, 헤드리스: {self.headless})")
    
    async def setup_driver(self):
        """웹드라이버 설정"""
        try:
            # 크롬드라이버 자동 설치
            chromedriver_path = chromedriver_autoinstaller.install()
            logger.info(f"크롬드라이버 설치 완료: {chromedriver_path}")
            
            # 크롬 옵션 설정
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless=new")
            
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument(f"user-agent={crawler_config.user_agent}")
            
            # 블로킹 방지를 위한 추가 옵션
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            
            # 웹드라이버 초기화
            service = Service(executable_path=chromedriver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
                """
            })
            
            # 대기 시간 설정
            self.wait = WebDriverWait(self.driver, crawler_config.timeout)
            
            # 에이전트 상태 업데이트
            self.result.add_agent_status(
                message="웹드라이버 초기화 완료",
                level=AgentStatusLevel.INFO
            )
            
            # 웹소켓 상태 업데이트
            await self._send_status_update()
            
            return True
        
        except Exception as e:
            logger.error(f"웹드라이버 설정 중 오류: {str(e)}")
            self.result.add_agent_status(
                message="웹드라이버 초기화 실패",
                level=AgentStatusLevel.ERROR,
                details={"error": str(e)}
            )
            self.result.add_error("웹드라이버 초기화 실패", {"error": str(e)})
            
            # 웹소켓 상태 업데이트
            await self._send_status_update()
            
            return False
    
    async def start(self):
        """크롤링 시작"""
        logger.info("AI 에이전트 크롤링 시작")
        
        try:
            # 크롤링 시작 시간 설정
            self.result.start_time = datetime.now()
            self.result.status = CrawlStatus.RUNNING
            
            # 웹드라이버 설정
            if not await self.setup_driver():
                self.result.status = CrawlStatus.FAILED
                self.result.end_time = datetime.now()
                await self._send_status_update()
                return self.result
            
            # 크롤링 실행
            await self._run_crawler()
            
            # 크롤링 완료
            if not self.should_stop:
                self.result.status = CrawlStatus.COMPLETED
                self.result.add_agent_status(
                    message="크롤링 완료",
                    level=AgentStatusLevel.SUCCESS
                )
            else:
                self.result.status = CrawlStatus.PAUSED
                self.result.add_agent_status(
                    message="크롤링 중지됨",
                    level=AgentStatusLevel.WARNING
                )
            
            # 결과 저장
            await self._save_results()
            
            # 웹소켓 완료 메시지 전송
            if self.websocket_manager.is_connected:
                await self.websocket_manager.send_completion(self.result)
            
        except Exception as e:
            logger.error(f"크롤링 중 오류: {str(e)}")
            self.result.status = CrawlStatus.FAILED
            self.result.add_agent_status(
                message="크롤링 중 오류 발생",
                level=AgentStatusLevel.ERROR,
                details={"error": str(e)}
            )
            self.result.add_error("크롤링 중 오류", {"error": str(e)})
        
        finally:
            # 종료 시간 설정
            self.result.end_time = datetime.now()
            
            # 웹드라이버 종료
            if self.driver:
                self.driver.quit()
            
            # 웹소켓 상태 업데이트
            await self._send_status_update()
            
            return self.result
    
    async def stop(self):
        """크롤링 중지"""
        logger.info("AI 에이전트 크롤링 중지 요청")
        self.should_stop = True
        self.result.add_agent_status(
            message="크롤링 중지 요청",
            level=AgentStatusLevel.WARNING
        )
        await self._send_status_update()
    
    async def _run_crawler(self):
        """크롤러 실행"""
        try:
            # 메인 페이지 접속
            self.driver.get(self.BASE_URL)
            await asyncio.sleep(random.uniform(1.0, 2.0))
            
            # 키워드별 크롤링
            for keyword_index, keyword in enumerate(self.keywords):
                if self.should_stop:
                    break
                
                # 키워드 진행 상황 업데이트
                self.result.update_progress(
                    processed_keywords=keyword_index,
                    current_keyword=keyword
                )
                
                # 에이전트 상태 업데이트
                self.result.add_agent_status(
                    message=f"키워드 '{keyword}' 검색 시작",
                    level=AgentStatusLevel.INFO
                )
                
                # 웹소켓 상태 업데이트
                await self._send_status_update()
                
                # 검색 페이지 접속
                self.driver.get(self.SEARCH_URL)
                await asyncio.sleep(random.uniform(1.0, 2.0))
                
                # 키워드 검색
                await self._search_keyword(keyword)
                
                # 검색 결과 처리기 생성
                search_processor = SearchResultProcessor(
                    self.driver,
                    self.wait,
                    self.result,
                    self.max_pages,
                    self.screenshot_dir,
                    self._send_status_update
                )
                
                # 결과 페이지 크롤링
                items_count = await search_processor.process_search_results(keyword)
                
                # 키워드 완료 후 상태 업데이트
                self.result.update_progress(
                    processed_keywords=keyword_index + 1
                )
                
                # 에이전트 상태 업데이트
                self.result.add_agent_status(
                    message=f"키워드 '{keyword}' 검색 완료 (항목: {items_count}개)",
                    level=AgentStatusLevel.SUCCESS
                )
                
                # 웹소켓 상태 업데이트
                await self._send_status_update()
            
            # 모든 키워드 검색 완료 후 상세 정보 추출
            if not self.should_stop and self.result.items:
                # 상세 정보 추출기 생성
                detail_extractor = DetailExtractor(
                    self.driver,
                    self.wait,
                    self.result,
                    self.max_details,
                    self.screenshot_dir,
                    self._send_status_update
                )
                
                # 상세 정보 추출
                details_count = await detail_extractor.process_details()
                
                # 에이전트 상태 업데이트
                self.result.add_agent_status(
                    message=f"입찰 상세 정보 추출 완료 (총 {details_count}개)",
                    level=AgentStatusLevel.SUCCESS
                )
                
                # 웹소켓 상태 업데이트
                await self._send_status_update()
            
            return True
            
        except Exception as e:
            logger.error(f"크롤러 실행 중 오류: {str(e)}")
            self.result.add_error("크롤러 실행 오류", {"error": str(e)})
            return False
    
    async def _search_keyword(self, keyword: str):
        """키워드 검색"""
        try:
            # 검색창 찾기
            search_box = None
            
            try:
                # 일반적인 검색창 찾기 시도
                search_box = self.wait.until(
                    EC.presence_of_element_located((By.ID, "bidNm"))
                )
            except:
                # 다른 방법으로 검색창 찾기
                search_box_selectors = [
                    (By.ID, "bidNm"),
                    (By.ID, "searchWrd"),
                    (By.NAME, "bidNm"),
                    (By.NAME, "searchWrd"),
                    (By.XPATH, "//input[@type='text']"),
                    (By.XPATH, "//input[contains(@placeholder, '검색')]"),
                ]
                
                for by, selector in search_box_selectors:
                    try:
                        elements = self.driver.find_elements(by, selector)
                        for element in elements:
                            if element.is_displayed() and element.is_enabled():
                                search_box = element
                                break
                        if search_box:
                            break
                    except:
                        continue
            
            if not search_box:
                # 검색창이 보이지 않는 경우 AI로 찾기 시도
                screenshot = await take_screenshot(self.driver)
                
                if screenshot:
                    # AI에 요청 (crawler_helper 모듈의 take_screenshot 사용)
                    # 여기서는 단순화를 위해 생략
                    pass
                
                # 그래도 못 찾으면 예외 발생
                if not search_box:
                    raise Exception("검색창을 찾을 수 없습니다.")
            
            # 검색창 클릭 및 내용 지우기
            search_box.click()
            search_box.clear()
            
            # 키워드 입력
            search_box.send_keys(keyword)
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # 검색 버튼 찾기
            search_button = None
            
            # 다양한 검색 버튼 셀렉터
            search_button_selectors = [
                (By.XPATH, "//input[@type='submit']"),
                (By.XPATH, "//button[@type='submit']"),
                (By.XPATH, "//input[@value='검색']"),
                (By.XPATH, "//button[contains(text(), '검색')]"),
                (By.XPATH, "//button[contains(@class, 'search')]"),
                (By.XPATH, "//a[contains(@class, 'search')]"),
                (By.CLASS_NAME, "search"),
            ]
            
            for by, selector in search_button_selectors:
                try:
                    elements = self.driver.find_elements(by, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            search_button = element
                            break
                    if search_button:
                        break
                except:
                    continue
            
            if not search_button:
                # 검색 버튼이 없으면 엔터 키 사용
                search_box.send_keys(Keys.RETURN)
            else:
                # 검색 버튼 클릭
                search_button.click()
            
            # 검색 결과 로딩 대기
            await asyncio.sleep(random.uniform(2.0, 3.0))
            
            return True
            
        except Exception as e:
            logger.error(f"키워드 검색 중 오류: {str(e)}")
            self.result.add_error(f"키워드 '{keyword}' 검색 오류", {"error": str(e)})
            return False
    
    async def _save_results(self):
        """결과 저장"""
        try:
            # 결과 저장 경로
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            result_filename = f"ai_crawl_result_{timestamp}.json"
            result_path = self.results_dir / result_filename
            
            # 결과를 JSON으로 저장
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(self.result.to_full_dict(), f, ensure_ascii=False, indent=2)
            
            logger.info(f"크롤링 결과 저장 완료: {result_path}")
            self.result.add_agent_status(
                message=f"크롤링 결과 저장 완료: {result_filename}",
                level=AgentStatusLevel.SUCCESS
            )
            
            return True
        
        except Exception as e:
            logger.error(f"결과 저장 중 오류: {str(e)}")
            self.result.add_error("결과 저장 오류", {"error": str(e)})
            return False
    
    async def _send_status_update(self, result: Optional[CrawlResult] = None):
        """웹소켓 상태 업데이트 전송"""
        if self.websocket_manager.is_connected:
            await self.websocket_manager.send_status_update(result or self.result)


# 크롤러 인스턴스 생성 함수
def create_crawler(
    keywords: List[str] = None,
    max_pages: int = None,
    max_details: int = 10,
    headless: bool = None,
    debug_mode: bool = None,
    websocket = None
) -> AIAgentCrawler:
    """
    AI 에이전트 크롤러 인스턴스 생성
    
    Args:
        keywords: 검색할 키워드 목록
        max_pages: 키워드당 최대 페이지 수
        max_details: 상세 정보를 추출할 최대 항목 수
        headless: 헤드리스 모드 여부
        debug_mode: 디버그 모드 여부
        websocket: 웹소켓 객체
    
    Returns:
        AIAgentCrawler 인스턴스
    """
    return AIAgentCrawler(
        keywords=keywords,
        max_pages_per_keyword=max_pages,
        max_details=max_details,
        headless=headless,
        debug_mode=debug_mode,
        websocket=websocket
    ) 