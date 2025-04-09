"""
나라장터 크롤러 HTML 파서 테스트 스크립트

이 스크립트는 HTML 파서를 통한 텍스트 추출 후 Gemini API 처리 방식만 사용합니다.
헤드리스 모드에서도 동작하며, 키워드 'AI'로 검색합니다.
"""

import os
import sys
import asyncio
import logging
import json
import re
import time
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

# 현재 스크립트 위치 기반으로 경로 설정
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.append(str(project_root))

# 필요한 모듈 임포트
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, StaleElementReferenceException
)
import chromedriver_autoinstaller
from bs4 import BeautifulSoup

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(current_dir / 'hptest.log', encoding='utf-8')
    ]
)
logger = logging.getLogger("hp-crawler-test")

# .env 파일 로드 (프로젝트 루트 기준)
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / '.env')
    logger.info("환경 변수 로드 성공")
except ImportError:
    print("dotenv 패키지가 설치되어 있지 않습니다. 환경 변수를 직접 설정해주세요.")

# Google Generative AI 모듈 임포트
try:
    import google.generativeai as genai
except ImportError:
    print("google-generativeai 패키지가 설치되어 있지 않습니다. 'pip install google-generativeai' 명령으로 설치해주세요.")
    sys.exit(1)

# 출력 폴더 생성
RESULTS_DIR = current_dir / 'hp_results'
RESULTS_DIR.mkdir(exist_ok=True)

# Gemini API 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)

# 헬퍼 함수
async def extract_with_gemini_text(text_content: str, prompt_template: str) -> Dict[str, Any]:
    """
    Gemini Pro 텍스트 모델로 텍스트에서 정보 추출
    
    Args:
        text_content: 추출할 텍스트 내용
        prompt_template: 프롬프트 템플릿
        
    Returns:
        추출된 정보 또는 빈 딕셔너리 (실패 시)
    """
    try:
        logger.info("Gemini 텍스트 모델로 정보 추출 중...")
        
        # 모델 설정
        model = genai.GenerativeModel('gemini-pro')
        
        # 프롬프트 구성
        prompt = prompt_template.format(content=text_content)
        
        # 모델 호출
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: model.generate_content(prompt)
        )
        
        # 응답 텍스트 
        result_text = response.text
        
        # JSON 부분 추출 시도
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', result_text)
        if json_match:
            result_text = json_match.group(1)
        
        # 중괄호로 둘러싸인 부분을 찾아 추출
        json_match = re.search(r'(\{[\s\S]*\})', result_text)
        if json_match:
            result_text = json_match.group(1)
        
        try:
            # JSON 파싱 시도
            result_data = json.loads(result_text)
            logger.info(f"Gemini 텍스트 추출 성공: {list(result_data.keys())}")
            return result_data
        except json.JSONDecodeError:
            logger.warning("JSON 파싱 실패, 수동 파싱 시도")
            
            # 수동 파싱 (키: 값 형식)
            result_data = {}
            lines = result_text.strip().split('\n')
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().strip('"\'').replace(' ', '_').lower()
                    value = value.strip().strip(',"\'')
                    result_data[key] = value
            
            logger.info(f"수동 파싱 결과: {list(result_data.keys())}")
            return result_data
    
    except Exception as e:
        logger.error(f"Gemini 텍스트 추출 중 오류: {str(e)}")
        logger.debug(traceback.format_exc())
        return {}

