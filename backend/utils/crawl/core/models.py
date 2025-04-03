"""
크롤링 데이터 모델 모듈

이 모듈은 크롤링된 데이터를 구조화하기 위한 Pydantic 모델을 정의합니다.
"""

from datetime import datetime, date
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


class G2BBidItem(BaseModel):
    """나라장터 입찰 항목 상세 모델"""
    business_type: str  # 업무구분 (물품/용역 등)
    bid_number: str  # 입찰공고번호
    title: str  # 공고명
    announce_agency: str  # 공고기관
    demand_agency: Optional[str] = None  # 수요기관 (공고기관과 다를 경우)
    post_date: datetime  # 게시일시
    bid_start_date: Optional[datetime] = None  # 입찰일시
    bid_open_date: Optional[datetime] = None  # 개찰일시
    bid_close_date: Optional[datetime] = None  # 마감일시
    status: str  # 단계
    url: Optional[str] = None  # 상세 URL
    is_same_agency: bool = False  # 공고기관과 수요기관이 같은지 여부
    crawled_at: datetime = Field(default_factory=datetime.now)  # 크롤링 시간
    
    @validator('is_same_agency', always=True)
    def check_same_agency(cls, v, values):
        """공고기관과 수요기관이 같은지 확인"""
        announce = values.get('announce_agency')
        demand = values.get('demand_agency')
        if announce and demand:
            return announce == demand
        return False
    
    def is_valid_date(self) -> bool:
        """날짜 기준으로 유효한 항목인지 검증
        
        조건:
        1. 게시일시가 오늘 기준 3일 이상 지난 경우 무효
        2. 마감일시가 오늘 기준 9일 미만인 경우 무효
        """
        today = datetime.now().date()
        
        # 게시일 확인 (3일 이상 지난 경우 제외)
        if self.post_date:
            post_date = self.post_date.date()
            days_since_post = (today - post_date).days
            if days_since_post > 3:
                return False
        
        # 마감일 확인 (9일 미만인 경우 제외)
        if self.bid_close_date:
            close_date = self.bid_close_date.date()
            days_until_close = (close_date - today).days
            if days_until_close < 9:
                return False
                
        return True
    
    def is_valid_business_type(self) -> bool:
        """업무구분 기준으로 유효한 항목인지 검증 (물품/용역만 포함)"""
        if not self.business_type:
            return False
            
        # 물품 또는 용역인 경우만 유효
        valid_types = ['물품', '용역']
        return any(t in self.business_type for t in valid_types)


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


class BidAttachment(BaseModel):
    """입찰 첨부파일 모델"""
    file_name: str  # 파일명
    file_url: Optional[str] = None  # 파일 URL
    file_size: Optional[str] = None  # 파일 크기
    upload_date: Optional[datetime] = None  # 업로드 일자
    file_type: Optional[str] = None  # 파일 유형
    content: Optional[str] = None  # 추출된 파일 내용
    downloaded: bool = False  # 다운로드 여부
    processed: bool = False  # 처리 여부


class BidContact(BaseModel):
    """입찰 담당자 정보 모델"""
    name: Optional[str] = None  # 담당자 이름
    department: Optional[str] = None  # 부서
    position: Optional[str] = None  # 직위
    phone: Optional[str] = None  # 전화번호
    email: Optional[str] = None  # 이메일
    fax: Optional[str] = None  # 팩스
    address: Optional[str] = None  # 주소
    note: Optional[str] = None  # 비고


class BidGeneralInfo(BaseModel):
    """공고 일반 정보 모델"""
    bid_method: Optional[str] = None  # 입찰방식
    contract_method: Optional[str] = None  # 계약방식
    industry_type: Optional[str] = None  # 업종구분
    bid_type: Optional[str] = None  # 낙찰자결정방법
    bid_gov_no: Optional[str] = None  # 공고번호
    announcement_type: Optional[str] = None  # 공고구분
    bid_limit: Optional[str] = None  # 참가제한여부
    mixed_contract: Optional[str] = None  # 혼합입찰여부
    joint_contract: Optional[str] = None  # 공동도급여부
    site_visit: Optional[str] = None  # 현장설명여부
    pre_price_evaluation: Optional[str] = None  # 사전가격공개여부
    price_evaluation: Optional[str] = None  # 가격평가방식


