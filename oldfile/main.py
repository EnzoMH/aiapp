from fastapi import FastAPI, WebSocket, APIRouter, HTTPException, WebSocketDisconnect, Request

from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates

from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Optional

import json

from datetime import datetime, timedelta, date
import asyncio, logging
from utils.constants import SEARCH_KEYWORDS
from utils.error_handler import ErrorHandler, CrawlerException
from utils.http_client import http_client
from utils.crawler_core import BidCrawlerTest, SearchValidator, NaraMarketCrawler

from dotenv import load_dotenv
import os

from contextlib import asynccontextmanager

import google.generativeai as genai

from data_processor import DataProcessor



load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작할 때 실행될 코드
    logger.info("크롤링 서버 오픈완료")
    yield
    # 종료할 때 실행될 코드
    logger.info("크롤링 서버가 종료됨됨")

app = FastAPI(lifespan=lifespan)

# 정적 파일 마운트
app.mount("/static", StaticFiles(directory="E:/smh/crawl/static"), name="static")
templates = Jinja2Templates(directory="E:/smh/crawl/static")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

class SearchModel(BaseModel):
    keywords: List[str] = Field(..., min_items=1)
    startDate: date
    endDate: date
    
    class Config:
        json_schema_extra = {
            "example": {
                "keywords": ["VR", "AR"],
                "startDate": "2025-01-03",
                "endDate": "2025-02-03"
            }
        }

class WebSocketMessage(BaseModel):
    type: str
    message: Optional[str] = None
    data: Optional[dict] = None
    
# 기존 모델 수정
class BasicInfo(BaseModel):
    no: Optional[str] = None
    business_type: Optional[str] = None
    business_status: str = "-"
    bid_category: str
    bid_number: str
    title: str
    announce_agency: str
    agency: Optional[str] = None
    post_date: str
    progress_stage: str = "-"
    detail_process: str = "-"
    process_status: str = "-"
    bid_progress: str = "-"

class ApiDetail(BaseModel):
    result: dict = {}
    ErrorMsg: str
    ErrorCode: int

class DetailInfo(BaseModel):
    general_notice: Optional[str] = None
    bid_qualification: Optional[str] = None
    bid_restriction: Optional[str] = None
    bid_progress: Optional[str] = None
    presentation_order: Optional[str] = None
    proposal_info: List = []
    negotiation_contract: Optional[str] = None
    bid_notice_files: List = []
    
class SearchResultItem(BaseModel):
    search_keyword: str
    basic_info: BasicInfo
    api_detail: ApiDetail
    detail_info: DetailInfo
    
class SearchResponse(BaseModel):
    timestamp: str
    total_keywords: int
    processed_keywords: List[str]
    total_results: int
    results: List[SearchResultItem]
    metadata: dict
    status: str = "success"
    saved_file: Optional[str] = None

QUALIFICATION_BUSINESS_SCOPE= []

data_processor = DataProcessor()

class CrawlingState:
    def __init__(self):
        self.is_running = False
        self.active_connections = []
        self.current_keyword = ""
        self.collected_data = []
        self.last_crawl_time = None
        self.next_crawl_time = None
        # 필요하다면 processed_keywords 추가
        self.processed_keywords = set()  # 처리된 키워드 추적용


# 크롤링 상태 인스턴스
crawling_state = CrawlingState()

async def perform_crawling(start_date: str, end_date: str):
    """실제 크롤링 수행"""
    crawler = BidCrawlerTest()  # BidCrawler 대신 BidCrawlerTest 사용
    try:
        crawler.setup_driver()
        await crawler.initialize()

        for keyword in SEARCH_KEYWORDS:
            if not crawling_state.is_running:  # 중지 요청 확인
                break
                
            crawling_state.current_keyword = keyword
            
            # 검색 및 데이터 수집
            await crawler.navigate_and_analyze()  # 개선된 크롤링 로직 사용
            
            # 진행 상황 저장
            crawler.save_progress()
            
            # WebSocket 클라이언트에게 진행 상황 전송
            await crawler.broadcast_message({
                "type": "status",
                "message": f"키워드 '{keyword}' 검색 완료",
                "current": keyword,
                "total": len(SEARCH_KEYWORDS)
            })

    except Exception as e:
        logger.error(f"크롤링 중 오류: {e}")
        await crawler.broadcast_message({
            "type": "error",
            "message": str(e)
        })
    finally:
        # 최종 결과 저장
        if crawler.all_results:
            crawler.save_all_crawling_results(crawler.all_results)
        await crawler.cleanup()


