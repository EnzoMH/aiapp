"""
나라장터 입찰공고 상세정보 추출 모듈

이 모듈은 나라장터 입찰공고 상세 페이지에서 정보를 추출하는 기능을 제공합니다.
BeautifulSoup를 사용하여 HTML을 파싱하고 구조화된 데이터를 추출합니다.
"""

import os
import re
import logging
import traceback
import json
import tempfile
import asyncio
import aiohttp
import aiofiles
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
from bs4 import BeautifulSoup

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# 모델 가져오기
from .core.models import (
    BidDetailInfo, BidGeneralInfo, BidQualification, BidRestriction,
    BidProgressInfo, BidPriceInfo, BidContact, BidAttachment
)

# 로깅 설정
logger = logging.getLogger(__name__)


class DetailExtractor:
    """나라장터 입찰공고 상세정보 추출 클래스"""
    
    def __init__(self, driver=None, download_path=None):
        """
        초기화
        
        Args:
            driver: Selenium WebDriver 인스턴스
            download_path: 첨부파일 다운로드 경로
        """
        self.driver = driver
        
        # 다운로드 경로 설정
        if download_path:
            self.download_path = Path(download_path)
        else:
            self.download_path = Path(tempfile.gettempdir()) / "bid_attachments"
            
        # 다운로드 폴더 생성
        os.makedirs(self.download_path, exist_ok=True)
        
        # HTTP 세션 (파일 다운로드용)
        self.session = None
        
    async def initialize_session(self):
        """HTTP 세션 초기화"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
            
    async def close_session(self):
        """HTTP 세션 종료"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def extract_detail(self, url: str = None, bid_number: str = None, title: str = None) -> Optional[BidDetailInfo]:
        """
        입찰공고 상세정보 추출
        
        Args:
            url: 상세 페이지 URL (없으면 현재 페이지 사용)
            bid_number: 입찰번호 (없으면 페이지에서 추출)
            title: 공고명 (없으면 페이지에서 추출)
            
        Returns:
            BidDetailInfo 객체 또는 None
        """
        try:
            logger.info(f"입찰공고 상세정보 추출 시작: {bid_number or '번호 미지정'}")
            
            if url and self.driver:
                logger.info(f"URL로 이동: {url}")
                self.driver.get(url)
                await asyncio.sleep(2)  # 페이지 로딩 대기
            
            if not self.driver:
                logger.error("WebDriver가 초기화되지 않았습니다.")
                return None
                
            # 현재 URL이 상세 페이지인지 확인
            current_url = self.driver.current_url
            if not self._is_detail_page(current_url):
                logger.warning(f"현재 페이지가 상세 페이지가 아닙니다: {current_url}")
                return None
                
            # 페이지 소스 가져오기
            html = self.driver.page_source
            
            # BeautifulSoup 객체 생성
            soup = BeautifulSoup(html, 'html.parser')
            
            # 기본 정보 추출 (bid_number, title)
            if not bid_number or not title:
                basic_info = self._extract_basic_info(soup)
                bid_number = bid_number or basic_info.get('bid_number')
                title = title or basic_info.get('title')
                
            if not bid_number or not title:
                logger.error("입찰번호 또는 공고명을 추출할 수 없습니다.")
                return None
                
            # 상세 정보 객체 생성
            detail_info = BidDetailInfo(
                bid_number=bid_number,
                title=title,
                url=current_url
            )
            
            # 각 섹션 정보 추출
            detail_info.general_info = self._extract_general_info(soup)
            detail_info.qualification = self._extract_qualification(soup)
            detail_info.restriction = self._extract_restriction(soup)
            detail_info.progress_info = self._extract_progress_info(soup)
            detail_info.price_info = self._extract_price_info(soup)
            detail_info.agency_contact = self._extract_agency_contact(soup)
            detail_info.demand_agency_contact = self._extract_demand_agency_contact(soup)
            
            # 첨부파일 정보 추출
            attachments = self._extract_attachments(soup)
            detail_info.attachments = attachments
            
            # 원본 HTML 저장
            detail_info.raw_html = html
            
            logger.info(f"입찰공고 상세정보 추출 완료: {bid_number}")
            return detail_info
            
        except Exception as e:
            logger.error(f"입찰공고 상세정보 추출 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return None
            
    def _is_detail_page(self, url: str) -> bool:
        """상세 페이지 URL인지 확인"""
        # 나라장터 상세 페이지 URL 패턴 확인
        # 다양한 패턴이 있을 수 있으므로 일반적인 패턴만 체크
        return bool(re.search(r'(bid|ebid).*detail', url, re.I))
            
    def _extract_basic_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """기본 정보(입찰번호, 공고명) 추출"""
        info = {}
        
        try:
            # 제목 추출 시도
            title_elements = [
                soup.select_one('h1.tit'),  # 일반적인 제목 위치
                soup.select_one('div.section h3'),  # 섹션 헤더
                soup.select_one('div.titArea h1'),  # 타이틀 영역
                soup.select_one('table.table_info_head td'),  # 정보 테이블
            ]
            
            for elem in title_elements:
                if elem and elem.get_text().strip():
                    info['title'] = elem.get_text().strip()
                    break
            
            # 입찰번호 추출 시도
            bid_number_elements = [
                soup.select_one('table.table_info_head th:contains("공고번호") + td'),
                soup.select_one('th:contains("입찰공고번호") + td'),
                soup.select_one('dt:contains("공고번호") + dd'),
            ]
            
            for elem in bid_number_elements:
                if elem and elem.get_text().strip():
                    bid_number = elem.get_text().strip()
                    # 숫자와 특수문자만 포함된 부분 추출
                    match = re.search(r'[0-9\-]+', bid_number)
                    if match:
                        info['bid_number'] = match.group()
                    else:
                        info['bid_number'] = bid_number
                    break
        except Exception as e:
            logger.warning(f"기본 정보 추출 중 오류: {str(e)}")
        
        return info
        
    def _extract_table_data(self, soup: BeautifulSoup, table_selector: str) -> Dict[str, str]:
        """테이블에서 데이터 추출 (th-td 쌍)"""
        data = {}
        
        try:
            # 테이블 선택
            table = soup.select_one(table_selector)
            if not table:
                return data
                
            # 모든 행 추출
            rows = table.select('tr')
            for row in rows:
                # th와 td 쌍 추출
                th_elements = row.select('th')
                td_elements = row.select('td')
                
                for i, th in enumerate(th_elements):
                    if i < len(td_elements):
                        key = th.get_text().strip().replace(':', '').replace('*', '')
                        value = td_elements[i].get_text().strip()
                        data[key] = value
        except Exception as e:
            logger.warning(f"테이블 데이터 추출 중 오류: {str(e)}")
            
        return data
        
    def _extract_general_info(self, soup: BeautifulSoup) -> Optional[BidGeneralInfo]:
        """공고 일반 정보 추출"""
        try:
            # 공고 일반 섹션 찾기
            section_selectors = [
                'div.section:contains("공고 일반")',
                'div.section:contains("입찰 개요")',
                'div.section:contains("입찰공고 기본")',
                'table.table_info',
                'div.bid_info'
            ]
            
            # 데이터 저장 딕셔너리
            data = {}
            
            # 각 선택자 시도
            for selector in section_selectors:
                section = soup.select_one(selector)
                if section:
                    # 테이블 형식 데이터 추출
                    table_data = self._extract_table_data(section, 'table')
                    if table_data:
                        data.update(table_data)
            
            # 필드 매핑 및 BidGeneralInfo 객체 생성
            if data:
                return BidGeneralInfo(
                    bid_method=self._get_field_value(data, ['입찰방식', '계약방법', '입찰방법']),
                    contract_method=self._get_field_value(data, ['계약방식', '계약방법']),
                    industry_type=self._get_field_value(data, ['업종구분', '업종', '입찰분류']),
                    bid_type=self._get_field_value(data, ['낙찰자결정방법', '낙찰자 결정방법']),
                    bid_gov_no=self._get_field_value(data, ['공고번호', '입찰공고번호']),
                    announcement_type=self._get_field_value(data, ['공고구분', '입찰공고구분']),
                    bid_limit=self._get_field_value(data, ['참가제한여부', '제한여부']),
                    mixed_contract=self._get_field_value(data, ['혼합입찰여부']),
                    joint_contract=self._get_field_value(data, ['공동도급여부', '공동계약']),
                    site_visit=self._get_field_value(data, ['현장설명여부', '현장설명']),
                    pre_price_evaluation=self._get_field_value(data, ['사전가격공개여부']),
                    price_evaluation=self._get_field_value(data, ['가격평가방식'])
                )
            
            return None
        except Exception as e:
            logger.warning(f"공고 일반 정보 추출 중 오류: {str(e)}")
            return None
            
    def _get_field_value(self, data: Dict[str, str], field_names: List[str]) -> Optional[str]:
        """여러 필드 이름 중 하나의 값 반환"""
        for field in field_names:
            if field in data:
                return data[field]
        return None
        
    def _extract_qualification(self, soup: BeautifulSoup) -> Optional[BidQualification]:
        """입찰자격 정보 추출"""
        try:
            # 입찰자격 섹션 찾기
            section_selectors = [
                'div.section:contains("입찰자격")',
                'div.section:contains("참가자격")',
                'div.section:contains("입찰참가자격")',
                'table[summary*="입찰참가자격"]',
                'h4:contains("입찰자격") + table',
                'h4:contains("참가자격") + table'
            ]
            
            # 데이터 저장 딕셔너리
            data = {}
            license_requirements = []
            
            # 각 선택자 시도
            for selector in section_selectors:
                section = soup.select_one(selector)
                if section:
                    # 테이블 형식 데이터 추출
                    if section.name == 'table':
                        table_data = self._extract_table_data(section, 'self')
                    else:
                        table_data = self._extract_table_data(section, 'table')
                        
                    if table_data:
                        data.update(table_data)
                        
                    # 면허/자격 목록 추출
                    license_elements = section.select('li, p:contains("면허"), p:contains("자격")')
                    for elem in license_elements:
                        text = elem.get_text().strip()
                        if text and len(text) > 5:  # 최소 길이 제한
                            license_requirements.append(text)
            
            # 업종제한사항 특별 처리 (중요 정보)
            business_conditions = None
            for key in ['업종제한사항', '입찰참가자격', '참가자격']:
                if key in data:
                    business_conditions = data[key]
                    break
                    
            # 업종제한사항이 없는 경우 전체 텍스트에서 추출 시도
            if not business_conditions:
                for selector in section_selectors:
                    section = soup.select_one(selector)
                    if section:
                        # 업종제한 관련 텍스트 찾기
                        restriction_text = section.get_text()
                        if '업종제한' in restriction_text or '참가자격' in restriction_text:
                            # 적절한 문단 추출
                            paragraphs = [p.strip() for p in restriction_text.split('\n') if p.strip()]
                            for p in paragraphs:
                                if '업종' in p or '자격' in p or '면허' in p:
                                    if len(p) > 10:  # 최소 길이 제한
                                        business_conditions = p
                                        break
            
            # 필드 매핑 및 BidQualification 객체 생성
            return BidQualification(
                business_license=self._get_field_value(data, ['사업자등록증', '사업자등록']),
                business_conditions=business_conditions,
                license_requirements=license_requirements if license_requirements else None,
                supply_performance=self._get_field_value(data, ['공급실적', '실적']),
                technical_capability=self._get_field_value(data, ['기술능력', '기술', '신용']),
                joint_execution=self._get_field_value(data, ['공동수급체', '공동수급']),
                other_qualifications=self._get_field_value(data, ['기타 자격조건', '기타자격', '기타'])
            )
        except Exception as e:
            logger.warning(f"입찰자격 정보 추출 중 오류: {str(e)}")
            return None
            
    def _extract_restriction(self, soup: BeautifulSoup) -> Optional[BidRestriction]:
        """투찰제한 정보 추출"""
        try:
            # 투찰제한 섹션 찾기
            section_selectors = [
                'div.section:contains("투찰제한")',
                'div.section:contains("참가제한")',
                'table[summary*="제한"]',
                'h4:contains("제한") + table',
                'div.section:contains("참가자격")'  # 자격과 제한이 같은 섹션에 있을 수 있음
            ]
            
            # 데이터 저장 딕셔너리
            data = {}
            
            # 각 선택자 시도
            for selector in section_selectors:
                section = soup.select_one(selector)
                if section:
                    # 테이블 형식 데이터 추출
                    if section.name == 'table':
                        table_data = self._extract_table_data(section, 'self')
                    else:
                        table_data = self._extract_table_data(section, 'table')
                        
                    if table_data:
                        data.update(table_data)
            
            # 업종제한사항 특별 처리 (가장 중요한 정보)
            industry_restriction = None
            for key in ['업종제한사항', '업종제한', '제한업종', '업종']:
                if key in data:
                    industry_restriction = data[key]
                    break
                    
            # 업종제한사항이 없는 경우 입찰자격에서 가져올 수 있음
            if not industry_restriction:
                qualification_section = soup.select_one('div.section:contains("입찰자격")')
                if qualification_section:
                    for key, value in self._extract_table_data(qualification_section, 'table').items():
                        if '업종' in key:
                            industry_restriction = value
                            break
            
            # 필드 매핑 및 BidRestriction 객체 생성
            return BidRestriction(
                industry_restriction=industry_restriction,
                region_restriction=self._get_field_value(data, ['지역제한', '지역']),
                small_business_restriction=self._get_field_value(data, ['중소기업 참여제한', '중소기업제한']),
                group_restriction=self._get_field_value(data, ['협업제한', '컨소시엄', '공동수급']),
                other_restrictions=self._get_field_value(data, ['기타 제한사항', '기타제한', '기타'])
            )
        except Exception as e:
            logger.warning(f"투찰제한 정보 추출 중 오류: {str(e)}")
            return None
            
    def _extract_progress_info(self, soup: BeautifulSoup) -> Optional[BidProgressInfo]:
        """입찰진행정보 추출"""
        try:
            # 입찰진행정보 섹션 찾기
            section_selectors = [
                'div.section:contains("입찰진행정보")',
                'div.section:contains("입찰일정")',
                'table[summary*="입찰진행"]',
                'table[summary*="입찰일정"]',
                'h4:contains("입찰일정") + table'
            ]
            
            # 데이터 저장 딕셔너리
            data = {}
            
            # 각 선택자 시도
            for selector in section_selectors:
                section = soup.select_one(selector)
                if section:
                    # 테이블 형식 데이터 추출
                    if section.name == 'table':
                        table_data = self._extract_table_data(section, 'self')
                    else:
                        table_data = self._extract_table_data(section, 'table')
                        
                    if table_data:
                        data.update(table_data)
            
            # 날짜 데이터 파싱 함수
            def parse_date(date_str):
                if not date_str:
                    return None
                    
                # 날짜 형식 정규식
                date_patterns = [
                    r'(\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{1,2})',  # 2023/01/01 14:30
                    r'(\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{1,2})',  # 2023-01-01 14:30
                    r'(\d{4}\.\d{1,2}\.\d{1,2}\s+\d{1,2}:\d{1,2})',  # 2023.01.01 14:30
                    r'(\d{4}/\d{1,2}/\d{1,2})',  # 2023/01/01
                    r'(\d{4}-\d{1,2}-\d{1,2})',  # 2023-01-01
                    r'(\d{4}\.\d{1,2}\.\d{1,2})'  # 2023.01.01
                ]
                
                for pattern in date_patterns:
                    match = re.search(pattern, date_str)
                    if match:
                        date_str = match.group(1)
                        break
                
                # 다양한 형식 시도
                formats = [
                    '%Y/%m/%d %H:%M',
                    '%Y-%m-%d %H:%M',
                    '%Y.%m.%d %H:%M',
                    '%Y/%m/%d',
                    '%Y-%m-%d',
                    '%Y.%m.%d'
                ]
                
                for fmt in formats:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except ValueError:
                        continue
                        
                return None
            
            # 필드 매핑 및 BidProgressInfo 객체 생성
            return BidProgressInfo(
                bid_start_date=parse_date(self._get_field_value(data, ['입찰시작일시', '입찰개시일시'])),
                bid_end_date=parse_date(self._get_field_value(data, ['입찰마감일시', '입찰종료일시'])),
                bid_open_date=parse_date(self._get_field_value(data, ['개찰일시', '개찰시작일시'])),
                contract_period_start=parse_date(self._get_field_value(data, ['계약기간 시작일', '계약시작일'])),
                contract_period_end=parse_date(self._get_field_value(data, ['계약기간 종료일', '계약종료일'])),
                delivery_date=parse_date(self._get_field_value(data, ['납품기한', '납품일'])),
                site_visit_date=parse_date(self._get_field_value(data, ['현장설명일시'])),
                site_visit_place=self._get_field_value(data, ['현장설명장소']),
                bid_deposit=self._get_field_value(data, ['입찰보증금', '입찰보증금률']),
                performance_deposit=self._get_field_value(data, ['계약이행보증금', '이행보증금률']),
                warranty_deposit=self._get_field_value(data, ['하자보수보증금', '하자보증금률']),
                bid_place=self._get_field_value(data, ['입찰장소'])
            )
        except Exception as e:
            logger.warning(f"입찰진행정보 추출 중 오류: {str(e)}")
            return None
            
    def _extract_price_info(self, soup: BeautifulSoup) -> Optional[BidPriceInfo]:
        """가격 부문 정보 추출"""
        try:
            # 가격 부문 섹션 찾기
            section_selectors = [
                'div.section:contains("가격부문")',
                'div.section:contains("가격정보")',
                'div.section:contains("예가정보")',
                'table[summary*="가격"]',
                'h4:contains("예가") + table',
                'h4:contains("가격") + table'
            ]
            
            # 데이터 저장 딕셔너리
            data = {}
            
            # 각 선택자 시도
            for selector in section_selectors:
                section = soup.select_one(selector)
                if section:
                    # 테이블 형식 데이터 추출
                    if section.name == 'table':
                        table_data = self._extract_table_data(section, 'self')
                    else:
                        table_data = self._extract_table_data(section, 'table')
                        
                    if table_data:
                        data.update(table_data)
            
            # 추정가격이 없는 경우 전체 텍스트에서 추출 시도
            estimated_price = self._get_field_value(data, ['추정가격', '예상가격'])
            if not estimated_price:
                for selector in section_selectors:
                    section = soup.select_one(selector)
                    if section:
                        text = section.get_text()
                        # 추정가격 패턴 매칭
                        match = re.search(r'추정가격[^\d]*?(\d[\d,\.]+)(?:원|만원|백만원|천원)', text)
                        if match:
                            estimated_price = match.group(1)
                            break
            
            # 필드 매핑 및 BidPriceInfo 객체 생성
            return BidPriceInfo(
                estimated_price=estimated_price,
                base_price=self._get_field_value(data, ['기초금액', '기초예비가격']),
                announced_price=self._get_field_value(data, ['예정가격', '예정가격공개']),
                bid_unit=self._get_field_value(data, ['입찰단위', '단위']),
                price_adjustment=self._get_field_value(data, ['물가변동 조정방법', '물가변동']),
                standard_market_price=self._get_field_value(data, ['시장단가', '표준시장단가']),
                bid_unit_price=self._get_field_value(data, ['단가입찰여부', '단가입찰']),
                low_price_limit=self._get_field_value(data, ['낮은투찰 제한', '낮은가격']),
                payment_method=self._get_field_value(data, ['대가지급방법', '지급방법']),
                payment_timing=self._get_field_value(data, ['지급시기', '지급기한'])
            )
        except Exception as e:
            logger.warning(f"가격 부문 정보 추출 중 오류: {str(e)}")
            return None
            
    def _extract_agency_contact(self, soup: BeautifulSoup) -> Optional[BidContact]:
        """기관담당자 정보 추출"""
        return self._extract_contact_info(soup, ['기관담당자', '담당자'])
            
    def _extract_demand_agency_contact(self, soup: BeautifulSoup) -> Optional[BidContact]:
        """수요기관 담당자 정보 추출"""
        return self._extract_contact_info(soup, ['수요기관', '수요기관 담당자'])
        
    def _extract_contact_info(self, soup: BeautifulSoup, keywords: List[str]) -> Optional[BidContact]:
        """담당자 정보 추출 (공통 로직)"""
        try:
            # 섹션 찾기
            section_selectors = []
            for keyword in keywords:
                section_selectors.extend([
                    f'div.section:contains("{keyword}")',
                    f'table[summary*="{keyword}"]',
                    f'h4:contains("{keyword}") + table'
                ])
            
            # 데이터 저장 딕셔너리
            data = {}
            
            # 각 선택자 시도
            for selector in section_selectors:
                section = soup.select_one(selector)
                if section:
                    # 테이블 형식 데이터 추출
                    if section.name == 'table':
                        table_data = self._extract_table_data(section, 'self')
                    else:
                        table_data = self._extract_table_data(section, 'table')
                        
                    if table_data:
                        data.update(table_data)
                        break  # 하나의 섹션에서 데이터를 찾으면 종료
            
            # 필드 매핑 및 BidContact 객체 생성
            if data:
                return BidContact(
                    name=self._get_field_value(data, ['담당자명', '담당자', '성명']),
                    department=self._get_field_value(data, ['부서', '부서명']),
                    position=self._get_field_value(data, ['직위', '직책']),
                    phone=self._get_field_value(data, ['전화번호', '연락처', '전화']),
                    email=self._get_field_value(data, ['이메일', '메일']),
                    fax=self._get_field_value(data, ['팩스', '팩스번호']),
                    address=self._get_field_value(data, ['주소', '소재지']),
                    note=self._get_field_value(data, ['비고', '기타'])
                )
            
            return None
        except Exception as e:
            logger.warning(f"담당자 정보 추출 중 오류: {str(e)}")
            return None
            
    def _extract_attachments(self, soup: BeautifulSoup) -> List[BidAttachment]:
        """첨부파일 정보 추출"""
        attachments = []
        
        try:
            # 첨부파일 섹션 찾기
            section_selectors = [
                'div.section:contains("첨부파일")',
                'div.fileList',
                'table[summary*="첨부파일"]',
                'h4:contains("첨부파일") + div',
                'table.attFileList',
                'div.fileDown',
                'a[href*="fileDown"]'
            ]
            
            # 각 선택자 시도
            for selector in section_selectors:
                elements = soup.select(selector)
                
                for element in elements:
                    # 링크 추출
                    links = element.select('a[href]')
                    
                    for link in links:
                        href = link.get('href', '')
                        # 다운로드 링크인지 확인
                        if ('fileDown' in href or 'download' in href or 'atchFileId' in href or 
                            '.hwp' in href or '.pdf' in href or '.doc' in href or '.xls' in href):
                            
                            file_name = link.get_text().strip()
                            if not file_name:
                                # href에서 파일명 추출 시도
                                file_name_match = re.search(r'fileName=([^&]+)', href)
                                if file_name_match:
                                    file_name = file_name_match.group(1)
                                else:
                                    file_name = f"첨부파일_{len(attachments) + 1}"
                            
                            # 파일 크기 추출 시도
                            file_size = None
                            size_elem = link.find_next('span')
                            if size_elem:
                                size_text = size_elem.get_text().strip()
                                if 'KB' in size_text or 'MB' in size_text:
                                    file_size = size_text
                            
                            # 상대 경로를 절대 경로로 변환
                            if href.startswith('/'):
                                href = f"https://www.g2b.go.kr{href}"
                            
                            attachment = BidAttachment(
                                file_name=file_name,
                                file_url=href,
                                file_size=file_size
                            )
                            
                            # 중복 첨부파일 제외
                            if not any(a.file_name == file_name for a in attachments):
                                attachments.append(attachment)
        except Exception as e:
            logger.warning(f"첨부파일 정보 추출 중 오류: {str(e)}")
        
        return attachments
        
    async def download_attachment(self, attachment: BidAttachment) -> bool:
        """첨부파일 다운로드"""
        if not attachment.file_url:
            logger.warning(f"다운로드 URL이 없음: {attachment.file_name}")
            return False
            
        try:
            # HTTP 세션 초기화
            await self.initialize_session()
            
            # 파일 확장자 확인
            file_ext = os.path.splitext(attachment.file_name)[-1].lower()
            if not file_ext:
                file_ext = '.bin'
                
            # 저장 경로
            safe_filename = re.sub(r'[^\w\.-]', '_', attachment.file_name)
            file_path = self.download_path / safe_filename
            
            # 이미 다운로드된 파일인지 확인
            if os.path.exists(file_path):
                logger.info(f"이미 다운로드된 파일: {safe_filename}")
                attachment.downloaded = True
                return True
                
            # 쿠키 가져오기 (Selenium이 있는 경우)
            cookies = {}
            if self.driver:
                selenium_cookies = self.driver.get_cookies()
                for cookie in selenium_cookies:
                    cookies[cookie['name']] = cookie['value']
            
            # 파일 다운로드
            logger.info(f"첨부파일 다운로드 시작: {attachment.file_name}")
            async with self.session.get(attachment.file_url, cookies=cookies) as response:
                if response.status == 200:
                    data = await response.read()
                    
                    # 파일 저장
                    async with aiofiles.open(file_path, 'wb') as f:
                        await f.write(data)
                        
                    logger.info(f"첨부파일 다운로드 완료: {attachment.file_name} ({len(data)} bytes)")
                    attachment.downloaded = True
                    return True
                else:
                    logger.warning(f"첨부파일 다운로드 실패 (상태 코드: {response.status}): {attachment.file_name}")
                    return False
                    
        except Exception as e:
            logger.error(f"첨부파일 다운로드 중 오류: {str(e)}")
            return False
            
    async def process_attachment(self, attachment: BidAttachment) -> bool:
        """첨부파일 처리 (다운로드 및 텍스트 추출)"""
        # 이미 처리된 경우 건너뛰기
        if attachment.processed:
            return True
            
        # 다운로드 시도
        if not attachment.downloaded:
            download_success = await self.download_attachment(attachment)
            if not download_success:
                return False
                
        try:
            # 파일명 정규화
            safe_filename = re.sub(r'[^\w\.-]', '_', attachment.file_name)
            file_path = self.download_path / safe_filename
            
            # 파일 확장자 확인
            file_ext = os.path.splitext(safe_filename)[-1].lower()
            
            # 확장자에 따라 텍스트 추출 로직 구현
            # 이 부분은 docpro.py의 로직을 활용하여 구현해야 함
            # 현재는 간단히 파일 크기만 저장
            file_size = os.path.getsize(file_path)
            attachment.file_size = f"{file_size / 1024:.1f} KB"
            
            # 처리 완료 표시
            attachment.processed = True
            return True
            
        except Exception as e:
            logger.error(f"첨부파일 처리 중 오류: {str(e)}")
            return False
            
# 모듈 단일 인스턴스 제공
detail_extractor = DetailExtractor() 