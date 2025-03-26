from fastapi import APIRouter, WebSocket, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from typing import Dict, List, Any
import json
import asyncio
from datetime import datetime
import logging
import os
import sys

# 프로젝트 구조에 맞는 import 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.utils.crawl.crawler_core import BidCrawlerTest
from backend.utils.crawl.error_handler import CrawlerException
from backend.utils.crawl.constants import SEARCH_KEYWORDS
from backend.utils.crawl.data_processor import DataProcessor

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# DataProcessor 인스턴스 생성
data_processor = DataProcessor()

# 크롤링 상태 관리
crawling_status = {
    "is_running": False,
    "current_keyword": None,
    "processed_count": 0,
    "total_keywords": len(SEARCH_KEYWORDS),
    "total_results": 0
}

# WebSocket 연결 관리
active_connections: Dict[str, WebSocket] = {}

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = id(websocket)
    active_connections[client_id] = websocket
    
    try:
        while True:
            data = await websocket.receive_text()
            # 클라이언트로부터의 메시지 처리
            await handle_websocket_message(websocket, data)
    except Exception as e:
        logger.error(f"WebSocket 오류: {str(e)}")
    finally:
        if client_id in active_connections:
            del active_connections[client_id]

async def handle_websocket_message(websocket: WebSocket, message: str):
    try:
        data = json.loads(message)
        message_type = data.get("type")
        
        if message_type == "start_crawling":
            await start_crawling(websocket)
        elif message_type == "stop_crawling":
            await stop_crawling(websocket)
        elif message_type == "get_status":
            await send_status_update(websocket)
            
    except json.JSONDecodeError:
        await websocket.send_json({
            "type": "error",
            "message": "잘못된 JSON 형식입니다."
        })
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": f"처리 중 오류 발생: {str(e)}"
        })

async def start_crawling(websocket: WebSocket):
    if crawling_status["is_running"]:
        await websocket.send_json({
            "type": "error",
            "message": "크롤링이 이미 실행 중입니다."
        })
        return

    try:
        crawling_status["is_running"] = True
        crawling_status["processed_count"] = 0
        crawling_status["total_results"] = 0
        
        await websocket.send_json({
            "type": "status",
            "message": "크롤링 시작"
        })

        # 크롤러 인스턴스 생성 및 실행
        crawler = BidCrawlerTest()
        crawler.setup_driver()
        
        # 비동기로 크롤링 실행
        asyncio.create_task(run_crawler(crawler, websocket))
        
    except Exception as e:
        crawling_status["is_running"] = False
        await websocket.send_json({
            "type": "error",
            "message": f"크롤링 시작 실패: {str(e)}"
        })

async def stop_crawling(websocket: WebSocket):
    if not crawling_status["is_running"]:
        await websocket.send_json({
            "type": "error",
            "message": "실행 중인 크롤링이 없습니다."
        })
        return

    try:
        crawling_status["is_running"] = False
        await websocket.send_json({
            "type": "status",
            "message": "크롤링 중지"
        })
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": f"크롤링 중지 실패: {str(e)}"
        })

async def run_crawler(crawler: BidCrawlerTest, websocket: WebSocket):
    try:
        await crawler.navigate_and_analyze()
        
        # 크롤링 결과가 있는 경우, DataProcessor로 엑셀 파일 생성
        if crawler.all_results:
            excel_filename = None
            try:
                df = data_processor.process_crawling_results(crawler.all_results)
                excel_path = data_processor.export_to_excel(df)
                excel_filename = os.path.basename(excel_path)
                logger.info(f"엑셀 파일 생성 완료: {excel_filename}")
            except Exception as e:
                logger.error(f"엑셀 파일 생성 중 오류: {str(e)}")
        
        # 크롤링 완료 후 상태 업데이트
        crawling_status["is_running"] = False
        if websocket:
            await websocket.send_json({
                "type": "status",
                "message": "크롤링 완료",
                "data": {
                    "total_results": len(crawler.all_results),
                    "processed_keywords": len(crawler.processed_keywords),
                    "excel_file": excel_filename if 'excel_filename' in locals() else None
                }
            })
        
    except Exception as e:
        logger.error(f"크롤링 실행 중 오류: {str(e)}")
        crawling_status["is_running"] = False
        if websocket:
            await websocket.send_json({
                "type": "error",
                "message": f"크롤링 중 오류 발생: {str(e)}"
            })
    finally:
        await crawler.cleanup()

