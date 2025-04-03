"""
나라장터 웹사이트 크롤러 모듈

이 모듈은 국가종합전자조달 나라장터 웹사이트의 입찰공고를 수집하는 크롤러를 구현합니다.
core 패키지의 모듈들을 사용하여 기능을 제공하며, crawl.py와 연결다리 역할을 합니다.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
import asyncio
import logging
import os
import json
import traceback

# core 모듈 가져오기
from .core.crawler_base import G2BCrawler
from .core.validator import SearchValidator
from .models import BidItem, BidStatus
from .core.models import BidDetailInfo
from .detail_extractor import DetailExtractor

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("crawler.log", mode="a", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# 기존 G2BCrawler와 SearchValidator 클래스를 여기서 호출하여 사용
# G2BCrawler는 core/crawler_base.py에 정의되어 있고,
# SearchValidator는 core/validator.py에 정의되어 있음

# crawler.py에서 G2BCrawler의 중요 메서드만 구현하고, 나머지는 core 모듈에 위임

class G2BCrawlerWrapper:
    """G2BCrawler 래퍼 클래스 - crawl.py와의 통합을 위한 인터페이스 제공"""
    
    def __init__(self, headless: bool = True, download_path: str = None):
        """
        크롤러 초기화
        
        Args:
            headless (bool): 헤드리스 모드 사용 여부 (기본값: True)
            download_path (str): 첨부파일 다운로드 경로 (기본값: None)
        """
        # 핵심 크롤러 인스턴스 생성
        self.crawler = G2BCrawler(headless=headless)
        self.validator = SearchValidator()
        
        # 상세 정보 추출기 인스턴스 생성
        self.detail_extractor = DetailExtractor(driver=None, download_path=download_path)
        
    async def initialize(self):
        """크롤러 초기화"""
        result = await self.crawler.initialize()
        
        # 상세 정보 추출기에 WebDriver 설정
        self.detail_extractor.driver = self.crawler.driver
        
        return result
    
    async def close(self):
        """크롤러 종료"""
        # 상세 정보 추출기 세션 종료
        await self.detail_extractor.close_session()
        
        # 크롤러 종료
        return await self.crawler.close()
    
    async def navigate_to_main(self):
        """메인 페이지로 이동"""
        return await self.crawler.navigate_to_main()
    
    async def navigate_to_bid_list(self):
        """입찰공고 목록 페이지로 이동"""
        return await self.crawler.navigate_to_bid_list()
    
    async def setup_search_conditions(self):
        """검색 조건 설정"""
        return await self.crawler.setup_search_conditions()
    
    async def search_keyword(self, keyword: str) -> List[Dict]:
        """키워드로 검색 수행"""
        # 여기서 core의 G2BCrawler.search_keyword 호출
        return await self.crawler.search_keyword(keyword)
    
    async def crawl_keywords(self, keywords: List[str]) -> Dict:
        """여러 키워드에 대해 크롤링 수행"""
        # 여기서 core의 G2BCrawler.crawl_keywords 호출
        return await self.crawler.crawl_keywords(keywords)

    async def crawl_keyword(self, keyword: str) -> List[BidItem]:
        """
        단일 키워드 크롤링 수행 - BidItem 객체 변환 포함
        
        Args:
            keyword (str): 검색할 키워드
            
        Returns:
            List[BidItem]: 크롤링 결과 항목 목록
        """
        try:
            logger.info(f"키워드 '{keyword}' 크롤링 시작")
            
            if not self.crawler.driver:
                await self.initialize()
            
            # 메인 페이지 접속
            if not await self.navigate_to_main():
                logger.error(f"키워드 '{keyword}' 크롤링 실패: 메인 페이지 접속 실패")
                return []
            
            # 입찰공고목록 페이지로 이동
            if not await self.navigate_to_bid_list():
                logger.error(f"키워드 '{keyword}' 크롤링 실패: 입찰공고목록 페이지 접속 실패")
                return []
            
            # 검색 조건 설정
            if not await self.setup_search_conditions():
                logger.warning("검색 조건 설정 중 오류 발생 (진행 계속)")
            
            # 키워드 검색 수행
            result_data = await self.search_keyword(keyword)
            
            # BidItem 객체로 변환
            items = []
            for data in result_data:
                try:
                    # 기본 정보와 상세 정보 추출
                    basic_info = data.get('basic_info', {})
                    detail_info = data.get('detail_info', {})
                    
                    # 필수 필드 확인
                    if not basic_info.get('title'):
                        logger.warning(f"제목 없는 항목 제외: {basic_info}")
                        continue
                    
                    # BidItem 객체 생성
                    item = BidItem(
                        bid_number=basic_info.get('bid_number'),
                        bid_name=basic_info.get('title'),
                        org_name=basic_info.get('organization') or basic_info.get('announce_agency'),
                        deadline=basic_info.get('deadline') or basic_info.get('deadline_date'),
                        status=basic_info.get('status') or basic_info.get('process_status') or BidStatus.UNKNOWN,
                        url=basic_info.get('url'),
                        bid_method=detail_info.get('bid_method'),
                        contract_type=detail_info.get('contract_type'),
                        price_evaluation=detail_info.get('price_evaluation'),
                        location=detail_info.get('location'),
                        search_keyword=keyword,
                        collected_at=datetime.now()
                    )
                    
                    items.append(item)
                    
                except Exception as e:
                    logger.error(f"BidItem 변환 중 오류: {str(e)}")
                    continue
            
            logger.info(f"키워드 '{keyword}' 크롤링 완료: {len(items)}개 항목")
            return items
            
        except Exception as e:
            logger.error(f"키워드 '{keyword}' 크롤링 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return []
            
    async def navigate_to_detail(self, row_index: int) -> bool:
        """
        입찰공고 목록에서 특정 행의 공고 상세 페이지로 이동
        
        Args:
            row_index: 행 인덱스
            
        Returns:
            bool: 성공 여부
        """
        return await self.crawler.navigate_to_detail(row_index)
    
    async def extract_bid_detail(self, url: str = None, row_index: int = None) -> Optional[BidDetailInfo]:
        """
        입찰공고 상세 정보 추출
        
        Args:
            url: 상세 페이지 URL (없으면 현재 페이지 사용)
            row_index: 행 인덱스 (URL이 없을 때 해당 행의 상세 페이지로 이동)
            
        Returns:
            BidDetailInfo 객체 또는 None
        """
        try:
            logger.info(f"입찰공고 상세 정보 추출 시작: {url or f'행 인덱스 {row_index}'}")
            
            # URL이 없고 행 인덱스가 있는 경우, 해당 행의 상세 페이지로 이동
            if not url and row_index is not None:
                if not await self.navigate_to_detail(row_index):
                    logger.error(f"행 {row_index}의 상세 페이지로 이동 실패")
                    return None
                    
                await asyncio.sleep(2)  # 페이지 로딩 대기
            
            # 상세 정보 추출
            detail_info = await self.detail_extractor.extract_detail(url)
            
            if not detail_info:
                logger.warning("상세 정보 추출 실패")
                return None
                
            logger.info(f"입찰공고 상세 정보 추출 완료: {detail_info.bid_number}")
            return detail_info
            
        except Exception as e:
            logger.error(f"입찰공고 상세 정보 추출 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return None
            
    async def download_attachments(self, detail_info: BidDetailInfo) -> bool:
        """
        입찰공고 첨부파일 다운로드 및 처리
        
        Args:
            detail_info: 상세 정보 객체
            
        Returns:
            bool: 성공 여부
        """
        try:
            if not detail_info or not detail_info.attachments:
                logger.warning("다운로드할 첨부파일이 없습니다")
                return False
                
            logger.info(f"첨부파일 다운로드 시작: {len(detail_info.attachments)}개 파일")
            
            # 각 첨부파일 처리
            success_count = 0
            for attachment in detail_info.attachments:
                if await self.detail_extractor.process_attachment(attachment):
                    success_count += 1
                    
            logger.info(f"첨부파일 다운로드 완료: {success_count}/{len(detail_info.attachments)}개 성공")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"첨부파일 다운로드 중 오류: {str(e)}")
            return False

# 모듈 내 인스턴스 노출
g2b_crawler = G2BCrawlerWrapper()