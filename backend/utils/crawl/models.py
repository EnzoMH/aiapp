"""
나라장터 크롤링 데이터 모델

이 모듈은 크롤링 요청과 결과에 대한 Pydantic 모델을 정의합니다.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, date
from enum import Enum


class BidStatus(str, Enum):
    """입찰 상태 열거형"""
    ONGOING = "진행중"
    COMPLETED = "완료"
    CANCELLED = "취소"
    PENDING = "대기"
    CLOSED = "마감"


class BidBasicInfo(BaseModel):
    """입찰 기본 정보"""
    bid_id: str = Field(..., description="입찰공고 고유번호")
    title: str = Field(..., description="입찰공고 제목")
    announce_agency: str = Field(..., description="공고기관")
    post_date: str = Field(..., description="게시일자")
    deadline_date: Optional[str] = Field(None, description="마감일시")
    estimated_amount: Optional[str] = Field(None, description="추정가격")
    progress_stage: str = Field(BidStatus.ONGOING, description="진행단계")
    url: str = Field(..., description="상세 페이지 URL")
    
    @validator('bid_id')
    def validate_bid_id(cls, v):
        if not v or len(v) < 5:
            raise ValueError('입찰공고 번호는 최소 5자 이상이어야 합니다')
        return v


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


class BidItem(BaseModel):
    """입찰 항목 정보"""
    basic_info: BidBasicInfo = Field(..., description="기본 정보")
    detail_info: Optional[BidDetailInfo] = Field(None, description="상세 정보")
    keywords: List[str] = Field(default_factory=list, description="매칭된 키워드 목록")
    crawled_at: datetime = Field(default_factory=datetime.now, description="크롤링 일시")


class CrawlingRequest(BaseModel):
    """크롤링 요청 모델"""
    start_date: Optional[date] = Field(None, description="시작일")
    end_date: Optional[date] = Field(None, description="종료일")
    keywords: List[str] = Field(..., description="검색 키워드 목록")
    headless: bool = Field(True, description="헤드리스 모드 사용 여부")
    client_info: Optional[Dict[str, Any]] = Field(None, description="클라이언트 정보")
    
    @validator('keywords')
    def validate_keywords(cls, v):
        if not v or len(v) == 0:
            raise ValueError('검색 키워드는 최소 1개 이상이어야 합니다')
        return v


class CrawlingStatus(BaseModel):
    """크롤링 상태 모델"""
    is_running: bool = Field(False, description="실행 중 여부")
    current_keyword: Optional[str] = Field(None, description="현재 처리 중인 키워드")
    processed_keywords: List[str] = Field(default_factory=list, description="처리된 키워드 목록")
    total_keywords: int = Field(0, description="전체 키워드 수")
    processed_count: int = Field(0, description="처리된 키워드 수")
    total_results: int = Field(0, description="수집된 결과 수")
    start_time: Optional[datetime] = Field(None, description="시작 시간")
    end_time: Optional[datetime] = Field(None, description="종료 시간")
    timestamp: datetime = Field(default_factory=datetime.now, description="상태 업데이트 시간")


class CrawlingResponse(BaseModel):
    """크롤링 응답 모델"""
    status: str = Field(..., description="응답 상태 (success, error, warning)")
    message: str = Field(..., description="응답 메시지")
    results: Optional[List[BidItem]] = Field(None, description="크롤링 결과 목록")
    crawling_status: Optional[CrawlingStatus] = Field(None, description="크롤링 상태")


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