class BidQualification(BaseModel):
    """입찰자격 정보 모델"""
    business_license: Optional[str] = None  # 사업자등록증
    business_conditions: Optional[str] = None  # 업종제한사항/입찰참가자격
    license_requirements: Optional[List[str]] = None  # 면허/자격 제한사항
    supply_performance: Optional[str] = None  # 공급실적
    technical_capability: Optional[str] = None  # 기술능력
    joint_execution: Optional[str] = None  # 공동수급체 구성/이행방식
    other_qualifications: Optional[str] = None  # 기타 자격조건


class BidRestriction(BaseModel):
    """투찰제한 정보 모델"""
    industry_restriction: Optional[str] = None  # 업종제한사항(가장중요)
    region_restriction: Optional[str] = None  # 지역제한
    small_business_restriction: Optional[str] = None  # 중소기업 참여제한
    group_restriction: Optional[str] = None  # 협업/컨소시엄 제한
    other_restrictions: Optional[str] = None  # 기타 제한사항


class BidProgressInfo(BaseModel):
    """입찰진행정보 모델"""
    bid_start_date: Optional[datetime] = None  # 입찰시작일시
    bid_end_date: Optional[datetime] = None  # 입찰마감일시
    bid_open_date: Optional[datetime] = None  # 개찰일시
    contract_period_start: Optional[datetime] = None  # 계약기간 시작일
    contract_period_end: Optional[datetime] = None  # 계약기간 종료일
    delivery_date: Optional[datetime] = None  # 납품기한
    site_visit_date: Optional[datetime] = None  # 현장설명일시
    site_visit_place: Optional[str] = None  # 현장설명장소
    bid_deposit: Optional[str] = None  # 입찰보증금
    performance_deposit: Optional[str] = None  # 계약이행보증금
    warranty_deposit: Optional[str] = None  # 하자보수보증금
    bid_place: Optional[str] = None  # 입찰장소


class BidPriceInfo(BaseModel):
    """가격 부문 정보 모델"""
    estimated_price: Optional[str] = None  # 추정가격
    base_price: Optional[str] = None  # 기초금액
    announced_price: Optional[str] = None  # 예정가격
    bid_unit: Optional[str] = None  # 입찰단위
    price_adjustment: Optional[str] = None  # 물가변동 조정방법
    standard_market_price: Optional[str] = None  # 시장단가
    bid_unit_price: Optional[str] = None  # 단가입찰여부
    low_price_limit: Optional[str] = None  # 낮은투찰 제한
    payment_method: Optional[str] = None  # 대가지급방법
    payment_timing: Optional[str] = None  # 지급시기


class BidDetailInfo(BaseModel):
    """입찰 상세 정보 통합 모델"""
    bid_number: str  # 입찰번호
    title: str  # 공고 제목
    url: Optional[str] = None  # 공고 URL
    
    # 섹션별 정보
    general_info: Optional[BidGeneralInfo] = None  # 공고 일반
    qualification: Optional[BidQualification] = None  # 입찰자격
    restriction: Optional[BidRestriction] = None  # 투찰제한
    progress_info: Optional[BidProgressInfo] = None  # 입찰진행정보
    price_info: Optional[BidPriceInfo] = None  # 가격 부문
    agency_contact: Optional[BidContact] = None  # 기관담당자
    demand_agency_contact: Optional[BidContact] = None  # 수요기관 담당자
    
    # 첨부파일 정보
    attachments: List[BidAttachment] = Field(default_factory=list)  # 첨부파일 목록
    
    # 추가 정보
    raw_html: Optional[str] = None  # 원본 HTML
    processed_at: datetime = Field(default_factory=datetime.now)  # 처리 시간
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "bid_number": self.bid_number,
            "title": self.title,
            "url": self.url,
            "general_info": self.general_info.dict() if self.general_info else None,
            "qualification": self.qualification.dict() if self.qualification else None,
            "restriction": self.restriction.dict() if self.restriction else None,
            "progress_info": self.progress_info.dict() if self.progress_info else None,
            "price_info": self.price_info.dict() if self.price_info else None,
            "agency_contact": self.agency_contact.dict() if self.agency_contact else None,
            "demand_agency_contact": self.demand_agency_contact.dict() if self.demand_agency_contact else None,
            "attachments": [attachment.dict() for attachment in self.attachments],
            "processed_at": self.processed_at.isoformat()
        } 