"""
웹소켓 관리자 모듈

이 모듈은 크롤링 상태를 클라이언트에게 실시간으로 전송하는 기능을 제공합니다.
"""

import json
import asyncio
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime

# 내부 모듈
from ..utils.logger import CrawlLogger
from ..core.models import CrawlResult, WebSocketMessage

# 로거 설정
logger = CrawlLogger("websocket_manager", debug=True)


class WebSocketManager:
    """웹소켓 관리자 클래스"""
    
    def __init__(self, websocket=None):
        """
        웹소켓 관리자 초기화
        
        Args:
            websocket: FastAPI WebSocket 객체
        """
        self.websocket = websocket
        self.clients = []
        self.is_connected = False
        self.should_stop = False
    
    async def connect(self, websocket):
        """
        웹소켓 연결 설정
        
        Args:
            websocket: FastAPI WebSocket 객체
        """
        try:
            self.websocket = websocket
            self.is_connected = True
            self.should_stop = False
            logger.info("클라이언트가 웹소켓에 연결됨")
            return True
        except Exception as e:
            logger.error(f"웹소켓 연결 중 오류: {str(e)}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """웹소켓 연결 종료"""
        try:
            self.is_connected = False
            self.should_stop = True
            logger.info("웹소켓 연결 종료")
        except Exception as e:
            logger.error(f"웹소켓 연결 종료 중 오류: {str(e)}")
    
    async def send_message(self, message_type: str, data: Dict[str, Any]):
        """
        메시지 전송
        
        Args:
            message_type: 메시지 유형
            data: 메시지 데이터
        
        Returns:
            전송 성공 여부
        """
        if not self.is_connected or not self.websocket:
            return False
        
        try:
            # 메시지 객체 생성
            message = WebSocketMessage(
                type=message_type,
                data=data,
                timestamp=datetime.now()
            )
            
            # JSON으로 변환
            message_json = json.dumps({
                "type": message.type,
                "data": message.data,
                "timestamp": message.timestamp.isoformat()
            })
            
            # 메시지 전송
            await self.websocket.send_text(message_json)
            return True
        
        except Exception as e:
            logger.error(f"웹소켓 메시지 전송 중 오류: {str(e)}")
            self.is_connected = False
            return False
    
    async def send_status_update(self, result: CrawlResult):
        """
        크롤링 상태 업데이트 전송
        
        Args:
            result: 크롤링 결과 객체
        
        Returns:
            전송 성공 여부
        """
        # 결과를 딕셔너리로 변환
        result_dict = result.to_dict()
        
        # 최근 상태 메시지 추가
        recent_status = None
        if result.agent_status and len(result.agent_status) > 0:
            latest_status = result.agent_status[-1]
            recent_status = {
                "message": latest_status.message,
                "level": latest_status.level.value,
                "timestamp": latest_status.timestamp.isoformat()
            }
        
        result_dict["recent_status"] = recent_status
        
        # 상태 업데이트 전송
        return await self.send_message("status_update", result_dict)
    
    async def send_error(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        오류 메시지 전송
        
        Args:
            message: 오류 메시지
            details: 오류 세부 정보
        
        Returns:
            전송 성공 여부
        """
        error_data = {
            "message": message,
            "details": details or {}
        }
        
        return await self.send_message("error", error_data)
    
    async def send_completion(self, result: CrawlResult):
        """
        크롤링 완료 메시지 전송
        
        Args:
            result: 크롤링 결과 객체
        
        Returns:
            전송 성공 여부
        """
        # 기본 결과 정보
        result_dict = result.to_dict()
        
        # 요약 정보 추가
        summary = {
            "total_keywords": result.progress.total_keywords,
            "processed_keywords": result.progress.processed_keywords,
            "total_items": len(result.items),
            "duration_seconds": (result.end_time - result.start_time).total_seconds() if result.end_time and result.start_time else 0,
            "status": result.status.value
        }
        
        result_dict["summary"] = summary
        
        return await self.send_message("completion", result_dict)
    
    async def receive_command(self) -> Optional[Dict[str, Any]]:
        """
        클라이언트로부터 명령 수신
        
        Returns:
            수신된 명령 또는 None
        """
        if not self.is_connected or not self.websocket:
            return None
        
        try:
            # 메시지 수신
            message_text = await self.websocket.receive_text()
            
            # JSON 파싱
            message_data = json.loads(message_text)
            
            logger.info(f"클라이언트로부터 명령 수신: {message_data['type'] if 'type' in message_data else 'unknown'}")
            
            return message_data
        
        except Exception as e:
            logger.error(f"웹소켓 명령 수신 중 오류: {str(e)}")
            return None
    
    async def listen_for_commands(self, command_handlers: Dict[str, Callable]):
        """
        명령 수신 리스너 시작
        
        Args:
            command_handlers: 명령 유형별 핸들러 함수 딕셔너리
        """
        if not self.is_connected or not self.websocket:
            return
        
        self.should_stop = False
        
        try:
            while not self.should_stop and self.is_connected:
                # 명령 수신
                command = await self.receive_command()
                
                if not command or "type" not in command:
                    continue
                
                # 명령 처리
                command_type = command["type"]
                data = command.get("data", {})
                
                if command_type in command_handlers:
                    # 핸들러 함수 호출
                    await command_handlers[command_type](data)
                else:
                    logger.warning(f"처리되지 않은 명령 유형: {command_type}")
        
        except Exception as e:
            logger.error(f"명령 리스너 실행 중 오류: {str(e)}")
            self.is_connected = False 