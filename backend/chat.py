from enum import Enum
from typing import List, Dict, Optional, Any, Union
import json
import time
import asyncio
import os
import logging
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import uuid

# AI 모델 라이브러리 임포트
from anthropic import AsyncAnthropic
import google.generativeai as genai
from llama_cpp import Llama
from transformers import AutoTokenizer

from dotenv import load_dotenv

from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Any, Union, Literal
from dataclasses import dataclass
import json
import time
import uuid

from pydantic import BaseModel, Field

# dbcon 모듈 경로 수정
from backend.dbcon import SessionLocal, Session, Message as DBMessage, Session as DBSession


load_dotenv()

# 로깅 설정 - 이미 INFO로 설정되어 있음
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MessageModel(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: float = Field(default_factory=time.time)
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

class SessionModel(BaseModel):
    session_id: str
    user_id: str
    model: str
    messages: List[MessageModel] = []
    created_at: float = Field(default_factory=time.time)
    last_updated: float = Field(default_factory=time.time)
    system_prompt: str = "당신은 도움이 되는 AI 어시스턴트입니다. 사용자의 질문에 대해 정확하고 친절하게 답변하세요."

class MemoryModel(BaseModel):
    content: str
    timestamp: float = Field(default_factory=time.time)
    importance: float = 1.0
    status: str = "active"
    keywords: List[str] = []

# AI 모델 타입 정의
class AIModel(str, Enum):
    META = "meta"
    CLAUDE = "claude"
    GEMINI = "gemini"

# 메시지 역할 정의
class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

# 메시지 구조 정의
class ChatMessage:
    def __init__(self, role: MessageRole, content: str, timestamp: Optional[float] = None):
        self.role = role
        self.content = content
        self.timestamp = timestamp or time.time()
        self.message_id = str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "message_id": self.message_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatMessage':
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp")
        )

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

