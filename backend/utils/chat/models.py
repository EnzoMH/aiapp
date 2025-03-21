# 메시지 및 세션 관련 데이터 모델
from enum import Enum
from typing import List, Dict, Optional, Any
import time
import uuid

# 메시지 역할 정의
class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    
    
# 메시지 구조 정의
class ChatMessage:
    def __init__(self, role, content, timestamp=None, model=None):
        self.role = role
        self.content = content
        self.timestamp = timestamp or time.time()
        self.message_id = str(uuid.uuid4())  # 이미 문자열로 변환되어 있음
        self.model = model
    
    def to_dict(self) -> Dict[str, Any]:
        """JSON 직렬화 가능한 딕셔너리로 변환"""
        return {
            "role": str(self.role),  # Enum 값을 문자열로 변환
            "content": self.content,
            "timestamp": self.timestamp,
            "message_id": self.message_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatMessage':
        """딕셔너리에서 ChatMessage 객체 생성"""
        return cls(
            role=MessageRole(data["role"]),  # 문자열을 Enum으로 변환
            content=data["content"],
            timestamp=data.get("timestamp")
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatMessage':
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp")
        )
        
# AIModel Enum 클래스 추가 (없는 경우)
class AIModel(str, Enum):
    CLAUDE = "claude"
    META = "meta"
    GEMINI = "gemini"
    
    def __str__(self):
        return self.value