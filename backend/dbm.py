"""
데이터베이스 관리 모듈
데이터베이스 CRUD 작업 및 비즈니스 로직을 처리합니다.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

# 데이터베이스 관련 임포트
# 수정 후
from backend.utils.db import User, DBSession, Message, Memory, UserRole
from backend.utils.db import AuthUtils as DBAuthUtils

class UserManager:
    """사용자 관리 클래스"""
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: str) -> Optional[Dict[str, Any]]:
        """사용자 ID로 사용자 조회"""
        user = DBAuthUtils.get_user_by_id(db, user_id)
        return user.to_dict() if user else None
    
    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[Dict[str, Any]]:
        """사용자 인증"""
        return DBAuthUtils.authenticate_user(db, username, password)
    
    @staticmethod
    def create_user(db: Session, user_id: str, password: str, role: UserRole = UserRole.USER) -> Dict[str, Any]:
        """새 사용자 생성"""
        return DBAuthUtils.create_user(db, user_id, password, role)
    
    @staticmethod
    def get_all_users(db: Session) -> List[Dict[str, Any]]:
        """모든 사용자 조회"""
        return DBAuthUtils.get_all_users(db)
    
    @staticmethod
    def update_user(db: Session, user_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """사용자 정보 업데이트"""
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return None
            
        # 업데이트 가능한 필드 목록
        updatable_fields = ['password', 'role']
        
        # 제공된 필드만 업데이트
        for field, value in kwargs.items():
            if field in updatable_fields:
                if field == 'password':
                    value = User.get_password_hash(value)
                setattr(user, field, value)
        
        db.commit()
        db.refresh(user)
        return user.to_dict()
    
    @staticmethod
    def delete_user(db: Session, user_id: str) -> bool:
        """사용자 삭제"""
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return False
            
        db.delete(user)
        db.commit()
        return True


class SessionManager:
    """채팅 세션 관리 클래스"""
    
    @staticmethod
    def get_session_by_id(db: Session, session_id: str) -> Optional[Dict[str, Any]]:
        """세션 ID로 세션 조회"""
        session = db.query(DBSession).filter(DBSession.session_id == session_id).first()
        if not session:
            return None
            
        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "model": session.model,
            "system_prompt": session.system_prompt,
            "created_at": session.created_at.isoformat(),
            "last_updated": session.last_updated.isoformat(),
            "active": session.active
        }
    
    @staticmethod
    def get_user_sessions(db: Session, user_id: str) -> List[Dict[str, Any]]:
        """사용자의 모든 세션 조회"""
        sessions = db.query(DBSession).filter(DBSession.user_id == user_id).all()
        return [
            {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "model": session.model,
                "system_prompt": session.system_prompt,
                "created_at": session.created_at.isoformat(),
                "last_updated": session.last_updated.isoformat(),
                "active": session.active
            }
            for session in sessions
        ]
    
    @staticmethod
    def create_session(db: Session, user_id: str, model: str, system_prompt: str = None) -> Dict[str, Any]:
        """새 세션 생성"""
        session = DBSession(
            user_id=user_id,
            model=model,
            system_prompt=system_prompt
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "model": session.model,
            "system_prompt": session.system_prompt,
            "created_at": session.created_at.isoformat(),
            "last_updated": session.last_updated.isoformat(),
            "active": session.active
        }
    
    @staticmethod
    def update_session(db: Session, session_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """세션 정보 업데이트"""
        session = db.query(DBSession).filter(DBSession.session_id == session_id).first()
        if not session:
            return None
            
        # 업데이트 가능한 필드 목록
        updatable_fields = ['model', 'system_prompt', 'active']
        
        # 제공된 필드만 업데이트
        for field, value in kwargs.items():
            if field in updatable_fields:
                setattr(session, field, value)
        
        # 마지막 업데이트 시간 갱신
        session.last_updated = datetime.utcnow()
        
        db.commit()
        db.refresh(session)
        
        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "model": session.model,
            "system_prompt": session.system_prompt,
            "created_at": session.created_at.isoformat(),
            "last_updated": session.last_updated.isoformat(),
            "active": session.active
        }
    
    @staticmethod
    def delete_session(db: Session, session_id: str) -> bool:
        """세션 삭제"""
        session = db.query(DBSession).filter(DBSession.session_id == session_id).first()
        if not session:
            return False
            
        db.delete(session)
        db.commit()
        return True


class MessageManager:
    """채팅 메시지 관리 클래스"""
    
    @staticmethod
    def get_session_messages(db: Session, session_id: str) -> List[Dict[str, Any]]:
        """세션의 모든 메시지 조회"""
        messages = db.query(Message).filter(Message.session_id == session_id).order_by(Message.timestamp).all()
        return [
            {
                "message_id": message.message_id,
                "session_id": message.session_id,
                "role": message.role,
                "content": message.content,
                "timestamp": message.timestamp.isoformat()
            }
            for message in messages
        ]
    
    @staticmethod
    def add_message(db: Session, session_id: str, role: str, content: str) -> Dict[str, Any]:
        """새 메시지 추가"""
        message = Message(
            session_id=session_id,
            role=role,
            content=content
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        
        return {
            "message_id": message.message_id,
            "session_id": message.session_id,
            "role": message.role,
            "content": message.content,
            "timestamp": message.timestamp.isoformat()
        }
    
    @staticmethod
    def get_message_by_id(db: Session, message_id: str) -> Optional[Dict[str, Any]]:
        """메시지 ID로 메시지 조회"""
        message = db.query(Message).filter(Message.message_id == message_id).first()
        if not message:
            return None
            
        return {
            "message_id": message.message_id,
            "session_id": message.session_id,
            "role": message.role,
            "content": message.content,
            "timestamp": message.timestamp.isoformat()
        }
    
    @staticmethod
    def delete_message(db: Session, message_id: str) -> bool:
        """메시지 삭제"""
        message = db.query(Message).filter(Message.message_id == message_id).first()
        if not message:
            return False
            
        db.delete(message)
        db.commit()
        return True


class MemoryManager:
    """메모리 관리 클래스"""
    
    @staticmethod
    def get_user_memories(db: Session, user_id: str, status: str = "active") -> List[Dict[str, Any]]:
        """사용자의 모든 메모리 조회"""
        query = db.query(Memory).filter(Memory.user_id == user_id)
        if status:
            query = query.filter(Memory.status == status)
        memories = query.order_by(Memory.timestamp.desc()).all()
        
        return [
            {
                "memory_id": memory.memory_id,
                "user_id": memory.user_id,
                "content": memory.content,
                "keywords": memory.keywords,
                "importance": memory.importance,
                "status": memory.status,
                "timestamp": memory.timestamp.isoformat()
            }
            for memory in memories
        ]
    
    @staticmethod
    def add_memory(db: Session, user_id: str, content: str, keywords: List[str] = None, importance: float = 1.0) -> Dict[str, Any]:
        """새 메모리 추가"""
        memory = Memory(
            user_id=user_id,
            content=content,
            keywords=keywords or [],
            importance=importance
        )
        db.add(memory)
        db.commit()
        db.refresh(memory)
        
        return {
            "memory_id": memory.memory_id,
            "user_id": memory.user_id,
            "content": memory.content,
            "keywords": memory.keywords,
            "importance": memory.importance,
            "status": memory.status,
            "timestamp": memory.timestamp.isoformat()
        }
    
    @staticmethod
    def update_memory_status(db: Session, memory_id: str, status: str) -> Optional[Dict[str, Any]]:
        """메모리 상태 업데이트"""
        memory = db.query(Memory).filter(Memory.memory_id == memory_id).first()
        if not memory:
            return None
            
        memory.status = status
        db.commit()
        db.refresh(memory)
        
        return {
            "memory_id": memory.memory_id,
            "user_id": memory.user_id,
            "content": memory.content,
            "keywords": memory.keywords,
            "importance": memory.importance,
            "status": memory.status,
            "timestamp": memory.timestamp.isoformat()
        }
    
    @staticmethod
    def search_memories_by_keywords(db: Session, user_id: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """키워드로 메모리 검색"""
        # PostgreSQL의 배열 연산자 사용
        from sqlalchemy import or_
        query = db.query(Memory).filter(Memory.user_id == user_id, Memory.status == "active")
        
        # 각 키워드에 대해 OR 조건 추가
        keyword_conditions = []
        for keyword in keywords:
            keyword_conditions.append(Memory.keywords.any(keyword))
        
        if keyword_conditions:
            query = query.filter(or_(*keyword_conditions))
            
        memories = query.order_by(Memory.importance.desc(), Memory.timestamp.desc()).all()
        
        return [
            {
                "memory_id": memory.memory_id,
                "user_id": memory.user_id,
                "content": memory.content,
                "keywords": memory.keywords,
                "importance": memory.importance,
                "status": memory.status,
                "timestamp": memory.timestamp.isoformat()
            }
            for memory in memories
        ]