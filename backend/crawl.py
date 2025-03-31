"""
나라장터 크롤링 관리 모듈

이 모듈은 app.py에서 임포트하여 사용하는 크롤링 관리 모듈입니다.
크롤링 기능에 대한 인터페이스를 제공합니다.
"""

import json
import logging
import asyncio
import traceback
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, date

from backend.utils.crawl import G2BCrawler, crawler_manager
from backend.utils.crawl.models import CrawlingRequest, CrawlingResponse, CrawlingStatus, BidItem

# 로깅 설정
logger = logging.getLogger(__name__)

# 기본 키워드 설정 (앱이 기본적으로 사용할 검색어)
DEFAULT_KEYWORDS = [
    "소프트웨어", "시스템", "개발", "유지보수", "AI", "인공지능", 
    "클라우드", "빅데이터", "데이터", "IT", "정보화", "플랫폼"
]

async def start_crawling(
    start_date: Optional[Union[str, date]] = None, 
    end_date: Optional[Union[str, date]] = None, 
    keywords: Optional[List[str]] = None, 
    headless: bool = True
) -> Dict[str, Any]:
    """
    크롤링 시작
    
    Args:
        start_date: 검색 시작일 (YYYY-MM-DD 형식 또는 date 객체)
        end_date: 검색 종료일 (YYYY-MM-DD 형식 또는 date 객체)
        keywords: 검색 키워드 목록 (None인 경우 기본 키워드 사용)
        headless: 헤드리스 모드 사용 여부
        
    Returns:
        Dict: 응답 결과 (status, message 등 포함)
    """
    try:
        # 키워드 목록 설정
        search_keywords = keywords if keywords else DEFAULT_KEYWORDS
        
        # 키워드가 문자열인 경우 목록으로 변환
        if isinstance(search_keywords, str):
            search_keywords = [k.strip() for k in search_keywords.split(',') if k.strip()]
            logger.debug(f"문자열 키워드를 목록으로 변환: {search_keywords}")
        
        # 키워드 유효성 검사
        if not search_keywords:
            logger.error("유효한 키워드가 제공되지 않았습니다.")
            error_response = CrawlingResponse(
                status="error",
                message="검색할 키워드가 제공되지 않았습니다.",
                timestamp=datetime.now()
            )
            return error_response.dict()
        
        # Pydantic 모델 생성 (검증용)
        try:
            request = CrawlingRequest(
                start_date=None,  # 날짜 처리는 백엔드에서 하지 않음
                end_date=None,    # 날짜 처리는 백엔드에서 하지 않음
                keywords=search_keywords,
                headless=headless
            )
            logger.debug(f"유효한 크롤링 요청: {len(request.keywords)}개 키워드")
        except Exception as e:
            logger.error(f"잘못된 크롤링 요청 매개변수: {str(e)}")
            error_response = CrawlingResponse(
                status="error",
                message=f"잘못된 요청 매개변수: {str(e)}",
                timestamp=datetime.now()
            )
            return error_response.dict()
        
        # 키워드 로깅
        logger.info(f"크롤링 시작: 키워드 {len(search_keywords)}개, 헤드리스={headless}")
        logger.debug(f"검색 키워드: {', '.join(search_keywords)}")
        
        # 크롤링 시작
        result = await crawler_manager.start_crawling(search_keywords, headless)
        
        # 결과 로깅
        if result.get("status") == "success":
            logger.info(f"크롤링 시작됨: {result.get('message', '')}")
            response = CrawlingResponse(
                status="success",
                message=result.get('message', '크롤링이 시작되었습니다.'),
                timestamp=datetime.now(),
                keywords=search_keywords,
                total_keywords=len(search_keywords)
            )
            return response.dict()
        else:
            logger.error(f"크롤링 시작 실패: {result.get('message', '')}")
            error_response = CrawlingResponse(
                status="error",
                message=result.get('message', '크롤링 시작에 실패했습니다.'),
                timestamp=datetime.now()
            )
            return error_response.dict()
    
    except Exception as e:
        logger.exception(f"크롤링 시작 중 오류: {str(e)}")
        error_response = CrawlingResponse(
            status="error",
            message=f"크롤링 시작 중 오류가 발생했습니다: {str(e)}",
            timestamp=datetime.now()
        )
        return error_response.dict()

