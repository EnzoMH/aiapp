"""
웹소켓 관리 모듈

이 모듈은 다양한 웹소켓 연결(채팅, 크롤링, AI 에이전트 등)을 관리합니다.
app.py에서 직접 관리하던 웹소켓 로직을 분리하여 관리합니다.
"""

import logging
import jwt
import traceback
from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime
import json
import base64
import uuid

# 로깅 설정
logger = logging.getLogger(__name__)

class WebSocketEndpoint:
    """웹소켓 엔드포인트 베이스 클래스"""
    
    def __init__(self, path: str, name: str):
        """
        웹소켓 엔드포인트 초기화
        
        Args:
            path: 웹소켓 경로(URL)
            name: 엔드포인트 이름(로깅용)
        """
        self.path = path
        self.name = name
        self.active_connections: List[WebSocket] = []
        logger.info(f"{name} 웹소켓 엔드포인트 초기화 - 경로: {path}")
    
    async def connect(self, websocket: WebSocket, **kwargs) -> bool:
        """
        클라이언트 연결 처리
        
        Args:
            websocket: 웹소켓 연결 객체
            **kwargs: 추가 매개변수
            
        Returns:
            bool: 연결 성공 여부
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"{self.name} 웹소켓 연결 성공 - 현재 {len(self.active_connections)}개 연결")
        return True
    
    def disconnect(self, websocket: WebSocket) -> None:
        """
        클라이언트 연결 해제 처리
        
        Args:
            websocket: 웹소켓 연결 객체
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"{self.name} 웹소켓 연결 종료 - 현재 {len(self.active_connections)}개 연결")
    
    async def broadcast(self, message: Dict[str, Any]) -> None:
        """
        모든 연결된 클라이언트에 메시지 브로드캐스트
        
        Args:
            message: 전송할 메시지
        """
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"{self.name} 브로드캐스트 중 오류: {str(e)}")
                disconnected.append(connection)
        
        # 오류가 발생한 연결 제거
        for conn in disconnected:
            self.disconnect(conn)
    
    async def handle_client(self, websocket: WebSocket, **kwargs) -> None:
        """
        클라이언트 연결 후 메시지 처리 (오버라이드 대상)
        
        Args:
            websocket: 웹소켓 연결 객체
            **kwargs: 추가 매개변수
        """
        try:
            # 연결 성공 메시지
            await websocket.send_json({
                "type": "connection_established",
                "message": f"{self.name} 웹소켓 연결이 설정되었습니다."
            })
            
            # 메시지 수신 대기 (기본 구현은 메아리)
            while True:
                data = await websocket.receive_text()
                await websocket.send_json({
                    "type": "echo",
                    "data": data
                })
                
        except WebSocketDisconnect:
            logger.info(f"{self.name} 웹소켓 연결 해제")
        except Exception as e:
            logger.error(f"{self.name} 웹소켓 처리 오류: {str(e)}")
            logger.debug(traceback.format_exc())
        finally:
            self.disconnect(websocket)

