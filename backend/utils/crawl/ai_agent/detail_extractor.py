"""
상세 내용 추출기 모듈

이 모듈은 입찰 공고 상세 페이지에서 정보를 추출하는 기능을 제공합니다.
"""

import asyncio
import random
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import os
from pathlib import Path

# 셀레니움 관련
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# 내부 모듈
from .api_client import gemini_client
from .prompts import DETAIL_EXTRACTOR_PROMPT
from ..utils.logger import CrawlLogger
from ..utils.config import crawler_config
from ..core.models import BidItem, BidDetail, CrawlResult, AgentStatusLevel
from .crawler_helper import (
    take_screenshot,
    extract_detail_data,
    save_screenshot
)

# 로거 설정
logger = CrawlLogger("detail_extractor", debug=True)


class DetailExtractor:
    """상세 내용 추출기 클래스"""
    
    def __init__(
        self, 
        driver, 
        wait, 
        result: CrawlResult,
        max_details: int = 10,
        screenshot_dir: Optional[Path] = None,
        websocket_handler = None
    ):
        """
        상세 내용 추출기 초기화
        
        Args:
            driver: 셀레니움 웹드라이버
            wait: 셀레니움 웨이트
            result: 크롤링 결과 객체
            max_details: 최대 상세 항목 수
            screenshot_dir: 스크린샷 저장 디렉토리
            websocket_handler: 웹소켓 핸들러
        """
        self.driver = driver
        self.wait = wait
        self.result = result
        self.max_details = max_details
        self.screenshot_dir = screenshot_dir or Path(crawler_config.screenshot_dir)
        self.websocket_handler = websocket_handler
        self.should_stop = False
    
    async def process_details(self, items: Optional[List[BidItem]] = None) -> int:
        """
        입찰 항목의 상세 정보 처리
        
        Args:
            items: 처리할 입찰 항목 목록 (None이면 result에서 가져옴)
        
        Returns:
            처리된 상세 항목 수
        """
        if items is None:
            items = self.result.items
        
        if not items:
            self.result.add_agent_status(
                message="처리할 입찰 항목이 없습니다.",
                level=AgentStatusLevel.WARNING
            )
            return 0
        
        # 처리할 최대 항목 수 계산
        items_to_process = items[:self.max_details]
        
        self.result.add_agent_status(
            message=f"입찰 상세 정보 추출 시작 (총 {len(items_to_process)}개 항목)",
            level=AgentStatusLevel.INFO
        )
        
        # 웹소켓 상태 업데이트 (있는 경우)
        if self.websocket_handler:
            await self.websocket_handler(self.result)
        
        # 상세 정보 추출
        processed_count = 0
        
        for index, item in enumerate(items_to_process):
            if self.should_stop:
                break
            
            # 상태 업데이트
            self.result.add_agent_status(
                message=f"입찰 상세 정보 추출 중 ({index+1}/{len(items_to_process)}): {item.title[:30]}...",
                level=AgentStatusLevel.INFO
            )
            
            # 웹소켓 상태 업데이트
            if self.websocket_handler:
                await self.websocket_handler(self.result)
            
            # 상세 정보 추출
            success = await self._extract_detail(item)
            
            if success:
                processed_count += 1
            
            # 약간의 대기 (차단 방지)
            await asyncio.sleep(random.uniform(1.5, 3.0))
        
        # 완료 상태 업데이트
        self.result.add_agent_status(
            message=f"입찰 상세 정보 추출 완료 ({processed_count}/{len(items_to_process)}개 성공)",
            level=AgentStatusLevel.SUCCESS if processed_count > 0 else AgentStatusLevel.WARNING
        )
        
        # 웹소켓 상태 업데이트
        if self.websocket_handler:
            await self.websocket_handler(self.result)
        
        return processed_count
    
    async def stop(self):
        """처리 중지"""
        self.should_stop = True
    
    async def _extract_detail(self, item: BidItem) -> bool:
        """
        입찰 항목의 상세 정보 추출
        
        Args:
            item: 입찰 항목
        
        Returns:
            성공 여부
        """
        try:
            # 이미 처리된 항목인지 확인
            if item.bid_id in self.result.details:
                logger.info(f"이미 처리된 항목 건너뜀: {item.bid_id}")
                return True
            
            # URL 확인
            if not item.url:
                logger.warning(f"URL이 없는 항목 건너뜀: {item.bid_id}")
                return False
            
            # 상세 페이지 접속
            self.driver.get(item.url)
            await asyncio.sleep(random.uniform(2.0, 3.0))
            
            # 스크린샷 저장
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            screenshot_filename = f"detail_{item.bid_id}_{timestamp}"
            screenshot_path = await save_screenshot(
                self.driver, 
                self.screenshot_dir, 
                screenshot_filename,
                full_page=True
            )
            
            # 직접 HTML에서 데이터 추출 시도
            detail_data = await self._extract_detail_from_html(item)
            
            # HTML 추출이 충분하지 않으면 AI 기반 추출 시도
            if not detail_data or len(detail_data) < 5:  # 최소 필드 수
                # AI 접근: 스크린샷으로 데이터 추출
                screenshot_data = await take_screenshot(self.driver, full_page=True)
                
                if not screenshot_data:
                    self.result.add_agent_status(
                        message=f"스크린샷 촬영 실패 - 상세 페이지 {item.bid_id}",
                        level=AgentStatusLevel.ERROR
                    )
                    return False
                
                # AI에 상세 정보 추출 요청
                prompt = DETAIL_EXTRACTOR_PROMPT.format(
                    bid_id=item.bid_id,
                    title=item.title
                )
                
                response = await gemini_client.query_vision(prompt, screenshot_data)
                
                if "error" in response:
                    self.result.add_agent_status(
                        message=f"AI 상세 정보 추출 실패 - {item.bid_id}: {response['error']}",
                        level=AgentStatusLevel.ERROR
                    )
                    return False
                
                # 상세 정보 데이터 추출
                ai_detail_data = await extract_detail_data(response["result"])
                
                # 기존 데이터와 AI 추출 데이터 병합
                if detail_data:
                    # 기존 데이터 유지하면서 AI 데이터로 보완
                    for key, value in ai_detail_data.items():
                        if key not in detail_data or not detail_data[key]:
                            detail_data[key] = value
                else:
                    detail_data = ai_detail_data
            
            # 필수 필드 확인
            if not detail_data or "bid_id" not in detail_data or "title" not in detail_data:
                # 최소한의 정보 추가
                if not detail_data:
                    detail_data = {}
                
                if "bid_id" not in detail_data:
                    detail_data["bid_id"] = item.bid_id
                
                if "title" not in detail_data:
                    detail_data["title"] = item.title
            
            # BidDetail 객체 생성
            bid_detail = BidDetail(
                bid_id=detail_data.get("bid_id", item.bid_id),
                title=detail_data.get("title", item.title),
                organization=detail_data.get("organization", item.organization),
                division=detail_data.get("division"),
                location=detail_data.get("location", item.location),
                reg_date=detail_data.get("reg_date", item.reg_date),
                close_date=detail_data.get("close_date", item.close_date),
                estimated_price=detail_data.get("estimated_price", item.price),
                contract_type=detail_data.get("contract_type"),
                bid_type=detail_data.get("bid_type", item.bid_type),
                industry=detail_data.get("industry"),
                contact_info=detail_data.get("contact_info"),
                description=detail_data.get("description"),
                requirements=detail_data.get("requirements"),
                attachments=detail_data.get("attachments"),
                additional_info=detail_data,
                crawled_at=datetime.now()
            )
            
            # 결과에 추가
            self.result.add_detail(bid_detail)
            
            return True
            
        except Exception as e:
            logger.error(f"상세 정보 추출 중 오류: {str(e)}")
            self.result.add_error(f"상세 정보 추출 오류 (입찰ID: {item.bid_id})", {"error": str(e)})
            return False
    
    async def _extract_detail_from_html(self, item: BidItem) -> Dict[str, Any]:
        """
        HTML에서 상세 정보 추출
        
        Args:
            item: 입찰 항목
        
        Returns:
            추출된 상세 정보
        """
        try:
            detail_data = {}
            
            # 기본 정보 설정
            detail_data["bid_id"] = item.bid_id
            detail_data["title"] = item.title
            
            # 테이블에서 정보 추출
            tables = self.driver.find_elements(By.TAG_NAME, "table")
            
            for table in tables:
                try:
                    # 테이블 행 추출
                    rows = table.find_elements(By.TAG_NAME, "tr")
                    
                    for row in rows:
                        try:
                            # 셀 추출
                            th_cells = row.find_elements(By.TAG_NAME, "th")
                            td_cells = row.find_elements(By.TAG_NAME, "td")
                            
                            if not th_cells or not td_cells:
                                continue
                            
                            # 각 헤더와 값 처리
                            for th, td in zip(th_cells, td_cells):
                                key = th.text.strip()
                                value = td.text.strip()
                                
                                if not key or not value:
                                    continue
                                
                                # 키 매핑
                                key_mapping = {
                                    "공고번호": "bid_id",
                                    "입찰공고번호": "bid_id",
                                    "공고명": "title",
                                    "제목": "title",
                                    "공고기관": "organization",
                                    "수요기관": "organization",
                                    "발주기관": "organization",
                                    "기관명": "organization",
                                    "담당부서": "division",
                                    "담당자": "division",
                                    "지역": "location",
                                    "공고일자": "reg_date",
                                    "등록일": "reg_date",
                                    "입찰마감일시": "close_date",
                                    "마감일시": "close_date",
                                    "마감일": "close_date",
                                    "추정가격": "estimated_price",
                                    "예정가격": "estimated_price",
                                    "계약방법": "contract_type",
                                    "계약방식": "contract_type",
                                    "입찰방식": "bid_type",
                                    "입찰유형": "bid_type",
                                    "업종제한": "industry",
                                    "업종": "industry",
                                    "세부내용": "description",
                                    "설명": "description",
                                }
                                
                                mapped_key = key_mapping.get(key)
                                if mapped_key:
                                    detail_data[mapped_key] = value
                        
                        except Exception as e:
                            logger.error(f"행 처리 중 오류: {str(e)}")
                            continue
                
                except Exception as e:
                    logger.error(f"테이블 처리 중 오류: {str(e)}")
                    continue
            
            # 첨부파일 추출
            attachments = []
            
            try:
                # 첨부파일 링크 찾기
                attach_links = self.driver.find_elements(
                    By.XPATH, 
                    "//a[contains(@href, 'download') or contains(@href, 'attach') or contains(@href, 'file')]"
                )
                
                for link in attach_links:
                    try:
                        file_name = link.text.strip()
                        file_href = link.get_attribute("href")
                        
                        if file_name and file_href:
                            attachments.append({
                                "name": file_name,
                                "url": file_href
                            })
                    except:
                        continue
            except:
                pass
            
            if attachments:
                detail_data["attachments"] = attachments
            
            return detail_data
            
        except Exception as e:
            logger.error(f"HTML에서 상세 정보 추출 중 오류: {str(e)}")
            return {} 