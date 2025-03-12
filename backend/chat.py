from typing import List, Dict, Optional, Any
import time
import uuid
import logging
from fastapi import WebSocket
from datetime import datetime

from backend.utils.chat.models import ChatMessage, MessageRole
from backend.utils.chat.memory import MemoryManager
from backend.utils.chat.ai_models import AIModelManager, AIModel
from backend.utils.chat.handlers import MessageHandler

from backend.utils.db import SessionLocal, DBSession, Message as DBMessage

# 로깅 설정
logger = logging.getLogger(__name__)

# 채팅 세션 관리
class ChatSession:
    def __init__(self, session_id: str, user_id: str, model: AIModel = AIModel.CLAUDE):
        self.session_id = session_id
        self.user_id = user_id
        self.model = model
        self.messages: List[ChatMessage] = []
        self.created_at = time.time()
        self.last_updated = time.time()
        self.system_prompt = "당신은 도움이 되는 AI 어시스턴트입니다. 사용자의 질문에 대해 정확하고 친절하게 답변하세요."
        
        # Memory 관리자 초기화
        self.memory_manager = MemoryManager()
        
    def add_message(self, message: ChatMessage) -> None:
        """메시지 추가 및 메모리 저장"""
        self.messages.append(message)
        self.last_updated = time.time()
        
        # 메모리에 대화 내용 저장 (키워드 추출 개선)
        if message.role == MessageRole.USER:
            keywords = self._extract_keywords(message.content)
            self.memory_manager.add_memory(
                content=message.content,
                keywords=keywords
            )
        
    def _extract_keywords(self, content: str) -> List[str]:
        """메시지에서 중요 키워드 추출"""
        # 임시로 간단한 키워드 추출 로직 구현
        # 나중에 더 정교한 알고리즘으로 대체 가능
        keywords = []
        # 문장 내 주요 명사나 핵심 단어를 추출
        words = content.split()
        for word in words:
            if len(word) > 1 and not word.isspace():  # 기본적인 필터링
                keywords.append(word)
        return list(set(keywords))  # 중복 제거
        
    def get_context_window(self, max_messages: int = 20) -> List[ChatMessage]:
        """메모리 기반의 컨텍스트 윈도우 생성"""
        # 시스템 프롬프트를 시작으로
        context = [ChatMessage(MessageRole.SYSTEM, self.system_prompt)]
        
        # 모든 메시지를 시간순으로 정렬
        all_messages = sorted(self.messages, key=lambda x: x.timestamp)
        
        # 메시지가 너무 많으면 앞부분 생략
        if len(all_messages) > max_messages - 1:
            # 중요: 대화의 연속성을 위해 최근 메시지 유지
            all_messages = all_messages[-(max_messages-1):]
        
        # 컨텍스트에 메시지 추가
        context.extend(all_messages)
        
        return context
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "model": self.model,
            "messages": [msg.to_dict() for msg in self.messages],
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "system_prompt": self.system_prompt,
            "memories": self.memory_manager.export_memories()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatSession':
        session = cls(
            session_id=data["session_id"],
            user_id=data["user_id"],
            model=data["model"]
        )
        session.messages = [ChatMessage.from_dict(msg) for msg in data["messages"]]
        session.created_at = data["created_at"]
        session.last_updated = data["last_updated"]
        session.system_prompt = data.get("system_prompt", session.system_prompt)
        
        # 메모리 복원
        if "memories" in data:
            session.memory_manager.import_memories(data["memories"])
            
        return session


