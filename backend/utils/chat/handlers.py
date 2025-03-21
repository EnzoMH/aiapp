from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect
from typing import Dict, Any
import logging
from uuid import UUID
from .models import AIModel
import traceback

# 로깅 설정
logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self, chat_manager: 'ChatManager'):
        self.chat_manager = chat_manager
    
    async def process_message(self, websocket: WebSocket, user_id: str, session_id: str, message_data: Dict[str, Any]) -> None:
        """웹소켓에서 받은 첫 메시지 처리"""
        try:
            content = message_data.get("content", "")
            model_name = message_data.get("model", "meta")
            
            # 메시지 처리 시작 알림
            await websocket.send_json({
                "type": "processing",
                "data": {"session_id": session_id}
            })
            
            # ChatManager를 통해 메시지 처리
            response = await self.chat_manager.process_message(
                user_id=user_id,
                content=content,
                session_id=session_id,
                model=model_name
            )
            
            # 응답 완료 알림
            await websocket.send_json({
                "type": "message_complete",
                "data": response
            })
            
        except Exception as e:
            logger.error(f"Error processing first message: {str(e)}")
            logger.error(traceback.format_exc())
            await websocket.send_json({
                "type": "error",
                "data": {"message": "첫 메시지 처리 중 오류가 발생했습니다"}
            })
    
    async def handle_message(self, websocket: WebSocket, user_id: str, session_id: str = None) -> None:
        """웹소켓 메시지 처리"""
        try:
            while True:
                # 메시지 수신
                data = await websocket.receive_json()
                logger.debug(f"Received message from {user_id}: {data}")
                
                # 메시지 유형 확인
                message_type = data.get("type", "message")
                
                if message_type == "message":
                    # 채팅 메시지 처리
                    content = data.get("content", "")
                    # 파라미터로 받은 session_id가 있으면 우선 사용, 없으면 메시지에서 가져오기
                    current_session_id = data.get("session_id", session_id)
                    model_name = data.get("model", AIModel.CLAUDE)
                    
                    # session_id가 있을 경우에만 문자열 변환
                    if current_session_id:
                        current_session_id = str(current_session_id)
                    
                    # 모델 유효성 검사
                    try:
                        model = AIModel(model_name)
                    except ValueError:
                        logger.warning(f"Invalid model name: {model_name}, using default")
                        model = AIModel.CLAUDE
                    
                    # 메시지 처리 시작 알림
                    await websocket.send_json({
                        "type": "processing",
                        "data": {"session_id": current_session_id}
                    })
                    
                    # 메시지 처리 및 응답 생성
                    response = await self.chat_manager.process_message(
                        user_id=user_id,
                        content=content,
                        session_id=current_session_id,
                        model=model
                    )
                    
                    # UUID 객체를 문자열로 변환
                    if isinstance(response.get("session_id"), UUID):
                        response["session_id"] = str(response["session_id"])
                    
                    # 응답 완료 알림
                    await websocket.send_json({
                        "type": "message_complete",
                        "data": response
                    })
                    
                elif message_type == "get_sessions":
                    # 사용자 세션 목록 요청 처리
                    sessions = await self.chat_manager.get_user_sessions(user_id)
                    await websocket.send_json({
                        "type": "sessions",
                        "data": {"sessions": sessions}
                    })
                    
                elif message_type == "change_model":
                    # 모델 변경 요청 처리
                    current_session_id = data.get("session_id", session_id)
                    model_name = data.get("model")
                    
                    if current_session_id and model_name:
                        try:
                            session = self.chat_manager.get_or_create_session(user_id, current_session_id)
                            model = AIModel(model_name)
                            session.model = model
                            
                            await websocket.send_json({
                                "type": "model_changed",
                                "data": {
                                    "session_id": str(current_session_id),
                                    "model": model.value
                                }
                            })
                        except ValueError as e:
                            logger.error(f"Model change error: {str(e)}")
                            await websocket.send_json({
                                "type": "error",
                                "data": {"message": "유효하지 않은 모델명"}
                            })
                            
                elif message_type == "reasoning_request":
                    # 추론 모드로 메시지 처리
                    content = data.get("content", "")
                    current_session_id = data.get("session_id", session_id)
                    model_name = data.get("model", AIModel.CLAUDE)
                    
                    if current_session_id:
                        current_session_id = str(current_session_id)
                    
                    try:
                        model = AIModel(model_name)
                    except ValueError:
                        model = AIModel.CLAUDE
                    
                    await websocket.send_json({
                        "type": "processing",
                        "data": {
                            "session_id": current_session_id,
                            "reasoning_mode": True
                        }
                    })
                    
                    response = await self.chat_manager.process_message_with_reasoning(
                        user_id=user_id,
                        content=content,
                        session_id=current_session_id,
                        model=model
                    )
                    
                    # UUID 객체를 문자열로 변환
                    if isinstance(response.get("session_id"), UUID):
                        response["session_id"] = str(response["session_id"])
                    
                    await websocket.send_json({
                        "type": "message_complete",
                        "data": response
                    })
                
                else:
                    # 알 수 없는 메시지 유형
                    logger.warning(f"Unknown message type: {message_type}")
                    await websocket.send_json({
                        "type": "error",
                        "data": {"message": "알 수 없는 메시지 유형"}
                    })
                    
        except WebSocketDisconnect:
            # 연결 해제 처리
            logger.info(f"WebSocket disconnected for user: {user_id}")
            self.chat_manager.disconnect_client(user_id)
            
        except Exception as e:
            # 오류 처리
            logger.error(f"Message handling error for user {user_id}: {str(e)}")
            logger.error(traceback.format_exc())
            try:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "서버 내부 오류가 발생했습니다"}
                })
            except:
                logger.error("Failed to send error message to client")
            finally:
                self.chat_manager.disconnect_client(user_id)