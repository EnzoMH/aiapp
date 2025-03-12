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