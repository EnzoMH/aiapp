# 메시지 처리 핸들러
from typing import Dict, Any, TYPE_CHECKING
from fastapi import WebSocket, WebSocketDisconnect
import logging


# 로깅 설정
logger = logging.getLogger(__name__)

# 타입 체크용 임포트
if TYPE_CHECKING:
    from backend.chat import ChatManager

# 실제 사용할 임포트
from backend.utils.chat.ai_models import AIModel

# 메시지 처리기
# 메시지 처리기
class MessageHandler:
    def __init__(self, chat_manager: 'ChatManager'):
        self.chat_manager = chat_manager
    
    async def handle_message(self, websocket: WebSocket, user_id: str) -> None:
        """웹소켓 메시지 처리"""
        try:
            while True:
                # 메시지 수신
                data = await websocket.receive_json()
                
                # 메시지 유형 확인
                message_type = data.get("type", "message")
                
                if message_type == "message":
                    # 채팅 메시지 처리
                    content = data.get("content", "")
                    session_id = data.get("session_id")
                    model_name = data.get("model", AIModel.CLAUDE)
                    
                    # 모델 유효성 검사
                    try:
                        model = AIModel(model_name)
                    except ValueError:
                        model = AIModel.CLAUDE
                    
                    # 메시지 처리 시작 알림
                    await websocket.send_json({
                        "type": "processing",
                        "data": {"session_id": session_id}
                    })
                    
                    # 메시지 처리 및 응답 생성
                    response = await self.chat_manager.process_message(
                        user_id=user_id,
                        content=content,
                        session_id=session_id,
                        model=model
                    )
                    
                    # 응답 완료 알림 (명시적으로 스트리밍 완료 신호 전송)
                    await websocket.send_json({
                        "type": "message_complete",
                        "data": response
                    })
                               
                elif message_type == "get_sessions":
                    # 사용자 세션 목록 요청 처리
                    # 실제 구현에서는 DB에서 사용자의 세션 목록 조회
                    await websocket.send_json({
                        "type": "sessions",
                        "data": {"sessions": []}  # 실제 세션 목록으로 대체 필요
                    })
                    
                elif message_type == "change_model":
                    # 모델 변경 요청 처리
                    session_id = data.get("session_id")
                    model_name = data.get("model")
                    
                    if session_id and model_name:
                        session = self.chat_manager.get_or_create_session(user_id, session_id)
                        try:
                            session.model = AIModel(model_name)
                            await websocket.send_json({
                                "type": "model_changed",
                                "data": {"session_id": session_id, "model": model_name}
                            })
                        except ValueError:
                            await websocket.send_json({
                                "type": "error",
                                "data": {"message": "유효하지 않은 모델명"}
                            })
                            
                elif message_type == "reasoning_request":
                    # 추론 모드로 메시지 처리
                    content = data.get("content", "")
                    session_id = data.get("session_id")
                    model_name = data.get("model", AIModel.CLAUDE)
                    
                    try:
                        model = AIModel(model_name)
                    except ValueError:
                        model = AIModel.CLAUDE
                    
                    await websocket.send_json({
                        "type": "processing",
                        "data": {"session_id": session_id, "reasoning_mode": True}
                    })
                    
                    response = await self.chat_manager.process_message_with_reasoning(
                        user_id=user_id,
                        content=content,
                        session_id=session_id,
                        model=model
                    )
                    
                    await websocket.send_json({
                        "type": "message_complete",
                        "data": response
                    })
                
                else:
                    # 알 수 없는 메시지 유형
                    await websocket.send_json({
                        "type": "error",
                        "data": {"message": "알 수 없는 메시지 유형"}
                    })
                    
        except WebSocketDisconnect:
            # 연결 해제 처리
            self.chat_manager.disconnect_client(user_id)
        except Exception as e:
            # 오류 처리
            logger.error(f"메시지 처리 오류: {str(e)}")
            try:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "서버 내부 오류"}
                })
            except:
                pass
            self.chat_manager.disconnect_client(user_id)
            