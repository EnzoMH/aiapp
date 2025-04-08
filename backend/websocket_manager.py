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

# 로깅 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

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
    
    def __init__(self, chat_manager, message_handler, login_utils, session_getter):
        """
        채팅 웹소켓 엔드포인트 초기화
        
        Args:
            chat_manager: 채팅 관리자
            message_handler: 메시지 처리기
            login_utils: 로그인 유틸리티
            session_getter: 데이터베이스 세션 생성 함수
        """
        super().__init__("/chat", "채팅")
        self.chat_manager = chat_manager
        self.message_handler = message_handler
        self.login_utils = login_utils
        self.session_getter = session_getter
    
    async def connect(self, websocket: WebSocket, token: Optional[str] = None) -> bool:
        """
        클라이언트 연결 처리 (토큰 인증 포함)
        
        Args:
            websocket: 웹소켓 연결 객체
            token: 인증 토큰 (선택)
            
        Returns:
            bool: 연결 성공 여부
        """
        # 사용자 인증 처리
        user_id = "anonymous_user"
        
        if token:
            try:
                # 직접 데이터베이스 세션 생성
                db = self.session_getter()
                try:
                    user = await self.login_utils.verify_user(token, db)
                    user_id = user["id"]
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"웹소켓 인증 실패: {str(e)}")
                await websocket.close(code=1008, reason="인증 실패")
                return False
        
        # 웹소켓 연결 수락
        await websocket.accept()
        self.active_connections.append(websocket)
        
        # 채팅 매니저에 연결 - accept()를 호출하지 않는 방식으로 수정해야 함
        # 기존 코드: await self.chat_manager.connect_client(websocket, user_id)
        # 수정된 코드: 
        self.chat_manager.connected_clients[user_id] = websocket
        logger.info(f"채팅 웹소켓 연결 성공 - 사용자: {user_id}")
        
        return True
    
    def disconnect(self, websocket: WebSocket) -> None:
        """
        클라이언트 연결 해제 처리
        
        Args:
            websocket: 웹소켓 연결 객체
        """
        super().disconnect(websocket)
        
        # 채팅 매니저에서 클라이언트 연결 해제
        # 여기서는 사용자 ID를 알 수 없어서 별도 처리 어려움
        # 채팅 매니저 내부에서 처리함
    
    async def handle_client(self, websocket: WebSocket, token: Optional[str] = None) -> None:
        """
        클라이언트 연결 후 메시지 처리
        
        Args:
            websocket: 웹소켓 연결 객체
            token: 인증 토큰 (선택)
        """
        # 연결 처리 (인증 포함)
        if not await self.connect(websocket, token):
            return
        
        try:
            # 사용자 ID 추출 (재인증)
            user_id = "anonymous_user"
            if token:
                try:
                    db = self.session_getter()
                    try:
                        user = await self.login_utils.verify_user(token, db)
                        user_id = user["id"]
                    finally:
                        db.close()
                except:
                    pass
            
            # 연결 성공 메시지
            await websocket.send_json({
                "type": "connection_established",
                "data": {"user_id": user_id}
            })
            
            # 메시지 처리 핸들러에 위임
            await self.message_handler.handle_message(websocket, user_id)
                
        except WebSocketDisconnect:
            logger.info(f"채팅 웹소켓 연결 해제 - 사용자: {user_id}")
        except Exception as e:
            logger.error(f"채팅 웹소켓 처리 오류: {str(e)}")
            logger.debug(traceback.format_exc())
        finally:
            # 채팅 관리자에서 클라이언트 연결 해제
            self.chat_manager.disconnect_client(user_id)
            self.disconnect(websocket)

class CrawlWebSocketEndpoint(WebSocketEndpoint):
    """크롤링 웹소켓 엔드포인트"""
    
    def __init__(self, crawling_state):
        """
        크롤링 웹소켓 엔드포인트 초기화
        
        Args:
            crawling_state: 크롤링 상태 객체
        """
        super().__init__("/ws", "크롤링")
        self.crawling_state = crawling_state
    
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
                "message": "AI 에이전트 WebSocket 연결이 설정되었습니다."
            })
            
            # AI 에이전트 기능 사용 불가 메시지
            await websocket.send_json({
                "type": "notice",
                "message": "AI 에이전트 기능은 현재 개발 중입니다."
            })
            
            # 연결 유지 및 메시지 수신 대기
            while True:
                data = await websocket.receive_text()
                logger.debug(f"AI 에이전트 메시지 수신 (무시됨): {data[:100]}")
                
        except WebSocketDisconnect:
            logger.info(f"AI 에이전트 웹소켓 연결 해제")
        except Exception as e:
            logger.error(f"AI 에이전트 웹소켓 처리 오류: {str(e)}")
            logger.debug(traceback.format_exc())
        finally:
            self.disconnect(websocket)

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