# 채팅 관리자
class ChatManager:
    def __init__(self):
        self.active_sessions: Dict[str, ChatSession] = {}
        self.connected_clients: Dict[str, WebSocket] = {}
        self.ai_model_manager = AIModelManager()
    
    async def connect_client(self, websocket: WebSocket, client_id: str) -> None:
        """클라이언트 연결 처리"""
        await websocket.accept()
        self.connected_clients[client_id] = websocket
    
    def disconnect_client(self, client_id: str) -> None:
        """클라이언트 연결 해제 처리"""
        if client_id in self.connected_clients:
            del self.connected_clients[client_id]
    
    def get_or_create_session(self, user_id: str, session_id: Optional[str] = None) -> ChatSession:
        """사용자 세션 가져오기 또는 생성"""
        if not session_id:
            session_id = str(uuid.uuid4())
            
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = ChatSession(session_id, user_id)
            
        return self.active_sessions[session_id]
    
    async def process_message(self, user_id: str, content: str, session_id: Optional[str] = None, 
                         model: AIModel = AIModel.CLAUDE) -> Dict[str, Any]:
        """사용자 메시지 처리 및 AI 응답 생성"""
        # 세션 ID가 없으면 사용자의 기존 세션을 찾거나 새로 생성
        if not session_id:
            # 사용자의 마지막 세션이 있는지 확인
            user_sessions = [s for s in self.active_sessions.values() if s.user_id == user_id]
            if user_sessions:
                # 가장 최근에 업데이트된 세션 사용
                session = max(user_sessions, key=lambda s: s.last_updated)
                session_id = session.session_id
                logger.info(f"사용자 {user_id}의 기존 세션 {session_id} 사용")
            else:
                # 새 세션 생성
                session_id = str(uuid.uuid4())
                logger.info(f"사용자 {user_id}의 새 세션 {session_id} 생성")
        
        # 세션 가져오기 또는 생성
        session = self.get_or_create_session(user_id, session_id)
        
        # 모델 업데이트 (필요한 경우)
        if session.model != model:
            session.model = model
        
        # 사용자 메시지 추가
        user_message = ChatMessage(MessageRole.USER, content)
        session.add_message(user_message)
        
        # 컨텍스트 윈도우 가져오기 (개선된 방식)
        context = self._get_full_context(session)
        
        # 클라이언트 웹소켓 가져오기
        websocket = self.connected_clients.get(user_id)
        
        # AI 응답 생성
        ai_response = await self.ai_model_manager.generate_response(context, model, websocket)
        
        # AI 응답 메시지 추가
        assistant_message = ChatMessage(MessageRole.ASSISTANT, ai_response)
        session.add_message(assistant_message)
        
        # 세션 저장
        self.save_session(session.session_id)
        
        # 응답 반환
        return {
            "session_id": session.session_id,
            "message": assistant_message.to_dict()
        }
        
    def _get_full_context(self, session: ChatSession) -> List[ChatMessage]:
        """전체 대화 컨텍스트 구성"""
        # 시스템 프롬프트를 시작으로
        context = [ChatMessage(MessageRole.SYSTEM, session.system_prompt)]
        
        # 모든 메시지를 시간순으로 정렬하여 추가
        messages = sorted(session.messages, key=lambda x: x.timestamp)
        
        # 토큰 제한을 고려하여 필요시 앞부분 메시지 생략 가능
        # 여기서는 간단히 모든 메시지를 포함
        context.extend(messages)
        
        return context
    

    async def send_message(self, client_id: str, message: Dict[str, Any]) -> None:
        """클라이언트에게 메시지 전송"""
        if client_id in self.connected_clients:
            await self.connected_clients[client_id].send_json(message)
    
    def save_session(self, session_id: str) -> None:
        """세션을 데이터베이스에 저장"""
        if session_id in self.active_sessions:
            chat_session = self.active_sessions[session_id]
            
            # 데이터베이스 세션 생성
            db = SessionLocal()
            try:
                # 세션 정보 조회 또는 생성
                db_session = db.query(DBSession).filter(DBSession.session_id == session_id).first()
                if not db_session:
                    # 새 세션 생성
                    db_session = DBSession(
                        session_id=session_id,
                        user_id=chat_session.user_id,
                        model=chat_session.model,
                        system_prompt=chat_session.system_prompt,
                        created_at=datetime.fromtimestamp(chat_session.created_at),
                        last_updated=datetime.fromtimestamp(chat_session.last_updated),
                        active=True
                    )
                    db.add(db_session)
                else:
                    # 기존 세션 업데이트
                    db_session.last_updated = datetime.fromtimestamp(chat_session.last_updated)
                    db_session.model = chat_session.model
                    db_session.system_prompt = chat_session.system_prompt
                
                # 메시지 저장
                for message in chat_session.messages:
                    # 이미 저장된 메시지는 건너뛰기
                    existing_message = db.query(DBMessage).filter(
                        DBMessage.message_id == message.message_id
                    ).first()
                    
                    if not existing_message:
                        db_message = DBMessage(
                            message_id=message.message_id,
                            session_id=session_id,
                            role=message.role,
                            content=message.content,
                            timestamp=datetime.fromtimestamp(message.timestamp)
                        )
                        db.add(db_message)
                
                # 변경사항 저장
                db.commit()
                logger.info(f"세션 저장 완료: {session_id}")
                
            except Exception as e:
                db.rollback()
                logger.error(f"세션 저장 오류: {str(e)}")
            finally:
                db.close()
    
    def load_session(self, session_id: str) -> Optional[ChatSession]:
        """데이터베이스에서 세션 로드"""
        # 이미 메모리에 있는 세션이면 그대로 반환
        if session_id in self.active_sessions:
            return self.active_sessions[session_id]
        
        # 데이터베이스에서 세션 로드
        db = SessionLocal()
        try:
            # 세션 정보 조회
            db_session = db.query(DBSession).filter(DBSession.session_id == session_id).first()
            if not db_session:
                return None
            
            # 세션 객체 생성
            chat_session = ChatSession(
                session_id=db_session.session_id,
                user_id=db_session.user_id,
                model=db_session.model
            )
            chat_session.system_prompt = db_session.system_prompt
            chat_session.created_at = db_session.created_at.timestamp()
            chat_session.last_updated = db_session.last_updated.timestamp()
            
            # 메시지 로드
            db_messages = db.query(DBMessage).filter(
                DBMessage.session_id == session_id
            ).order_by(DBMessage.timestamp).all()
            
            for db_message in db_messages:
                message = ChatMessage(
                    role=db_message.role,
                    content=db_message.content,
                    timestamp=db_message.timestamp.timestamp()
                )
                message.message_id = db_message.message_id
                chat_session.messages.append(message)
            
            # 메모리에 세션 저장
            self.active_sessions[session_id] = chat_session
            logger.info(f"세션 로드 완료: {session_id}")
            
            return chat_session
            
        except Exception as e:
            logger.error(f"세션 로드 오류: {str(e)}")
            return None
        finally:
            db.close()
    
    async def process_message_with_reasoning(self, user_id: str, content: str, 
                                         session_id: Optional[str] = None,
                                         model: AIModel = AIModel.CLAUDE) -> Dict[str, Any]:
        """추론 기능을 활용한 사용자 메시지 처리"""
        
        # 기존 세션 관리 로직과 동일
        session = self.get_or_create_session(user_id, session_id)
        
        # 사용자 메시지 추가
        user_message = ChatMessage(MessageRole.USER, content)
        session.add_message(user_message)
        
        # 컨텍스트 윈도우 가져오기
        context = self._get_full_context(session)
        
        # 클라이언트 웹소켓 가져오기
        websocket = self.connected_clients.get(user_id)
        
        # 복잡도 평가 (간단한 휴리스틱)
        is_complex = self._is_complex_question(content)
        
        # 복잡한 질문인 경우 추론 모드 사용
        if is_complex:
            ai_response = await self.ai_model_manager.generate_response_with_reasoning(
                context, model, websocket)
        else:
            ai_response = await self.ai_model_manager.generate_response(
                context, model, websocket)
        
        # 응답 처리 및 반환 (기존 코드와 동일)
        assistant_message = ChatMessage(MessageRole.ASSISTANT, ai_response)
        session.add_message(assistant_message)
        self.save_session(session.session_id)
        
        return {
            "session_id": session.session_id,
            "message": assistant_message.to_dict(),
            "reasoning_used": is_complex
        }

    def _is_complex_question(self, content: str) -> bool:
        """질문의 복잡성 평가 (단순 휴리스틱)"""
        # 복잡한 질문 식별을 위한 키워드
        complex_keywords = [
            "왜", "어떻게", "분석", "설명", "이유", "차이", "비교", "계산",
            "예측", "추론", "해결", "증명", "평가"
        ]
        
        # 질문 길이 기반 복잡도
        is_long = len(content) > 100
        
        # 키워드 기반 복잡도
        has_complex_keywords = any(keyword in content for keyword in complex_keywords)
        
        return is_long or has_complex_keywords
