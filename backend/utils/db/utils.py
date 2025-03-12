"""
데이터베이스 유틸리티 함수
"""
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

from backend.utils.db.models import User, UserRole

class AuthUtils:
    @staticmethod
    def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
        """사용자 ID로 사용자 조회"""
        return db.query(User).filter(User.user_id == user_id).first()
    
    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[Dict[str, Any]]:
        """사용자 인증"""
        user = db.query(User).filter(User.user_id == username).first()
        if not user:
            return None
        if not user.verify_password(password):
            return None
        
        # 마지막 로그인 시간 업데이트
        from datetime import datetime
        user.last_login = datetime.utcnow()
        db.commit()
        
        return user.to_dict()
    
    @staticmethod
    def create_user(db: Session, user_id: str, password: str, role: UserRole = UserRole.USER) -> Dict[str, Any]:
        """새 사용자 생성"""
        hashed_password = User.get_password_hash(password)
        user = User(
            user_id=user_id,
            password=hashed_password,
            role=role
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.to_dict()
    
    @staticmethod
    def get_all_users(db: Session) -> List[Dict[str, Any]]:
        """모든 사용자 조회"""
        users = db.query(User).all()
        return [user.to_dict() for user in users]