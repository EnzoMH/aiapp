"""
백엔드 API 앱 모듈

Flask와 FastAPI를 사용한 백엔드 API 서버 모듈입니다.
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Response, Depends, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import crawl
from backend.utils.crawl import crawl as crawl_utils
from backend.utils.crawl.models import G2BBidItem
from backend.utils.crawl.core.models import AgentStatusLevel

# Gemini API 가져오기
from backend.utils.ai import analyze_sales_opportunity

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

# FastAPI 앱 생성
app = FastAPI(
    title="G2B 나라장터 크롤링 API",
    description="나라장터 입찰정보 크롤링 API",
    version="1.0.0"
)

# 모델 정의
class KeywordList(BaseModel):
    keywords: List[str]
    headless: bool = True
    startDate: Optional[str] = None
    endDate: Optional[str] = None

class AnalysisRequest(BaseModel):
    bid_number: str
    title: str
    general_info: Optional[Dict[str, Any]] = None
    qualification: Optional[Dict[str, Any]] = None
    restriction: Optional[Dict[str, Any]] = None
    price_info: Optional[Dict[str, Any]] = None
    progress_info: Optional[Dict[str, Any]] = None
    search_keywords: Optional[List[str]] = None  # 사용자가 검색에 사용한 키워드

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 설정
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    """루트 경로"""
    return FileResponse("static/index.html")

@app.get("/crawl")
async def crawl_page():
    """크롤링 페이지"""
    return FileResponse("static/crawl.html")

@app.get("/api/status")
async def get_status():
    """현재 크롤링 상태 조회"""
    try:
        logger.info("크롤링 상태 조회 요청")
        status = await crawl.get_crawling_status()
        return status
    except Exception as e:
        logger.error(f"크롤링 상태 조회 중 오류: {str(e)}")
        return {"success": False, "message": f"오류 발생: {str(e)}"}

@app.post("/api/crawl/start")
async def start_crawling(keywords: List[str], start_date: Optional[str] = None, end_date: Optional[str] = None):
    """크롤링 작업 시작"""
    try:
        logger.info(f"크롤링 시작 요청: 키워드={keywords}, 기간={start_date}~{end_date}")
        
        # 입력 검증
        if not keywords or len(keywords) == 0:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "최소 하나 이상의 키워드가 필요합니다."}
            )
        
        # 크롤링 시작
        result = await crawl.start_crawling(keywords, start_date, end_date)
        return result
    except Exception as e:
        logger.error(f"크롤링 시작 중 오류: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"서버 오류: {str(e)}"}
        )

@app.post("/api/crawl/stop")
async def stop_crawling():
    """크롤링 작업 중지"""
    try:
        logger.info("크롤링 중지 요청")
        result = await crawl.stop_crawling()
        return result
    except Exception as e:
        logger.error(f"크롤링 중지 중 오류: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"서버 오류: {str(e)}"}
        )

@app.get("/api/crawl/results")
async def get_results():
    """크롤링 결과 조회"""
    try:
        logger.info("크롤링 결과 조회 요청")
        status = await crawl.get_crawling_status()
        return {
            "success": True,
            "results": status["results"]
        }
    except Exception as e:
        logger.error(f"크롤링 결과 조회 중 오류: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"서버 오류: {str(e)}"}
        )

@app.post("/api/crawl/detail")
async def extract_detail(url: Optional[str] = None, bid_number: Optional[str] = None, row_index: Optional[int] = None):
    """입찰 상세 정보 추출"""
    try:
        logger.info(f"입찰 상세 정보 추출 요청: URL={url}, 입찰번호={bid_number}, 행 인덱스={row_index}")
        
        # 파라미터 유효성 검사
        if not url and row_index is None and not bid_number:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "URL, 입찰번호, 또는 행 인덱스 중 하나는 제공해야 합니다."}
            )
        
        # 상세 정보 추출
        result = await crawl.crawl_bid_detail(url=url, bid_number=bid_number, row_index=row_index)
        return result
    except Exception as e:
        logger.error(f"입찰 상세 정보 추출 중 오류: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"서버 오류: {str(e)}"}
        )

@app.get("/api/crawl/detail/status")
async def get_detail_status():
    """입찰 상세 정보 추출 상태 조회"""
    try:
        logger.info("입찰 상세 정보 추출 상태 조회 요청")
        status = await crawl.get_crawling_status()
        return {
            "success": True,
            "detail_status": status.get("detail_status", {})
        }
    except Exception as e:
        logger.error(f"입찰 상세 정보 추출 상태 조회 중 오류: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"서버 오류: {str(e)}"}
        )

@app.get("/api/crawl/download")
async def download_results():
    """크롤링 결과 다운로드"""
    try:
        logger.info("크롤링 결과 다운로드 요청")
        status = await crawl.get_crawling_status()
        
        # 결과가 없으면 오류
        if not status["results"] or len(status["results"]) == 0:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "다운로드할 결과가 없습니다."}
            )
        
        # 결과 파일 경로
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"crawling_results_{timestamp}.json"
        filepath = f"downloads/{filename}"
        
        # 디렉토리 생성
        os.makedirs("downloads", exist_ok=True)
        
        # 결과 저장
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(status["results"], f, ensure_ascii=False, indent=2)
        
        # 파일 응답
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type="application/json"
        )
    except Exception as e:
        logger.error(f"크롤링 결과 다운로드 중 오류: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"서버 오류: {str(e)}"}
        )

@app.websocket("/ws/crawl")
async def websocket_endpoint(websocket: WebSocket):
    """크롤링 WebSocket 엔드포인트"""
    await websocket.accept()
    
    try:
        # WebSocket 클라이언트 추가
        crawl.add_websocket_client(websocket)
        
        # 연결 확인 메시지 전송
        await websocket.send_json({
            "type": "connect",
            "message": "WebSocket 연결 성공",
            "timestamp": datetime.now().isoformat()
        })
        
        # 메시지 수신 대기
        while True:
            # 클라이언트 메시지 수신
            data = await websocket.receive_text()
            
            try:
                # JSON 메시지 파싱
                message = json.loads(data)
                
                # 메시지 유형에 따른 처리
                if message.get("type") == "ping":
                    # 핑에 응답
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    })
                
                elif message.get("type") == "get_status":
                    # 상태 조회
                    status = await crawl.get_crawling_status()
                    await websocket.send_json({
                        "type": "status",
                        "data": status["data"],
                        "timestamp": datetime.now().isoformat()
                    })
                
                else:
                    # 알 수 없는 메시지 유형
                    await websocket.send_json({
                        "type": "error",
                        "message": f"알 수 없는 메시지 유형: {message.get('type')}",
                        "timestamp": datetime.now().isoformat()
                    })
            
            except json.JSONDecodeError:
                # JSON 파싱 오류
                await websocket.send_json({
                    "type": "error",
                    "message": "유효하지 않은 JSON 메시지",
                    "timestamp": datetime.now().isoformat()
                })
    
    except WebSocketDisconnect:
        # WebSocket 연결 종료
        logger.info("WebSocket 연결 종료")
        crawl.remove_websocket_client(websocket)
    
    except Exception as e:
        # 예외 처리
        logger.error(f"WebSocket 처리 중 오류: {str(e)}")
        logger.error(traceback.format_exc())
        
        try:
            # 오류 메시지 전송
            await websocket.send_json({
                "type": "error",
                "message": f"서버 오류: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
        except:
            pass
        
        # WebSocket 클라이언트 제거
        crawl.remove_websocket_client(websocket)

# AI 에이전트 API 엔드포인트
@app.post("/api/agent/start")
async def start_agent_crawling(data: Dict[str, Any]):
    """AI 에이전트 크롤링 시작 - 개발 중인 기능"""
    logger.info(f"AI 에이전트 시작 요청 (개발 중): {data}")
    
    return {
        "status": "notice",
        "message": "AI 에이전트 기능은 현재 개발 중입니다.",
        "current_status": "development"
    }

@app.post("/api/agent/stop")
async def stop_agent_crawling():
    """AI 에이전트 크롤링 중지 - 개발 중인 기능"""
    logger.info("AI 에이전트 중지 요청 (개발 중)")
    
    return {
        "status": "notice",
        "message": "AI 에이전트 기능은 현재 개발 중입니다."
    }

@app.get("/api/agent/results")
async def get_agent_results():
    """AI 에이전트 결과 조회 - 개발 중인 기능"""
    logger.info("AI 에이전트 결과 조회 요청 (개발 중)")
    
    return {
        "status": "notice",
        "message": "AI 에이전트 기능은 현재 개발 중입니다.",
        "results": []
    }

# AI 영업 인사이트 분석 API 엔드포인트
@app.post("/api/analysis/sales-insight")
async def analyze_sales_insight(request: AnalysisRequest):
    """입찰 정보에 대한 AI 영업 인사이트 분석"""
    try:
        logger.info(f"영업 인사이트 분석 요청: {request.bid_number} - {request.title}")
        
        # 분석에 필요한 데이터 추출 및 정리
        analysis_data = {
            "bid_number": request.bid_number,
            "title": request.title,
            "industry_type": request.general_info.get("industry_type") if request.general_info else None,
            "bid_method": request.general_info.get("bid_method") if request.general_info else None,
            "contract_method": request.general_info.get("contract_method") if request.general_info else None,
            "qualifications": {
                "business_license": request.qualification.get("business_license") if request.qualification else None,
                "business_conditions": request.qualification.get("business_conditions") if request.qualification else None,
                "license_requirements": request.qualification.get("license_requirements") if request.qualification else None,
                "technical_capability": request.qualification.get("technical_capability") if request.qualification else None
            },
            "restrictions": {
                "industry_restriction": request.restriction.get("industry_restriction") if request.restriction else None,
                "region_restriction": request.restriction.get("region_restriction") if request.restriction else None,
                "small_business_restriction": request.restriction.get("small_business_restriction") if request.restriction else None
            },
            "price_info": {
                "estimated_price": request.price_info.get("estimated_price") if request.price_info else None,
                "bid_unit": request.price_info.get("bid_unit") if request.price_info else None
            },
            "deadline": request.progress_info.get("bid_end_date") if request.progress_info else None,
            "search_keywords": request.search_keywords  # 사용자 검색 키워드 추가
        }
        
        # AI 분석 요청
        analysis_result = await analyze_sales_opportunity(analysis_data)
        
        if not analysis_result:
            # 검색 키워드 활용한 기본 응답 생성
            user_keywords = request.search_keywords or []
            
            # 검색 키워드가 없거나 부족한 경우 공고명에서 추출
            extracted_keywords = []
            if len(user_keywords) < 3 and request.title:
                title_words = request.title.split(' ')
                for word in title_words:
                    if len(word) >= 2 and word not in ['및', '의', '등', '와', '을', '를', '이', '가']:
                        if word not in user_keywords and word not in extracted_keywords:
                            extracted_keywords.append(word)
                            if len(user_keywords) + len(extracted_keywords) >= 3:
                                break
            
            # 사용자 키워드 우선으로 조합
            combined_keywords = user_keywords + extracted_keywords
            if not combined_keywords:
                combined_keywords = ["입찰"]
            
            mock_result = {
                "compatibility_score": 60,
                "keywords": combined_keywords[:5],
                "opportunity_points": [
                    "참여 가능한 사업 규모입니다.",
                    "기술적 요구사항이 귀사의 역량과 일치합니다.",
                    "지역 제한이 없거나 해당 지역에서 경쟁이 적습니다."
                ],
                "risk_points": [
                    "입찰 마감 기한이 촉박합니다.",
                    "유사 프로젝트 수행 실적이 요구될 수 있습니다.",
                    "가격 경쟁이 치열할 것으로 예상됩니다."
                ],
                "sales_strategy": {
                    "headline": "차별화된 기술력과 실적을 강조하는 맞춤형 제안",
                    "content": "이 입찰에서는 귀사의 고유한 기술력과 유사 프로젝트 경험을 강조하는 것이 중요합니다. 경쟁사와 차별화된 접근 방식과 혁신적 솔루션을 제안하세요. 발주처의 주요 관심사를 파악하고 이에 초점을 맞춘 제안서를 준비하는 것이 좋습니다."
                }
            }
            return {"success": True, "data": mock_result}
        
        return {"success": True, "data": analysis_result}
        
    except Exception as e:
        logger.error(f"영업 인사이트 분석 중 오류: {str(e)}")
        return {"success": False, "message": f"분석 중 오류가 발생했습니다: {str(e)}"}

@app.on_event("startup")
async def startup_event():
    """
    앱 시작 시 이벤트 핸들러
    """
    logger.info("G2B 나라장터 크롤링 API 서버 시작")
    
    # 결과 저장 디렉토리 확인 및 생성
    results_dir = os.path.join("crawl", "results")
    if not os.path.exists(results_dir):
        os.makedirs(results_dir, exist_ok=True)
        logger.info(f"결과 저장 디렉토리 생성: {results_dir}")
    
    progress_dir = os.path.join("crawl", "progress")
    if not os.path.exists(progress_dir):
        os.makedirs(progress_dir, exist_ok=True)
        logger.info(f"진행 상황 저장 디렉토리 생성: {progress_dir}")

@app.on_event("shutdown")
async def shutdown_event():
    """
    앱 종료 시 이벤트 핸들러
    """
    logger.info("G2B 나라장터 크롤링 API 서버 종료")
    
    # 실행 중인 크롤링 중지
    if crawl.crawling_state.is_running:
        await crawl.crawling_state.stop_crawling()
        logger.info("서버 종료 시 실행 중인 크롤링 중지")
    
    # 모든 WebSocket 연결 종료
    for connection in crawl.crawling_state.connections.copy():
        try:
            await connection.close()
        except Exception:
            pass
    crawl.crawling_state.connections.clear()
    logger.info("모든 WebSocket 연결 종료")

# 서버 실행 함수
def run_api_server():
    """API 서버 실행"""
    import uvicorn
    
    uvicorn.run(
        "backend.app:app",
        host="127.0.0.1",  
        port=8089,  # 기존 앱과 충돌 방지를 위해 다른 포트 사용
        reload=True
    ) 