"""
나라장터 크롤링 데이터 모델

이 모듈은 크롤링 요청과 결과에 대한 Pydantic 모델을 정의합니다.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Dict, Any, Optional, Set, Union, ClassVar, Type
from datetime import datetime, date
from enum import Enum
import os
import json


class BidStatus(str, Enum):
    """입찰 상태 열거형"""
    OPEN = "공고중"
    CLOSED = "마감"
    CANCELLED = "취소"
    RENOTICE = "재공고"
    UNKNOWN = "알수없음"


class BidBasicInfo(BaseModel):
    """입찰 기본 정보"""
    bid_number: Optional[str] = None  # 입찰공고번호
    bid_name: Optional[str] = None    # 입찰명
    org_name: Optional[str] = None    # 공고기관
    deadline: Optional[str] = None    # 마감일시
    status: Optional[BidStatus] = BidStatus.UNKNOWN  # 입찰상태
    url: Optional[str] = None         # 상세 URL
    
    model_config = {
        "populate_by_name": True,
        "use_enum_values": True,
        "extra": "allow",
    }


class BidDetailInfo(BaseModel):
    """입찰 상세 정보"""
    contract_method: Optional[str] = Field(None, description="계약체결방법")
    contract_type: Optional[str] = Field(None, description="계약방식")
    general_notice: Optional[str] = Field(None, description="일반공고내용")
    specific_notice: Optional[str] = Field(None, description="특수조건내용")
    bidding_method: Optional[str] = Field(None, description="입찰방식")
    budget_year: Optional[str] = Field(None, description="집행년도")
    digital_bid: Optional[bool] = Field(None, description="전자입찰 여부")
    additional_info: Optional[Dict[str, Any]] = Field(None, description="추가 정보")


class BidItem(BidBasicInfo):
    """입찰 항목 상세 모델"""
    bid_method: Optional[str] = None  # 입찰방식
    contract_type: Optional[str] = None  # 계약방식
    bid_type: Optional[str] = None    # 입찰종류
    budget: Optional[str] = None      # 예산금액
    price_evaluation: Optional[str] = None  # 낙찰자 선정방법
    location: Optional[str] = None    # 사업장소
    registration_date: Optional[str] = None  # 등록일시
    opened_date: Optional[str] = None      # 개찰일시
    search_keyword: Optional[str] = None  # 검색 키워드
    # 이 입찰이 수집된 시간
    collected_at: Optional[datetime] = None
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "extra": "allow",
    }
    
    @field_validator('bid_number')
    @classmethod
    def validate_bid_number(cls, value):
        """입찰번호 검증 및 정규화"""
        if not value:
            return None
        # 입찰번호 정규화 (공백 및 특수문자 제거)
        value = ''.join(c for c in value if c.isalnum())
        return value
    
    @model_validator(mode='after')
    def set_collected_at(self):
        """수집 시간 설정"""
        if not self.collected_at:
            self.collected_at = datetime.now()
        return self
    
    # 검색 키워드 검증
    @field_validator('search_keyword')
    @classmethod
    def validate_keywords(cls, value):
        """검색 키워드 검증"""
        if not value:
            return None
        return value.strip()


class CrawlingRequest(BaseModel):
    """크롤링 요청 모델"""
    keywords: List[str]
    headless: bool = True
    start_date: Optional[Union[str, date]] = None  # 검색 시작일
    end_date: Optional[Union[str, date]] = None    # 검색 종료일
    
    model_config = {
        "populate_by_name": True
    }
    
    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date(cls, v):
        """날짜 형식 검증"""
        if v is None:
            return None
        
        # 이미 date 객체인 경우
        if isinstance(v, date):
            return v
        
        # 문자열 형식인 경우 변환 시도
        try:
            return datetime.strptime(v, "%Y-%m-%d").date()
        except ValueError:
            try:
                return datetime.strptime(v, "%Y%m%d").date()
            except ValueError:
                raise ValueError("날짜는 YYYY-MM-DD 또는 YYYYMMDD 형식이어야 합니다")


class CrawlingStatus(str, Enum):
    """크롤링 상태 열거형"""
    NOT_STARTED = "not_started"  # 시작 전
    RUNNING = "running"          # 실행 중
    COMPLETED = "completed"      # 완료
    STOPPED = "stopped"          # 중지됨
    FAILED = "failed"            # 실패


class CrawlingResponse(BaseModel):
    """크롤링 응답 모델"""
    status: str
    message: str
    total_keywords: int = 0
    processed_keywords: int = 0
    total_items: int = 0
    error_count: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    results: List[BidItem] = []
    errors: List[str] = []
    metadata: Optional[Dict[str, Any]] = None
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "examples": [
                {
                    "status": "completed",
                    "message": "크롤링이 완료되었습니다.",
                    "total_keywords": 3,
                    "processed_keywords": 3,
                    "total_items": 15,
                    "error_count": 0,
                    "started_at": "2023-08-01T12:00:00",
                    "completed_at": "2023-08-01T12:05:00"
                }
            ]
        }
    }


class SearchValidator(BaseModel):
    """검색 입력 검증 모델"""
    keywords: List[str]
    headless: bool = True
    start_date: Optional[Union[str, date]] = None  # 검색 시작일
    end_date: Optional[Union[str, date]] = None    # 검색 종료일
    
    @field_validator('keywords')
    @classmethod
    def validate_keywords(cls, keywords):
        """키워드 유효성 검증"""
        if not keywords:
            raise ValueError("검색 키워드가 필요합니다.")
        
        # 빈 키워드 제거
        valid_keywords = [k.strip() for k in keywords if k and k.strip()]
        
        if not valid_keywords:
            raise ValueError("유효한 검색 키워드가 필요합니다.")
        
        # 중복 제거
        unique_keywords = list(set(valid_keywords))
        
        return unique_keywords
    
    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date(cls, v):
        """날짜 형식 검증"""
        if v is None:
            return None
        
        # 이미 date 객체인 경우
        if isinstance(v, date):
            return v
        
        # 문자열 형식인 경우 변환 시도
        try:
            return datetime.strptime(v, "%Y-%m-%d").date()
        except ValueError:
            try:
                return datetime.strptime(v, "%Y%m%d").date()
            except ValueError:
                raise ValueError("날짜는 YYYY-MM-DD 또는 YYYYMMDD 형식이어야 합니다")
    
    @model_validator(mode='after')
    def validate_date_range(self):
        """날짜 범위 검증"""
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValueError("시작일은 종료일보다 이전이어야 합니다")
        return self
    
    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "examples": [
                {
                    "keywords": ["소프트웨어", "시스템 개발", "정보화"],
                    "headless": True,
                    "start_date": "2023-01-01",
                    "end_date": "2023-12-31"
                }
            ]
        }
    }


class ResultFileInfo(BaseModel):
    """결과 파일 정보 모델"""
    filename: str
    filepath: str
    file_size: int
    created_at: datetime
    item_count: int = 0
    
    model_config = {
        "arbitrary_types_allowed": True
    }
    
    @classmethod
    def from_filepath(cls, filepath: str) -> 'ResultFileInfo':
        """파일 경로로부터 결과 파일 정보 생성"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"결과 파일을 찾을 수 없습니다: {filepath}")
        
        filename = os.path.basename(filepath)
        file_size = os.path.getsize(filepath)
        created_at = datetime.fromtimestamp(os.path.getctime(filepath))
        
        # 파일에서 항목 수 계산
        item_count = 0
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "results" in data and isinstance(data["results"], list):
                    item_count = len(data["results"])
        except Exception:
            # 파일 읽기 실패 시 항목 수는 0으로 유지
            pass
        
        return cls(
            filename=filename,
            filepath=filepath,
            file_size=file_size,
            created_at=created_at,
            item_count=item_count
        )