# AI 모델 관리자
class AIModelManager:
    def __init__(self):
        self.setup_models()
    
    def setup_models(self):
        """AI 모델 초기화"""
        try:
            # Claude 설정
            self.anthropic = AsyncAnthropic(api_key=os.getenv('CLAUDE_API_KEY'))
            
            # Gemini 설정
            genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
            self.gemini_config = {
                'temperature': 0.9,
                'top_p': 1,
                'top_k': 1,
                'max_output_tokens': 3000,
            }
            self.gemini_model = genai.GenerativeModel(
                'gemini-1.5-flash',
                generation_config=self.gemini_config
            )
            
            # Meta(로컬) 모델 설정
            self.local_model = self._initialize_local_model()
            self.tokenizer = AutoTokenizer.from_pretrained('Bllossom/llama-3.2-Korean-Bllossom-3B')
            
            logger.info("AI 모델 초기화 성공")
        except Exception as e:
            logger.error(f"AI 모델 초기화 실패: {e}")
            raise

    def _initialize_local_model(self):
        """로컬 LLM 초기화 (GPU 지원 가능 시 활용)"""
        MODEL_PATH=r"C:\\Users\\MyoengHo Shin\\pjt\\progen\\llama-korean\\llama-3.2-Korean-Bllossom-3B-gguf-Q4_K_M.gguf"
        
        # 모델 경로가 비어있거나 존재하지 않는 경우 처리
        if not MODEL_PATH or not os.path.exists(MODEL_PATH):
            logger.warning(f"모델 경로가 유효하지 않습니다: '{MODEL_PATH}'. Meta 모델을 사용하지 않습니다.")
            return None
        
        try:
            logger.info("GPU 레이어 활성화 시도 중...")
            model = Llama(
                model_path=MODEL_PATH,
                n_ctx=2048,
                n_threads=8,
                n_batch=1024,
                n_gpu_layers=32,
                f16_kv=True,
                offload_kqv=True,
                verbose=True  # 상세 로그 출력
            )
            logger.info("GPU 레이어 활성화 성공!")
            return model
        except Exception as e:
            logger.warning(f"GPU 초기화 실패, CPU로 대체: {e}")
            try:
                logger.info("CPU 모드로 모델 초기화 시도 중...")
                model = Llama(
                    model_path=MODEL_PATH,
                    n_ctx=2048,
                    n_threads=8,
                    n_batch=512,
                    n_gpu_layers=0,
                    verbose=True  # 상세 로그 출력
                )
                logger.info("CPU 모드로 모델 초기화 성공!")
                return model
            except Exception as e:
                logger.error(f"CPU 모델 초기화도 실패: {e}")
                return None

    async def generate_response(self, messages: List[ChatMessage], model: AIModel, websocket: Optional[WebSocket] = None) -> str:
        """개선된 컨텍스트 기반 응답 생성"""
        try:
            # 메시지를 프롬프트로 변환
            prompt = self._format_messages_to_prompt(messages)
            
            # 모델별 응답 생성
            if model == AIModel.GEMINI:
                return await self._generate_gemini_response(prompt, websocket)
            elif model == AIModel.CLAUDE:
                return await self._generate_claude_response(prompt, websocket)
            else:  # META
                return await self._generate_local_response(prompt, websocket)
                
        except Exception as e:
            logger.error(f"{model} 모델 응답 생성 오류: {e}")
            return f"죄송합니다. {model} 모델 응답 생성 중 오류가 발생했습니다."

    def _format_messages_to_prompt(self, messages: List[ChatMessage]) -> str:
        """대화 맥락을 유지하는 프롬프트 구성"""
        formatted_prompt = ""
        
        # 시스템 프롬프트 처리
        system_messages = [msg for msg in messages if msg.role == MessageRole.SYSTEM]
        if system_messages:
            formatted_prompt += f"시스템: {system_messages[0].content}\n\n"
        
        # 대화 컨텍스트 구성 (시스템 메시지 제외)
        chat_messages = [msg for msg in messages if msg.role != MessageRole.SYSTEM]
        
        # 시간순으로 정렬
        chat_messages.sort(key=lambda x: x.timestamp)
        
        # 대화 이력 추가
        for msg in chat_messages:
            role_prefix = "사용자: " if msg.role == MessageRole.USER else "어시스턴트: "
            formatted_prompt += f"{role_prefix}{msg.content}\n\n"
        
        # 최종 응답 유도
        formatted_prompt += "어시스턴트: "
        return formatted_prompt

    async def _generate_gemini_response(self, prompt: str, websocket: Optional[WebSocket] = None) -> str:
        """Gemini 모델용 응답 생성 로직"""
        response = await self.gemini_model.generate_content_async(prompt)
        formatted_response = self._format_gemini_response(response.text)
        
        if websocket:
            for chunk in self._simulate_streaming(formatted_response):
                await self._send_chunk(websocket, chunk, "gemini")
            
            await websocket.send_json({
                "type": "assistant",
                "isFullResponse": True,
                "model": "gemini"
            })
        
        return formatted_response

    async def _generate_claude_response(self, prompt: str, websocket: Optional[WebSocket] = None) -> str:
        """Claude 모델용 응답 생성 로직"""
        stream = await self.anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
            stream=True
        )
        
        response = ""
        async for chunk in stream:
            if chunk.type == "content_block_delta" and chunk.delta:
                response += chunk.delta.text
                if websocket:
                    await self._send_chunk(websocket, chunk.delta.text, "claude")
        
        if websocket:
            await websocket.send_json({
                "type": "assistant",
                "isFullResponse": True,
                "model": "claude"
            })
        
        return response

    async def _generate_local_response(self, prompt: str, websocket: Optional[WebSocket] = None) -> str:
        """로컬(Meta) 모델용 응답 생성 로직"""
        try:
            formatted_prompt = self.tokenizer.apply_chat_template(
                self._convert_to_chat_format(prompt),
                tokenize=False,
                add_generation_prompt=True
            )
            
            response = ""
            for chunk in self.local_model(formatted_prompt, max_tokens=512, stream=True):
                if chunk and "choices" in chunk:
                    text = chunk["choices"][0]["text"]
                    if text:
                        response += text
                        if websocket:
                            await self._send_chunk(websocket, text, "meta")
            
            if websocket:
                await websocket.send_json({
                    "type": "assistant",
                    "isFullResponse": True,
                    "model": "meta"
                })
            
            return response
            
        except Exception as e:
            logger.error(f"로컬 모델 응답 생성 오류: {e}")
            return "죄송합니다. 응답 생성 중 오류가 발생했습니다."
        
    def _convert_to_chat_format(self, prompt: str) -> List[Dict[str, str]]:
        """프롬프트를 채팅 형식으로 변환"""
        messages = []
        current_role = None
        current_content = []
        
        for line in prompt.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('시스템:'):
                if current_role:
                    messages.append({"role": current_role, "content": '\n'.join(current_content)})
                current_role = "system"
                current_content = [line[4:].strip()]
            elif line.startswith('사용자:'):
                if current_role:
                    messages.append({"role": current_role, "content": '\n'.join(current_content)})
                current_role = "user"
                current_content = [line[4:].strip()]
            elif line.startswith('어시스턴트:'):
                if current_role:
                    messages.append({"role": current_role, "content": '\n'.join(current_content)})
                current_role = "assistant"
                current_content = [line[7:].strip()]
            else:
                if current_content:
                    current_content.append(line)
        
        if current_role and current_content:
            messages.append({"role": current_role, "content": '\n'.join(current_content)})
            
        return messages

    def _simulate_streaming(self, text: str, chunk_size: int = 10) -> List[str]:
        """스트리밍 시뮬레이션 (Gemini는 스트리밍을 직접 지원하지 않을 경우)"""
        return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

    async def _send_chunk(self, websocket: WebSocket, text: str, model: str) -> None:
        """웹소켓을 통해 응답 청크 전송"""
        await websocket.send_json({
            "type": "assistant",
            "content": text,
            "streaming": True,
            "model": model
        })

    def _format_gemini_response(self, text: str) -> str:
        """Gemini 응답 포맷팅"""
        formatted = text.replace('•', '* ')
        return formatted
    
    async def generate_response_with_reasoning(self, messages: List[ChatMessage], model: AIModel, 
                                           websocket: Optional[WebSocket] = None) -> str:
        """추론 기능이 강화된 응답 생성"""
        
        # 시스템 프롬프트 추출 및 강화
        system_prompt = next((msg.content for msg in messages if msg.role == MessageRole.SYSTEM), "")
        reasoning_prompt = system_prompt + "\n\n추가 지시사항: 복잡한 질문에 대답할 때는 다음과 같이 하세요:\n"
        reasoning_prompt += "1. 문제를 작은 부분으로 분해하세요\n"
        reasoning_prompt += "2. 각 부분에 대해 단계적으로 생각하세요\n"
        reasoning_prompt += "3. 중간 결론을 통해 최종 답변을 도출하세요\n"
        
        # 추론 강화 프롬프트로 교체
        for i, msg in enumerate(messages):
            if msg.role == MessageRole.SYSTEM:
                messages[i] = ChatMessage(MessageRole.SYSTEM, reasoning_prompt)
                break
        
        # 일반 응답 생성과 동일한 흐름 사용
        return await self.generate_response(messages, model, websocket)

