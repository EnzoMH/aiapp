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