class AIAgentRequest(BaseModel):
    """AI 에이전트 크롤링 요청 모델"""
    keywords: List[str] = Field(..., description="검색 키워드 목록")
    fallback_mode: bool = Field(True, description="강제 AI 에이전트 모드 사용 여부")
    options: Optional[Dict[str, Any]] = Field(None, description="추가 옵션")


class AgentStatus(BaseModel):
    """AI 에이전트 상태 모델"""
    is_running: bool = Field(False, description="실행 중 여부")
    current_keyword: Optional[str] = Field(None, description="현재 처리 중인 키워드")
    processed_count: int = Field(0, description="처리된 키워드 수")
    fallback_mode: bool = Field(True, description="AI 에이전트 모드 사용 여부")
    results_count: int = Field(0, description="수집된 결과 수")
    timestamp: datetime = Field(default_factory=datetime.now, description="상태 업데이트 시간")


class ResultFileInfo(BaseModel):
    """결과 파일 정보 모델"""
    filename: str = Field(..., description="파일명")
    filepath: str = Field(..., description="파일 경로")
    created_at: datetime = Field(default_factory=datetime.now, description="생성 시간")
    file_size: Optional[int] = Field(None, description="파일 크기(바이트)")
    result_count: Optional[int] = Field(None, description="결과 개수")
    
    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat() if v else None
        }
    } 