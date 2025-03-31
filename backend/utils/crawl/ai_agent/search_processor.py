"""
검색 결과 처리 모듈

이 모듈은 검색 결과 페이지를 처리하고 데이터를 추출하는 기능을 제공합니다.
"""

import asyncio
import random
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import os
from pathlib import Path

# 셀레니움 관련
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# 내부 모듈
from .api_client import gemini_client
from .prompts import TABLE_EXTRACTOR_PROMPT
from ..utils.logger import CrawlLogger
from ..utils.config import crawler_config
from ..core.models import BidItem, CrawlResult, AgentStatusLevel
from .crawler_helper import (
    take_screenshot,
    extract_table_data,
    navigate_to_page,
    save_screenshot,
    create_bid_item
)

# 로거 설정
logger = CrawlLogger("search_processor", debug=True)


class SearchResultProcessor:
    """검색 결과 처리 클래스"""
    
    def __init__(
        self, 
        driver, 
        wait, 
        result: CrawlResult,
        max_pages: int = 5,
        screenshot_dir: Optional[Path] = None,
        websocket_handler = None
    ):
        """
        검색 결과 처리기 초기화
        
        Args:
            driver: 셀레니움 웹드라이버
            wait: 셀레니움 웨이트
            result: 크롤링 결과 객체
            max_pages: 최대 페이지 수
            screenshot_dir: 스크린샷 저장 디렉토리
            websocket_handler: 웹소켓 핸들러
        """
        self.driver = driver
        self.wait = wait
        self.result = result
        self.max_pages = max_pages
        self.screenshot_dir = screenshot_dir or Path(crawler_config.screenshot_dir)
        self.websocket_handler = websocket_handler
        self.should_stop = False
    
    async def process_search_results(self, keyword: str) -> int:
        """
        검색 결과 페이지 처리
        
        Args:
            keyword: 검색 키워드
        
        Returns:
            수집된 항목 수
        """
        total_items = 0
        current_page = 1
        
        try:
            while current_page <= self.max_pages and not self.should_stop:
                # 현재 페이지 정보 업데이트
                self.result.update_progress(
                    current_page=current_page,
                    processed_pages=self.result.progress.processed_pages + 1
                )
                
                # 에이전트 상태 업데이트
                self.result.add_agent_status(
                    message=f"키워드 '{keyword}' 검색 결과 - 페이지 {current_page} 처리 중",
                    level=AgentStatusLevel.INFO
                )
                
                # 웹소켓 상태 업데이트 (있는 경우)
                if self.websocket_handler:
                    await self.websocket_handler(self.result)
                
                # 페이지 결과 추출
                items_count = await self._extract_page_results(keyword, current_page)
                total_items += items_count
                
                # 다음 페이지로 이동
                if current_page < self.max_pages:
                    has_next = await navigate_to_page(self.driver, self.wait)
                    if not has_next:
                        # 다음 페이지가 없으면 종료
                        self.result.add_agent_status(
                            message=f"키워드 '{keyword}' 검색 결과 - 마지막 페이지 도달 (페이지 {current_page})",
                            level=AgentStatusLevel.INFO
                        )
                        break
                
                # 페이지 진행 정보 업데이트
                self.result.update_progress(
                    processed_pages=self.result.progress.processed_pages + 1
                )
                
                # 다음 페이지로
                current_page += 1
                
                # 약간의 대기 (차단 방지)
                await asyncio.sleep(random.uniform(1.0, 2.0))
            
            return total_items
            
        except Exception as e:
            logger.error(f"검색 결과 처리 중 오류: {str(e)}")
            self.result.add_error(f"검색 결과 처리 오류 (키워드: {keyword})", {"error": str(e)})
            return total_items
    
    async def stop(self):
        """처리 중지"""
        self.should_stop = True
    
    async def _extract_page_results(self, keyword: str, page_num: int) -> int:
        """
        페이지 결과 추출
        
        Args:
            keyword: 검색 키워드
            page_num: 페이지 번호
        
        Returns:
            추출된 항목 수
        """
        try:
            # 결과 테이블 찾기 시도
            table_found = False
            try:
                # 일반적인 테이블 찾기
                table = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, "//table[contains(@class, 'list') or contains(@class, 'results')]"))
                )
                if table:
                    table_found = True
            except TimeoutException:
                # 테이블을 찾지 못함
                pass
            
            # 스크린샷 저장
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            screenshot_filename = f"{keyword.replace(' ', '_')}_{page_num}_{timestamp}"
            screenshot_path = await save_screenshot(
                self.driver, 
                self.screenshot_dir, 
                screenshot_filename,
                full_page=True
            )
            
            if not table_found:
                # AI 접근: 스크린샷으로 테이블 데이터 추출
                screenshot_data = await take_screenshot(self.driver, full_page=True)
                
                if not screenshot_data:
                    self.result.add_agent_status(
                        message=f"스크린샷 촬영 실패 - 페이지 {page_num}",
                        level=AgentStatusLevel.ERROR
                    )
                    return 0
                
                # AI에 테이블 추출 요청
                prompt = TABLE_EXTRACTOR_PROMPT.format(
                    keyword=keyword,
                    page_number=page_num
                )
                
                response = await gemini_client.query_vision(prompt, screenshot_data)
                
                if "error" in response:
                    self.result.add_agent_status(
                        message=f"AI 테이블 추출 실패 - 페이지 {page_num}: {response['error']}",
                        level=AgentStatusLevel.ERROR
                    )
                    return 0
                
                # 테이블 데이터 추출
                items_data = await extract_table_data(response["result"])
            else:
                # HTML 테이블에서 직접 데이터 추출
                items_data = await self._extract_table_data_from_html()
            
            # 추출된 항목이 없으면
            if not items_data:
                self.result.add_agent_status(
                    message=f"추출된 항목 없음 - 키워드 '{keyword}' 페이지 {page_num}",
                    level=AgentStatusLevel.WARNING
                )
                return 0
            
            # BidItem 객체 생성 및 결과에 추가
            added_items = 0
            for item_data in items_data:
                try:
                    bid_item = await create_bid_item(item_data, keyword)
                    self.result.add_item(bid_item)
                    added_items += 1
                except Exception as e:
                    logger.error(f"항목 생성 중 오류: {str(e)}")
                    continue
            
            # 상태 업데이트
            self.result.add_agent_status(
                message=f"키워드 '{keyword}' 검색 결과 - 페이지 {page_num}에서 {added_items}개 항목 추출",
                level=AgentStatusLevel.SUCCESS if added_items > 0 else AgentStatusLevel.WARNING
            )
            
            return added_items
            
        except Exception as e:
            logger.error(f"페이지 결과 추출 중 오류: {str(e)}")
            self.result.add_error(f"페이지 결과 추출 오류 (키워드: {keyword}, 페이지: {page_num})", {"error": str(e)})
            return 0
    
    async def _extract_table_data_from_html(self) -> List[Dict[str, Any]]:
        """
        HTML 테이블에서 데이터 추출
        
        Returns:
            추출된 테이블 데이터 목록
        """
        try:
            items_data = []
            
            # 테이블 찾기
            tables = self.driver.find_elements(By.XPATH, "//table[contains(@class, 'list') or contains(@class, 'results')]")
            if not tables:
                return []
            
            # 첫 번째 테이블 선택
            table = tables[0]
            
            # 테이블 행 추출
            rows = table.find_elements(By.XPATH, ".//tr[td]")  # 헤더 제외
            
            for row in rows:
                try:
                    # 셀 추출
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) < 3:
                        continue
                    
                    # 데이터 추출 (일반적인 나라장터 테이블 구조)
                    item_data = {}
                    
                    # 공고번호
                    if len(cells) > 0:
                        item_data["bid_id"] = cells[0].text.strip()
                    
                    # 공고명 및 URL
                    if len(cells) > 1:
                        title_cell = cells[1]
                        item_data["title"] = title_cell.text.strip()
                        
                        # URL 추출
                        links = title_cell.find_elements(By.TAG_NAME, "a")
                        if links:
                            href = links[0].get_attribute("href")
                            if href:
                                item_data["url"] = href
                    
                    # 발주기관
                    if len(cells) > 2:
                        item_data["organization"] = cells[2].text.strip()
                    
                    # 등록일
                    if len(cells) > 3:
                        item_data["reg_date"] = cells[3].text.strip()
                    
                    # 마감일
                    if len(cells) > 4:
                        item_data["close_date"] = cells[4].text.strip()
                    
                    # 항목 추가 (필수 필드가 있는 경우)
                    if "bid_id" in item_data and "title" in item_data:
                        items_data.append(item_data)
                        
                except Exception as e:
                    logger.error(f"행 처리 중 오류: {str(e)}")
                    continue
            
            return items_data
            
        except Exception as e:
            logger.error(f"HTML 테이블 데이터 추출 중 오류: {str(e)}")
            return [] 