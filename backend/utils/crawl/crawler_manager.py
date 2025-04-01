"""
나라장터 크롤러 관리 모듈

이 모듈은 나라장터 크롤링 작업을 관리하고 클라이언트에 상태 업데이트를 제공합니다.
"""

import asyncio
import logging
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Set, Optional

from fastapi import WebSocket
from .crawler import G2BCrawler
from .models import CrawlingStatus, BidItem, BidBasicInfo, BidDetailInfo

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("crawler_manager.log", mode="a", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

class CrawlerManager:
    """나라장터 크롤러 관리 클래스"""
    
    def __init__(self):
        """크롤러 관리자 초기화"""
        self.is_running = False
        self.active_connections: List[WebSocket] = []
        self.current_keyword = None
        self.processed_keywords: Set[str] = set()
        self.total_keywords = 0
        self.results = []
        self.crawler: Optional[G2BCrawler] = None
        self.crawl_task = None
        self.start_time = None
        self.end_time = None
        self.save_interval = 300  # 저장 간격 (초 단위, 5분)
        self.last_save_time = datetime.now()
    
    def add_connection(self, websocket: WebSocket):
        """웹소켓 연결 추가"""
        if websocket not in self.active_connections:
            self.active_connections.append(websocket)
            logger.info(f"새 WebSocket 연결 추가됨 (현재 {len(self.active_connections)}개)")
    
    def remove_connection(self, websocket: WebSocket):
        """웹소켓 연결 제거"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket 연결 제거됨 (현재 {len(self.active_connections)}개)")
    
    async def send_to_all_clients(self, data: Dict):
        """모든 연결된 클라이언트에 메시지 전송"""
        if not self.active_connections:
            return
        
        for connection in self.active_connections:
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
    
    async def send_result(self, result_data: Dict):
        """결과 데이터 전송"""
        await self.send_to_all_clients({
            "type": "result",
            "results": result_data["results"][:10],  # 첫 10개 결과만 전송
            "total_results": len(result_data["results"]),
            "timestamp": datetime.now().isoformat()
        })
    
    async def broadcast_status(self):
        """현재 크롤링 상태 브로드캐스트"""
        status_data = {
            "type": "crawling_status",
            "current_keyword": self.current_keyword,
            "processed_count": len(self.processed_keywords),
            "processed_keywords": list(self.processed_keywords),
            "total_keywords": self.total_keywords,
            "total_results": len(self.results),
            "is_running": self.is_running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.send_to_all_clients(status_data)
    
    async def send_progress(self, current: int, total: int, message: str):
        """진행 상황 전송"""
        progress = current / total if total > 0 else 0
        await self.send_to_all_clients({
            "type": "progress",
            "progress": progress,
            "current": current,
            "total": total,
            "status": message,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })
    
    async def start_crawling(self, keywords: List[str], headless: bool = True) -> Dict:
        """크롤링 시작"""
        # 이미 실행 중인 경우
        if self.is_running:
            await self.send_status("이미 크롤링이 실행 중입니다.", type_="error")
            return {
                "status": "error",
                "message": "이미 크롤링이 실행 중입니다."
            }
        
        # 키워드 유효성 검사
        if not keywords:
            await self.send_status("검색할 키워드가 없습니다.", type_="error")
            return {
                "status": "error",
                "message": "검색할 키워드가 없습니다."
            }
        
        # 상태 초기화
        self.is_running = True
        self.start_time = datetime.now()
        self.end_time = None
        self.current_keyword = None
        self.processed_keywords.clear()
        self.total_keywords = len(keywords)
        self.results.clear()
        self.last_save_time = datetime.now()
        
        # 현재 상태 브로드캐스트
        await self.broadcast_status()
        
        # 크롤러 초기화
        self.crawler = G2BCrawler(headless=headless)
        
        # 비동기로 크롤링 실행 (백그라운드 태스크)
        self.crawl_task = asyncio.create_task(self._run_crawling(keywords))
        
        # 성공 응답 반환
        await self.send_status(f"크롤링이 시작되었습니다. 키워드 {len(keywords)}개를 처리합니다.", type_="status")
        return {
            "status": "success",
            "message": f"크롤링이 시작되었습니다. 키워드 {len(keywords)}개를 처리합니다."
        }
    
    async def _run_crawling(self, keywords: List[str]):
        """백그라운드에서 크롤링 실행"""
        try:
            logger.info(f"크롤링 시작: 키워드 {len(keywords)}개")
            logger.debug("="*80)
            logger.debug(f"크롤링 백그라운드 프로세스 시작: {datetime.now().isoformat()}")
            logger.debug(f"크롤링 키워드 목록 ({len(keywords)}개): {', '.join(keywords)}")
            
            # 크롤링 실행
            await self.send_status("나라장터 크롤러 초기화 중...", type_="status")
            
            # 진행 상황 업데이트
            await self.send_progress(0, len(keywords), "크롤러 초기화 중...")
            
            # 초기화 및 메인 페이지로 이동
            if not await self.crawler.initialize():
                logger.error("크롤러 초기화 실패")
                await self.send_error("크롤러 초기화 실패")
                self.is_running = False
                await self.broadcast_status()
                return
            
            logger.debug("크롤러 초기화 성공")
            
            if not await self.crawler.navigate_to_main():
                logger.error("메인 페이지 접속 실패")
                await self.send_error("메인 페이지 접속 실패")
                self.is_running = False
                await self.broadcast_status()
                return
            
            logger.debug("메인 페이지 접속 성공")
            
            # 입찰공고목록 페이지로 이동
            await self.send_status("입찰공고목록 페이지로 이동 중...", type_="status")
            if not await self.crawler.navigate_to_bid_list():
                logger.error("입찰공고목록 페이지 접속 실패")
                await self.send_error("입찰공고목록 페이지 접속 실패")
                self.is_running = False
                await self.broadcast_status()
                return
            
            logger.debug("입찰공고목록 페이지 이동 성공")
            
            # 검색 조건 설정
            await self.send_status("검색 조건 설정 중...", type_="status")
            if not await self.crawler.setup_search_conditions():
                logger.warning("검색 조건 설정 중 오류 발생 (진행 계속)")
                await self.send_status("검색 조건 설정 중 오류 발생 (진행 계속)", type_="warning")
            else:
                logger.debug("검색 조건 설정 성공")
            
            # 각 키워드에 대해 검색 수행
            for idx, keyword in enumerate(keywords):
                # 중단 여부 확인
                if not self.is_running:
                    logger.info("사용자에 의해 크롤링이 중단되었습니다.")
                    await self.send_status("사용자에 의해 크롤링이 중단되었습니다.")
                    break
                
                try:
                    # 현재 키워드 업데이트
                    self.current_keyword = keyword
                    await self.broadcast_status()
                    
                    # 진행 상황 업데이트
                    progress_msg = f"키워드 '{keyword}' 검색 중... ({idx + 1}/{len(keywords)})"
                    logger.debug(progress_msg)
                    await self.send_progress(idx + 1, len(keywords), progress_msg)
                    await self.send_status(progress_msg)
                    
                    # 페이지 상태 확인 (복구 필요 여부)
                    if not await self.crawler._check_table_exists():
                        logger.warning("테이블이 표시되지 않음. 페이지 복구 시도")
                        if not await self.crawler.recover_page_state(None):
                            logger.error("페이지 복구 실패")
                            await self.send_status("페이지 상태 복구 실패. 다시 시도합니다.", type_="warning")
                            await self.crawler.navigate_to_bid_list()
                            await self.crawler.setup_search_conditions()
                    
                    # 키워드 검색 수행
                    start_time = datetime.now()
                    keyword_results = await self.crawler.search_keyword(keyword)
                    end_time = datetime.now()
                    
                    # 키워드 검색 결과 디버그 로깅
                    logger.debug(f"키워드 '{keyword}' 검색 완료: {len(keyword_results)}건")
                    logger.debug(f"검색 소요 시간: {(end_time - start_time).total_seconds():.2f}초")
                    
                    # 중복 제거 (SearchValidator 활용)
                    unique_results = self.crawler.validator.remove_duplicates(keyword_results)
                    logger.info(f"중복 제거 후: {len(unique_results)}/{len(keyword_results)}건")
                    
                    # 결과 저장
                    self.results.extend(unique_results)
                    self.processed_keywords.add(keyword)
                    
                    # 주기적 저장 확인
                    await self._check_and_save_periodically()
                    
                    # 상태 업데이트 브로드캐스트
                    await self.broadcast_status()
                    
                    # 키워드별 결과 요약 전송
                    result_msg = f"키워드 '{keyword}' 검색 완료: {len(unique_results)}건 수집 ({idx + 1}/{len(keywords)})"
                    logger.info(result_msg)
                    await self.send_status(result_msg)
                    
                    # 다음 검색을 위해 입찰공고 목록 페이지로 새로 이동 (옵션)
                    if idx < len(keywords) - 1:
                        await self.crawler.navigate_to_bid_list()
                        await self.crawler.setup_search_conditions()
                    
                    # 잠시 대기 (서버 부하 방지)
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"키워드 '{keyword}' 처리 중 오류: {str(e)}")
                    await self.send_error(f"키워드 '{keyword}' 처리 중 오류 발생: {str(e)}")
                    
                    # 오류 발생 시 페이지 복구 시도
                    try:
                        self.crawler.driver.back()
                        await asyncio.sleep(2)
                        await self.crawler.navigate_to_bid_list()
                        await self.crawler.setup_search_conditions()
                    except Exception as recover_error:
                        logger.error(f"복구 중 추가 오류: {str(recover_error)}")
            
            # 크롤링 완료
            logger.info(f"크롤링 완료: {len(self.processed_keywords)}/{len(keywords)} 키워드, 총 {len(self.results)}건")
            
            # 최종 결과 저장
            self._save_crawling_results()
            
            # 완료 메시지 전송
            await self.send_status(f"크롤링이 완료되었습니다. {len(self.processed_keywords)}/{len(keywords)} 키워드, 총 {len(self.results)}건", type_="success")
            
            # 결과 요약 전송
            await self.send_result({"results": self.results})
            
        except Exception as e:
            logger.exception(f"크롤링 프로세스 중 오류: {str(e)}")
            await self.send_error(f"크롤링 프로세스 중 오류가 발생했습니다: {str(e)}")
        finally:
            # 작업 완료 대기
            logger.info("크롤링 작업 완료, 웹드라이버 종료 대기 중...")
            await asyncio.sleep(3)  # 드라이버 종료 전 안정화를 위한 대기
            
            # 상태 업데이트
            self.is_running = False
            self.end_time = datetime.now()
            await self.broadcast_status()
            
            # 정리
            if self.crawler:
                await self.crawler.close()
                self.crawler = None
    
    async def _check_and_save_periodically(self):
        """주기적 저장 확인 및 수행"""
        current_time = datetime.now()
        if (current_time - self.last_save_time).seconds >= self.save_interval:
            # 진행 상황 저장
            logger.info("주기적 저장 시작")
            try:
                self._save_progress()
                self.last_save_time = current_time
                logger.info("주기적 저장 완료")
            except Exception as e:
                logger.error(f"주기적 저장 중 오류: {str(e)}")
    
    def _save_progress(self):
        """진행 상황 저장"""
        try:
            # 저장 경로 설정
            save_dir = os.path.join("crawl", "progress")
            os.makedirs(save_dir, exist_ok=True)
            
            progress_data = {
                "timestamp": datetime.now().strftime('%Y%m%d_%H%M%S'),
                "processed_keywords": list(self.processed_keywords),
                "total_keywords": self.total_keywords,
                "total_results": len(self.results),
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "current_time": datetime.now().isoformat()
            }
            
            filename = os.path.join(save_dir, f"crawling_progress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"진행 상황 저장 완료: {filename}")
            
        except Exception as e:
            logger.error(f"진행 상황 저장 실패: {str(e)}")
    
    def _save_crawling_results(self):
        """전체 크롤링 결과 저장"""
        try:
            # 저장 경로 설정
            save_dir = os.path.join("crawl", "results")
            os.makedirs(save_dir, exist_ok=True)
            
            # 현재 시간으로 파일명 생성
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join(save_dir, f"all_crawling_results_{timestamp}.json")
            
            # 모델 변환을 통한 데이터 정제
            cleaned_results = []
            
            for item in self.results:
                try:
                    # BidItem 모델 기준으로 변환
                    basic_info = item.get('basic_info', {})
                    detail_info = item.get('detail_info', {})
                    
                    # 간단한 형태로 변환하여 저장
                    cleaned_item = {
                        "keyword": item.get('search_keyword', ''),
                        "bid_info": {
                            "number": basic_info.get('bid_number', ''),
                            "title": basic_info.get('title', ''),
                            "agency": basic_info.get('announce_agency', ''),
                            "date": basic_info.get('post_date', ''),
                            "deadline": basic_info.get('deadline_date', ''),
                            "stage": basic_info.get('progress_stage', '-'),
                        },
                        "details": {
                            "notice": detail_info.get('general_notice', ''),
                            "qualification": detail_info.get('bid_qualification', '')
                        },
                        "collected_at": item.get('collected_at', datetime.now().isoformat())
                    }
                    
                    cleaned_results.append(cleaned_item)
                except Exception as e:
                    logger.warning(f"결과 정제 중 오류 (항목 스킵): {str(e)}")
            
            # 저장할 데이터 구조화
            save_data = {
                "timestamp": timestamp,
                "total_results": len(cleaned_results),
                "processed_keywords": list(self.processed_keywords),
                "total_keywords": self.total_keywords,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "results": cleaned_results
            }
            
            # JSON 파일로 저장
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"전체 크롤링 결과 저장 완료: {filename} (총 {len(cleaned_results)}건)")
            return filename
            
        except Exception as e:
            logger.error(f"전체 결과 저장 실패: {str(e)}")
            return None
            
    async def stop_crawling(self) -> Dict:
        """크롤링 중지"""
        if not self.is_running:
            await self.send_status("현재 실행 중인 크롤링이 없습니다.", type_="warning")
            return {
                "status": "warning",
                "message": "현재 실행 중인 크롤링이 없습니다."
            }
        
        logger.info("크롤링 중지 요청 수신")
        await self.send_status("크롤링 중지 요청 처리 중...", type_="status")
        
        # 실행 상태 변경
        self.is_running = False
        self.end_time = datetime.now()
        
        # 크롤링 작업 취소 시도
        if self.crawl_task and not self.crawl_task.done():
            try:
                # 크롤링 작업 취소
                self.crawl_task.cancel()
                await asyncio.sleep(1)
                
                # 웹드라이버 종료
                if self.crawler:
                    await self.crawler.close()
                    self.crawler = None
                
                logger.info("크롤링 중지 완료")
                await self.send_status("크롤링이 중지되었습니다.", type_="success")
                
                # 상태 업데이트
                await self.broadcast_status()
                
                return {
                    "status": "success",
                    "message": "크롤링이 중지되었습니다.",
                    "processed_keywords": list(self.processed_keywords),
                    "total_results": len(self.results)
                }
            except Exception as e:
                logger.error(f"크롤링 중지 중 오류: {str(e)}")
                await self.send_error(f"크롤링 중지 중 오류가 발생했습니다: {str(e)}")
                return {
                    "status": "error",
                    "message": f"크롤링 중지 중 오류가 발생했습니다: {str(e)}"
                }
        else:
            # 이미 완료된 경우
            logger.info("크롤링 작업이 이미 완료되었습니다.")
            await self.send_status("크롤링 작업이 이미 완료되었습니다.", type_="info")
            return {
                "status": "info",
                "message": "크롤링 작업이 이미 완료되었습니다."
            }
    
    def get_results(self) -> Dict:
        """크롤링 결과 가져오기"""
        result_count = len(self.results)
        logger.info(f"크롤링 결과 조회: {result_count}건")
        
        # 마지막으로 저장된 결과 파일 찾기
        latest_result_file = None
        try:
            save_dir = os.path.join("crawl", "results")
            if os.path.exists(save_dir):
                result_files = [os.path.join(save_dir, f) for f in os.listdir(save_dir) if f.startswith("all_crawling_results_")]
                if result_files:
                    latest_result_file = max(result_files, key=os.path.getmtime)
        except Exception as e:
            logger.error(f"결과 파일 조회 중 오류: {str(e)}")
        
        return {
            "status": "success",
            "message": f"{result_count}개의 입찰 공고를 찾았습니다.",
            "results": self.results,
            "processed_keywords": list(self.processed_keywords),
            "total_keywords": self.total_keywords,
            "is_running": self.is_running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "latest_result_file": latest_result_file
        }

# 싱글톤 인스턴스 생성
crawler_manager = CrawlerManager() 