# WebSocket 엔드포인트
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    crawling_state.active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:  # 구체적인 예외 처리 필요
        if websocket in crawling_state.active_connections:
            crawling_state.active_connections.remove(websocket)

class CrawlStartParams(BaseModel):
    startDate: str
    endDate: str

# API 엔드포인트
@app.post("/api/start")
async def start_crawling(params: CrawlStartParams):
    if not crawling_state.is_running:
        crawling_state.is_running = True
        asyncio.create_task(perform_crawling(params.startDate, params.endDate))
    return {"status": "started"}

@app.post("/api/stop")
async def stop_crawling():
    crawling_state.is_running = False
    return {"status": "stopped"}

@app.get("/api/download-excel/{filename}")
async def download_excel(filename: str):
    file_path = f"E:/smh/crawl/exports/{filename}"
    if os.path.exists(file_path):
        return FileResponse(
            file_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename
        )
    raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

@app.post("/api/search", response_model=SearchResponse)
async def search(params: SearchModel):
    try:
        logger.info(f"검색 요청 수신 - 키워드: {params.keywords}, 시작일: {params.startDate}, 종료일: {params.endDate}")
        
        crawler = BidCrawlerTest()
        try:
            crawler.setup_driver()
            await crawler.navigate_to_bid_list()
            
            all_results = []
            total_processed = 0
            
            # WebSocket 클라이언트들에게 검색 시작 알림
            for connection in crawling_state.active_connections:
                await connection.send_json({
                    "type": "search_start",
                    "total_keywords": len(params.keywords)
                })
            
            for keyword in params.keywords:
                crawling_state.current_keyword = keyword
                
                # 검색 진행상황 전송
                for connection in crawling_state.active_connections:
                    await connection.send_json({
                        "type": "search_progress",
                        "keyword": keyword,
                        "progress": f"{total_processed + 1}/{len(params.keywords)}"
                    })
                
                results = await crawler.perform_search(keyword)
                if results:
                    all_results.extend(results)
                    
                total_processed += 1
                await asyncio.sleep(1)
            
            # 검색 결과 저장
            save_result = crawler.save_all_crawling_results(all_results)
            
            if save_result:
                try:
                    with open(save_result, 'r', encoding='utf-8') as f:
                        saved_data = json.load(f)
                    
                    response_data = SearchResponse(
                        timestamp=saved_data["timestamp"],
                        total_keywords=saved_data["total_keywords"],
                        processed_keywords=saved_data.get("processed_keywords", []),  # get 사용
                        total_results=saved_data["total_results"],
                        results=[
                            SearchResultItem(
                                search_keyword=result.get("search_keyword", ""),
                                basic_info=BasicInfo(**result["basic_info"]),
                                api_detail=ApiDetail(**result.get("api_detail", {"result": {}, "ErrorMsg": "", "ErrorCode": 0})),
                                detail_info=DetailInfo(**result.get("detail_info", {}))
                            ) for result in saved_data["results"]
                        ],
                        metadata=saved_data.get("metadata", {}),
                        saved_file=save_result
                    )
                    return response_data
                except json.JSONDecodeError as e:
                    raise HTTPException(status_code=500, detail="JSON 파싱 오류")
                except KeyError as e:
                    raise HTTPException(status_code=500, detail=f"필수 필드 누락: {str(e)}")
            
        except Exception as e:
            logger.error(f"검색 중 오류: {e}")
            # WebSocket 클라이언트들에게 오류 알림
            for connection in crawling_state.active_connections:
                await connection.send_json({
                    "type": "search_error",
                    "error": str(e)
                })
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            await crawler.cleanup()
            
    except Exception as e:
        logger.error(f"API 오류: {e}")
        raise HTTPException(status_code=500, detail="검색 처리 중 오류가 발생했습니다.")


if __name__ == "__main__":
    import uvicorn
    import os

    # 현재 디렉토리의 절대 경로 얻기
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 감시할 디렉토리들의 절대 경로 설정
    watch_dirs = [
        current_dir,
        os.path.join(current_dir, "utils"),
        os.path.join(current_dir, "static")
    ]

    config = uvicorn.Config(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_includes=[
            "*.py",    # Python 파일
            "*.html",  # HTML 파일
            "*.css",   # CSS 파일
            "*.js",    # JavaScript 파일
            "*.json"   # JSON 파일
        ],
        reload_dirs=watch_dirs,
        reload_delay=1.0,  # 리로드 간 최소 대기 시간 (초)
        log_level="debug"  # 디버그 로그 활성화
    )

    server = uvicorn.Server(config)
    server.run()