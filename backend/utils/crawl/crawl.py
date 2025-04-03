"""
나라장터 크롤링 애플리케이션 모듈

이 모듈은 나라장터 웹사이트 크롤링 애플리케이션의 주요 API를 제공합니다.
웹 인터페이스와 크롤러 사이를 연결하는 역할을 합니다.
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import traceback

# 크롤러 모듈 가져오기
from .crawler import g2b_crawler
from .core.models import G2BBidItem

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("server.log", mode="a", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# 웹소켓 클라이언트 목록
websocket_clients = []
agent_websocket_clients = []


# 웹소켓 클라이언트 관리
def add_websocket_client(websocket):
    """웹소켓 클라이언트 추가"""
    if websocket not in websocket_clients:
        websocket_clients.append(websocket)
        logger.info(f"웹소켓 클라이언트 추가됨, 현재 {len(websocket_clients)}개 연결")


def remove_websocket_client(websocket):
    """웹소켓 클라이언트 제거"""
    if websocket in websocket_clients:
        websocket_clients.remove(websocket)
        logger.info(f"웹소켓 클라이언트 제거됨, 현재 {len(websocket_clients)}개 연결")


def add_agent_websocket_client(websocket):
    """에이전트 웹소켓 클라이언트 추가"""
    if websocket not in agent_websocket_clients:
        agent_websocket_clients.append(websocket)
        logger.info(f"에이전트 웹소켓 클라이언트 추가됨, 현재 {len(agent_websocket_clients)}개 연결")


def remove_agent_websocket_client(websocket):
    """에이전트 웹소켓 클라이언트 제거"""
    if websocket in agent_websocket_clients:
        agent_websocket_clients.remove(websocket)
        logger.info(f"에이전트 웹소켓 클라이언트 제거됨, 현재 {len(agent_websocket_clients)}개 연결")


# 웹소켓 메시지 전송
async def broadcast_status(message, message_type="info"):
    """모든 웹소켓 클라이언트에게 상태 메시지 전송"""
    if not websocket_clients:
        logger.warning("연결된 웹소켓 클라이언트가 없음")
        return

    data = {
        "type": message_type,
        "message": message,
        "timestamp": datetime.now().isoformat()
    }

    for client in websocket_clients:
        try:
            await client.send_json(data)
        except Exception as e:
            logger.error(f"상태 메시지 전송 중 오류: {e}")
            # 오류 발생 시 클라이언트 제거
            remove_websocket_client(client)


async def broadcast_results(results):
    """모든 웹소켓 클라이언트에게 결과 전송"""
    if not websocket_clients:
        logger.warning("연결된 웹소켓 클라이언트가 없음")
        return

    data = {
        "type": "results",
        "results": results,
        "timestamp": datetime.now().isoformat()
    }

    for client in websocket_clients:
        try:
            await client.send_json(data)
        except Exception as e:
            logger.error(f"결과 전송 중 오류: {e}")
            # 오류 발생 시 클라이언트 제거
            remove_websocket_client(client)


async def broadcast_detail(detail):
    """모든 웹소켓 클라이언트에게 상세 정보 전송"""
    if not websocket_clients:
        logger.warning("연결된 웹소켓 클라이언트가 없음")
        return

    data = {
        "type": "detail",
        "detail": detail,
        "timestamp": datetime.now().isoformat()
    }

    for client in websocket_clients:
        try:
            await client.send_json(data)
        except Exception as e:
            logger.error(f"상세 정보 전송 중 오류: {e}")
            # 오류 발생 시 클라이언트 제거
            remove_websocket_client(client)


async def broadcast_progress(progress):
    """모든 웹소켓 클라이언트에게 진행 상황 전송"""
    if not websocket_clients:
        logger.warning("연결된 웹소켓 클라이언트가 없음")
        return

    data = {
        "type": "progress",
        "progress": progress,
        "timestamp": datetime.now().isoformat()
    }

    for client in websocket_clients:
        try:
            await client.send_json(data)
        except Exception as e:
            logger.error(f"진행 상황 전송 중 오류: {e}")
            # 오류 발생 시 클라이언트 제거
            remove_websocket_client(client)


# 크롤링 작업 상태
crawling_status = {
    "is_running": False,
    "keywords": [],
    "total_keywords": 0,
    "processed_keywords": 0,
    "results": [],
    "start_time": None,
    "end_time": None,
    "errors": []
}

# 상세 정보 크롤링 상태
detail_crawling_status = {
    "is_running": False,
    "bid_number": None,
    "title": None,
    "url": None,
    "detail": None,
    "start_time": None,
    "end_time": None,
    "error": None
}


# 입찰 정보 수집
async def crawl_bid_list(keyword: str, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
    """
    나라장터에서 입찰 정보 수집
    
    Args:
        keyword: 검색할 키워드
        start_date: 시작 날짜 (YYYY-MM-DD)
        end_date: 종료 날짜 (YYYY-MM-DD)
        
    Returns:
        수집된 입찰 정보 목록
    """
    try:
        logger.info(f"입찰 정보 수집 시작: 키워드={keyword}, 기간={start_date}~{end_date}")
        
        # 브로드캐스트 상태 업데이트
        await broadcast_status(f"키워드 '{keyword}'에 대한 입찰 정보 수집 시작", "info")
        
        # 크롤러 초기화
        if not g2b_crawler.driver:
            logger.info("크롤러 초기화 중...")
            await g2b_crawler.initialize()
            
        # 메인 페이지 접속
        if not await g2b_crawler.navigate_to_main():
            error_msg = "메인 페이지 접속 실패"
            logger.error(error_msg)
            await broadcast_status(error_msg, "error")
            return []
            
        # 입찰공고 목록 페이지로 이동
        if not await g2b_crawler.navigate_to_bid_list():
            error_msg = "입찰공고 목록 페이지 접속 실패"
            logger.error(error_msg)
            await broadcast_status(error_msg, "error")
            return []
            
        # 검색 조건 설정
        if not await g2b_crawler.setup_search_conditions():
            logger.warning("검색 조건 설정 중 오류 발생 (진행 계속)")
            await broadcast_status("검색 조건 설정 중 일부 오류 발생", "warning")
        
        # 키워드 검색
        await broadcast_status(f"키워드 '{keyword}' 검색 중...", "info")
        await g2b_crawler.search_keyword(keyword)
        
        # 입찰 정보 추출
        await broadcast_status("입찰 정보 추출 중...", "info")
        bid_items = await g2b_crawler.extract_all_bid_data()
        
        # 결과 변환
        results = []
        for item in bid_items:
            # Pydantic 모델을 딕셔너리로 변환
            item_dict = item.dict()
            
            # 날짜 필드를 ISO 형식 문자열로 변환
            for field in ['post_date', 'bid_start_date', 'bid_open_date', 'bid_close_date', 'crawled_at']:
                if item_dict.get(field):
                    item_dict[field] = item_dict[field].isoformat()
            
            results.append(item_dict)
        
        # 브로드캐스트 결과
        await broadcast_status(f"입찰 정보 수집 완료: {len(results)}개 항목 발견", "success")
        await broadcast_results(results)
        
        # 크롤링 상태 업데이트
        crawling_status["results"].extend(results)
        
        logger.info(f"입찰 정보 수집 완료: {len(results)}개 항목")
        return results
        
    except Exception as e:
        error_msg = f"입찰 정보 수집 중 오류 발생: {str(e)}"
        logger.error(error_msg)
        await broadcast_status(error_msg, "error")
        return []


# 입찰 상세 정보 수집
async def crawl_bid_detail(url: str = None, bid_number: str = None, row_index: int = None) -> Dict[str, Any]:
    """
    입찰 상세 정보 수집
    
    Args:
        url: 상세 페이지 URL (없으면 현재 페이지 또는 행 인덱스 사용)
        bid_number: 입찰번호
        row_index: 행 인덱스
        
    Returns:
        상세 정보 딕셔너리
    """
    global detail_crawling_status
    
    try:
        # 상태 초기화
        detail_crawling_status = {
            "is_running": True,
            "bid_number": bid_number,
            "url": url,
            "title": None,
            "detail": None,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "error": None
        }
        
        # 브로드캐스트 상태 업데이트
        await broadcast_status(f"입찰 상세 정보 수집 시작: {bid_number or url or f'행 {row_index}'}", "info")
        
        # 크롤러 초기화
        if not g2b_crawler.crawler.driver:
            logger.info("크롤러 초기화 중...")
            await g2b_crawler.initialize()
        
        # 상세 정보 추출
        detail_info = await g2b_crawler.extract_bid_detail(url, row_index)
        
        if not detail_info:
            error_msg = "상세 정보 추출 실패"
            logger.error(error_msg)
            await broadcast_status(error_msg, "error")
            
            detail_crawling_status["is_running"] = False
            detail_crawling_status["end_time"] = datetime.now().isoformat()
            detail_crawling_status["error"] = error_msg
            
            return {"success": False, "message": error_msg}
        
        # 첨부파일 처리
        if detail_info.attachments:
            await broadcast_status(f"첨부파일 처리 중: {len(detail_info.attachments)}개 파일", "info")
            await g2b_crawler.download_attachments(detail_info)
        
        # 결과 변환
        detail_dict = detail_info.to_dict()
        
        # 일부 첨부파일 정보 제외 (용량 절약)
        if "attachments" in detail_dict:
            for attachment in detail_dict["attachments"]:
                if "content" in attachment:
                    attachment["content"] = None  # 콘텐츠 제외
        
        # 브로드캐스트 결과
        await broadcast_status(f"입찰 상세 정보 수집 완료: {detail_info.bid_number}", "success")
        await broadcast_detail(detail_dict)
        
        # 상태 업데이트
        detail_crawling_status["is_running"] = False
        detail_crawling_status["end_time"] = datetime.now().isoformat()
        detail_crawling_status["detail"] = detail_dict
        detail_crawling_status["bid_number"] = detail_info.bid_number
        detail_crawling_status["title"] = detail_info.title
        
        logger.info(f"입찰 상세 정보 수집 완료: {detail_info.bid_number}")
        return {"success": True, "detail": detail_dict}
        
    except Exception as e:
        error_msg = f"입찰 상세 정보 수집 중 오류 발생: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        # 상태 업데이트
        detail_crawling_status["is_running"] = False
        detail_crawling_status["end_time"] = datetime.now().isoformat()
        detail_crawling_status["error"] = error_msg
        
        await broadcast_status(error_msg, "error")
        return {"success": False, "message": error_msg}


# 크롤링 작업 관리
async def start_crawling(keywords: List[str], start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    """
    크롤링 작업 시작
    
    Args:
        keywords: 검색할 키워드 목록
        start_date: 시작 날짜 (YYYY-MM-DD)
        end_date: 종료 날짜 (YYYY-MM-DD)
        
    Returns:
        작업 시작 결과
    """
    global crawling_status
    
    # 이미 실행 중이면 오류
    if crawling_status["is_running"]:
        return {
            "success": False,
            "message": "이미 크롤링이 실행 중입니다.",
            "data": crawling_status
        }
    
    # 크롤링 상태 초기화
    crawling_status = {
        "is_running": True,
        "keywords": keywords,
        "total_keywords": len(keywords),
        "processed_keywords": 0,
        "results": [],
        "start_time": datetime.now().isoformat(),
        "end_time": None,
        "errors": []
    }
    
    # 백그라운드 작업으로 크롤링 시작
    asyncio.create_task(
        _crawling_task(keywords, start_date, end_date)
    )
    
    return {
        "success": True,
        "message": f"{len(keywords)}개 키워드에 대한 크롤링을 시작합니다.",
        "data": crawling_status
    }


async def stop_crawling() -> Dict[str, Any]:
    """
    크롤링 작업 중지
    
    Returns:
        작업 중지 결과
    """
    global crawling_status
    
    # 실행 중이 아니면 오류
    if not crawling_status["is_running"]:
        return {
            "success": False,
            "message": "실행 중인 크롤링이 없습니다.",
            "data": crawling_status
        }
    
    # 크롤링 상태 업데이트
    crawling_status["is_running"] = False
    crawling_status["end_time"] = datetime.now().isoformat()
    
    # 브로드캐스트 상태 업데이트
    await broadcast_status("크롤링이 중지되었습니다.", "info")
    
    return {
        "success": True,
        "message": "크롤링이 중지되었습니다.",
        "data": crawling_status
    }


async def get_crawling_status() -> Dict[str, Any]:
    """
    현재 크롤링 상태 조회
    
    Returns:
        현재 크롤링 상태
    """
    return {
        "success": True,
        "data": crawling_status,
        "results": crawling_status["results"],
        "detail_status": detail_crawling_status
    }


async def _crawling_task(keywords: List[str], start_date: str = None, end_date: str = None):
    """
    백그라운드 크롤링 작업
    
    Args:
        keywords: 검색할 키워드 목록
        start_date: 시작 날짜 (YYYY-MM-DD)
        end_date: 종료 날짜 (YYYY-MM-DD)
    """
    global crawling_status
    
    try:
        logger.info(f"백그라운드 크롤링 작업 시작: {len(keywords)}개 키워드")
        
        for idx, keyword in enumerate(keywords):
            # 작업 중지 확인
            if not crawling_status["is_running"]:
                logger.info("크롤링 작업이 중지되었습니다.")
                break
            
            # 진행 상황 업데이트
            progress = {
                "current_keyword": keyword,
                "current_index": idx,
                "total": len(keywords),
                "progress": (idx / len(keywords)) if len(keywords) > 0 else 0
            }
            
            await broadcast_progress(progress)
            
            try:
                # 키워드 크롤링 수행
                results = await crawl_bid_list(keyword, start_date, end_date)
                
                # 처리 완료 키워드 수 증가
                crawling_status["processed_keywords"] += 1
                
                # 결과 저장 (crawl_bid_list 함수에서 이미 처리됨)
                
                # 키워드 사이 짧은 딜레이
                await asyncio.sleep(1)
                
            except Exception as e:
                error_msg = f"키워드 '{keyword}' 처리 중 오류: {str(e)}"
                logger.error(error_msg)
                
                # 오류 저장
                crawling_status["errors"].append({
                    "keyword": keyword,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                
                # 브로드캐스트 상태 업데이트
                await broadcast_status(error_msg, "error")
                
                # 처리 완료 키워드 수 증가
                crawling_status["processed_keywords"] += 1
        
        # 크롤링 완료
        crawling_status["is_running"] = False
        crawling_status["end_time"] = datetime.now().isoformat()
        
        # 브로드캐스트 상태 업데이트
        await broadcast_status(
            f"크롤링이 완료되었습니다. {crawling_status['processed_keywords']}/{crawling_status['total_keywords']} 키워드 처리, "
            f"{len(crawling_status['results'])}개 결과, {len(crawling_status['errors'])}개 오류",
            "success"
        )
        
        logger.info(f"백그라운드 크롤링 작업 완료: {crawling_status['processed_keywords']}/{crawling_status['total_keywords']} 키워드 처리")
        
    except Exception as e:
        error_msg = f"백그라운드 크롤링 작업 중 오류: {str(e)}"
        logger.error(error_msg)
        
        # 크롤링 상태 업데이트
        crawling_status["is_running"] = False
        crawling_status["end_time"] = datetime.now().isoformat()
        
        # 오류 저장
        crawling_status["errors"].append({
            "keyword": "전체 작업",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        
        # 브로드캐스트 상태 업데이트
        await broadcast_status(error_msg, "error")
    
    finally:
        # 크롤러 리소스 정리
        try:
            await g2b_crawler.close()
        except:
            pass 