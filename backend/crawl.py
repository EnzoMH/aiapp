"""
나라장터 크롤링 관리 모듈

이 모듈은 app.py에서 임포트하여 사용하는 크롤링 관리 모듈입니다.
크롤링 기능에 대한 인터페이스를 제공합니다.
"""

import json
import logging
import asyncio
import traceback
import os
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, date

from backend.utils.crawl import G2BCrawler, crawler_manager
from backend.utils.crawl.models import (
    CrawlingRequest, 
    CrawlingResponse, 
    CrawlingStatus, 
    BidItem,
    SearchValidator,
    ResultFileInfo
)

# 로깅 설정
logger = logging.getLogger(__name__)

# 기본 키워드 설정 (앱이 기본적으로 사용할 검색어)
DEFAULT_KEYWORDS = [
    "소프트웨어", "시스템", "개발", "유지보수", "AI", "인공지능", 
    "클라우드", "빅데이터", "데이터", "IT", "정보화", "플랫폼"
]

# 크롤링 상태 관리
class CrawlingState:
    def __init__(self):
        self.is_running = False
        self.current_process = None
        self.current_crawler = None
        self.keywords = []
        self.processed_keywords = []
        self.total_items = 0
        self.error_count = 0
        self.started_at = None
        self.completed_at = None
        self.results = []
        self.errors = []
        self.headless = True
        self.save_interval = 5  # 5개 키워드마다 저장
        self.last_save_time = None
        self.stop_requested = False
        self.connections = []  # WebSocket 연결 목록
        
    def reset(self):
        """크롤링 상태 초기화"""
        self.is_running = False
        self.current_process = None
        self.current_crawler = None
        self.keywords = []
        self.processed_keywords = []
        self.total_items = 0
        self.error_count = 0
        self.started_at = None
        self.completed_at = None
        self.results = []
        self.errors = []
        self.stop_requested = False
        # 연결은 초기화하지 않음
        
    def add_connection(self, websocket):
        """WebSocket 연결 추가"""
        if websocket not in self.connections:
            self.connections.append(websocket)
            logger.info(f"WebSocket 연결 추가: 현재 {len(self.connections)}개 연결")
    
    def remove_connection(self, websocket):
        """WebSocket 연결 제거"""
        if websocket in self.connections:
            self.connections.remove(websocket)
            logger.info(f"WebSocket 연결 제거: 현재 {len(self.connections)}개 연결")
    
    async def broadcast_status(self):
        """모든 WebSocket 연결에 현재 상태 브로드캐스트"""
        if not self.connections:
            return
        
        # 상태 정보 가져오기
        status_data = get_crawling_status()
        
        # 메시지 구성
        message = {
            "type": "crawling_status",
            "data": status_data,
            "timestamp": datetime.now().isoformat()
        }
        
        # 현재 연결 복사 (루프 중 변경 방지)
        connections = self.connections.copy()
        
        # 모든 연결에 메시지 전송
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"WebSocket 메시지 전송 중 오류: {str(e)}")
                # 문제가 있는 연결은 제거
                self.remove_connection(connection)
        
    async def stop_crawling(self):
        """크롤링 중지 요청"""
        logger.info("크롤링 중지 요청")
        self.stop_requested = True
        
        if self.current_crawler:
            try:
                await self.current_crawler.close()
                logger.info("크롤러 인스턴스 종료")
            except Exception as e:
                logger.error(f"크롤러 종료 중 오류: {e}")
        
        if self.current_process and not self.current_process.done():
            self.current_process.cancel()
            logger.info("크롤링 프로세스 취소")
            
        self.is_running = False
        self.completed_at = datetime.now()
        
        # 최종 결과 저장
        await self.save_results()
        
    async def save_results(self, is_final=False):
        """크롤링 결과 저장"""
        if not self.results and not is_final:
            logger.info("저장할 결과가 없습니다.")
            return
        
        # 결과 디렉토리 확인 및 생성
        results_dir = os.path.join("crawl", "results")
        os.makedirs(results_dir, exist_ok=True)
        
        # 타임스탬프 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        status = "final" if is_final else "progress"
        filename = f"g2b_results_{status}_{timestamp}.json"
        filepath = os.path.join(results_dir, filename)
        
        # 결과 데이터 구성
        data = {
            "status": "completed" if is_final else "in_progress",
            "message": "크롤링이 완료되었습니다." if is_final else "크롤링 진행 중 저장",
            "total_keywords": len(self.keywords),
            "processed_keywords": len(self.processed_keywords),
            "total_items": self.total_items,
            "error_count": self.error_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "results": [item.model_dump() for item in self.results],
            "errors": self.errors,
            "metadata": {
                "saved_at": datetime.now().isoformat(),
                "is_final": is_final,
                "headless": self.headless
            }
        }
        
        # JSON 파일로 저장
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"크롤링 결과 저장 완료: {filepath} (항목 수: {len(self.results)})")
            self.last_save_time = datetime.now()
            
            return filepath
        except Exception as e:
            logger.error(f"크롤링 결과 저장 중 오류: {e}")
            return None