class ChatWebSocketEndpoint(WebSocketEndpoint):
    """채팅 웹소켓 엔드포인트"""
    
    def __init__(self, chat_manager, message_handler, auth_utils, db_session):
        """
        채팅 웹소켓 엔드포인트 초기화
        
        Args:
            chat_manager: 채팅 관리자
            message_handler: 메시지 처리기
            auth_utils: 인증 유틸리티
            db_session: 데이터베이스 세션 생성 함수
        """
        super().__init__("/chat", "채팅")
        self.chat_manager = chat_manager
        self.message_handler = message_handler
        self.auth_utils = auth_utils
        self.db_session = db_session
        self.active_connections: Dict[WebSocket, Dict] = {}  # 웹소켓 객체를 키로 사용
    
    async def connect(self, websocket: WebSocket, user_data=None):
        """
        클라이언트 연결 처리 (쿠키 기반 인증 포함)
        
        Args:
            websocket: 웹소켓 연결 객체
            user_data: 사용자 데이터 (선택)
            
        Returns:
            bool: 연결 성공 여부
        """
        await websocket.accept()
        
        connection_id = str(uuid.uuid4())
        
        if user_data:
            client_id = user_data.get("id")
            self.active_connections[websocket] = {
                "connection_id": connection_id,
                "user_id": client_id,
                "user_data": user_data,
                "authenticated": True,
                "connected_at": datetime.now().isoformat()
            }
            logger.info(f"인증된 사용자 연결: {client_id} (연결 ID: {connection_id})")
        else:
            self.active_connections[websocket] = {
                "connection_id": connection_id,
                "user_id": "anonymous",
                "authenticated": False,
                "connected_at": datetime.now().isoformat()
            }
            logger.info(f"익명 사용자 연결 (연결 ID: {connection_id})")
        
        # 환영 메시지 전송
        await websocket.send_json({
            "type": "connection_established",
            "data": {
                "connection_id": connection_id,
                "message": "서버에 연결되었습니다",
                "timestamp": datetime.now().isoformat()
            }
        })
        
        return True
    
    async def disconnect(self, websocket: WebSocket):
        """
        클라이언트 연결 해제 처리
        
        Args:
            websocket: 웹소켓 연결 객체
        """
        if websocket in self.active_connections:
            user_info = self.active_connections[websocket]
            user_id = user_info.get("user_id", "unknown")
            connection_id = user_info.get("connection_id", "unknown")
            logger.info(f"웹소켓 연결 종료: 사용자={user_id} (연결 ID: {connection_id})")
            del self.active_connections[websocket]
    
    def _parse_session_cookie(self, cookies_header):
        """
        쿠키 헤더에서 세션 정보 파싱

        Args:
            cookies_header: 쿠키 헤더 문자열
            
        Returns:
            Dict: 파싱된 쿠키 정보
        """
        cookies = {}
        if cookies_header:
            cookie_items = cookies_header.split("; ")
            for item in cookie_items:
                if "=" in item:
                    key, value = item.split("=", 1)
                    cookies[key] = value
        
        # 세션 쿠키 이름은 app.py의 SessionMiddleware 설정과 일치해야 함
        session_data = cookies.get("user_session")
        
        if session_data:
            try:
                # URL 디코딩 및 base64 디코딩 시도 (세션 형식에 따라 다를 수 있음)
                session_data = session_data.replace("%3D", "=")
                session_data = base64.b64decode(session_data).decode('utf-8')
                logger.debug(f"세션 쿠키 디코딩: {session_data[:30]}...")
            except Exception as e:
                logger.debug(f"세션 쿠키 디코딩 실패: {str(e)}")
        
        return {
            "cookies": cookies,
            "session": session_data
        }
    
    async def handle_client(self, websocket: WebSocket, token=None):
        """
        클라이언트 연결 후 메시지 처리
        
        Args:
            websocket: 웹소켓 연결 객체
            token: 인증 토큰 (선택, 이제 사용하지 않음)
        """
        try:
            # 세션에서 사용자 정보 확인 (쿠키 기반)
            user_data = None
            db = self.db_session()
            
            # 쿠키를 통해 세션에서 사용자 ID 얻기 시도
            try:
                # WebSocket에서 쿠키 추출
                cookies_header = websocket.headers.get("cookie", "")
                cookie_info = self._parse_session_cookie(cookies_header)
                
                logger.debug(f"WebSocket 연결 쿠키: {list(cookie_info['cookies'].keys()) if cookie_info['cookies'] else '없음'}")
                
                session_cookie = cookie_info['cookies'].get("user_session")
                if session_cookie:
                    # 세션 쿠키가 있으면 로그
                    connection_id = str(uuid.uuid4())
                    logger.debug(f"WebSocket 세션 쿠키 발견 (연결 ID: {connection_id})")
                    
                    # 여기서는 세션에서 직접 사용자 ID를 가져올 수 없으므로
                    # 클라이언트의 init 메시지 대기 (이후에 처리)
                    
                # 기본 연결 진행 (인증은 init 메시지에서 처리)
                await self.connect(websocket, user_data)
            except Exception as e:
                logger.error(f"세션 확인 중 오류: {str(e)}")
                logger.error(traceback.format_exc())
                await self.connect(websocket)  # 인증 없이 기본 연결
            
            try:
                # 연결 성공 후 클라이언트에게 초기화 메시지 요청
                connection_info = self.active_connections.get(websocket, {})
                connection_id = connection_info.get("connection_id", "unknown")
                
                await websocket.send_json({
                    "type": "connection_established",
                    "data": {
                        "connection_id": connection_id,
                        "message": "서버에 연결되었습니다",
                        "requires_auth": True,  # 인증 필요함을 알림
                        "timestamp": datetime.now().isoformat()
                    }
                })
                
                while True:
                    # 메시지 수신
                    data = await websocket.receive_json()
                    message_type = data.get("type", "unknown")
                    logger.debug(f"메시지 수신 [{connection_id}] [{message_type}]: {json.dumps(data, ensure_ascii=False)[:100] if isinstance(data, dict) else str(data)[:100]}")
                    
                    # init 메시지면 사용자 정보 설정 (세션 쿠키로 인증되지 않은 경우)
                    if message_type == "init" and not connection_info.get("authenticated", False):
                        user_id = data.get("user_id")
                        if user_id:
                            # 로컬 스토리지에서 받은 사용자 ID 검증
                            try:
                                user = self.auth_utils.get_user_by_id(db, user_id)
                                if user:
                                    connection_info = self.active_connections.get(websocket, {})
                                    connection_info["user_id"] = user_id
                                    connection_info["user_role"] = data.get("user_role", "user")
                                    connection_info["authenticated"] = True
                                    self.active_connections[websocket] = connection_info
                                    logger.info(f"사용자 ID {user_id} 인증 성공 (연결 ID: {connection_id})")
                                    
                                    # 인증 성공 응답
                                    await websocket.send_json({
                                        "type": "auth_success",
                                        "data": {
                                            "connection_id": connection_id,
                                            "user_id": user_id,
                                            "timestamp": datetime.now().isoformat()
                                        }
                                    })
                                else:
                                    logger.warning(f"사용자 ID 검증 실패: {user_id} (연결 ID: {connection_id})")
                                    await websocket.send_json({
                                        "type": "auth_error",
                                        "data": {
                                            "connection_id": connection_id,
                                            "message": "인증이 필요합니다",
                                            "timestamp": datetime.now().isoformat()
                                        }
                                    })
                            except Exception as e:
                                logger.error(f"사용자 검증 중 오류: {str(e)} (연결 ID: {connection_id})")
                                await websocket.send_json({
                                    "type": "auth_error",
                                    "data": {
                                        "connection_id": connection_id,
                                        "message": "인증 처리 중 오류가 발생했습니다",
                                        "timestamp": datetime.now().isoformat()
                                    }
                                })
                        else:
                            # 익명 사용자로 연결 유지
                            logger.info(f"익명 사용자 연결 유지 (연결 ID: {connection_id})")
                        continue
                    
                    # 메시지 처리 및 응답
                    await self.message_handler.handle_message(websocket, data)
            except WebSocketDisconnect:
                connection_info = self.active_connections.get(websocket, {})
                connection_id = connection_info.get("connection_id", "unknown")
                logger.info(f"WebSocket 연결 종료: 클라이언트={websocket.client.host} (연결 ID: {connection_id})")
            except Exception as e:
                connection_info = self.active_connections.get(websocket, {})
                connection_id = connection_info.get("connection_id", "unknown")
                logger.error(f"메시지 처리 중 오류: {str(e)} (연결 ID: {connection_id})")
                logger.error(traceback.format_exc())
                try:
                    await websocket.send_json({
                        "type": "error",
                        "data": {
                            "connection_id": connection_id,
                            "message": f"오류 발생: {str(e)}",
                            "timestamp": datetime.now().isoformat()
                        }
                    })
                except:
                    pass  # 이미 연결이 끊어진 경우
        except Exception as e:
            logger.error(f"웹소켓 처리 중 예외 발생: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
            await self.disconnect(websocket)

class CrawlWebSocketEndpoint(WebSocketEndpoint):
    """크롤링 웹소켓 엔드포인트"""
    
    def __init__(self, crawling_state):
        """
        크롤링 웹소켓 엔드포인트 초기화
        
        Args:
            crawling_state: 크롤링 상태 관리 객체
        """
        super().__init__("/ws", "크롤링")
        self.crawling_state = crawling_state
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket) -> bool:
        """
        클라이언트 연결 처리
        
        Args:
            websocket: 웹소켓 연결 객체
            
        Returns:
            bool: 연결 성공 여부
        """
        await super().connect(websocket)
        
        # 크롤링 상태 매니저에 연결 추가
        self.crawling_state.add_connection(websocket)
        return True
    
    def disconnect(self, websocket: WebSocket) -> None:
        """
        클라이언트 연결 해제 처리
        
        Args:
            websocket: 웹소켓 연결 객체
        """
        super().disconnect(websocket)
        
        # 크롤링 상태 매니저에서 연결 제거
        self.crawling_state.remove_connection(websocket)
    
    async def handle_client(self, websocket: WebSocket) -> None:
        """
        클라이언트 연결 후 메시지 처리
        
        Args:
            websocket: 웹소켓 연결 객체
        """
        # 연결 처리
        if not await self.connect(websocket):
            return
        
        try:
            # 연결 성공 메시지
            await websocket.send_json({
                "type": "connection_established",
                "message": "크롤링 WebSocket 연결이 설정되었습니다."
            })
            
            # 현재 상태 전송
            await self.crawling_state.broadcast_status()
            
            # 메시지 수신 대기
            while True:
                await websocket.receive_text()  # 클라이언트 메시지 수신
                
        except WebSocketDisconnect:
            logger.info(f"크롤링 웹소켓 연결 해제")
        except Exception as e:
            logger.error(f"크롤링 웹소켓 처리 오류: {str(e)}")
            logger.debug(traceback.format_exc())
        finally:
            self.disconnect(websocket)

