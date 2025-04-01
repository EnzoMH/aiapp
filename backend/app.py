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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Response
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import crawl

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title="G2B 나라장터 크롤링 API",
    description="나라장터 입찰정보 크롤링 API",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 모델 정의
class KeywordList(BaseModel):
    keywords: List[str]
    headless: bool = True
    startDate: Optional[str] = None
    endDate: Optional[str] = None

@app.get("/api/status")
async def get_status():
    """
    크롤링 상태 조회 API
    
    Returns:
        Dict: 현재 크롤링 상태
    """
    try:
        logger.debug("크롤링 상태 조회 요청")
        
        result = crawl.get_crawling_status()
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.exception(f"크롤링 상태 조회 중 오류: {str(e)}")
        error_response = {
            "status": "error",
            "message": f"크롤링 상태 조회 중 오류가 발생했습니다: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
        return JSONResponse(content=error_response, status_code=500)

@app.post("/api/start")
async def start_crawling(data: KeywordList):
    """
    키워드 크롤링 시작 API
    
    Args:
        data: 검색 키워드 목록 및 옵션
    
    Returns:
        Dict: API 응답 (상태 및 메시지)
    """
    try:
        logger.info(f"크롤링 시작 요청: {len(data.keywords)}개 키워드")
        
        # 키워드 로깅
        if data.keywords:
            keywords_str = ", ".join(data.keywords[:5])
            if len(data.keywords) > 5:
                keywords_str += f" 외 {len(data.keywords) - 5}개"
            logger.info(f"검색 키워드: {keywords_str}")
        
        # 날짜 로깅
        if data.startDate or data.endDate:
            logger.info(f"검색 기간: {data.startDate or '전체'} ~ {data.endDate or '전체'}")
        
        # 크롤링 시작
        result = await crawl.start_crawling(
            keywords=data.keywords,
            headless=data.headless,
            start_date=data.startDate,
            end_date=data.endDate
        )
        
        # 상태 브로드캐스트
        await crawl.crawling_state.broadcast_status()
        
        return JSONResponse(content=result)
    
    except Exception as e:
        logger.exception(f"크롤링 시작 중 오류: {str(e)}")
        error_response = {
            "status": "error",
            "message": f"크롤링 시작 중 오류가 발생했습니다: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
        return JSONResponse(content=error_response, status_code=500)

@app.post("/api/stop")
async def stop_crawling():
    """
    크롤링 중지 API
    
    Returns:
        Dict: API 응답 (상태 및 메시지)
    """
    try:
        logger.info("크롤링 중지 요청")
        
        result = crawl.stop_crawling()
        
        # 상태 브로드캐스트
        await crawl.crawling_state.broadcast_status()
        
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.exception(f"크롤링 중지 중 오류: {str(e)}")
        error_response = {
            "status": "error",
            "message": f"크롤링 중지 중 오류가 발생했습니다: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
        return JSONResponse(content=error_response, status_code=500)

@app.get("/api/crawl-results/")
async def get_results():
    """
    크롤링 결과 조회 API
    
    Returns:
        Dict: 크롤링 결과
    """
    try:
        logger.info("크롤링 결과 조회 요청")
        
        result = crawl.get_results()
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.exception(f"크롤링 결과 조회 중 오류: {str(e)}")
        error_response = {
            "status": "error",
            "message": f"크롤링 결과 조회 중 오류가 발생했습니다: {str(e)}",
            "timestamp": datetime.now().isoformat(),
            "results": []
        }
        return JSONResponse(content=error_response, status_code=500)

@app.get("/api/results/download")
async def download_results():
    """
    최신 크롤링 결과 파일 다운로드 API
    
    Returns:
        FileResponse: 크롤링 결과 파일
    """
    try:
        logger.info("크롤링 결과 파일 다운로드 요청")
        
        # 최신 결과 파일 경로 가져오기
        latest_file = crawl.get_latest_result_file()
        
        if not latest_file or not os.path.exists(latest_file):
            error_response = {
                "status": "error",
                "message": "다운로드할 결과 파일이 없습니다.",
                "timestamp": datetime.now().isoformat()
            }
            return JSONResponse(content=error_response, status_code=404)
        
        # 파일 다운로드 응답 생성
        filename = os.path.basename(latest_file)
        return FileResponse(
            path=latest_file, 
            filename=filename,
            media_type="application/json"
        )
        
    except Exception as e:
        logger.exception(f"크롤링 결과 파일 다운로드 중 오류: {str(e)}")
        error_response = {
            "status": "error",
            "message": f"크롤링 결과 파일 다운로드 중 오류가 발생했습니다: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
        return JSONResponse(content=error_response, status_code=500)

@app.get("/api/results/file")
async def get_results_from_file(filepath: Optional[str] = None):
    """
    파일에서 크롤링 결과 로드 API
    
    Args:
        filepath: 결과 파일 경로 (없으면 최신 파일 사용)
    
    Returns:
        Dict: 크롤링 결과
    """
    try:
        logger.info(f"파일에서 크롤링 결과 로드 요청: {filepath}")
        
        # 파일 경로가 제공되지 않은 경우 최신 파일 사용
        if not filepath:
            filepath = crawl.get_latest_result_file()
            
            if not filepath:
                error_response = {
                    "status": "error",
                    "message": "로드할 결과 파일이 없습니다.",
                    "timestamp": datetime.now().isoformat(),
                    "results": []
                }
                return JSONResponse(content=error_response, status_code=404)
        
        # 파일에서 결과 로드
        result = crawl.load_crawling_results_from_file(filepath)
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.exception(f"파일에서 크롤링 결과 로드 중 오류: {str(e)}")
        error_response = {
            "status": "error",
            "message": f"파일에서 크롤링 결과 로드 중 오류가 발생했습니다: {str(e)}",
            "timestamp": datetime.now().isoformat(),
            "results": []
        }
        return JSONResponse(content=error_response, status_code=500)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 엔드포인트
    
    클라이언트의 WebSocket 연결을 처리하고 크롤링 상태 업데이트를 전송합니다.
    
    Args:
        websocket: WebSocket 연결
    """
    await websocket.accept()
    
    # 크롤링 상태 객체에 WebSocket 연결 추가
    crawl.crawling_state.add_connection(websocket)
    
    try:
        # 초기 상태 전송
        status = crawl.get_crawling_status()
        await websocket.send_json({
            "type": "crawling_status",
            "data": status,
            "timestamp": datetime.now().isoformat()
        })
        
        # 클라이언트의 메시지 수신 대기
        while True:
            data = await websocket.receive_text()
            logger.debug(f"WebSocket 메시지 수신: {data}")
            
            try:
                message = json.loads(data)
                message_type = message.get("type")
                
                # 메시지 유형에 따른 처리
                if message_type == "get_status":
                    status = crawl.get_crawling_status()
                    await websocket.send_json({
                        "type": "crawling_status",
                        "data": status,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                elif message_type == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    })
                
            except json.JSONDecodeError:
                logger.warning(f"유효하지 않은 JSON 형식의 WebSocket 메시지: {data}")
    
    except WebSocketDisconnect:
        # 연결 종료 시 목록에서 제거
        crawl.crawling_state.remove_connection(websocket)
        logger.info("WebSocket 연결 종료")
    
    except Exception as e:
        # 기타 오류 처리
        logger.exception(f"WebSocket 처리 중 오류: {str(e)}")
        crawl.crawling_state.remove_connection(websocket)

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