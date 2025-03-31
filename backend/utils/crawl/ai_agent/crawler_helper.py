"""
크롤러 헬퍼 모듈

이 모듈은 AI 에이전트 크롤러에서 사용하는 유틸리티 함수를 제공합니다.
"""

import os
import base64
import json
import asyncio
import random
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from pathlib import Path
import re

# 셀레니움 관련 라이브러리
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# 이미지 처리
from PIL import Image
import io

# 내부 모듈
from ..utils.logger import CrawlLogger
from ..core.models import BidItem, BidDetail, AgentStatusLevel

# 로거 설정
logger = CrawlLogger("crawler_helper", debug=True)


async def take_screenshot(driver, full_page=False):
    """
    웹 페이지 스크린샷 촬영
    
    Args:
        driver: 셀레니움 웹드라이버
        full_page: 전체 페이지 스크린샷 여부
    
    Returns:
        base64로 인코딩된 이미지 데이터
    """
    try:
        if full_page:
            # 전체 페이지 스크린샷
            original_size = driver.get_window_size()
            required_width = driver.execute_script('return document.body.parentNode.scrollWidth')
            required_height = driver.execute_script('return document.body.parentNode.scrollHeight')
            
            driver.set_window_size(required_width, required_height)
            await asyncio.sleep(0.5)  # 크기 조정 후 대기
            
            # 스크린샷 촬영
            screenshot = driver.get_screenshot_as_png()
            
            # 원래 크기로 복원
            driver.set_window_size(original_size['width'], original_size['height'])
        else:
            # 현재 화면 스크린샷
            screenshot = driver.get_screenshot_as_png()
        
        # 이미지 처리 (크기 조정)
        image = Image.open(io.BytesIO(screenshot))
        
        # 최대 크기 제한 (Gemini API 요구사항)
        max_width, max_height = 1600, 1600
        if image.width > max_width or image.height > max_height:
            # 비율 유지하면서 크기 조정
            ratio = min(max_width / image.width, max_height / image.height)
            new_width = int(image.width * ratio)
            new_height = int(image.height * ratio)
            image = image.resize((new_width, new_height), Image.LANCZOS)
        
        # 이미지를 base64로 인코딩
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=90)
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        return img_base64
    
    except Exception as e:
        logger.error(f"스크린샷 촬영 중 오류: {str(e)}")
        return None


async def parse_element_location(response_text: str) -> Dict[str, Any]:
    """
    AI 응답에서 요소 위치 정보 추출
    
    Args:
        response_text: AI 응답 텍스트
    
    Returns:
        요소 위치 정보 딕셔너리 (ID, XPath, CSS 선택자 등)
    """
    try:
        # JSON 형식으로 응답이 온 경우
        try:
            # JSON 블록 찾기
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
            if json_match:
                json_str = json_match.group(1)
                data = json.loads(json_str)
                return data
        except:
            pass
        
        # XPath 추출
        xpaths = re.findall(r'XPath[:\s]+(["\'])(\/\/.*?)\1', response_text, re.IGNORECASE)
        xpaths.extend(re.findall(r'XPath[:\s]+(\/\/.*?)(?:\s|$)', response_text, re.IGNORECASE))
        
        # ID 추출
        id_matches = re.findall(r'ID[:\s]+["\']?([a-zA-Z0-9_-]+)["\']?', response_text, re.IGNORECASE)
        
        # CSS 선택자 추출
        css_matches = re.findall(r'CSS[:\s]+(["\'])(.*?)\1', response_text, re.IGNORECASE)
        css_matches.extend(re.findall(r'CSS Selector[:\s]+(["\'])(.*?)\1', response_text, re.IGNORECASE))
        
        # 클래스 추출
        class_matches = re.findall(r'class[:\s]+["\']?([a-zA-Z0-9_\s-]+)["\']?', response_text, re.IGNORECASE)
        
        result = {}
        
        if xpaths:
            result["xpaths"] = [xpath[1] if isinstance(xpath, tuple) else xpath for xpath in xpaths]
        if id_matches:
            result["id"] = id_matches[0]
        if css_matches:
            result["css"] = css_matches[0][1] if css_matches and isinstance(css_matches[0], tuple) else css_matches[0]
        if class_matches:
            result["class"] = class_matches[0]
        
        return result
    
    except Exception as e:
        logger.error(f"요소 위치 정보 추출 중 오류: {str(e)}")
        return {}


