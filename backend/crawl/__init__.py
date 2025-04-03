from typing import List, Optional, Dict, Any
import asyncio
from datetime import datetime
import traceback
import logging

# 로깅 설정
logger = logging.getLogger(__name__)

# 크롤링 상태 클래스 가져오기
from backend.crawl.state import CrawlingState

# 크롤링 관련 함수 가져오기
try:
    from backend.utils.crawl import crawler
    from backend.utils.crawl.crawler_manager import CrawlerManager
    CRAWLER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"크롤링 모듈 로드 실패: {e}")
    CRAWLER_AVAILABLE = False
    
    # 더미 클래스 정의
    class DummyCrawlerManager:
        def __init__(self, *args, **kwargs):
            pass
            
        async def initialize(self, *args, **kwargs):
            return False
            
        async def close(self, *args, **kwargs):
            return True
            
        async def search_and_collect(self, *args, **kwargs):
            logger.warning("크롤링 기능을 사용할 수 없습니다. 필요한 라이브러리를 설치하세요.")
            return []
            
        async def extract_bid_detail(self, *args, **kwargs):
            return {}
            
    # 더미 객체로 대체
    CrawlerManager = DummyCrawlerManager

# 크롤링 상태 인스턴스 생성
crawling_state = CrawlingState()

async def crawl_in_background(keywords: List[str], date_range: Optional[tuple] = None, headless: bool = True):
    """
    백그라운드에서 크롤링 실행
    
    Args:
        keywords: 검색 키워드 목록
        date_range: 검색 기간 (시작일, 종료일)
        headless: 헤드리스 모드 여부
    """
    try:
        logger.info(f"백그라운드 크롤링 시작: {len(keywords)}개 키워드")
        
        # 크롤러 매니저 생성
        crawler_manager = CrawlerManager(headless=headless)
        
        # 크롤러 초기화
        await crawler_manager.initialize()
        
        # 크롤링 상태에 현재 크롤러 설정
        crawling_state.set_current_crawler(crawler_manager)
        
        # 키워드별 크롤링 수행
        for i, keyword in enumerate(keywords):
            if not crawling_state.is_running:
                logger.info("중지 요청으로 크롤링을 종료합니다.")
                break
                
            logger.info(f"키워드 크롤링 중: '{keyword}' ({i+1}/{len(keywords)})")
            
            # 검색 및 결과 수집
            results = await crawler_manager.search_and_collect(keyword, date_range)
            
            # 결과 추가
            if results:
                crawling_state.add_results(results)
                logger.info(f"키워드 '{keyword}' 검색 결과: {len(results)}개 항목")
            else:
                logger.warning(f"키워드 '{keyword}' 검색 결과가 없습니다.")
            
            # 처리된 키워드 증가
            crawling_state.increment_processed_keywords()
            
            # 진행률 업데이트
            progress = (i + 1) / len(keywords) * 100
            crawling_state.update_progress(progress)
            
            # WebSocket 클라이언트에 상태 전송
            await broadcast_status()
        
        # 크롤링 완료
        crawling_state.set_completed_at(datetime.now())
        crawling_state.set_running(False)
        
        # 최종 결과 전송
        await broadcast_status(is_final=True)
        
        logger.info(f"크롤링 완료: 총 {len(crawling_state.results)}개 항목")
        
    except Exception as e:
        logger.error(f"백그라운드 크롤링 중 오류 발생: {e}")
        logger.error(traceback.format_exc())
        
        # 오류 발생시 상태 업데이트
        crawling_state.set_running(False)
        crawling_state.set_completed_at(datetime.now())
        
        # 오류 상태 전송
        await broadcast_status(error=str(e))
    finally:
        # 크롤러 종료 처리
        if crawling_state.current_crawler:
            await crawling_state.current_crawler.close()

