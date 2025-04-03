"""
나라장터 웹사이트 크롤러 기본 모듈

이 모듈은 국가종합전자조달 나라장터 웹사이트의 입찰공고를 수집하는 크롤러의 기본 기능을 구현합니다.
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

# 로깅 설정
logger = logging.getLogger(__name__)

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
        
        # 필드 초기화
        from .validator import SearchValidator
        self.validator = SearchValidator()  # 검증 객체
        
        # 추가 필드
        self.all_results = []  # 모든 결과 저장
        self.processed_keywords = set()  # 처리된 키워드 추적
        self.last_save_time = datetime.now()  # 마지막 저장 시간 추적
        self.save_interval = 300  # 저장 간격 (초 단위, 5분)
        
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

    async def _extract_bid_data(self, row_index: int) -> Optional['G2BBidItem']:
        """
        테이블에서 입찰 정보 추출
        
        Args:
            row_index: 추출할 행 인덱스
            
        Returns:
            G2BBidItem 객체 또는 None
        """
        try:
            from datetime import datetime
            from .models import G2BBidItem
            
            logger.info(f"행 {row_index}에서 입찰 정보 추출 중")
            
            # 각 열의 셀 ID 패턴
            cell_ids = {
                'business_type': f"mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_cell_{row_index}_1",  # 업무구분
                'bid_number': f"mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_cell_{row_index}_3",    # 입찰공고번호
                'title': f"mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_cell_{row_index}_6",         # 공고명
                'agency': f"mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_cell_{row_index}_8",        # 공고기관
                'date': f"mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_cell_{row_index}_10",         # 게시일시
                'status': f"mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_cell_{row_index}_12"        # 단계
            }
            
            # 데이터 추출
            extracted_data = {}
            
            # 각 셀에서 텍스트 추출
            for field, cell_id in cell_ids.items():
                try:
                    logger.debug(f"셀 데이터 추출 시도 - ID: {cell_id}")
                    
                    # 셀 요소 찾기
                    cell_element = self.driver.find_element(By.ID, cell_id)
                    
                    # 셀 데이터 추출
                    if field == 'title':
                        # 제목 셀에서는 링크도 추출
                        link_element = cell_element.find_element(By.TAG_NAME, 'a')
                        extracted_data[field] = link_element.text.strip()
                        extracted_data['url'] = link_element.get_attribute('href')
                    else:
                        extracted_data[field] = cell_element.text.strip()
                        
                    logger.debug(f"셀 데이터 추출 성공 - {field}: {extracted_data[field]}")
                    
                except Exception as e:
                    logger.warning(f"셀 데이터 추출 실패 - ID: {cell_id}, 오류: {str(e)}")
                    extracted_data[field] = ""
            
            # 업무구분 확인 - 물품 또는 용역만 처리
            business_type = extracted_data.get('business_type', '')
            if business_type and not any(t in business_type for t in ['물품', '용역']):
                logger.info(f"업무구분이 물품/용역이 아니므로 건너뜀: {business_type}")
                return None
            
            # 수요기관 정보 추출 (공고기관 셀 또는 추가 정보에서)
            agency_info = extracted_data.get('agency', '').split('/')
            announce_agency = agency_info[0].strip() if agency_info else ''
            demand_agency = agency_info[1].strip() if len(agency_info) > 1 else announce_agency
            
            # 날짜 정보 파싱
            date_str = extracted_data.get('date', '')
            date_parts = date_str.split('\n')
            
            post_date_str = date_parts[0] if len(date_parts) > 0 else ''
            bid_start_date_str = ''
            bid_open_date_str = ''
            bid_close_date_str = ''
            
            # 날짜 문자열 분석 및 형식 조정
            for part in date_parts:
                if '개찰' in part:
                    bid_open_date_str = part.replace('개찰:', '').strip()
                elif '입찰' in part and '마감' not in part:
                    bid_start_date_str = part.replace('입찰:', '').strip()
                elif '마감' in part:
                    bid_close_date_str = part.replace('마감:', '').strip()
            
            # 날짜 문자열을 datetime 객체로 변환
            try:
                post_date = datetime.strptime(post_date_str, '%Y/%m/%d %H:%M') if post_date_str else None
                bid_start_date = datetime.strptime(bid_start_date_str, '%Y/%m/%d %H:%M') if bid_start_date_str else None
                bid_open_date = datetime.strptime(bid_open_date_str, '%Y/%m/%d %H:%M') if bid_open_date_str else None
                bid_close_date = datetime.strptime(bid_close_date_str, '%Y/%m/%d %H:%M') if bid_close_date_str else None
            except ValueError as e:
                logger.warning(f"날짜 파싱 오류: {str(e)}")
                # 날짜 형식이 다른 경우 다양한 형식 시도
                try:
                    formats = ['%Y/%m/%d %H:%M', '%Y-%m-%d %H:%M', '%Y.%m.%d %H:%M', '%Y%m%d %H:%M']
                    for fmt in formats:
                        try:
                            post_date = datetime.strptime(post_date_str, fmt) if post_date_str else None
                            break
                        except ValueError:
                            continue
                    
                    # 기타 날짜도 동일하게 시도
                    for fmt in formats:
                        try:
                            bid_start_date = datetime.strptime(bid_start_date_str, fmt) if bid_start_date_str else None
                            break
                        except ValueError:
                            continue
                    
                    for fmt in formats:
                        try:
                            bid_open_date = datetime.strptime(bid_open_date_str, fmt) if bid_open_date_str else None
                            break
                        except ValueError:
                            continue
                    
                    for fmt in formats:
                        try:
                            bid_close_date = datetime.strptime(bid_close_date_str, fmt) if bid_close_date_str else None
                            break
                        except ValueError:
                            continue
                except Exception as parsing_error:
                    logger.error(f"날짜 파싱 최종 실패: {str(parsing_error)}")
                    # 날짜 파싱에 실패하더라도 계속 진행
            
            # G2BBidItem 객체 생성
            bid_item = G2BBidItem(
                business_type=business_type,
                bid_number=extracted_data.get('bid_number', ''),
                title=extracted_data.get('title', ''),
                announce_agency=announce_agency,
                demand_agency=demand_agency,
                post_date=post_date or datetime.now(),  # 파싱 실패 시 현재 시간으로 대체
                bid_start_date=bid_start_date,
                bid_open_date=bid_open_date,
                bid_close_date=bid_close_date,
                status=extracted_data.get('status', ''),
                url=extracted_data.get('url', ''),
                crawled_at=datetime.now()
            )
            
            # 날짜와 업무구분 유효성 검사
            if not bid_item.is_valid_date():
                logger.info(f"날짜 조건을 만족하지 않아 건너뜀: {bid_item.bid_number}")
                return None
                
            if not bid_item.is_valid_business_type():
                logger.info(f"업무구분 조건을 만족하지 않아 건너뜀: {bid_item.business_type}")
                return None
            
            logger.info(f"입찰 정보 추출 성공: {bid_item.bid_number} - {bid_item.title}")
            return bid_item
            
        except Exception as e:
            logger.error(f"입찰 정보 추출 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return None

    async def extract_all_bid_data(self) -> List['G2BBidItem']:
        """
        테이블의 모든 행에서 입찰 정보 추출
        
        Returns:
            유효한 G2BBidItem 객체 리스트
        """
        valid_items = []
        
        try:
            logger.info("모든 행에서 입찰 정보 추출 시작")
            
            # 테이블이 존재하는지 확인
            if not await self._check_table_exists():
                logger.warning("테이블이 존재하지 않습니다.")
                return valid_items
            
            # 검색 결과가 없는지 확인
            if await self._check_no_results():
                logger.info("검색 결과가 없습니다.")
                return valid_items
            
            # 총 행 수 확인
            total_rows = await self._get_total_rows()
            logger.info(f"총 {total_rows}개 행 처리 시작")
            
            # 각 행에서 데이터 추출
            for row_idx in range(total_rows):
                try:
                    bid_item = await self._extract_bid_data(row_idx)
                    
                    # 유효한 항목만 추가
                    if bid_item:
                        valid_items.append(bid_item)
                        logger.info(f"유효한 입찰 항목 추가 ({len(valid_items)}): {bid_item.bid_number}")
                    
                    # 항목 사이 짧은 딜레이
                    await asyncio.sleep(0.2)
                    
                except Exception as e:
                    logger.warning(f"행 {row_idx} 처리 중 오류: {str(e)}")
                    continue
            
            logger.info(f"입찰 정보 추출 완료: 총 {total_rows}개 중 {len(valid_items)}개 유효")
            
        except Exception as e:
            logger.error(f"입찰 정보 추출 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
        
        return valid_items

    async def navigate_to_detail(self, row_index: int) -> bool:
        """
        입찰 목록에서 상세 페이지로 이동
        
        Args:
            row_index: 클릭할 행 인덱스 (0부터 시작)
            
        Returns:
            성공 여부
        """
        try:
            logger.info(f"상세 페이지 이동 시도 (행 인덱스: {row_index})")
            
            # 제목 셀 ID
            title_cell_id = f"mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_cell_{row_index}_6"
            
            # 제목 셀 찾기
            try:
                logger.debug(f"셀 데이터 추출 시도 - ID: {title_cell_id}")
                
                # 제목 요소 찾기
                title_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, title_cell_id))
                )
                
                # 요소가 화면에 보이도록 스크롤
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", title_element)
                await asyncio.sleep(1)
                
                # XPath를 사용하여 링크 엘리먼트 찾기
                link_xpath = f"//*[@id='{title_cell_id}']/nobr/a"
                link_element = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, link_xpath))
                )
                
                # 링크 클릭
                link_element.click()
                logger.info(f"상세 페이지 링크({row_index}행) 클릭 성공")
                
                # 페이지 로딩 대기
                await asyncio.sleep(3)
                
                return True
                
            except Exception as e:
                # 기본 방식 실패 시 JavaScript 클릭 시도
                logger.warning(f"기본 방식으로 상세 페이지 이동 실패: {str(e)}")
                
                try:
                    logger.info("JavaScript를 사용한 상세 페이지 이동 시도")
                    # 셀 ID로 직접 JavaScript 실행
                    script = f"""
                        var cell = document.getElementById('{title_cell_id}');
                        if (cell) {{
                            var link = cell.querySelector('nobr > a');
                            if (link) {{
                                link.click();
                                return true;
                            }}
                        }}
                        return false;
                    """
                    result = self.driver.execute_script(script)
                    
                    if result:
                        logger.info("JavaScript를 사용한 상세 페이지 이동 성공")
                        await asyncio.sleep(3)
                        return True
                    else:
                        logger.warning("JavaScript를 사용한 상세 페이지 이동 실패")
                        return False
                except Exception as js_error:
                    logger.error(f"JavaScript를 사용한 상세 페이지 이동 실패: {str(js_error)}")
                    return False
                
        except Exception as e:
            logger.error(f"상세 페이지 이동 중 오류: {str(e)}")
            return False 