class AgentWebSocketEndpoint(WebSocketEndpoint):
    """AI 에이전트 웹소켓 엔드포인트"""
    
    def __init__(self):
        """AI 에이전트 웹소켓 엔드포인트 초기화"""
        super().__init__("/ws/agent", "AI 에이전트")
        self.active_connections: Dict[WebSocket, Dict] = {}
    
    async def connect(self, websocket: WebSocket) -> bool:
        """
        클라이언트 연결 처리
        
        Args:
            websocket: 웹소켓 연결 객체
            
        Returns:
            bool: 연결 성공 여부
        """
        await websocket.accept()
        self.active_connections[websocket] = {
            "connected_at": datetime.now().isoformat()
        }
        logger.info(f"AI 에이전트 웹소켓 연결 수락: {websocket.client.host}")
        
        # 개발 중 메시지 전송
        await websocket.send_json({
            "type": "info",
            "data": {
                "message": "AI 에이전트 기능은 현재 개발 중입니다.",
                "status": "development",
                "timestamp": datetime.now().isoformat()
            }
        })
        
        return True
    
    async def disconnect(self, websocket: WebSocket) -> None:
        """
        클라이언트 연결 해제 처리
        
        Args:
            websocket: 웹소켓 연결 객체
        """
        if websocket in self.active_connections:
            del self.active_connections[websocket]
            logger.info(f"AI 에이전트 웹소켓 연결 종료: {websocket.client.host}")
    
    async def handle_client(self, websocket: WebSocket) -> None:
        """
        클라이언트 연결 후 메시지 처리
        
        Args:
            websocket: 웹소켓 연결 객체
        """
        await self.connect(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                logger.debug(f"AI 에이전트 메시지 수신: {data}")
                
                # 에코 응답
                response = {
                    "type": "echo",
                    "data": data,
                    "message": "개발 중인 기능입니다.",
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send_json(response)
                
        except WebSocketDisconnect:
            logger.info(f"AI 에이전트 WebSocket 연결 종료: {websocket.client.host}")
        except Exception as e:
            logger.error(f"AI 에이전트 WebSocket 처리 중 오류: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
            await self.disconnect(websocket)

class WebSocketManager:
    """웹소켓 관리 클래스"""
    
    def __init__(self):
        """웹소켓 관리자 초기화"""
        self.endpoints = {}
        logger.info("웹소켓 관리자 초기화")
    
    def register_endpoint(self, endpoint: WebSocketEndpoint) -> None:
        """
        웹소켓 엔드포인트 등록
        
        Args:
            endpoint: 등록할 웹소켓 엔드포인트
        """
        self.endpoints[endpoint.path] = endpoint
        logger.info(f"웹소켓 엔드포인트 등록: {endpoint.name} ({endpoint.path})")
    
    def get_endpoint(self, path: str) -> Optional[WebSocketEndpoint]:
        """
        경로로 웹소켓 엔드포인트 조회
        
        Args:
            path: 웹소켓 경로
            
        Returns:
            Optional[WebSocketEndpoint]: 엔드포인트 또는 None
        """
        return self.endpoints.get(path)
    
    async def broadcast_all(self, message: Dict[str, Any]) -> None:
        """
        모든 엔드포인트의 모든 연결에 메시지 브로드캐스트
        
        Args:
            message: 전송할 메시지
        """
        for endpoint in self.endpoints.values():
            await endpoint.broadcast(message)

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