async def broadcast_status(is_final: bool = False, error: str = None):
    """
    WebSocket 클라이언트에 상태 전송
    
    Args:
        is_final: 최종 상태 여부
        error: 오류 메시지 (있는 경우)
    """
    # 상태 정보 구성
    status_data = await get_crawling_status()
    
    # 최종 상태 또는 오류 정보 추가
    if is_final:
        status_data["is_final"] = True
    
    if error:
        status_data["error"] = error
    
    # 모든 WebSocket 클라이언트에 전송
    for connection in crawling_state.connections:
        try:
            await connection.send_json({
                "type": "status",
                "data": status_data,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"WebSocket 상태 전송 중 오류: {e}")

async def start_crawling(keywords: List[str], start_date: Optional[str] = None, end_date: Optional[str] = None, headless: bool = True) -> Dict[str, Any]:
    """
    크롤링 시작
    
    Args:
        keywords: 검색 키워드 목록
        start_date: 검색 시작 날짜 (YYYY-MM-DD)
        end_date: 검색 종료 날짜 (YYYY-MM-DD)
        headless: 헤드리스 모드 여부
    
    Returns:
        상태 및 성공 여부
    """
    try:
        logger.info(f"크롤링 시작: keywords={keywords}, period={start_date}~{end_date}, headless={headless}")
        
        # 크롤링 중인 경우 오류
        if crawling_state.is_running:
            logger.warning("크롤링이 이미 실행 중입니다.")
            return {"success": False, "message": "크롤링이 이미 실행 중입니다."}
        
        # 검색 기간 설정
        date_range = None
        if start_date and end_date:
            try:
                start_parsed = datetime.strptime(start_date, "%Y-%m-%d")
                end_parsed = datetime.strptime(end_date, "%Y-%m-%d")
                date_range = (start_date, end_date)
            except ValueError:
                logger.warning(f"유효하지 않은 날짜 형식: {start_date} ~ {end_date}")
                # 날짜 형식 오류는 무시하고 진행
        
        # 결과 초기화
        crawling_state.reset_results()
        
        # 상태 업데이트
        crawling_state.set_running(True)
        crawling_state.set_keywords(keywords)
        crawling_state.set_date_range(date_range)
        crawling_state.set_start_time(datetime.now())
        crawling_state.user_search_keywords = keywords  # 사용자 검색 키워드 저장
        
        # 백그라운드에서 크롤링 시작
        asyncio.create_task(crawl_in_background(keywords, date_range, headless))
        
        return {
            "success": True,
            "message": "크롤링이 시작되었습니다.",
            "data": {
                "is_running": True,
                "keywords": keywords,
                "date_range": date_range,
                "start_time": crawling_state.start_time.isoformat() if crawling_state.start_time else None,
                "total_keywords": len(keywords),
                "processed_keywords": 0
            }
        }
    except Exception as e:
        logger.error(f"크롤링 시작 중 오류 발생: {e}")
        logger.error(traceback.format_exc())
        
        # 오류 발생시 상태 초기화
        crawling_state.set_running(False)
        
        return {"success": False, "message": f"크롤링 시작 중 오류가 발생했습니다: {str(e)}"}

async def get_crawling_status() -> Dict[str, Any]:
    """
    현재 크롤링 상태 조회
    
    Returns:
        상태 정보
    """
    try:
        # 상태 정보 구성
        status_data = {
            "is_running": crawling_state.is_running,
            "keywords": crawling_state.keywords,
            "date_range": crawling_state.date_range,
            "start_time": crawling_state.start_time.isoformat() if crawling_state.start_time else None,
            "completed_at": crawling_state.completed_at.isoformat() if crawling_state.completed_at else None,
            "total_keywords": len(crawling_state.keywords) if crawling_state.keywords else 0,
            "processed_keywords": crawling_state.processed_keywords,
            "current_progress": crawling_state.current_progress,
            "user_search_keywords": crawling_state.user_search_keywords  # 사용자 검색 키워드 추가
        }
        return status_data
    except Exception as e:
        logger.error(f"크롤링 상태 조회 중 오류 발생: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "message": f"크롤링 상태 조회 중 오류가 발생했습니다: {str(e)}"}

async def stop_crawling() -> Dict[str, Any]:
    """
    크롤링 중지
    
    Returns:
        상태 및 성공 여부
    """
    try:
        logger.info("크롤링 중지 요청")
        
        # 크롤링 중이 아닌 경우
        if not crawling_state.is_running:
            logger.warning("중지할 크롤링이 없습니다.")
            return {"success": False, "message": "실행 중인 크롤링이 없습니다."}
        
        # 크롤링 상태 업데이트
        crawling_state.set_running(False)
        
        # 크롤러 종료
        if crawling_state.current_crawler:
            await crawling_state.current_crawler.close()
        
        return {"success": True, "message": "크롤링이 중지되었습니다."}
    except Exception as e:
        logger.error(f"크롤링 중지 중 오류 발생: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "message": f"크롤링 중지 중 오류가 발생했습니다: {str(e)}"}

async def get_results() -> Dict[str, Any]:
    """
    크롤링 결과 조회
    
    Returns:
        결과 목록
    """
    try:
        logger.info("크롤링 결과 조회 요청")
        return {"success": True, "results": crawling_state.results}
    except Exception as e:
        logger.error(f"크롤링 결과 조회 중 오류 발생: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "message": f"크롤링 결과 조회 중 오류가 발생했습니다: {str(e)}"}

def add_websocket_client(websocket: any):
    """
    WebSocket 클라이언트 추가
    
    Args:
        websocket: WebSocket 연결 객체
    """
    crawling_state.add_websocket_connection(websocket)

def remove_websocket_client(websocket: any):
    """
    WebSocket 클라이언트 제거
    
    Args:
        websocket: WebSocket 연결 객체
    """
    crawling_state.remove_websocket_connection(websocket)

async def crawl_bid_detail(url: Optional[str] = None, bid_number: Optional[str] = None, row_index: Optional[int] = None) -> Dict[str, Any]:
    """
    입찰 상세 정보 추출
    
    Args:
        url: 상세 페이지 URL
        bid_number: 입찰 번호
        row_index: 결과 목록의 행 인덱스
        
    Returns:
        상세 정보
    """
    try:
        logger.info(f"입찰 상세 정보 추출 요청: URL={url}, 입찰번호={bid_number}, 행 인덱스={row_index}")
        
        # 크롤러가 없는 경우
        if not crawling_state.current_crawler:
            logger.error("상세 정보 추출을 위한 크롤러가 없습니다.")
            return {"success": False, "message": "크롤링을 먼저 시작해야 합니다."}
        
        # 입찰 번호로 조회
        if bid_number:
            for i, item in enumerate(crawling_state.results):
                if item.get("bid_number") == bid_number:
                    row_index = i
                    break
            
            if row_index is None:
                logger.error(f"입찰번호 {bid_number}에 해당하는 항목을 찾을 수 없습니다.")
                return {"success": False, "message": f"입찰번호 {bid_number}에 해당하는 항목을 찾을 수 없습니다."}
        
        # 행 인덱스로 URL 찾기
        if row_index is not None and not url:
            if 0 <= row_index < len(crawling_state.results):
                url = crawling_state.results[row_index].get("detail_url")
            else:
                logger.error(f"행 인덱스 {row_index}에 해당하는 항목이 없습니다.")
                return {"success": False, "message": f"행 인덱스 {row_index}에 해당하는 항목이 없습니다."}
        
        # URL이 없는 경우
        if not url:
            logger.error("상세 정보 추출을 위한 URL이 제공되지 않았습니다.")
            return {"success": False, "message": "상세 정보 추출을 위한 URL이 제공되지 않았습니다."}
        
        # 상세 정보 추출
        detail = await crawling_state.current_crawler.extract_bid_detail(url)
        
        # 상태 업데이트
        if detail and "bid_number" in detail:
            crawling_state.update_detail_status(detail["bid_number"], {
                "status": "completed",
                "timestamp": datetime.now().isoformat()
            })
        
        return {"success": True, "detail": detail}
    except Exception as e:
        logger.error(f"입찰 상세 정보 추출 중 오류 발생: {e}")
        logger.error(traceback.format_exc())
        
        # 오류 상태 저장
        if bid_number:
            crawling_state.update_detail_status(bid_number, {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
        
        return {"success": False, "message": f"입찰 상세 정보 추출 중 오류가 발생했습니다: {str(e)}"} 