async def extract_table_data(response_text: str) -> List[Dict[str, Any]]:
    """
    AI 응답에서 테이블 데이터 추출
    
    Args:
        response_text: AI 응답 텍스트
    
    Returns:
        추출된 테이블 데이터 목록
    """
    try:
        # JSON 형식으로 응답이 온 경우
        try:
            # JSON 블록 찾기
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
            if json_match:
                json_str = json_match.group(1)
                data = json.loads(json_str)
                
                # 목록인 경우 그대로 반환
                if isinstance(data, list):
                    return data
                
                # items 키가 있는 경우
                if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
                    return data["items"]
                
                # 목록이 아닌 경우 목록으로 변환
                return [data]
        except Exception as e:
            logger.error(f"JSON 추출 중 오류: {str(e)}")
        
        # 텍스트에서 행 분리
        lines = response_text.split('\n')
        items = []
        
        current_item = {}
        for line in lines:
            # 키-값 패턴 찾기
            kv_match = re.match(r'^\s*(?:-\s*)?([A-Za-z가-힣_]+)[\s:]+(.+)$', line)
            if kv_match:
                key, value = kv_match.groups()
                key = key.strip().lower()
                value = value.strip()
                
                # 키 변환 (영문화)
                key_mapping = {
                    "입찰공고번호": "bid_id",
                    "공고번호": "bid_id",
                    "번호": "bid_id",
                    "제목": "title",
                    "공고명": "title",
                    "링크": "url",
                    "url": "url",
                    "발주처": "organization",
                    "기관": "organization",
                    "기관명": "organization",
                    "지역": "location",
                    "공고일": "reg_date",
                    "등록일": "reg_date",
                    "마감일": "close_date",
                    "마감일시": "close_date",
                    "가격": "price",
                    "예산": "price",
                    "예정가격": "price",
                    "상태": "status",
                }
                
                mapped_key = key_mapping.get(key, key)
                current_item[mapped_key] = value
            
            # 빈 줄이면 새 항목 시작
            elif line.strip() == "" and current_item:
                if "bid_id" in current_item and "title" in current_item:
                    items.append(current_item)
                current_item = {}
        
        # 마지막 항목 추가
        if current_item and "bid_id" in current_item and "title" in current_item:
            items.append(current_item)
        
        return items
    
    except Exception as e:
        logger.error(f"테이블 데이터 추출 중 오류: {str(e)}")
        return []


async def extract_detail_data(response_text: str) -> Dict[str, Any]:
    """
    AI 응답에서 상세 정보 데이터 추출
    
    Args:
        response_text: AI 응답 텍스트
    
    Returns:
        추출된 상세 정보 데이터
    """
    try:
        # JSON 형식으로 응답이 온 경우
        try:
            # JSON 블록 찾기
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
            if json_match:
                json_str = json_match.group(1)
                return json.loads(json_str)
        except Exception as e:
            logger.error(f"JSON 추출 중 오류: {str(e)}")
        
        # 텍스트에서 키-값 패턴 찾기
        detail_data = {}
        lines = response_text.split('\n')
        
        for line in lines:
            # 키-값 패턴 찾기
            kv_match = re.match(r'^\s*(?:-\s*)?([A-Za-z가-힣_]+)[\s:]+(.+)$', line)
            if kv_match:
                key, value = kv_match.groups()
                key = key.strip().lower()
                value = value.strip()
                
                # 키 변환 (영문화)
                key_mapping = {
                    "입찰공고번호": "bid_id",
                    "공고번호": "bid_id",
                    "제목": "title",
                    "공고명": "title",
                    "발주처": "organization",
                    "기관": "organization",
                    "기관명": "organization",
                    "부서": "division",
                    "담당부서": "division",
                    "지역": "location",
                    "공고일": "reg_date",
                    "등록일": "reg_date",
                    "마감일": "close_date",
                    "마감일시": "close_date",
                    "예정가격": "estimated_price",
                    "추정가격": "estimated_price",
                    "계약방식": "contract_type",
                    "계약방법": "contract_type",
                    "입찰유형": "bid_type",
                    "입찰방식": "bid_type",
                    "업종": "industry",
                    "업종제한": "industry",
                    "설명": "description",
                    "세부내용": "description",
                    "요구사항": "requirements",
                    "첨부파일": "attachments",
                    "연락처": "contact_info",
                }
                
                mapped_key = key_mapping.get(key, key)
                detail_data[mapped_key] = value
        
        return detail_data
    
    except Exception as e:
        logger.error(f"상세 정보 데이터 추출 중 오류: {str(e)}")
        return {}