async def check_relevance_with_ai(title: str, keyword: str) -> bool:
    """
    Gemini AI를 사용하여 검색어와 공고명 사이의 연관성을 판단
    
    Args:
        title: 공고명
        keyword: 검색어
        
    Returns:
        bool: 연관성이 있으면 True, 없으면 False
    """
    try:
        logger.info(f"검색어 '{keyword}'와 공고명 '{title}' 사이의 연관성 판단 중...")
        
        # 모델 설정
        model = genai.GenerativeModel('gemini-pro')
        
        # 프롬프트 구성
        prompt = f"""
        당신은 입찰공고명과 검색어 사이의 실제 연관성을 판단하는 AI 전문가입니다.
        
        입찰공고명: {title}
        검색어: {keyword}
        
        위 입찰공고가 검색어와 실제로 연관이 있는지 판단해주세요.
        
        다음 규칙을 따라주세요:
        1. 단순히 텍스트가 포함되어 있는 것이 아니라 의미적 연관성을 판단해야 합니다.
        2. 같은 의미를 가진 유사어도 연관성이 있다고 판단합니다 (예: '인공지능'과 'AI', '머신러닝'과 'ML' 등).
        3. 제품명이나 회사명에 우연히 검색어의 일부가 포함된 경우는 연관이 없습니다 (예: 'AI'가 'MAIN', 'TRAIN'의 일부로 포함된 경우).
        4. 검색어가 약어인 경우 전체 단어도 확인합니다 (예: 'AI'는 'Artificial Intelligence'와 연관).
        
        결과는 아래 형식으로 출력해주세요:
        {{
            "is_relevant": true/false,
            "reason": "판단 이유를 1-2문장으로 설명"
        }}
        """
        
        # 모델 호출
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: model.generate_content(prompt)
        )
        
        # 응답 텍스트
        result_text = response.text
        
        # JSON 부분 추출 시도
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', result_text)
        if json_match:
            result_text = json_match.group(1)
        
        # 중괄호로 둘러싸인 부분을 찾아 추출
        json_match = re.search(r'(\{[\s\S]*\})', result_text)
        if json_match:
            result_text = json_match.group(1)
        
        try:
            # JSON 파싱 시도
            result_data = json.loads(result_text)
            is_relevant = result_data.get("is_relevant", False)
            reason = result_data.get("reason", "이유 없음")
            
            if is_relevant:
                logger.info(f"판단 결과: 연관성 있음 - {reason}")
            else:
                logger.info(f"판단 결과: 연관성 없음 - {reason}")
                
            return is_relevant
            
        except json.JSONDecodeError:
            logger.warning("JSON 파싱 실패, 텍스트에서 결과 추출 시도")
            
            # 단순 텍스트 기반 판단
            is_relevant = "true" in result_text.lower() and "is_relevant" in result_text.lower()
            logger.info(f"단순 텍스트 기반 판단 결과: {'연관성 있음' if is_relevant else '연관성 없음'}")
            
            return is_relevant
    
    except Exception as e:
        logger.error(f"연관성 판단 중 오류: {str(e)}")
        logger.debug(traceback.format_exc())
        # 오류 발생 시 기본적으로 연관성 있다고 가정 (false negative 방지)
        return True

