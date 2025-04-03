"""
검색 결과 검증 및 데이터 정제 모듈

이 모듈은 G2BCrawler에서 사용되는 검색 결과 검증 및 데이터 정제 기능을 제공합니다.
"""

import logging
from typing import List, Dict, Any, Optional, Set

# 로깅 설정
logger = logging.getLogger(__name__)

class SearchValidator:
    """검색 결과 검증 및 데이터 정제 클래스"""
    
    def __init__(self):
        self.seen_bids = set()  # 중복 체크를 위한 bid_number 저장
        self.logger = logging.getLogger(__name__)
        
    def _clean_date(self, date_str: str) -> str:
        """날짜 문자열 정제"""
        if not date_str:
            return ""
        # "2025/02/10 16:14\n(2025/02/11 13:30)" -> "2025-02-10"
        try:
            return date_str.split()[0].replace("/", "-")
        except:
            return date_str

    def _clean_text(self, text: str) -> str:
        """텍스트 정제 (Grid 제거, 개행 정리)"""
        if not text:
            return ""
        # Grid 관련 텍스트 제거
        lines = [line.strip() for line in text.split('\n') 
                if line.strip() and 'Grid' not in line]
        return ' '.join(lines)

    def clean_bid_data(self, raw_data: dict) -> dict:
        """크롤링된 데이터 정제"""
        basic_info = raw_data.get("basic_info", {})
        detail_info = raw_data.get("detail_info", {})
        
        return {
            "keyword": raw_data.get("search_keyword", ""),
            "bid_info": {
                "number": basic_info.get("bid_number", ""),
                "title": basic_info.get("title", ""),
                "agency": basic_info.get("announce_agency", ""),
                "date": self._clean_date(basic_info.get("post_date", "")),
                "stage": basic_info.get("progress_stage", "-"),
                "status": basic_info.get("process_status", "-")
            },
            "details": {
                "notice": self._clean_text(detail_info.get("general_notice", "")),
                "qualification": self._clean_text(detail_info.get("bid_qualification", "")),
                "files": detail_info.get("bid_notice_files", [])
            }
        }

    def validate_search_result(self, keyword: str, bid_data: dict) -> bool:
        """검색어와 입찰 데이터 연관성 검증"""
        if not bid_data:
            return False
            
        # 검색어가 제목이나 내용에 포함되어 있는지 확인
        keyword_lower = keyword.lower()
        basic_info = bid_data.get('basic_info', {})
        detail_info = bid_data.get('detail_info', {})
        
        title = basic_info.get('title', '').lower()
        general_notice = detail_info.get('general_notice', '').lower()
        
        # 검색어 포함 여부 확인 (더 유연하게)
        contains_keyword = (
            keyword_lower in title or 
            keyword_lower in general_notice or
            any(kw in title or kw in general_notice for kw in keyword_lower.split())
        )
        
        if contains_keyword:
            self.logger.info(f"키워드 '{keyword}' 매칭됨: {title}")
        
        return contains_keyword

    def remove_duplicates(self, results: list) -> list:
        """중복 데이터 제거"""
        unique_results = []
        for result in results:
            basic_info = result.get('basic_info', {})
            bid_number = basic_info.get('bid_number')
            if bid_number and bid_number not in self.seen_bids:
                self.seen_bids.add(bid_number)
                unique_results.append(result)
                self.logger.debug(f"중복되지 않은 입찰건 추가: {bid_number}")
        return unique_results

    def validate_required_fields(self, bid_data: dict) -> bool:
        """필수 필드 존재 여부 검증"""
        if not bid_data:
            return False
            
        basic_info = bid_data.get('basic_info', {})
        required_fields = ['title']  # 필수 필드를 title만으로 완화
        
        is_valid = all(basic_info.get(field) for field in required_fields)
        
        if not is_valid:
            self.logger.warning(f"필수 필드 누락: {bid_data}")
        
        return is_valid 