# 채팅 관리자
class ChatManager:
    def __init__(self):
        self.active_sessions: Dict[str, ChatSession] = {}
        self.connected_clients: Dict[str, WebSocket] = {}
        self.ai_model_manager = AIModelManager()
    
    async def connect_client(self, websocket: WebSocket, client_id: str) -> None:
        """클라이언트 연결 처리"""
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

# 메시지 처리기
class MessageHandler:
    def __init__(self, chat_manager: ChatManager):
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
            
            
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional
from datetime import datetime
import json

class MemoryStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"

@dataclass
class Memory:
    """대화 메모리의 기본 단위"""
    content: str
    timestamp: float
    importance: float = 1.0
    status: MemoryStatus = MemoryStatus.ACTIVE
    keywords: List[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "timestamp": self.timestamp,
            "importance": self.importance,
            "status": self.status.value,
            "keywords": self.keywords or []
        }

class MemoryManager:
    def __init__(self):
        self.memories: List[Memory] = []
        self.importance_threshold = 0.5  # 중요도 임계값
        
    def add_memory(self, content: str, keywords: List[str] = None) -> Memory:
        """새로운 메모리 추가"""
        memory = Memory(
            content=content,
            timestamp=datetime.now().timestamp(),
            keywords=keywords or []
        )
        self._evaluate_importance(memory)
        self.memories.append(memory)
        return memory
        
    def _evaluate_importance(self, memory: Memory) -> None:
        """메모리의 중요도 평가"""
        # 기본 중요도는 1.0
        importance = 1.0
        
        # 키워드가 있으면 중요도 증가
        if memory.keywords:
            importance += len(memory.keywords) * 0.1
            
        # 시간에 따른 중요도 감소 (나중에 구현)
        
        memory.importance = min(importance, 2.0)  # 최대 2.0으로 제한
        
    def get_active_memories(self) -> List[Memory]:
        """활성화된 메모리만 반환"""
        return [m for m in self.memories if m.status == MemoryStatus.ACTIVE]
        
    def update_memory_status(self, timestamp: float, status: MemoryStatus) -> bool:
        """특정 시점의 메모리 상태 업데이트"""
        for memory in self.memories:
            if memory.timestamp == timestamp:
                memory.status = status
                return True
        return False
        
    def get_recent_memories(self, limit: int = 10) -> List[Memory]:
        """최근 메모리 반환 (중요도 고려)"""
        active_memories = self.get_active_memories()
        sorted_memories = sorted(
            active_memories,
            key=lambda x: (x.importance, x.timestamp),
            reverse=True
        )
        return sorted_memories[:limit]
        
    def search_by_keywords(self, keywords: List[str]) -> List[Memory]:
        """키워드로 메모리 검색"""
        result = []
        for memory in self.get_active_memories():
            if any(kw in memory.keywords for kw in keywords):
                result.append(memory)
        return result

    def cleanup_old_memories(self, threshold_days: int = 30) -> int:
        """오래된 메모리 정리"""
        current_time = datetime.now().timestamp()
        threshold = threshold_days * 24 * 60 * 60  # 일 -> 초
        
        cleanup_count = 0
        for memory in self.memories:
            if current_time - memory.timestamp > threshold:
                memory.status = MemoryStatus.ARCHIVED
                cleanup_count += 1
                
        return cleanup_count
        
    def export_memories(self) -> str:
        """메모리를 JSON 형식으로 내보내기"""
        memory_list = [m.to_dict() for m in self.memories]
        return json.dumps(memory_list, ensure_ascii=False, indent=2)
        
    def import_memories(self, json_str: str) -> None:
        """JSON에서 메모리 가져오기"""
        memory_list = json.loads(json_str)
        for data in memory_list:
            memory = Memory(
                content=data["content"],
                timestamp=data["timestamp"],
                importance=data["importance"],
                status=MemoryStatus(data["status"]),
                keywords=data["keywords"]
            )
            self.memories.append(memory)