async def send_status_update(websocket: WebSocket):
    await websocket.send_json({
        "type": "crawling_status",
        "data": {
            "is_running": crawling_status["is_running"],
            "current_keyword": crawling_status["current_keyword"],
            "processed_count": crawling_status["processed_count"],
            "total_keywords": crawling_status["total_keywords"],
            "total_results": crawling_status["total_results"]
        }
    })

# 크롤링 시작 API
@router.post("/api/start")
async def start_crawling_api(request: Request):
    if crawling_status["is_running"]:
        raise HTTPException(
            status_code=400,
            detail="크롤링이 이미 실행 중입니다."
        )
    
    try:
        data = await request.json()
        start_date = data.get("startDate", "")
        end_date = data.get("endDate", "")
        
        # 비동기 작업으로 크롤링 시작
        crawling_status["is_running"] = True
        crawling_status["processed_count"] = 0
        crawling_status["total_results"] = 0
        
        # 크롤러 인스턴스 생성 및 실행
        crawler = BidCrawlerTest()
        crawler.setup_driver()
        
        # 비동기로 크롤링 실행
        asyncio.create_task(run_crawler(crawler, None))
        
        return {"status": "success", "message": "크롤링이 시작되었습니다."}
    except Exception as e:
        logger.error(f"크롤링 시작 API 오류: {str(e)}")
        crawling_status["is_running"] = False
        raise HTTPException(
            status_code=500,
            detail=f"크롤링 시작 중 오류 발생: {str(e)}"
        )

# 크롤링 중지 API
@router.post("/api/stop")
async def stop_crawling_api():
    if not crawling_status["is_running"]:
        raise HTTPException(
            status_code=400,
            detail="실행 중인 크롤링이 없습니다."
        )
    
    try:
        crawling_status["is_running"] = False
        return {"status": "success", "message": "크롤링이 중지되었습니다."}
    except Exception as e:
        logger.error(f"크롤링 중지 API 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"크롤링 중지 중 오류 발생: {str(e)}"
        )

@router.get("/api/crawl-results/")
async def get_crawl_results():
    try:
        # 결과 파일 읽기
        save_dir = "C:/Users/MyoengHo Shin/pjt/progen/test"
        latest_file = None
        latest_time = None
        
        for file in os.listdir(save_dir):
            if file.startswith("all_crawling_results_"):
                file_path = os.path.join(save_dir, file)
                file_time = os.path.getmtime(file_path)
                if latest_time is None or file_time > latest_time:
                    latest_time = file_time
                    latest_file = file_path
        
        if not latest_file:
            return {
                "summary": {"total_results": 0},
                "results": []
            }
            
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 결과를 DataFrame으로 변환하고 엑셀 파일로 저장
        results = data.get("results", [])
        if results:
            df = data_processor.process_crawling_results(results)
            excel_path = data_processor.export_to_excel(df)
            excel_filename = os.path.basename(excel_path)
        else:
            excel_filename = None
            
        return {
            "summary": {
                "total_results": len(results),
                "processed_keywords": len(data.get("processed_keywords", [])),
                "total_keywords": data.get("total_keywords", 0),
                "excel_file": excel_filename
            },
            "results": results
        }
        
    except Exception as e:
        logger.error(f"결과 조회 중 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"결과 조회 중 오류 발생: {str(e)}"
        )
