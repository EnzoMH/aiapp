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
            "timestamp": datetime.now().isoformat()
        }
        
        await self.send_to_all_clients(status_data)
    
    async def send_progress(self, current: int, total: int, message: str):
        """진행 상황 전송"""
        await self.send_to_all_clients({
            "type": "progress",
            "current": current,
            "total": total,
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
        self.current_keyword = None
        self.processed_keywords.clear()
        self.total_keywords = len(keywords)
        self.results.clear()
        
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
                    
                    # 키워드 검색 수행
                    start_time = datetime.now()
                    keyword_results = await self.crawler.search_keyword(keyword)
                    end_time = datetime.now()
                    
                    # 키워드 검색 결과 디버그 로깅
                    logger.debug(f"키워드 '{keyword}' 검색 완료: {len(keyword_results)}건")
                    logger.debug(f"검색 소요 시간: {(end_time - start_time).total_seconds():.2f}초")
                    
                    # 결과 저장
                    self.results.extend(keyword_results)
                    self.processed_keywords.add(keyword)
                    
                    # 상태 업데이트 브로드캐스트
                    await self.broadcast_status()
                    
                    # 키워드별 결과 요약 전송
                    result_msg = f"키워드 '{keyword}' 검색 완료: {len(keyword_results)}건 수집 ({idx + 1}/{len(keywords)})"
                    logger.info(result_msg)
                    await self.send_status(result_msg)
                    
                    # 잠시 대기 (서버 부하 방지)
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"키워드 '{keyword}' 처리 중 오류: {str(e)}")
                    await self.send_error(f"키워드 '{keyword}' 처리 중 오류: {str(e)}")
            
            # 크롤링 완료 처리
            self.is_running = False
            self.current_keyword = None
            
            # 최종 상태 업데이트
            await self.broadcast_status()
            
            # 결과 저장
            if self.results:
                result_data = {
                    "status": "success",
                    "total_keywords": len(keywords),
                    "processed_keywords": list(self.processed_keywords),
                    "total_results": len(self.results),
                    "results": self.results
                }
                
                # 결과 저장
                filepath = self.crawler.save_results(result_data)
                completion_msg = ""
                if filepath:
                    completion_msg = f"크롤링 완료: 총 {len(self.results)}건의 결과를 수집했습니다. 파일 저장 위치: {filepath}"
                    logger.info(completion_msg)
                    await self.send_status(completion_msg)
                else:
                    completion_msg = f"크롤링 완료: 총 {len(self.results)}건의 결과를 수집했습니다. (파일 저장 실패)"
                    logger.warning(completion_msg)
                    await self.send_status(completion_msg)
                
                # 결과 데이터 전송
                await self.send_result(result_data)
            else:
                logger.info("크롤링 완료: 수집된 결과가 없습니다.")
                await self.send_status("크롤링 완료: 수집된 결과가 없습니다.")
            
            logger.debug("="*80)
            logger.debug(f"크롤링 백그라운드 프로세스 종료: {datetime.now().isoformat()}")
            logger.debug(f"총 처리된 키워드: {len(self.processed_keywords)}개, 수집된 결과: {len(self.results)}건")
            logger.debug("="*80)
        
        except Exception as e:
            logger.error(f"크롤링 실행 중 오류: {str(e)}")
            await self.send_error(f"크롤링 실행 중 오류: {str(e)}")
            self.is_running = False
            await self.broadcast_status()
        
        finally:
            # 크롤러 종료
            if self.crawler:
                await self.crawler.close()
    
    async def stop_crawling(self) -> Dict:
        """크롤링 중지"""
        if not self.is_running:
            await self.send_status("현재 실행 중인 크롤링이 없습니다.")
            return {
                "status": "warning",
                "message": "현재 실행 중인 크롤링이 없습니다."
            }
        
        # 실행 중지 설정
        self.is_running = False
        
        # 상태 업데이트
        await self.send_status("크롤링 중지 요청이 전송되었습니다. 현재 작업 완료 후 중지됩니다.")
        await self.broadcast_status()
        
        # 태스크 취소 (있는 경우)
        if self.crawl_task and not self.crawl_task.done():
            # 태스크가 안전하게 종료될 때까지 잠시 대기
            await asyncio.sleep(2)
        
        return {
            "status": "success",
            "message": "크롤링이 중지되었습니다."
        }
    
    def get_results(self) -> Dict:
        """현재까지 수집된 결과 반환"""
        return {
            "status": "success",
            "total_results": len(self.results),
            "results": self.results
        }

# 전역 인스턴스 생성 (앱 실행 시 사용)
crawler_manager = CrawlerManager() 