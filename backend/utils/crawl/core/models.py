"""
크롤링 데이터 모델 모듈

이 모듈은 크롤링된 데이터를 구조화하기 위한 Pydantic 모델을 정의합니다.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator


class CrawlStatus(str, Enum):
    """크롤링 상태 열거형"""
    WAITING = "waiting"  # 대기 중
    RUNNING = "running"  # 실행 중
    COMPLETED = "completed"  # 완료됨
    FAILED = "failed"  # 실패
    PAUSED = "paused"  # 일시 중지


class CrawlType(str, Enum):
    """크롤링 유형 열거형"""
    GENERAL = "general"  # 일반 크롤러
    AI_AGENT = "ai_agent"  # AI 에이전트 크롤러


class AgentStatusLevel(str, Enum):
    """에이전트 상태 수준 열거형"""
    INFO = "info"  # 정보
    WARNING = "warning"  # 경고
    ERROR = "error"  # 오류
    SUCCESS = "success"  # 성공


class WebSocketMessage(BaseModel):
    """웹소켓 메시지 모델"""
    type: str  # 메시지 유형
    data: Dict[str, Any]  # 메시지 데이터
    timestamp: datetime = Field(default_factory=datetime.now)  # 타임스탬프


class AgentStatus(BaseModel):
    """에이전트 상태 메시지 모델"""
    message: str  # 상태 메시지
    level: AgentStatusLevel = AgentStatusLevel.INFO  # 상태 수준
    details: Optional[Dict[str, Any]] = None  # 추가 세부 정보
    timestamp: datetime = Field(default_factory=datetime.now)  # 타임스탬프


class CrawlProgress(BaseModel):
    """크롤링 진행 상황 모델"""
    total_keywords: int = 0  # 총 키워드 수
    processed_keywords: int = 0  # 처리된 키워드 수
    total_pages: int = 0  # 총 페이지 수
    processed_pages: int = 0  # 처리된 페이지 수
    total_items: int = 0  # 총 항목 수
    collected_items: int = 0  # 수집된 항목 수
    current_keyword: Optional[str] = None  # 현재 처리 중인 키워드
    current_page: Optional[int] = None  # 현재 처리 중인 페이지
    timestamp: datetime = Field(default_factory=datetime.now)  # 타임스탬프

    @property
    def keyword_progress_percent(self) -> float:
        """키워드 진행률 계산"""
        if self.total_keywords == 0:
            return 0.0
        return round((self.processed_keywords / self.total_keywords) * 100, 1)

    @property
    def page_progress_percent(self) -> float:
        """페이지 진행률 계산"""
        if self.total_pages == 0:
            return 0.0
        return round((self.processed_pages / self.total_pages) * 100, 1)

    @property
    def item_progress_percent(self) -> float:
        """항목 진행률 계산"""
        if self.total_items == 0:
            return 0.0
        return round((self.collected_items / self.total_items) * 100, 1)

    @property
    def overall_progress_percent(self) -> float:
        """전체 진행률 계산"""
        if self.total_keywords == 0:
            return 0.0
        
        # 키워드, 페이지, 항목 진행률 조합
        keyword_weight = 0.2
        page_weight = 0.3
        item_weight = 0.5
        
        overall = (
            self.keyword_progress_percent * keyword_weight +
            self.page_progress_percent * page_weight + 
            self.item_progress_percent * item_weight
        )
        
        return round(overall, 1)


class BidItem(BaseModel):
    """입찰 항목 모델"""
    bid_id: str  # 입찰 ID
    title: str  # 입찰 제목
    url: str  # 입찰 URL
    organization: Optional[str] = None  # 기관명
    location: Optional[str] = None  # 지역
    bid_type: Optional[str] = None  # 입찰 유형
    reg_date: Optional[str] = None  # 등록일
    close_date: Optional[str] = None  # 마감일
    price: Optional[str] = None  # 예상 가격
    status: Optional[str] = None  # 입찰 상태
    details: Optional[Dict[str, Any]] = Field(default_factory=dict)  # 추가 세부 정보
    raw_html: Optional[str] = None  # 원본 HTML
    keyword: Optional[str] = None  # 검색 키워드
    crawled_at: datetime = Field(default_factory=datetime.now)  # 크롤링 시간


class BidDetail(BaseModel):
    """입찰 상세 정보 모델"""
    bid_id: str  # 입찰 ID
    title: str  # 입찰 제목
    organization: Optional[str] = None  # 기관명
    division: Optional[str] = None  # 부서/담당
    location: Optional[str] = None  # 지역
    reg_date: Optional[str] = None  # 등록일
    close_date: Optional[str] = None  # 마감일
    estimated_price: Optional[str] = None  # 추정가격
    contract_type: Optional[str] = None  # 계약방식
    bid_type: Optional[str] = None  # 입찰유형
    industry: Optional[str] = None  # 업종
    contact_info: Optional[Dict[str, str]] = None  # 연락처 정보
    description: Optional[str] = None  # 상세 설명
    requirements: Optional[List[str]] = None  # 요구사항
    attachments: Optional[List[Dict[str, str]]] = None  # 첨부파일
    additional_info: Optional[Dict[str, Any]] = None  # 추가 정보
    crawled_at: datetime = Field(default_factory=datetime.now)  # 크롤링 시간


class CrawlResult(BaseModel):
    """크롤링 결과 모델"""
    id: Optional[str] = None  # 결과 ID
    status: CrawlStatus = CrawlStatus.WAITING  # 크롤링 상태
    crawl_type: CrawlType = CrawlType.GENERAL  # 크롤링 유형
    keywords: List[str] = Field(default_factory=list)  # 검색 키워드
    start_time: Optional[datetime] = None  # 시작 시간
    end_time: Optional[datetime] = None  # 종료 시간
    items: List[BidItem] = Field(default_factory=list)  # 수집된 항목
    details: Dict[str, BidDetail] = Field(default_factory=dict)  # 상세 정보
    errors: List[Dict[str, Any]] = Field(default_factory=list)  # 오류 목록
    progress: CrawlProgress = Field(default_factory=CrawlProgress)  # 진행 상황
    agent_status: List[AgentStatus] = Field(default_factory=list)  # 에이전트 상태
    created_at: datetime = Field(default_factory=datetime.now)  # 생성 시간
    updated_at: datetime = Field(default_factory=datetime.now)  # 업데이트 시간
    
    @validator('updated_at', always=True)
    def update_timestamp(cls, v, values):
        """업데이트 시간을 현재 시간으로 설정"""
        return datetime.now()
    
    def update_progress(self, **kwargs):
        """진행 상황 업데이트"""
        for key, value in kwargs.items():
            if hasattr(self.progress, key):
                setattr(self.progress, key, value)
        self.progress.timestamp = datetime.now()
        self.updated_at = datetime.now()
    
    def add_agent_status(self, message: str, level: AgentStatusLevel = AgentStatusLevel.INFO, details: Optional[Dict[str, Any]] = None):
        """에이전트 상태 추가"""
        status = AgentStatus(
            message=message,
            level=level,
            details=details,
            timestamp=datetime.now()
        )
        self.agent_status.append(status)
        self.updated_at = datetime.now()
        return status
    
    def add_error(self, message: str, details: Optional[Dict[str, Any]] = None):
        """오류 추가"""
        error = {
            "message": message,
            "details": details or {},
            "timestamp": datetime.now()
        }
        self.errors.append(error)
        self.updated_at = datetime.now()
        return error
    
    def add_item(self, item: BidItem):
        """항목 추가"""
        self.items.append(item)
        self.progress.collected_items += 1
        self.updated_at = datetime.now()
        return item
    
    def add_detail(self, detail: BidDetail):
        """상세 정보 추가"""
        self.details[detail.bid_id] = detail
        self.updated_at = datetime.now()
        return detail
    
    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            "id": self.id,
            "status": self.status.value,
            "crawl_type": self.crawl_type.value,
            "keywords": self.keywords,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "progress": {
                "total_keywords": self.progress.total_keywords,
                "processed_keywords": self.progress.processed_keywords,
                "total_pages": self.progress.total_pages,
                "processed_pages": self.progress.processed_pages,
                "total_items": self.progress.total_items,
                "collected_items": self.progress.collected_items,
                "current_keyword": self.progress.current_keyword,
                "current_page": self.progress.current_page,
                "keyword_progress_percent": self.progress.keyword_progress_percent,
                "page_progress_percent": self.progress.page_progress_percent,
                "item_progress_percent": self.progress.item_progress_percent,
                "overall_progress_percent": self.progress.overall_progress_percent,
            },
            "items_count": len(self.items),
            "details_count": len(self.details),
            "errors_count": len(self.errors),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
    
    def to_full_dict(self):
        """모든 데이터를 포함한 딕셔너리로 변환"""
        base_dict = self.to_dict()
        base_dict["items"] = [item.dict() for item in self.items]
        base_dict["details"] = {bid_id: detail.dict() for bid_id, detail in self.details.items()}
        base_dict["errors"] = self.errors
        base_dict["agent_status"] = [status.dict() for status in self.agent_status]
        return base_dict 