class HTMLParserCrawler:
    """HTML 파서 크롤러 테스트 클래스"""
    
    def __init__(self, headless: bool = False):
        """
        크롤러 초기화
        
        Args:
            headless (bool): 헤드리스 모드 사용 여부
        """
        self.base_url = "https://www.g2b.go.kr"
        self.driver = None
        self.wait = None
        self.headless = headless
        self.results = []
        self.keyword = "AI"  # 테스트 키워드 고정
    
    async def initialize(self):
        """크롤러 초기화 및 웹드라이버 설정"""
        try:
            logger.info("크롤러 초기화 시작")
            
            # ChromeDriver 자동 설치
            chromedriver_autoinstaller.install(True)
            
            # Chrome 옵션 설정
            chrome_options = Options()
            
            # 헤드리스 모드 설정
            if self.headless:
                chrome_options.add_argument('--headless=new')
                logger.info("헤드리스 모드 활성화")
            
            # 기타 옵션 설정
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-popup-blocking')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
            
            # 웹드라이버 초기화
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 10)
            
            logger.info("크롤러 초기화 성공")
            return True
        except Exception as e:
            logger.error(f"크롤러 초기화 실패: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
    
    async def close(self):
        """웹드라이버 종료 및 리소스 정리"""
        if self.driver:
            try:
                logger.info("웹드라이버 종료 시작")
                
                # 열려있는 모든 팝업창 닫기
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
                
                try:
                    # ESC 키를 눌러 혹시 남은 팝업 닫기 시도
                    from selenium.webdriver.common.action_chains import ActionChains
                    from selenium.webdriver.common.keys import Keys
                    
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
            
            # 먼저 메인 페이지로 이동
            if not await self.navigate_to_main():
                logger.error("메인 페이지 접속 실패")
                return False
            
            for attempt in range(3):  # 최대 3번 시도
                try:
                    # 페이지 안정화를 위한 짧은 대기
                    await asyncio.sleep(1)
                    
                    # 메뉴 클릭을 통한 탐색
                    try:
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
                    except Exception as e:
                        logger.error(f"메뉴 클릭 실패: {str(e)}")
                        if attempt == 2:  # 마지막 시도에서 실패
                            raise
                        continue
                    
                    # 팝업창 다시 닫기
                    await self._close_popups()
                    
                    # 페이지 상태 확인
                    try:
                        # 검색 버튼 존재 확인 (테스트 페이지와 실제 페이지 모두 지원)
                        search_button = None
                        try:
                            # 실제 운영 페이지 버튼 ID
                            search_button = WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_btnS0004"))
                            )
                        except Exception:
                            # 테스트 페이지 버튼 ID
                            search_button = WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.ID, "buttonSearch"))
                            )
                        
                        logger.info("입찰공고 목록 페이지 이동 성공")
                        return True
                    except Exception:
                        logger.warning(f"페이지 확인 실패 (재시도 {attempt+1}/3)")
                        continue
                
                except Exception as e:
                    logger.warning(f"입찰공고 목록 페이지 이동 시도 {attempt+1}/3 실패: {str(e)}")
                    if attempt == 2:  # 마지막 시도에서도 실패
                        raise
                    # 페이지 새로고침 후 재시도
                    self.driver.refresh()
                    await asyncio.sleep(3)
                    await self._close_popups()
            
            # 모든 시도 실패
            raise Exception("3번의 시도 후에도 입찰공고 목록 페이지 이동 실패")
        
        except Exception as e:
            logger.error(f"입찰공고 목록 페이지 이동 실패: {str(e)}")
            logger.debug(traceback.format_exc())
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
            logger.debug(traceback.format_exc())
            return False

    async def search_keyword(self):
        """키워드 검색 수행 (self.keyword 사용)"""
        try:
            logger.info(f"키워드 '{self.keyword}' 검색 시작")
            
            # 검색 조건 설정
            await self.setup_search_conditions()
            
            # 검색어 입력 필드 찾기 (정확한 ID 사용)
            try:
                search_input = self.wait.until(
                    EC.presence_of_element_located((By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_bidPbancNm"))
                )
                search_input.clear()
                search_input.send_keys(self.keyword)
                logger.info(f"검색어 '{self.keyword}' 입력 완료")
            except Exception as e:
                # 대체 선택자 시도
                logger.warning(f"기본 검색창 찾기 실패, 대체 검색창 시도: {str(e)}")
                search_input = self.wait.until(
                    EC.presence_of_element_located((By.ID, "bidNm"))
                )
                search_input.clear()
                search_input.send_keys(self.keyword)
                logger.info(f"대체 검색창에 검색어 '{self.keyword}' 입력 완료")
            
            # 검색 버튼 클릭 (정확한 ID 사용)
            try:
                search_button = self.wait.until(
                    EC.element_to_be_clickable((By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_btnS0004"))
                )
                search_button.click()
                logger.info("검색 버튼 클릭 완료")
            except Exception as e:
                # 대체 선택자 시도
                logger.warning(f"기본 검색 버튼 찾기 실패, 대체 버튼 시도: {str(e)}")
                search_button = self.wait.until(
                    EC.element_to_be_clickable((By.ID, "buttonSearch"))
                )
                search_button.click()
                logger.info("대체 검색 버튼 클릭 완료")
            
            # 검색 결과 로딩 대기
            await asyncio.sleep(3)
            
            # 테이블 존재 확인
            try:
                table = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table.st_list"))
                )
                logger.info("검색 결과 테이블 확인")
                return True
            except Exception as e:
                logger.warning(f"검색 결과 테이블 확인 실패: {str(e)}")
                return False
            
        except Exception as e:
            logger.error(f"키워드 검색 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
    
    async def extract_search_results(self, search_page_url=None, max_items=3):
        """
        검색 결과 페이지에서 입찰 목록을 추출

        Args:
            search_page_url: 검색 결과 페이지 URL (None인 경우 현재 페이지 사용)
            max_items: 최대 처리할 항목 수

        Returns:
            추출된 입찰 항목 리스트
        """
        try:
            logger.info("검색 결과 추출 시작")
            
            # 검색 결과 행 가져오기
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table.st_list tbody tr")
            
            if not rows:
                logger.warning("검색 결과가 없습니다.")
                return []
            
            logger.info(f"검색 결과 {len(rows)}개 항목 발견")
            
            # 결과 저장 리스트
            search_results = []
            
            # 현재 날짜 가져오기
            current_date = datetime.now()
            logger.info(f"현재 날짜: {current_date.strftime('%Y/%m/%d')}")
            
            # 최대 항목 수로 제한
            rows_to_process = rows[:min(len(rows), max_items)]
            
            for i, row in enumerate(rows_to_process):
                try:
                    # 행에서 셀 가져오기
                    cells = row.find_elements(By.TAG_NAME, "td")
                    
                    if len(cells) < 8: # 최소 8개 셀이 필요 (날짜 정보는 보통 8번째 셀)
                        logger.warning(f"행 {i+1}: 셀 수가 충분하지 않음, 건너뜀")
                        continue
                    
                    # 기본 데이터 추출
                    try:
                        bid_number = cells[3].text.strip()
                    except Exception:
                        bid_number = f"unknown_{i}"
                    
                    try:
                        title = cells[2].text.strip()
                    except Exception:
                        title = f"제목 없음 {i}"
                    
                    try:
                        organization = cells[6].text.strip()
                    except Exception:
                        organization = ""
                    
                    # AI로 검색어와 공고명의 연관성 판단
                    is_relevant = await check_relevance_with_ai(title, self.keyword)
                    
                    if not is_relevant:
                        logger.info(f"입찰 {bid_number}: 검색어 '{self.keyword}'와 연관성이 없어 건너뜁니다.")
                        continue
                    else:
                        logger.info(f"입찰 {bid_number}: 검색어 '{self.keyword}'와 연관성이 있어 처리합니다.")
                    
                    # 게시일시(입찰마감일시) 데이터 추출 및 파싱
                    try:
                        date_cell = cells[7]
                        date_text = date_cell.text.strip()
                        
                        # 날짜 형식 확인 및 입찰마감일시 추출
                        # 형식: "YYYY/MM/DD HH:MM\n(YYYY/MM/DD HH:MM)"
                        logger.debug(f"날짜 텍스트: {date_text}")
                        
                        # 정규식을 사용하여 입찰마감일시 추출
                        deadline_match = re.search(r'\(([\d/]+)\s+([\d:]+)\)', date_text)
                        
                        if deadline_match:
                            deadline_date_str = deadline_match.group(1)  # YYYY/MM/DD
                            deadline_time_str = deadline_match.group(2)  # HH:MM
                            deadline_str = f"{deadline_date_str} {deadline_time_str}"
                            
                            # 날짜 객체로 변환
                            deadline_date = datetime.strptime(deadline_str, "%Y/%m/%d %H:%M")
                            
                            # 현재 날짜와의 차이 계산 (일 단위)
                            days_remaining = (deadline_date - current_date).days
                            
                            logger.info(f"입찰 {bid_number}: 입찰마감일시 {deadline_str}, 남은 일수: {days_remaining}")
                            
                            # 입찰마감일시가 7일 이내인지 확인
                            is_within_7days = days_remaining <= 7
                            
                            if is_within_7days:
                                logger.info(f"입찰 {bid_number}의 마감일시가 7일 이내 ({days_remaining}일)입니다. 건너뜁니다.")
                                continue
                        else:
                            # 입찰마감일시를 추출할 수 없을 경우
                            logger.warning(f"입찰 {bid_number}의 마감일시를 추출할 수 없습니다.")
                            deadline_str = date_text
                            is_within_7days = False
                    except Exception as e:
                        logger.warning(f"입찰마감일시 파싱 중 오류: {str(e)}")
                        deadline_str = ""
                        is_within_7days = False
                    
                    # 항목 데이터 구성
                    item_data = {
                        "bid_number": bid_number,
                        "title": title,
                        "organization": organization,
                        "deadline": deadline_str,
                        "is_within_7days": is_within_7days,
                        "is_relevant": is_relevant,
                        "row_index": i
                    }
                    
                    logger.info(f"항목 {i+1} 추출 성공: {title}")
                    search_results.append(item_data)
                    
                except Exception as e:
                    logger.error(f"행 {i+1} 처리 중 오류: {str(e)}")
                    logger.debug(traceback.format_exc())
            
            logger.info(f"총 {len(search_results)}개 항목 추출 완료")
            return search_results
            
        except Exception as e:
            logger.error(f"검색 결과 추출 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return []
    
    async def process_detail_page(self, item):
        """
        항목의 상세 페이지 처리 (HTML 파서 버전)
        
        Args:
            item: 처리할 항목 데이터
            
        Returns:
            상세 정보 (성공 시) 또는 None (실패 시)
        """
        try:
            logger.info(f"상세 페이지 처리 시작 - {item['title']}")
            
            # 검색어와 연관성이 없는 경우 처리하지 않음
            if not item.get('is_relevant', True):
                logger.info(f"입찰 {item['bid_number']}의 공고명이 검색어 '{self.keyword}'와 연관성이 없습니다. 상세 페이지를 처리하지 않습니다.")
                return None
            
            # 입찰마감일시가 7일 이내인 경우 처리하지 않음
            if item.get('is_within_7days', False):
                logger.info(f"입찰 {item['bid_number']}의 마감일시가 7일 이내입니다. 상세 페이지를 처리하지 않습니다.")
                return None
            
            logger.info(f"입찰 {item['bid_number']}의 마감일시가 7일 이후이고 검색어와 연관성이 있으므로 상세 페이지를 처리합니다.")
            
            # 해당 행 인덱스의 제목 셀 찾기
            row_index = item["row_index"]
            
            # 제목 링크 찾기 (다양한 방법 시도)
            title_link = None
            
            try:
                # 방법 1: 테이블 셀 위치로 찾기
                title_selector = f"table.st_list tbody tr:nth-child({row_index + 1}) td:nth-child(3) a"
                title_link = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, title_selector))
                )
                logger.info("방법 1: 테이블 셀 위치로 제목 링크 찾기 성공")
            except Exception as e:
                logger.warning(f"방법 1 실패: {str(e)}")
                
                try:
                    # 방법 2: 텍스트로 찾기
                    title_text = item["title"]
                    title_links = self.driver.find_elements(By.XPATH, f"//a[contains(text(), '{title_text}')]")
                    
                    if title_links:
                        title_link = title_links[0]
                        logger.info("방법 2: 텍스트로 제목 링크 찾기 성공")
                    else:
                        # 방법 3: 타이틀 부분 매칭으로 찾기
                        words = title_text.split()
                        if len(words) > 3:  # 최소 3단어 이상인 경우 앞부분만 사용
                            partial_title = ' '.join(words[:3])
                            title_links = self.driver.find_elements(By.XPATH, f"//a[contains(text(), '{partial_title}')]")
                            if title_links:
                                title_link = title_links[0]
                                logger.info("방법 3: 부분 텍스트 매칭으로 제목 링크 찾기 성공")
                except Exception as e2:
                    logger.warning(f"방법 2, 3 실패: {str(e2)}")
                    
                    try:
                        # 방법 4: 테이블 내 모든 링크 중에서 찾기
                        table = self.driver.find_element(By.CSS_SELECTOR, "table.st_list")
                        all_links = table.find_elements(By.TAG_NAME, "a")
                        
                        # 빈 href 속성과 onclick 이벤트가 있는 링크 찾기
                        for link in all_links:
                            href = link.get_attribute("href")
                            onclick = link.get_attribute("onclick")
                            if (not href or href == "#" or href == "") and onclick and "event.returnValue=false" in onclick:
                                title_link = link
                                logger.info("방법 4: 테이블 내 onclick 이벤트가 있는 링크 찾기 성공")
                                break
                    except Exception as e3:
                        logger.warning(f"방법 4 실패: {str(e3)}")
            
            if not title_link:
                raise Exception("제목 링크를 찾을 수 없습니다.")
            
            # 링크 텍스트 로그
            link_text = title_link.text.strip()
            logger.info(f"클릭할 링크 텍스트: {link_text}")
            
            # JavaScript onclick 이벤트 처리
            try:
                # 1. 직접 클릭 시도
                logger.info("방법 A: 직접 클릭 시도")
                title_link.click()
            except Exception as click_error:
                logger.warning(f"직접 클릭 실패: {str(click_error)}")
                
                try:
                    # 2. JavaScript 실행으로 시도
                    logger.info("방법 B: JavaScript 실행으로 클릭 시도")
                    self.driver.execute_script("arguments[0].click();", title_link)
                except Exception as js_error:
                    logger.warning(f"JavaScript 클릭 실패: {str(js_error)}")
                    
                    # 3. 데이터 속성으로 행 ID 찾아서 이벤트 처리
                    try:
                        logger.info("방법 C: 데이터 속성으로 행 ID 찾아서 이벤트 처리")
                        row = title_link.find_element(By.XPATH, "./ancestor::tr")
                        row_id = row.get_attribute("id")
                        
                        if row_id:
                            # onClick 이벤트 추출 시도
                            self.driver.execute_script(f"""
                                var elements = document.querySelectorAll('tr#{row_id} a');
                                if (elements.length > 0) {{
                                    elements[0].click();
                                }}
                            """)
                        else:
                            raise Exception("행 ID를 찾을 수 없습니다.")
                    except Exception as e4:
                        logger.error(f"방법 C 실패: {str(e4)}")
                        raise
            
            # 상세 페이지 로딩 대기
            await asyncio.sleep(3)
            
            # HTML 파서로 데이터 추출
            detail_data = await self._extract_detail_with_html_parser(item)
            logger.info(f"HTML 파서 추출 결과: {list(detail_data.keys()) if detail_data else 'None'}")
            
            # 기본 정보 추가
            detail_data["bid_number"] = item["bid_number"]
            detail_data["title"] = item["title"]
            
            # JSON 결과 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_file = RESULTS_DIR / f"detail_{item['bid_number']}_{timestamp}.json"
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(detail_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"상세 정보 저장 완료: {result_file}")
            
            # 목록으로 돌아가기
            # 뒤로가기 버튼이 있으면 클릭
            try:
                back_button = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn_list"))
                )
                back_button.click()
                logger.info("목록 버튼 클릭")
            except Exception:
                # 뒤로가기 버튼이 없으면 브라우저 뒤로가기
                logger.info("목록 버튼 없음, 브라우저 뒤로가기 사용")
                self.driver.back()
            
            # 목록 페이지 로딩 대기
            await asyncio.sleep(3)
            
            return detail_data
            
        except Exception as e:
            logger.error(f"상세 페이지 처리 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            
            # 오류 발생 시 뒤로가기 시도
            try:
                self.driver.back()
                await asyncio.sleep(3)
                logger.info("오류 복구: 브라우저 뒤로가기 실행")
            except Exception as back_error:
                logger.error(f"뒤로가기 실패: {str(back_error)}")
                
                # 입찰 목록 페이지로 다시 이동 시도
                await self.navigate_to_bid_list()
                await self.search_keyword()
            
            return None
    
    async def _extract_detail_with_html_parser(self, item):
        """
        HTML 파서를 사용하여 상세 페이지 정보 추출
        
        Args:
            item: 항목 데이터
            
        Returns:
            추출된 상세 정보
        """
        try:
            logger.info("HTML 파서로 상세 페이지 추출 시작")
            
            # 현재 페이지 소스 가져오기
            html_source = self.driver.page_source
            
            # BeautifulSoup으로 파싱
            soup = BeautifulSoup(html_source, 'html.parser')
            
            # 텍스트 내용 추출
            main_content = soup.select_one('.detail_content') or soup.select_one('#container')
            
            if not main_content:
                logger.warning("메인 콘텐츠 영역을 찾을 수 없음")
                return {}
                
            # 텍스트 추출
            extracted_text = main_content.get_text(separator='\n', strip=True)
            
            # 텍스트가 너무 길면 잘라내기
            if len(extracted_text) > 10000:
                extracted_text = extracted_text[:10000] + "..."
                logger.warning("텍스트가 너무 길어 잘라냄")
            
            # Gemini 텍스트 모델로 정보 추출
            prompt_template = """
            당신은 나라장터 웹사이트에서 입찰공고 상세 정보를 추출하는 AI 전문가입니다.
            아래 텍스트는 나라장터 입찰공고 상세 페이지에서 추출한 내용입니다.
            
            다음 정보를 JSON 형식으로 추출해주세요:
            1. organization: 공고기관
            2. division: 수요기관/담당자
            3. deadline: 입찰마감일시
            4. contract_method: 계약방법
            5. bid_type: 입찰방식
            6. qualification: 입찰참가자격
            7. description: 주요 과업내용 요약
            8. estimated_price: 추정가격 또는 예산금액
            
            각 필드에 해당하는 정보가 없는 경우 null로 표시하세요.
            반드시 JSON 형식으로 응답해주세요.
            
            텍스트:
            {content}
            """
            
            detail_data = await extract_with_gemini_text(extracted_text, prompt_template)
            
            # 첨부파일 정보 추출
            attachments = []
            file_links = soup.select('a[href*="download"]') or soup.select('.file a')
            
            for link in file_links:
                try:
                    file_name = link.get_text(strip=True)
                    file_url = link.get('href', '')
                    if file_name and file_url:
                        attachments.append({
                            "name": file_name,
                            "url": file_url
                        })
                except Exception as e:
                    logger.debug(f"첨부파일 추출 오류 (무시): {str(e)}")
            
            if attachments:
                detail_data["attachments"] = attachments
                logger.info(f"첨부파일 {len(attachments)}개 추출")
            
            return detail_data
            
        except Exception as e:
            logger.error(f"HTML 파서 처리 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return {} 

    async def run(self):
        """
        전체 크롤링 작업 실행
        """
        try:
            logger.info("=== HTML 파서 크롤링 테스트 시작 ===")
            
            # 초기화
            if not await self.initialize():
                logger.error("크롤러 초기화 실패")
                return False
            
            # 먼저 메인 페이지로 이동
            if not await self.navigate_to_main():
                logger.error("메인 페이지 접속 실패")
                return False
            
            # 입찰 목록 페이지로 이동
            if not await self.navigate_to_bid_list():
                logger.error("입찰 목록 페이지 이동 실패")
                return False
            
            # 키워드 검색
            if not await self.search_keyword():
                logger.error("키워드 검색 실패")
                return False
            
            # 검색 결과 추출
            search_results = await self.extract_search_results(max_items=3)
            if not search_results:
                logger.error("검색 결과 추출 실패 또는 결과 없음")
                return False
            
            # 결과 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            search_result_file = RESULTS_DIR / f"search_results_{self.keyword}_{timestamp}.json"
            with open(search_result_file, 'w', encoding='utf-8') as f:
                json.dump(search_results, f, ensure_ascii=False, indent=2)
            
            logger.info(f"검색 결과 저장 완료: {search_result_file}")
            
            # 상세 페이지 처리
            for item in search_results:
                logger.info(f"=== 상세 페이지 처리: {item['title']} ===")
                detail_data = await self.process_detail_page(item)
                
                # 결과에 추가
                if detail_data:
                    self.results.append(detail_data)
                
                # 다음 항목 전 잠시 대기
                await asyncio.sleep(2)
            
            # 최종 결과 저장
            if self.results:
                final_result_file = RESULTS_DIR / f"final_results_{self.keyword}_{timestamp}.json"
                with open(final_result_file, 'w', encoding='utf-8') as f:
                    json.dump(self.results, f, ensure_ascii=False, indent=2)
                
                logger.info(f"최종 결과 저장 완료: {final_result_file}")
            
            logger.info("=== HTML 파서 크롤링 테스트 완료 ===")
            return True
            
        except Exception as e:
            logger.error(f"크롤링 실행 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
        finally:
            # 리소스 정리
            await self.close()


async def main():
    """메인 실행 함수"""
    try:
        # 헤드리스 모드 설정 (커맨드 라인 인자로 받을 수도 있음)
        headless = False  # GUI 모드 활성화
        
        # 크롤러 인스턴스 생성 및 실행
        crawler = HTMLParserCrawler(headless=headless)
        await crawler.run()
        
    except Exception as e:
        logger.error(f"메인 실행 중 오류: {str(e)}")
        logger.debug(traceback.format_exc())
    

if __name__ == "__main__":
    # Windows에서 올바른 이벤트 루프 정책 설정
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # 비동기 메인 함수 실행
    asyncio.run(main()) 