# 크롤링 상태 인스턴스
crawling_state = CrawlingState()

async def start_crawling(
    keywords: Optional[List[str]] = None, 
    headless: bool = True,
    start_date: Optional[Union[str, date]] = None, 
    end_date: Optional[Union[str, date]] = None
) -> Dict[str, Any]:
    """
    크롤링 시작
    
    Args:
        keywords: 검색 키워드 목록 (None인 경우 기본 키워드 사용)
        headless: 헤드리스 모드 사용 여부
        start_date: 검색 시작일 (YYYY-MM-DD 형식 또는 date 객체) - 현재 미사용
        end_date: 검색 종료일 (YYYY-MM-DD 형식 또는 date 객체) - 현재 미사용
        
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
        
        # 날짜 정보 로그 기록 (현재는 사용하지 않음)
        if start_date or end_date:
            logger.debug(f"검색 기간: {start_date} ~ {end_date} (현재 미사용)")
        
        # 키워드 유효성 검사
        if not search_keywords:
            logger.error("유효한 키워드가 제공되지 않았습니다.")
            error_response = CrawlingResponse(
                status="error",
                message="검색할 키워드가 제공되지 않았습니다.",
                timestamp=datetime.now()
            )
            return error_response.model_dump()
        
        # Pydantic 모델 생성 (검증용)
        try:
            # 검색 유효성 검증
            validator = SearchValidator(
                keywords=search_keywords,
                headless=headless
            )
            validated_keywords = validator.keywords
            logger.debug(f"유효한 크롤링 요청: {len(validated_keywords)}개 키워드")
        except Exception as e:
            logger.error(f"잘못된 크롤링 요청 매개변수: {str(e)}")
            error_response = CrawlingResponse(
                status="error",
                message=f"잘못된 요청 매개변수: {str(e)}",
                timestamp=datetime.now()
            )
            return error_response.model_dump()
        
        # 키워드 로깅
        logger.info(f"크롤링 시작: 키워드 {len(search_keywords)}개, 헤드리스={headless}")
        logger.debug(f"검색 키워드: {', '.join(search_keywords)}")
        
        # 크롤링 상태 초기화
        crawling_state.reset()
        crawling_state.is_running = True
        crawling_state.keywords = validated_keywords
        crawling_state.headless = headless
        crawling_state.started_at = datetime.now()
        
        # 크롤링 프로세스 시작
        crawling_process = asyncio.create_task(
            crawl_process(validated_keywords, headless)
        )
        crawling_state.current_process = crawling_process
        
        # 크롤링 시작 응답
        response = CrawlingResponse(
            status="success",
            message=f"{len(validated_keywords)}개 키워드에 대한 크롤링이 시작되었습니다.",
            total_keywords=len(validated_keywords),
            processed_keywords=0,
            started_at=datetime.now()
        )
        
        return response.model_dump()
    
    except Exception as e:
        logger.exception(f"크롤링 시작 중 오류: {str(e)}")
        error_response = CrawlingResponse(
            status="error",
            message=f"크롤링 시작 중 오류가 발생했습니다: {str(e)}",
            timestamp=datetime.now()
        )
        
        # 에러 발생 시 상태 초기화
        crawling_state.reset()
        return error_response.model_dump()

async def crawl_process(keywords: List[str], headless: bool = True):
    """
    크롤링 프로세스 실행
    
    Args:
        keywords: 검색 키워드 목록
        headless: 헤드리스 모드 여부
    """
    global crawling_state
    
    logger.info(f"크롤링 프로세스 시작: {len(keywords)}개 키워드")
    
    try:
        # G2B 크롤러 인스턴스 생성
        crawler = G2BCrawler(headless=headless)
        crawling_state.current_crawler = crawler
        
        # 크롤러 초기화
        await crawler.initialize()
        
        # 키워드별 크롤링 수행
        for i, keyword in enumerate(keywords):
            if crawling_state.stop_requested:
                logger.info("중지 요청으로 크롤링을 종료합니다.")
                break
            
            logger.info(f"키워드 크롤링 중: '{keyword}' ({i+1}/{len(keywords)})")
            
            try:
                # 키워드 검색 및 결과 수집
                items = await crawler.crawl_keyword(keyword)
                
                if items:
                    # 결과 추가
                    for item in items:
                        item.search_keyword = keyword
                    
                    crawling_state.results.extend(items)
                    crawling_state.total_items += len(items)
                    logger.info(f"키워드 '{keyword}' 검색 결과: {len(items)}개 항목")
                else:
                    logger.info(f"키워드 '{keyword}'에 대한 검색 결과가 없습니다.")
                
                # 처리된 키워드 목록에 추가
                crawling_state.processed_keywords.append(keyword)
                
                # 정기 저장 (5개 키워드마다)
                if (i + 1) % crawling_state.save_interval == 0:
                    await crawling_state.save_results()
                
            except Exception as e:
                error_msg = f"키워드 '{keyword}' 크롤링 중 오류: {str(e)}"
                logger.error(error_msg)
                logger.debug(traceback.format_exc())
                crawling_state.errors.append(error_msg)
                crawling_state.error_count += 1
                
                # 오류에도 불구하고 다음 키워드로 계속 진행
                continue
        
        # 크롤링 완료
        logger.info(f"크롤링 완료: 총 {crawling_state.total_items}개 항목, {crawling_state.error_count}개 오류")
        
    except Exception as e:
        error_msg = f"크롤링 프로세스 실행 중 오류: {str(e)}"
        logger.error(error_msg)
        logger.debug(traceback.format_exc())
        crawling_state.errors.append(error_msg)
        crawling_state.error_count += 1
        
    finally:
        # 크롤러 리소스 정리
        if crawling_state.current_crawler:
            try:
                await crawling_state.current_crawler.close()
                logger.info("크롤러 인스턴스 종료")
            except Exception as e:
                logger.error(f"크롤러 종료 중 오류: {e}")
        
        # 상태 업데이트
        crawling_state.is_running = False
        crawling_state.completed_at = datetime.now()
        
        # 최종 결과 저장
        await crawling_state.save_results(is_final=True)

def stop_crawling() -> Dict[str, Any]:
    """
    크롤링 중지
    
    Returns:
        Dict: 크롤링 중지 결과
    """
    global crawling_state
    
    try:
        # 실행 중이 아닌 경우
        if not crawling_state.is_running:
            logger.warning("실행 중인 크롤링이 없습니다.")
            return {
                "status": "warning",
                "message": "실행 중인 크롤링이 없습니다.",
                "timestamp": datetime.now().isoformat()
            }
        
        # 중지 요청 설정
        crawling_state.stop_requested = True
        
        # 비동기 중지 함수 실행
        asyncio.create_task(crawling_state.stop_crawling())
        
        return {
            "status": "success",
            "message": "크롤링 중지 요청이 전송되었습니다.",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception(f"크롤링 중지 중 오류: {str(e)}")
        return {
            "status": "error",
            "message": f"크롤링 중지 중 오류가 발생했습니다: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

def get_crawling_status() -> Dict[str, Any]:
    """
    크롤링 상태 조회
    
    Returns:
        Dict: 현재 크롤링 상태
    """
    global crawling_state
    
    try:
        status = "running" if crawling_state.is_running else "idle"
        
        if crawling_state.stop_requested:
            status = "stopping"
        
        # 상태 정보 구성
        status_data = {
            "status": status,
            "is_running": crawling_state.is_running,
            "total_keywords": len(crawling_state.keywords),
            "processed_keywords": len(crawling_state.processed_keywords),
            "current_keyword": crawling_state.processed_keywords[-1] if crawling_state.processed_keywords else None,
            "total_items": crawling_state.total_items,
            "error_count": crawling_state.error_count,
            "headless": crawling_state.headless,
            "started_at": crawling_state.started_at.isoformat() if crawling_state.started_at else None,
            "completed_at": crawling_state.completed_at.isoformat() if crawling_state.completed_at else None,
            "last_save_time": crawling_state.last_save_time.isoformat() if crawling_state.last_save_time else None,
            "timestamp": datetime.now().isoformat()
        }
        
        return {
            "status": "success",
            "data": status_data,
            "message": "크롤링 상태 조회 성공",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception(f"크롤링 상태 조회 중 오류: {str(e)}")
        return {
            "status": "error",
            "message": f"크롤링 상태 조회 중 오류가 발생했습니다: {str(e)}",
            "data": {
                "is_running": False,
                "timestamp": datetime.now().isoformat()
            },
            "timestamp": datetime.now().isoformat()
        }

def get_results() -> Dict[str, Any]:
    """
    현재 크롤링 결과 조회
    
    Returns:
        Dict: 크롤링 결과
    """
    global crawling_state
    
    try:
        # 결과 정보 구성
        result_data = {
            "status": "running" if crawling_state.is_running else "completed",
            "message": "크롤링 결과 조회 성공",
            "total_keywords": len(crawling_state.keywords),
            "processed_keywords": len(crawling_state.processed_keywords),
            "total_items": crawling_state.total_items,
            "error_count": crawling_state.error_count,
            "started_at": crawling_state.started_at.isoformat() if crawling_state.started_at else None,
            "completed_at": crawling_state.completed_at.isoformat() if crawling_state.completed_at else None,
            "results": [item.model_dump() for item in crawling_state.results],
            "errors": crawling_state.errors,
            "timestamp": datetime.now().isoformat()
        }
        
        return result_data
        
    except Exception as e:
        logger.exception(f"크롤링 결과 조회 중 오류: {str(e)}")
        return {
            "status": "error",
            "message": f"크롤링 결과 조회 중 오류가 발생했습니다: {str(e)}",
            "results": [],
            "timestamp": datetime.now().isoformat()
        }

def get_latest_result_file() -> Optional[str]:
    """
    최신 크롤링 결과 파일 경로 가져오기
    
    Returns:
        Optional[str]: 최신 결과 파일 경로 또는 None
    """
    try:
        # 저장 디렉토리 확인
        save_dir = os.path.join("crawl", "results")
        if not os.path.exists(save_dir):
            logger.warning(f"결과 디렉토리가 존재하지 않습니다: {save_dir}")
            return None
        
        # 파일 목록 조회
        result_files = [os.path.join(save_dir, f) for f in os.listdir(save_dir) 
                        if f.startswith("g2b_results") and f.endswith(".json")]
        
        if not result_files:
            logger.warning("결과 파일이 존재하지 않습니다.")
            return None
        
        # 가장 최근 파일 반환
        latest_file = max(result_files, key=os.path.getmtime)
        logger.info(f"최신 결과 파일: {latest_file}")
        return latest_file
    except Exception as e:
        logger.error(f"최신 결과 파일 조회 중 오류: {str(e)}")
        return None

def load_crawling_results_from_file(filepath: str) -> Dict[str, Any]:
    """
    파일에서 크롤링 결과 로드
    
    Args:
        filepath: 결과 파일 경로
        
    Returns:
        Dict: 크롤링 결과
    """
    try:
        if not os.path.exists(filepath):
            logger.error(f"파일이 존재하지 않습니다: {filepath}")
            return {
                "status": "error",
                "message": "파일이 존재하지 않습니다",
                "results": []
            }
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"파일에서 {len(data.get('results', []))}건의 결과 로드 완료: {filepath}")
        return {
            "status": "success",
            "message": f"{len(data.get('results', []))}건의 결과를 로드했습니다.",
            "results": data.get("results", []),
            "timestamp": data.get("timestamp", datetime.now().isoformat()),
            "processed_keywords": data.get("processed_keywords", []),
            "total_keywords": data.get("total_keywords", 0),
            "filepath": filepath
        }
    except Exception as e:
        logger.exception(f"파일 로드 중 오류: {str(e)}")
        return {
            "status": "error",
            "message": f"파일 로드 중 오류가 발생했습니다: {str(e)}",
            "results": []
        }

# 전역 변수로 크롤링 상태 객체 노출 (app.py에서 사용)
crawling_state = crawling_state 