def stop_crawling() -> Dict[str, Any]:
    """
    크롤링 중지
    
    Returns:
        Dict: 응답 결과
    """
    try:
        logger.info("크롤링 중지 요청")
        
        # 비동기 태스크 생성
        loop = asyncio.get_event_loop()
        task = loop.create_task(crawler_manager.stop_crawling())
        
        # Pydantic 모델 사용하여 응답 생성
        response = CrawlingResponse(
            status="success",
            message="크롤링 중지 요청이 전송되었습니다.",
            timestamp=datetime.now()
        )
        
        return response.dict()
    except Exception as e:
        logger.exception(f"크롤링 중지 중 오류: {str(e)}")
        
        # 오류 발생 시 응답
        error_response = CrawlingResponse(
            status="error",
            message=f"크롤링 중지 중 오류가 발생했습니다: {str(e)}",
            timestamp=datetime.now()
        )
        
        return error_response.dict()

def get_results() -> Dict[str, Any]:
    """
    크롤링 결과 가져오기
    
    Returns:
        Dict: 수집된 크롤링 결과 (Pydantic 모델 기반)
    """
    try:
        logger.debug("크롤링 결과 조회 요청")
        
        # 크롤러 매니저에서 결과 가져오기
        raw_results = crawler_manager.get_results()
        
        # 상태 정보 생성
        status = get_crawling_status()
        status_data = status.get("crawling_status", {})
        
        # 결과 데이터 구성
        result_items = []
        for item in raw_results.get("results", []):
            # 개별 BidItem 모델 생성 (가능한 경우)
            try:
                bid_item = BidItem(**item)
                result_items.append(bid_item.dict())
            except Exception as e:
                logger.warning(f"BidItem 모델 변환 실패, 원본 데이터 사용: {str(e)}")
                result_items.append(item)
        
        # 응답 구성
        response = CrawlingResponse(
            status="success",
            message=f"{len(result_items)}개의 입찰 공고를 찾았습니다.",
            timestamp=datetime.now(),
            results=result_items,
            crawling_status=status_data
        )
        
        logger.info(f"크롤링 결과 조회: {len(result_items)}건")
        return response.dict()
        
    except Exception as e:
        logger.exception(f"크롤링 결과 조회 중 오류: {str(e)}")
        error_response = CrawlingResponse(
            status="error",
            message=f"크롤링 결과 조회 중 오류가 발생했습니다: {str(e)}",
            timestamp=datetime.now(),
            results=[]
        )
        return error_response.dict()

def get_crawling_status() -> Dict[str, Any]:
    """
    현재 크롤링 상태 가져오기
    
    Returns:
        Dict: 현재 크롤링 상태 (Pydantic 모델 기반)
    """
    try:
        # Pydantic 모델을 사용하여 상태 생성
        status = CrawlingStatus(
            is_running=crawler_manager.is_running,
            current_keyword=crawler_manager.current_keyword,
            processed_keywords=list(crawler_manager.processed_keywords),
            processed_count=len(crawler_manager.processed_keywords),
            total_keywords=crawler_manager.total_keywords,
            total_results=len(crawler_manager.results),
            start_time=getattr(crawler_manager, "start_time", None),
            end_time=getattr(crawler_manager, "end_time", None),
            timestamp=datetime.now()
        )
        
        # CrawlingResponse 모델로 응답 생성
        response = CrawlingResponse(
            status="success",
            message="크롤링 상태 조회 완료",
            timestamp=datetime.now(),
            crawling_status=status.dict()
        )
        
        logger.debug(f"크롤링 상태 조회 완료")
        return response.dict()
    except Exception as e:
        logger.exception(f"크롤링 상태 조회 중 오류: {str(e)}")
        error_response = CrawlingResponse(
            status="error",
            message=f"크롤링 상태 조회 중 오류가 발생했습니다: {str(e)}",
            timestamp=datetime.now()
        )
        return error_response.dict()

# 전역 변수로 크롤링 상태 객체 노출 (app.py에서 사용)
crawling_state = crawler_manager 