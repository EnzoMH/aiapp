"""
나라장터 웹사이트 크롤러 모듈

이 모듈은 국가종합전자조달 나라장터 웹사이트의 입찰공고를 수집하는 크롤러를 구현합니다.
Selenium과 Chrome 웹드라이버를 사용하여 웹 페이지를 자동으로 탐색하고 데이터를 추출합니다.
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    StaleElementReferenceException,
    ElementClickInterceptedException
)
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

import os
import time
import logging
import json
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
import asyncio
import chromedriver_autoinstaller

from backend.utils.crawl.models import BidItem, SearchValidator, BidStatus

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("crawler.log", mode="a", encoding="utf-8")
    ]
)
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

class G2BCrawler:
    """나라장터 크롤러 클래스"""
    
    def __init__(self, headless: bool = True):
        """
        크롤러 초기화
        
        Args:
            headless (bool): 헤드리스 모드 사용 여부 (기본값: True)
        """
        self.base_url = "https://www.g2b.go.kr"
        self.driver = None
        self.wait = None
        self.headless = headless
        self.results = []
        
        # 추가 필드
        self.all_results = []  # 모든 결과 저장
        self.processed_keywords = set()  # 처리된 키워드 추적
        self.last_save_time = datetime.now()  # 마지막 저장 시간 추적
        self.save_interval = 300  # 저장 간격 (초 단위, 5분)
        self.validator = SearchValidator()  # 검증 및 정제 객체
        
    async def initialize(self):
        """크롤러 초기화 및 웹드라이버 설정"""
        try:
            # 웹드라이버 설정
            await self._setup_driver()
            return True
        except Exception as e:
            logger.error(f"크롤러 초기화 실패: {str(e)}")
            return False
    
    async def _setup_driver(self):
        """웹드라이버 설정"""
        logger.info("Chrome 웹드라이버 설정 중...")
        
        # ChromeDriver 자동 설치 및 설정
        chrome_ver = chromedriver_autoinstaller.get_chrome_version().split('.')[0]
        try:
            chromedriver_autoinstaller.install(True)
        except Exception as e:
            logger.warning(f"ChromeDriver 자동 설치 실패: {str(e)}. 기본 경로 사용 시도.")
            
        # 크롬 옵션 설정
        chrome_options = Options()
        
        # 헤드리스 모드 설정 (선택적)
        if self.headless:
            chrome_options.add_argument('--headless=new')
            
        # 기타 기본 옵션 설정
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-popup-blocking')
        
        # 최신 크롬 user agent 설정
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        
        # 웹드라이버 초기화
        try:
            # 자동 설치된 크롬드라이버 사용
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 10)
            logger.info("Chrome 웹드라이버 초기화 성공")
        except Exception as e:
            logger.error(f"Chrome 웹드라이버 초기화 실패: {str(e)}")
            raise
    
    async def close(self):
        """웹드라이버 종료 및 리소스 정리"""
        if self.driver:
            try:
                logger.info("웹드라이버 종료 시작")
                # 열려있는 모든 팝업창 닫기 시도
                try:
                    main_window = self.driver.current_window_handle
                    for handle in self.driver.window_handles:
                        if handle != main_window:
                            self.driver.switch_to.window(handle)
                            self.driver.close()
                    self.driver.switch_to.window(main_window)
                except Exception as e:
                    logger.warning(f"팝업창 닫기 중 오류 (무시): {str(e)}")
                
                # 드라이버 종료
                self.driver.quit()
                logger.info("웹드라이버 종료 완료")
            except Exception as e:
                logger.error(f"웹드라이버 종료 중 오류: {str(e)}")
            finally:
                # 참조 제거
                self.driver = None
                self.wait = None
    
    async def navigate_to_main(self):
        """나라장터 메인 페이지로 이동"""
        try:
            logger.info(f"나라장터 메인 페이지 접속 중: {self.base_url}")
            self.driver.get(self.base_url)
            
            # 페이지 로딩 대기
            await asyncio.sleep(3)
            
            # 팝업창 닫기
            await self._close_popups()
            
            return True
        except Exception as e:
            logger.error(f"메인 페이지 접속 실패: {str(e)}")
            return False
    
    async def _close_popups(self):
        """팝업창 닫기"""
        try:
            # 모든 팝업창 탐색 및 닫기
            logger.info("팝업창 닫기 시도 중...")
            
            # 메인 윈도우 핸들 저장
            main_window = self.driver.current_window_handle
            
            # 모든 윈도우 핸들 가져오기
            all_windows = self.driver.window_handles
            
            # 팝업 윈도우 닫기
            popup_count = 0
            for window in all_windows:
                if window != main_window:
                    self.driver.switch_to.window(window)
                    self.driver.close()
                    popup_count += 1
                    logger.info(f"윈도우 팝업 닫기 성공 ({popup_count})")
            
            if popup_count > 0:
                logger.info(f"총 {popup_count}개의 윈도우 팝업을 닫았습니다.")
            
            # 메인 윈도우로 복귀
            self.driver.switch_to.window(main_window)
            
            # 나라장터 특정 팝업창 닫기 (공지사항 등)
            try:
                # 제공된 XPath 기반으로 닫기 버튼 찾기
                popup_close_buttons = []
                
                # 팝업 확인을 위한 다양한 방법 시도 (순서 중요)
                
                # 1. WebDriverWait로 팝업 창 닫기 버튼을 명시적으로 찾아보기
                try:
                    # 공지사항 팝업 닫기 (가장 일반적인 팝업)
                    notice_close = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, "//div[contains(@class,'w2window')]//button[contains(@class,'w2window_close')]"))
                    )
                    notice_close.click()
                    logger.info("공지사항 팝업 닫기 성공")
                    await asyncio.sleep(0.5)
                except Exception:
                    logger.debug("공지사항 팝업이 없거나 닫기 실패")
                
                # 2. 일반적인 닫기 버튼 선택자
                popup_close_buttons.extend(self.driver.find_elements(By.CSS_SELECTOR, ".w2window_close, .close, [aria-label='창닫기'], .popup_close"))
                
                # 3. 나라장터 특정 공지사항 팝업 닫기 버튼
                popup_close_buttons.extend(self.driver.find_elements(By.XPATH, "//button[contains(@id, 'poupR') and contains(@id, '_close')]"))
                popup_close_buttons.extend(self.driver.find_elements(By.XPATH, "//button[contains(@class, 'w2window_close_acc') and @aria-label='창닫기']"))
                
                # 4. ID 패턴 기반 닫기 버튼 찾기
                popup_close_buttons.extend(self.driver.find_elements(By.CSS_SELECTOR, "[id*='poupR'][id$='_close']"))
                
                # 5. iframe 내부 팝업 처리
                iframe_elements = self.driver.find_elements(By.TAG_NAME, "iframe")
                for iframe in iframe_elements:
                    try:
                        iframe_id = iframe.get_attribute("id")
                        if iframe_id:
                            logger.debug(f"iframe 확인: {iframe_id}")
                            self.driver.switch_to.frame(iframe)
                            iframe_close_buttons = self.driver.find_elements(By.CSS_SELECTOR, ".close, .popup_close, [aria-label='창닫기']")
                            for btn in iframe_close_buttons:
                                popup_close_buttons.append(btn)
                            self.driver.switch_to.default_content()
                    except Exception as iframe_err:
                        logger.debug(f"iframe 접근 실패 (무시): {str(iframe_err)}")
                        self.driver.switch_to.default_content()
                
                # 찾은 모든 버튼 클릭 시도
                closed_count = 0
                for button in popup_close_buttons:
                    try:
                        button_id = button.get_attribute('id') or "알 수 없음"
                        logger.info(f"팝업 닫기 버튼 발견 (ID: {button_id}), 클릭 시도...")
                        button.click()
                        closed_count += 1
                        logger.info(f"페이지 내 팝업창 닫기 성공: {button_id}")
                        await asyncio.sleep(0.5)  # 약간의 지연
                    except Exception as e:
                        logger.debug(f"팝업 버튼 클릭 실패 (무시): {str(e)}")
                
                if closed_count > 0:
                    logger.info(f"총 {closed_count}개의 페이지 내 팝업창을 닫았습니다.")
                
                # ESC 키를 눌러 혹시 남은 팝업 닫기 시도
                try:
                    logger.debug("ESC 키를 눌러 나머지 팝업 닫기 시도")
                    actions = ActionChains(self.driver)
                    actions.send_keys(Keys.ESCAPE).perform()
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.debug(f"ESC 키 입력 실패 (무시): {str(e)}")
                
                # 메인 컨텐츠 영역 클릭해서 포커스 주기
                try:
                    main_content = self.driver.find_element(By.ID, "container")
                    main_content.click()
                    logger.debug("메인 컨텐츠 영역 포커스 설정")
                except Exception:
                    try:
                        # 대체 방법: 본문 영역 클릭
                        body = self.driver.find_element(By.TAG_NAME, "body")
                        body.click()
                        logger.debug("본문 영역 포커스 설정")
                    except Exception:
                        pass
                
            except Exception as e:
                logger.warning(f"페이지 내 팝업창 닫기 실패 (무시 가능): {str(e)}")
                
        except Exception as e:
            logger.warning(f"팝업창 닫기 중 오류 (계속 진행): {str(e)}")
    
    async def navigate_to_bid_list(self):
        """입찰공고 목록 페이지로 이동"""
        try:
            logger.info("입찰공고 목록 페이지로 이동 중...")
            
            for attempt in range(3):  # 최대 3번 시도
                try:
                    # 페이지 안정화를 위한 짧은 대기
                    await asyncio.sleep(1)
                    
                    # 먼저 탭이나 메뉴가 접혀있는지 확인하고 펼치기
                    try:
                        # 1. URL로 직접 이동 시도 (대체방법)
                        if attempt > 0:  # 첫 번째 시도 실패 후 URL 직접 이동 시도
                            logger.info("URL을 통한 직접 이동 시도")
                            self.driver.get("https://www.g2b.go.kr:8101/ep/tbid/tbidList.do?taskClCd=5")
                            await asyncio.sleep(3)
                            return True
                        
                        # 2. 일반 탐색 방법
                        # '입찰' 메뉴 클릭 (javasciprt 실행으로 시도)
                        try:
                            logger.debug("'입찰' 메뉴 클릭 시도 (JS)")
                            self.driver.execute_script("javascript:clickMenuLvl1('01','mf_wfm_gnb_wfm_gnbMenu');")
                            await asyncio.sleep(1)
                        except Exception:
                            logger.debug("JS 실행 실패, 요소 직접 클릭 시도")
                            # 직접 요소 클릭 시도
                            bid_menu = WebDriverWait(self.driver, 5).until(
                                EC.element_to_be_clickable((By.ID, "mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_btn_menuLvl1_span"))
                            )
                            bid_menu.click()
                            await asyncio.sleep(1)
                    
                        # '입찰공고목록' 클릭 (javasciprt 실행으로 시도)
                        try:
                            logger.debug("'입찰공고목록' 클릭 시도 (JS)")
                            self.driver.execute_script("javascript:clickMenuLvl3('0101','mf_wfm_gnb_wfm_gnbMenu');")
                            await asyncio.sleep(3)
                        except Exception:
                            logger.debug("JS 실행 실패, 요소 직접 클릭 시도")
                            bid_list = WebDriverWait(self.driver, 5).until(
                                EC.element_to_be_clickable((By.ID, "mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_genDepth2_0_genDepth3_0_btn_menuLvl3_span"))
                            )
                            bid_list.click()
                            await asyncio.sleep(3)
                        
                        # 3. 페이지 상태 확인
                        # 입찰공고목록 페이지 확인 (검색 버튼이 있는지)
                        try:
                            search_button = WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_btnS0004"))
                            )
                            logger.info("입찰공고 목록 페이지 이동 성공")
                            return True
                        except Exception:
                            logger.warning(f"페이지 확인 실패 (재시도 {attempt+1}/3)")
                            continue
                            
                    except Exception as inner_e:
                        logger.warning(f"탐색 시도 {attempt+1}/3 실패: {str(inner_e)}")
                        if attempt == 2:  # 마지막 시도에서도 실패
                            raise
                        continue
                
                except Exception as retry_e:
                    logger.warning(f"입찰공고 목록 페이지 이동 시도 {attempt+1}/3 실패: {str(retry_e)}")
                    if attempt == 2:  # 마지막 시도에서도 실패
                        raise
                    # 페이지 새로고침 후 재시도
                    self.driver.refresh()
                    await asyncio.sleep(3)
                    await self._close_popups()  # 팝업창 다시 닫기
            
            # 모든 시도 실패
            raise Exception("3번의 시도 후에도 입찰공고 목록 페이지 이동 실패")
        
        except Exception as e:
            logger.error(f"입찰공고 목록 페이지 이동 실패: {str(e)}")
            return False
    
    async def setup_search_conditions(self):
        """검색 조건 설정"""
        try:
            logger.info("검색 조건 설정 중...")
            
            # 탭 선택 (검색조건 탭이 있는 경우)
            try:
                tab_element = self.driver.find_element(By.CSS_SELECTOR, ".tab_wrap li:nth-child(2) a")
                tab_element.click()
                await asyncio.sleep(1)
            except NoSuchElementException:
                logger.info("검색조건 탭을 찾을 수 없습니다. 계속 진행합니다.")
            
            # '입찰마감제외' 체크박스 클릭
            try:
                checkbox = self.driver.find_element(By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_chkSlprRcptDdlnYn_input_0")
                if not checkbox.is_selected():
                    checkbox.click()
                    logger.info("'입찰마감제외' 체크박스 선택 완료")
            except Exception as e:
                logger.warning(f"'입찰마감제외' 체크박스 선택 실패 (무시): {str(e)}")
            
            # 보기 개수 설정 (100개)
            try:
                select_element = self.driver.find_element(By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_sbxRecordCountPerPage1")
                select = Select(select_element)
                select.select_by_visible_text("100")
                logger.info("보기 개수 100개로 설정 완료")
            except Exception as e:
                logger.warning(f"보기 개수 설정 실패 (무시): {str(e)}")
            
            return True
        except Exception as e:
            logger.error(f"검색 조건 설정 실패: {str(e)}")
            return False
    
    async def search_keyword(self, keyword: str) -> List[Dict]:
        """키워드로 검색 수행"""
        results = []
        try:
            logger.info(f"'{keyword}' 키워드 검색 시작")
            
            # 페이지 안정화를 위한 대기
            logger.debug("검색 전 페이지 안정화를 위한 대기")
            await asyncio.sleep(2)
            
            # 공고명 검색 필드 찾기 및 입력
            try:
                logger.debug("공고명 검색 필드 찾기 시도")
                bid_name_input = self.driver.find_element(By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_bidPbancNm")
                bid_name_input.clear()
                bid_name_input.send_keys(keyword)
                logger.info(f"공고명 검색 필드에 '{keyword}' 입력 완료")
                
                # 포커스 변경을 위해 탭 키 입력 (선택적)
                bid_name_input.send_keys(Keys.TAB)
                logger.debug("공고명 검색 필드에서 탭 키 입력 완료")
            except Exception as e:
                logger.warning(f"공고명 검색 필드 입력 실패 (계속 진행): {str(e)}")
                
                # 대체 방법으로 키워드 검색어 입력 필드 사용
                try:
                    logger.debug("키워드 검색어 입력 필드 찾기 시도")
                    search_input = self.driver.find_element(By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_txtNmInptKwd_inputExt")
                    search_input.clear()
                    search_input.send_keys(keyword)
                    logger.debug(f"키워드 검색어 필드에 '{keyword}' 입력 완료")
                except Exception as sub_e:
                    logger.error(f"모든 검색 필드 입력 실패: {str(sub_e)}")
                    return []
            
            # UI 업데이트를 위한 짧은 대기
            await asyncio.sleep(1)
            
            # 검색 버튼 찾기
            logger.debug("검색 버튼 찾기 시도")
            search_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_btnS0004"))
            )
            
            # 검색 버튼 클릭
            logger.debug("검색 버튼 클릭 시도")
            search_button.click()
            logger.info("검색 버튼 클릭 완료")
            
            # 결과 로딩 대기 (시간 증가)
            logger.debug("검색 결과 로딩 대기 중...")
            await asyncio.sleep(5)  # 3초에서 5초로 증가
            
            # 결과 없음 확인
            if await self._check_no_results():
                logger.info(f"'{keyword}' 키워드에 대한 검색 결과가 없습니다.")
                return []
                
            # 테이블 존재 확인
            if not await self._check_table_exists():
                logger.warning(f"'{keyword}' 키워드 검색 결과 테이블을 찾을 수 없습니다.")
                if await self.recover_page_state(keyword):
                    logger.info("페이지 복구 성공, 다시 검색 결과 확인")
                    if not await self._check_table_exists():
                        return []
                else:
                    return []
            
            # 검색 결과 행 수 확인
            total_rows = await self._get_total_rows()
            if total_rows == 0:
                logger.info(f"'{keyword}' 키워드에 대한 검색 결과가 없습니다.")
                return []
            
            logger.info(f"총 {total_rows}개의 검색 결과 발견")
            
            # 각 행의 데이터 추출 (최대 20개로 제한)
            max_rows = min(total_rows, 20)
            for row_num in range(max_rows):
                try:
                    # 기본 행 데이터 추출
                    basic_data = await self._extract_row_data(row_num)
                    if not basic_data:
                        continue
                        
                    # 데이터 구조화
                    bid_info = {
                        'search_keyword': keyword,
                        'basic_info': basic_data,
                        'detail_info': {},
                        'collected_at': datetime.now().isoformat()
                    }
                    
                    # 상세 정보 추출 (상세 정보 페이지로 이동하여 추출)
                    try:
                        detail_data = await self._safely_navigate_and_extract_detail(row_num)
                        if detail_data:
                            bid_info['detail_info'] = detail_data
                    except Exception as e:
                        logger.error(f"{row_num}번 행의 상세 정보 추출 실패: {str(e)}")
                    
                    # 결과 검증
                    if self.validator.validate_required_fields(bid_info):
                        results.append(bid_info)
                        logger.info(f"행 {row_num + 1}/{max_rows} 처리 완료: {basic_data.get('title', '제목 없음')}")
                    
                except Exception as e:
                    logger.error(f"{row_num}번 행 처리 중 오류: {str(e)}")
                    continue
            
            # 결과에 키워드 정보 추가 및 중복 제거
            if results:
                self.all_results.extend(results)
                self.processed_keywords.add(keyword)
                
                # 주기적 저장 확인
                await self._check_and_save_results()
            
            logger.info(f"'{keyword}' 키워드 검색 완료: {len(results)}건 수집")
            return results
        except Exception as e:
            logger.error(f"'{keyword}' 키워드 검색 실패: {str(e)}")
            # 스택 트레이스 로깅
            logger.error(f"스택 트레이스: {traceback.format_exc()}")
            
            # 페이지 복구 시도
            await self.recover_page_state(None)
            
            return []
    
    async def crawl_keywords(self, keywords: List[str]) -> Dict:
        """여러 키워드에 대해 크롤링 수행"""
        all_results = []
        processed_keywords = []
        failed_keywords = []
        
        try:
            # 초기화 및 메인 페이지로 이동
            if not await self.initialize():
                return {
                    "status": "error",
                    "message": "크롤러 초기화 실패",
                    "results": []
                }
            
            if not await self.navigate_to_main():
                return {
                    "status": "error",
                    "message": "메인 페이지 접속 실패",
                    "results": []
                }
            
            # 입찰공고목록 페이지로 이동
            if not await self.navigate_to_bid_list():
                return {
                    "status": "error",
                    "message": "입찰공고목록 페이지 접속 실패",
                    "results": []
                }
            
            # 검색 조건 설정
            if not await self.setup_search_conditions():
                logger.warning("검색 조건 설정 중 오류 발생 (진행 계속)")
            
            # 진행 상태 추적
            total_keywords = len(keywords)
            
            # 각 키워드에 대해 검색 수행
            for idx, keyword in enumerate(keywords, 1):
                try:
                    # 진행 상황 로깅
                    logger.info(f"\n진행 상황: {idx}/{total_keywords} ({(idx/total_keywords)*100:.1f}%)")
                    logger.info(f"\n{'='*30}\n{keyword} 검색 시작\n{'='*30}")
                    
                    # 이미 처리된 키워드 스킵
                    if keyword in self.processed_keywords:
                        logger.warning(f"키워드 '{keyword}' 이미 처리됨, 건너뜀")
                        processed_keywords.append(keyword)
                        continue
                    
                    # 페이지 상태 확인
                    if not await self._check_table_exists():
                        logger.warning("테이블이 표시되지 않음. 페이지 복구 시도")
                        if not await self.recover_page_state(None):
                            logger.error("페이지 복구 실패")
                            # 처음부터 다시 시작
                            await self.navigate_to_bid_list()
                            await self.setup_search_conditions()
                    
                    # 키워드 검색 수행
                    keyword_results = await self.search_keyword(keyword)
                    
                    # 중복 제거
                    unique_results = self.validator.remove_duplicates(keyword_results)
                    logger.info(f"중복 제거 후: {len(unique_results)}/{len(keyword_results)}건")
                    
                    # 결과 저장
                    all_results.extend(unique_results)
                    processed_keywords.append(keyword)
                    
                    logger.info(f"키워드 '{keyword}' 처리 완료 ({len(unique_results)}건)")
                    
                    # 키워드 간 대기
                    await asyncio.sleep(2)
                    
                    # 다음 키워드 검색을 위해 검색 페이지 초기화
                    if idx < total_keywords:
                        # 검색 필드 초기화
                        try:
                            bid_name_input = self.driver.find_element(By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_bidPbancNm")
                            bid_name_input.clear()
                            logger.debug("공고명 검색 필드 초기화 완료")
                        except Exception as clear_e:
                            logger.warning(f"공고명 검색 필드 초기화 실패: {str(clear_e)}")
                            
                            # 다음 키워드를 위해 새로 입찰공고 페이지로 이동
                            await self.navigate_to_bid_list()
                            await self.setup_search_conditions()
                        
                except Exception as e:
                    logger.error(f"키워드 '{keyword}' 처리 중 오류: {str(e)}")
                    failed_keywords.append(keyword)
                    
                    # 오류 발생 시 페이지 복구 시도
                    try:
                        # 페이지 새로고침 시도
                        self.driver.refresh()
                        await asyncio.sleep(3)
                        
                        # 복구 시도 후에도 실패하면 처음부터 다시 시작
                        if not await self._check_table_exists():
                            await self.navigate_to_bid_list()
                            await self.setup_search_conditions()
                    except Exception as recover_error:
                        logger.error(f"복구 중 추가 오류: {str(recover_error)}")
                        # 메인 화면부터 다시 시작
                        await self.navigate_to_main()
                        await self.navigate_to_bid_list()
                        await self.setup_search_conditions()
            
            # 최종 결과 저장
            result_filename = self.save_all_crawling_results()
            
            # 결과 요약
            result_summary = {
                "status": "success",
                "total_keywords": total_keywords,
                "processed_keywords": processed_keywords,
                "failed_keywords": failed_keywords,
                "total_results": len(all_results),
                "results": all_results,
                "result_file": result_filename
            }
            
            logger.info("크롤링 작업 완료, 결과 요약 생성")
            return result_summary
        except Exception as e:
            logger.error(f"크롤링 프로세스 중 오류: {str(e)}")
            return {
                "status": "error",
                "message": f"크롤링 프로세스 중 오류: {str(e)}",
                "processed_keywords": processed_keywords,
                "failed_keywords": failed_keywords + [k for k in keywords if k not in processed_keywords and k not in failed_keywords],
                "results": all_results
            }
        finally:
            # 작업 완료 대기
            logger.info("크롤링 작업 완료, 웹드라이버 종료 대기 중...")
            await asyncio.sleep(3)  # 드라이버 종료 전 안정화를 위한 대기
            
            # 웹드라이버 종료
            await self.close()

    def save_results(self, results: Dict, filename_prefix: str = "crawl_results") -> str:
        """결과를 JSON 파일로 저장"""
        try:
            # 결과 디렉토리 확인 및 생성
            results_dir = os.path.join("crawl", "results")
            os.makedirs(results_dir, exist_ok=True)
            
            # 파일명 생성 (날짜시간 포함)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{filename_prefix}_{timestamp}.json"
            filepath = os.path.join(results_dir, filename)
            
            # JSON 파일로 저장
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            logger.info(f"결과 저장 완료: {filepath} ({len(results['results'])}건)")
            return filepath
        except Exception as e:
            logger.error(f"결과 저장 실패: {str(e)}")
            return ""

    async def recover_page_state(self, keyword: str, retry_count=0):
        """페이지 상태 복구 시도"""
        MAX_RETRIES = 2
        table_id = "mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_dataLayer"
        
        try:
            logger.info(f"페이지 상태 복구 시도 중 (시도 {retry_count+1}/{MAX_RETRIES+1})")
            
            # 첫 번째: 뒤로가기 시도
            self.driver.back()
            await asyncio.sleep(2)
            
            try:
                table = self.wait.until(EC.presence_of_element_located((By.ID, table_id)))
                if table.is_displayed():
                    logger.info("뒤로가기로 페이지 복구 성공")
                    return True
            except Exception as e:
                logger.warning(f"뒤로가기로 복구 시도 실패: {str(e)}")
                
                if retry_count < MAX_RETRIES:
                    logger.warning(f"복구 시도 {retry_count + 1} 실패, 처음부터 다시 시도")
                    # 입찰공고 목록부터 다시 시작
                    await self.navigate_to_main()
                    await self.navigate_to_bid_list()
                    await asyncio.sleep(2)
                    
                    # 검색조건 설정
                    await self.setup_search_conditions()
                    
                    # 검색어 다시 입력 (필요시)
                    if keyword:
                        await self.search_keyword(keyword)
                        await asyncio.sleep(2)
                    
                    return await self.recover_page_state(keyword, retry_count + 1)
                else:
                    logger.error("최대 복구 시도 횟수 초과")
                    return False
                    
        except Exception as e:
            logger.error(f"페이지 복구 중 오류: {str(e)}")
            return False

    async def _check_table_exists(self) -> bool:
        """검색 결과 테이블 존재 여부 확인"""
        table_id = "mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_dataLayer"
        try:
            table = self.wait.until(EC.presence_of_element_located((By.ID, table_id)))
            return table.is_displayed()
        except Exception:
            logger.warning("검색 결과 테이블을 찾을 수 없습니다.")
            return False
    
    async def _check_no_results(self) -> bool:
        """검색 결과 없음 메시지 확인"""
        try:
            no_result = self.driver.find_element(By.XPATH, "//td[contains(text(), '검색된 데이터가 없습니다')]")
            if no_result.is_displayed():
                logger.info("검색 결과가 없습니다.")
                return True
        except NoSuchElementException:
            pass
        return False
    
    async def _get_total_rows(self) -> int:
        """테이블의 총 행 수 확인"""
        row_count = 0
        try:
            while True:
                try:
                    cell_id = f"mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_cell_{row_count}_0"
                    cell = self.driver.find_element(By.ID, cell_id)
                    if not cell.is_displayed():
                        break
                    row_count += 1
                except NoSuchElementException:
                    break
                except Exception as e:
                    logger.debug(f"행 수 확인 예외 발생: {str(e)}")
                    break
                    
            logger.info(f"총 {row_count}개의 행 발견")
        except Exception as e:
            logger.error(f"행 수 확인 중 오류: {str(e)}")
        return row_count
    
    async def _extract_row_data(self, row_num: int) -> Dict:
        """행 데이터 추출"""
        logger.info(f"행 데이터 추출 시작 - 행 번호: {row_num}")
        
        cells = {}
        cell_names = ['no', 'business_type', 'business_status', '', 'bid_category', 
                     'bid_number', 'title', 'announce_agency', 'agency', 'post_date', 
                     'deadline_date', 'progress_stage', 'process_status', '', 'bid_progress']
        
        try:
            for col, name in enumerate(cell_names):
                if name:  # 의미 있는 필드만 추출
                    try:
                        cell_id = f"mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_cell_{row_num}_{col}"
                        logger.debug(f"셀 데이터 추출 시도 - ID: {cell_id}")
                        
                        cell_element = self.wait.until(EC.presence_of_element_located((By.ID, cell_id)))
                        cells[name] = cell_element.text.strip()
                        
                        # 중요 필드에 대해서만 상세 로깅
                        if name in ['bid_number', 'title']:
                            logger.info(f"{name}: {cells[name]}")
                        else:
                            logger.debug(f"{name}: {cells[name]}")
                            
                    except Exception as e:
                        logger.error(f"컬럼 '{name}' 추출 실패 (행: {row_num}, 열: {col}): {str(e)}")
                        cells[name] = None  # None으로 설정하여 데이터 누락 표시
                        
            logger.info(f"행 데이터 추출 완료 - 행 번호: {row_num}")
            return cells
            
        except Exception as e:
            logger.error(f"행 전체 데이터 추출 실패 - 행 번호: {row_num}: {str(e)}")
            return {}
    
    async def _safely_navigate_and_extract_detail(self, row_num: int) -> Dict:
        """안전한 상세 페이지 탐색 및 데이터 추출"""
        original_window = None
        try:
            # 현재 창 핸들 저장
            original_window = self.driver.current_window_handle
            
            # 1. 상세 페이지 이동 (제목 클릭)
            title_cell_id = f"mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_cell_{row_num}_6"
            title_element = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, title_cell_id))
            )
            logger.info(f"상세 페이지 이동 시도 - 행: {row_num}")
            
            # 스크립트로 클릭 실행 (더 안정적)
            self.driver.execute_script("arguments[0].click();", title_element)
            await asyncio.sleep(3)  # 새 창이 열릴 때까지 충분히 대기
            
            # 2. 새 창이 열렸는지 확인
            new_window = None
            if len(self.driver.window_handles) > 1:
                # 새 창으로 전환
                for handle in self.driver.window_handles:
                    if handle != original_window:
                        new_window = handle
                        self.driver.switch_to.window(handle)
                        logger.info("새 창으로 전환 성공")
                        break
            
            # 3. 상세 데이터 추출
            detail_data = await self._extract_detail_page_data()
            
            # 4. 창 닫기 및 원래 창으로 복귀
            if new_window:
                self.driver.close()
                self.driver.switch_to.window(original_window)
                logger.info("원래 창으로 복귀 성공")
                
                # 원래 창의 상태 확인 및 대기
                await asyncio.sleep(2)
            else:
                # 새 창이 아닌 경우 뒤로 가기
                self.driver.back()
                await asyncio.sleep(3)  # 충분한 로딩 대기 시간
                logger.info("상세 페이지에서 뒤로 가기 성공")
            
            # 5. 테이블 상태 확인
            retries = 3
            for i in range(retries):
                if await self._check_table_exists():
                    logger.info("테이블 상태 확인 완료, 계속 진행")
                    break
                else:
                    logger.warning(f"테이블이 없음, 복구 시도 {i+1}/{retries}")
                    if i == retries - 1:
                        # 마지막 시도에서도 실패한 경우, 페이지 복구 시도
                        await self.recover_page_state(None)
                    else:
                        # 일시적인 지연 후 다시 시도
                        await asyncio.sleep(2)
            
            return detail_data
            
        except Exception as e:
            logger.error(f"상세 페이지 처리 중 오류: {str(e)}")
            
            # 오류 복구 시도
            try:
                # 현재 열린 창 모두 확인
                current_handles = self.driver.window_handles
                
                # 원래 창이 아닌 다른 창이 있으면 닫기
                if original_window:
                    for handle in current_handles:
                        if handle != original_window:
                            self.driver.switch_to.window(handle)
                            self.driver.close()
                    
                    # 원래 창으로 돌아가기
                    if original_window in current_handles:
                        self.driver.switch_to.window(original_window)
                
                # 페이지 상태 복구 시도
                await self.recover_page_state(None)
                
            except Exception as recovery_error:
                logger.error(f"오류 복구 중 추가 오류 발생: {str(recovery_error)}")
            
            return {}
    
    async def _extract_detail_page_data(self) -> Dict:
        """상세 페이지 데이터 추출"""
        
        def get_section_base_xpath():
            # 기본 섹션 XPath 확인
            base_paths = [
                "/html/body/div[1]/div[3]/div/div[2]/div/div[2]/div[4]/div[1]",  # 표준 패턴
                "/html/body/div[1]/div[3]/div/div[2]/div/div[2]/div[3]/div[1]"   # 대체 패턴
            ]
            
            for path in base_paths:
                try:
                    if self.driver.find_element(By.XPATH, path).is_displayed():
                        return path
                except:
                    pass
            
            logger.warning("기본 섹션 XPath를 찾을 수 없습니다. 기본값 사용")
            return base_paths[0]  # 기본값 반환
        
        base_xpath = get_section_base_xpath()
        detail_data = {}
        
        # 섹션 매핑 정의
        sections = {
            'general_notice': {
                'path': f"{base_xpath}/div[3]",
                'type': 'section'
            },
            'bid_qualification': {
                'path': f"{base_xpath}/div[5]",
                'type': 'section'
            },
            'bid_restriction': {
                'path': f"{base_xpath}/div[6]/div[2]",
                'type': 'section'
            },
            'bid_progress': {
                'path': f"{base_xpath}/div[9]",
                'type': 'section'
            },
            'presentation_order': {
                'path': f"{base_xpath}/div[12]",
                'type': 'section'
            },
            'proposal_info': {
                'path': f"{base_xpath}/div[13]/div[2]",
                'type': 'document',
                'table_path': "./div/div[2]/div/table/tbody/tr"
            },
            'negotiation_contract': {
                'path': f"{base_xpath}/div[13]/div[4]",
                'type': 'section',
                'table_path': "./table"
            },
            # 파일첨부 섹션
            'bid_notice_files': {
                'path': f"{base_xpath}/div[35]/div",
                'type': 'document',
                'table_path': ".//table[contains(@id, 'grdFile_body_table')]//tbody/tr"
            }
        }
        
        try:
            logger.info("상세 페이지 데이터 추출 시작")
            
            for section_name, info in sections.items():
                try:
                    elements = self.driver.find_elements(By.XPATH, info['path'])
                    
                    if elements and elements[0].is_displayed():
                        element = elements[0]
                        
                        if info['type'] == 'section':
                            detail_data[section_name] = element.text.strip()
                            logger.debug(f"섹션 '{section_name}' 추출 성공")
                            
                        elif info['type'] == 'document':
                            try:
                                table_rows = element.find_elements(By.XPATH, info['table_path'])
                                documents = []
                                
                                for row in table_rows:
                                    try:
                                        # 입찰공고문 파일 여부 확인
                                        if section_name == 'bid_notice_files':
                                            doc_info = await self._extract_file_info(row)
                                        else:
                                            doc_info = await self._extract_document_info(row)
                                            
                                        if doc_info:
                                            documents.append(doc_info)
                                    except Exception as e:
                                        logger.error(f"문서 정보 추출 실패: {str(e)}")
                                        
                                detail_data[section_name] = documents
                                logger.debug(f"문서 섹션 '{section_name}' 추출 성공")
                                
                            except Exception as e:
                                logger.error(f"테이블 처리 실패 - {section_name}: {str(e)}")
                                
                except Exception as e:
                    logger.debug(f"{section_name} 섹션 처리 실패: {str(e)}")
                    continue
                    
            logger.info("상세 페이지 데이터 추출 완료")
            return detail_data
            
        except Exception as e:
            logger.error(f"상세 페이지 데이터 추출 중 오류: {str(e)}")
            return {}
    
    async def _extract_file_info(self, row) -> Dict:
        """파일 정보 추출"""
        try:
            file_info = {
                'name': '',
                'size': '',
                'type': '',
                'download_url': None
            }
            
            # 파일명 추출
            try:
                # td[4]의 nobr 태그 내용을 가져옴
                name_cells = row.find_elements(By.XPATH, ".//td[4]//nobr[contains(@class, 'w2grid_input')]")
                if name_cells:
                    file_info['name'] = name_cells[0].text.strip()
                    logger.debug(f"파일명 추출 성공: {file_info['name']}")
            except Exception as e:
                logger.debug(f"파일명 추출 실패: {str(e)}")
                
            # 파일 크기 추출
            try:
                size_cells = row.find_elements(By.XPATH, ".//td[5]//nobr[contains(@class, 'w2grid_input')]")
                if size_cells:
                    file_info['size'] = size_cells[0].text.strip()
                    logger.debug(f"파일 크기 추출 성공: {file_info['size']}")
            except Exception as e:
                logger.debug(f"파일 크기 추출 실패: {str(e)}")
                
            return file_info
                
        except Exception as e:
            logger.error(f"파일 정보 추출 전체 실패: {str(e)}")
            return None
    
    async def _extract_document_info(self, element) -> Dict:
        """문서 요소에서 상세 정보 추출"""
        try:
            # 기본 문서 정보 구조체
            doc_info = {
                'text': '',
                'file_name': '',
                'download_link': None,
                'onclick': None
            }
            
            # 문서명 추출
            try:
                doc_info['text'] = element.text.strip()
            except:
                pass
                
            # 파일명과 다운로드 정보 추출
            try:
                links = element.find_elements(By.TAG_NAME, "a")
                if links:
                    doc_info['file_name'] = links[0].text.strip()
                    doc_info['download_link'] = links[0].get_attribute('href')
                    doc_info['onclick'] = links[0].get_attribute('onclick')
            except:
                # a 태그가 없는 경우 버튼 확인
                try:
                    buttons = element.find_elements(By.TAG_NAME, "button")
                    if buttons:
                        doc_info['file_name'] = buttons[0].text.strip()
                        doc_info['onclick'] = buttons[0].get_attribute('onclick')
                except:
                    pass
                    
            return doc_info if any(doc_info.values()) else None
            
        except Exception as e:
            logger.error(f"문서 정보 추출 실패: {str(e)}")
            return None
    
    async def _check_and_save_results(self):
        """주기적 저장 확인 및 수행"""
        current_time = datetime.now()
        if (current_time - self.last_save_time).seconds >= self.save_interval:
            # 진행 상황 저장
            logger.info("주기적 저장 시작")
            try:
                self.save_progress()
                self.last_save_time = current_time
                logger.info("주기적 저장 완료")
            except Exception as e:
                logger.error(f"주기적 저장 중 오류: {str(e)}")
    
    def save_progress(self):
        """진행 상황 저장"""
        try:
            # 저장 경로 설정
            save_dir = os.path.join("crawl", "progress")
            os.makedirs(save_dir, exist_ok=True)
            
            progress_data = {
                "timestamp": datetime.now().strftime('%Y%m%d_%H%M%S'),
                "processed_keywords": list(self.processed_keywords),
                "total_results": len(self.all_results)
            }
            
            filename = os.path.join(save_dir, f"crawling_progress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"진행 상황 저장 완료: {filename}")
            
        except Exception as e:
            logger.error(f"진행 상황 저장 실패: {str(e)}")
            
    def save_all_crawling_results(self):
        """전체 크롤링 결과를 하나의 JSON 파일로 저장"""
        try:
            # 저장 경로 설정 
            save_dir = os.path.join("crawl", "results")
            os.makedirs(save_dir, exist_ok=True)
            
            # 현재 시간으로 파일명 생성
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join(save_dir, f"all_crawling_results_{timestamp}.json")
            
            # 데이터 정제
            validator = self.validator
            cleaned_results = [validator.clean_bid_data(result) for result in self.all_results]
            
            # 저장할 데이터 구조화
            save_data = {
                "timestamp": timestamp,
                "total_results": len(cleaned_results),
                "processed_keywords": list(self.processed_keywords),
                "results": cleaned_results
            }
            
            # JSON 파일로 저장
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"전체 크롤링 결과 저장 완료: {filename} (총 {len(cleaned_results)}건)")
            return filename
            
        except Exception as e:
            logger.error(f"전체 결과 저장 실패: {str(e)}")
            return None

    async def crawl_keyword(self, keyword: str) -> List[BidItem]:
        """
        단일 키워드 크롤링 수행
        
        Args:
            keyword (str): 검색할 키워드
            
        Returns:
            List[BidItem]: 크롤링 결과 항목 목록
        """
        try:
            logger.info(f"키워드 '{keyword}' 크롤링 시작")
            
            # 메인 페이지 접속
            if not await self.navigate_to_main():
                logger.error(f"키워드 '{keyword}' 크롤링 실패: 메인 페이지 접속 실패")
                return []
            
            # 입찰공고목록 페이지로 이동
            if not await self.navigate_to_bid_list():
                logger.error(f"키워드 '{keyword}' 크롤링 실패: 입찰공고목록 페이지 접속 실패")
                return []
            
            # 검색 조건 설정
            if not await self.setup_search_conditions():
                logger.warning("검색 조건 설정 중 오류 발생 (진행 계속)")
            
            # 키워드 검색 수행
            result_data = await self.search_keyword(keyword)
            
            # BidItem 객체로 변환
            items = []
            for data in result_data:
                try:
                    # 기본 정보와 상세 정보 추출
                    basic_info = data.get('basic_info', {})
                    detail_info = data.get('detail_info', {})
                    
                    # 필수 필드 확인
                    if not basic_info.get('title'):
                        logger.warning(f"제목 없는 항목 제외: {basic_info}")
                        continue
                    
                    # BidItem 객체 생성
                    item = BidItem(
                        bid_number=basic_info.get('bid_number'),
                        bid_name=basic_info.get('title'),
                        org_name=basic_info.get('organization'),
                        deadline=basic_info.get('deadline'),
                        status=basic_info.get('status'),
                        url=basic_info.get('url'),
                        bid_method=detail_info.get('bid_method'),
                        contract_type=detail_info.get('contract_type'),
                        price_evaluation=detail_info.get('price_evaluation'),
                        location=detail_info.get('location'),
                        search_keyword=keyword,
                        collected_at=datetime.now()
                    )
                    
                    items.append(item)
                    
                except Exception as e:
                    logger.error(f"BidItem 변환 중 오류: {str(e)}")
                    continue
            
            logger.info(f"키워드 '{keyword}' 크롤링 완료: {len(items)}개 항목")
            return items
            
        except Exception as e:
            logger.error(f"키워드 '{keyword}' 크롤링 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return []

    async def _click_element_safely(self, by, selector, timeout=10, attempts=3):
        """요소를 안전하게 클릭 (여러 번 시도)"""
        for attempt in range(attempts):
            try:
                # 요소가 나타날 때까지 대기
                element = WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable((by, selector))
                )
                # 요소 클릭
                element.click()
                return True
            except StaleElementReferenceException:
                logger.warning(f"요소가 DOM에서 사라짐 - 재시도 중 ({attempt+1}/{attempts})")
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"요소 클릭 실패: {by}={selector}, 오류: {str(e)} - 재시도 중 ({attempt+1}/{attempts})")
                await asyncio.sleep(1)
        
        # 모든 시도 실패
        raise Exception(f"{attempts}번 시도 후 요소 클릭 실패: {by}={selector}")