async def find_navigation_elements(driver, wait, page_num=None):
    """
    페이지 네비게이션 요소 찾기
    
    Args:
        driver: 셀레니움 웹드라이버
        wait: 셀레니움 웨이트
        page_num: 이동할 페이지 번호 (None이면 다음 페이지)
    
    Returns:
        페이지 네비게이션 요소 또는 None
    """
    try:
        # 다음 페이지 버튼 찾기 (일반적인 방법)
        if page_num is None:
            # 다음 페이지 버튼
            selectors = [
                (By.XPATH, "//a[contains(text(), '다음') or contains(@title, '다음') or contains(@class, 'next')]"),
                (By.XPATH, "//img[contains(@alt, '다음') or contains(@alt, '다음 페이지')]"),
                (By.XPATH, "//a[contains(@onclick, 'next') or contains(@href, 'next')]"),
                (By.XPATH, "//button[contains(text(), '다음') or contains(@title, '다음')]"),
            ]
        else:
            # 특정 페이지 버튼
            selectors = [
                (By.XPATH, f"//a[contains(text(), '{page_num}') or @title='{page_num}']"),
                (By.XPATH, f"//span[contains(text(), '{page_num}')]"),
                (By.XPATH, f"//button[contains(text(), '{page_num}')]"),
            ]
        
        for by, selector in selectors:
            try:
                elements = driver.find_elements(by, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        return element
            except:
                continue
        
        return None
    
    except Exception as e:
        logger.error(f"페이지 네비게이션 요소 찾기 중 오류: {str(e)}")
        return None


async def navigate_to_page(driver, wait, page_num=None):
    """
    특정 페이지로 이동
    
    Args:
        driver: 셀레니움 웹드라이버
        wait: 셀레니움 웨이트
        page_num: 이동할 페이지 번호 (None이면 다음 페이지)
    
    Returns:
        이동 성공 여부
    """
    try:
        # 페이지 네비게이션 요소 찾기
        nav_element = await find_navigation_elements(driver, wait, page_num)
        
        if nav_element:
            # 요소가 화면에 보이도록 스크롤
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", nav_element)
            await asyncio.sleep(random.uniform(0.3, 0.7))
            
            # 요소 클릭
            nav_element.click()
            await asyncio.sleep(random.uniform(1.5, 2.5))
            return True
        
        return False
    
    except Exception as e:
        logger.error(f"페이지 이동 중 오류: {str(e)}")
        return False


async def save_screenshot(driver, folder_path, filename, full_page=False):
    """
    스크린샷 저장
    
    Args:
        driver: 셀레니움 웹드라이버
        folder_path: 저장 폴더 경로
        filename: 파일명
        full_page: 전체 페이지 스크린샷 여부
    
    Returns:
        저장된 파일 경로
    """
    try:
        # 폴더 생성
        os.makedirs(folder_path, exist_ok=True)
        
        # 파일 경로 생성
        file_path = os.path.join(folder_path, f"{filename}.jpg")
        
        # 스크린샷 촬영
        if full_page:
            # 전체 페이지 스크린샷
            original_size = driver.get_window_size()
            required_width = driver.execute_script('return document.body.parentNode.scrollWidth')
            required_height = driver.execute_script('return document.body.parentNode.scrollHeight')
            
            driver.set_window_size(required_width, required_height)
            await asyncio.sleep(0.5)  # 크기 조정 후 대기
            
            # 스크린샷 촬영
            screenshot = driver.get_screenshot_as_png()
            
            # 원래 크기로 복원
            driver.set_window_size(original_size['width'], original_size['height'])
        else:
            # 현재 화면 스크린샷
            screenshot = driver.get_screenshot_as_png()
        
        # 이미지 저장
        image = Image.open(io.BytesIO(screenshot))
        image.save(file_path, "JPEG", quality=90)
        
        return file_path
    
    except Exception as e:
        logger.error(f"스크린샷 저장 중 오류: {str(e)}")
        return None


async def create_bid_item(item_data: Dict[str, Any], keyword: Optional[str] = None) -> BidItem:
    """
    입찰 항목 객체 생성
    
    Args:
        item_data: 입찰 항목 데이터
        keyword: 검색 키워드
    
    Returns:
        BidItem 객체
    """
    try:
        # URL 처리 (상대 경로인 경우 절대 경로로 변환)
        url = item_data.get("url", "")
        if url and not url.startswith(("http://", "https://")):
            if url.startswith("/"):
                url = f"https://www.g2b.go.kr{url}"
            else:
                url = f"https://www.g2b.go.kr/{url}"
        
        # BidItem 객체 생성
        bid_item = BidItem(
            bid_id=item_data.get("bid_id", ""),
            title=item_data.get("title", ""),
            url=url,
            organization=item_data.get("organization"),
            location=item_data.get("location"),
            bid_type=item_data.get("bid_type"),
            reg_date=item_data.get("reg_date"),
            close_date=item_data.get("close_date"),
            price=item_data.get("price"),
            status=item_data.get("status"),
            keyword=keyword,
            details=item_data,
            crawled_at=datetime.now()
        )
        
        return bid_item
    
    except Exception as e:
        logger.error(f"입찰 항목 객체 생성 중 오류: {str(e)}")
        raise 