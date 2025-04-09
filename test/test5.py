"""
나라장터 크롤러 테스트 스크립트 - 상세 페이지 개선 버전

이 스크립트는 나라장터 웹사이트의 상세 페이지 처리를 개선하기 위한 테스트 스크립트입니다.
HTML 파서를 통한 텍스트 추출 후 Gemini API 처리를 활용합니다.

헤드리스 모드에서도 동작하며, 키워드 'AI'로 검색합니다.
"""

import os
import sys
import asyncio
import logging
import json
import base64
import io
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
from PIL import Image

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(current_dir / 'test5.log', encoding='utf-8')
    ]
)
logger = logging.getLogger("crawler-test")

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
SCREENSHOTS_DIR = current_dir / 'screenshots'
RESULTS_DIR = current_dir / 'results'
SCREENSHOTS_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

# Gemini API 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)

async def extract_with_gemini_text(text_content: str, prompt_template: str) -> str:
    """
    텍스트 콘텐츠를 Gemini API에 전달하여 정보 추출
    
    Args:
        text_content: 분석할 텍스트 콘텐츠
        prompt_template: 프롬프트 템플릿 문자열 ('{content}' 플레이스홀더 포함)
        
    Returns:
        추출된 정보 문자열
    """
    try:
        # 환경 변수에서 API 키 가져오기
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.error("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
            return "API 키 오류로 정보 추출 실패"
        
        # Gemini API 설정
        genai.configure(api_key=api_key)
        
        # 보안 및 처리를 위한 텍스트 길이 제한
        # 너무 긴 경우 앞부분과 뒷부분만 유지하여 중요 부분 캡처
        max_length = 32000  # Gemini 모델의 최대 컨텍스트 길이보다 적게 설정
        if len(text_content) > max_length:
            # 앞부분 2/3, 뒷부분 1/3 유지
            front_portion = int(max_length * 0.67)
            back_portion = max_length - front_portion
            text_content = text_content[:front_portion] + "\n... (중략) ...\n" + text_content[-back_portion:]
            logger.warning(f"텍스트가 너무 길어 일부를 생략했습니다: {len(text_content)} -> {max_length}")
        
        # 프롬프트 구성
        prompt = prompt_template.format(content=text_content)
        
        # 모델 설정
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # 응답 생성
        response = model.generate_content(prompt)
        
        # 응답 추출 및 정리
        result_text = response.text
        
        # 결과 로깅 (첫 200자만)
        logger.info(f"Gemini API 응답 (일부): {result_text[:200]}...")
        
        return result_text
        
    except Exception as e:
        logger.error(f"Gemini API 호출 중 오류: {str(e)}")
        logger.debug(traceback.format_exc())
        return f"오류: {str(e)}"

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
        model = genai.GenerativeModel('gemini-2.0-flash')
        
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

class G2BCrawlerTest:
    """나라장터 크롤러 테스트 클래스"""
    
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
            logger.debug(traceback.format_exc())
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
            await asyncio.sleep(5)  # 대기 시간 증가
            
            # 페이지가 완전히 로드될 때까지 기다리기
            try:
                WebDriverWait(self.driver, 15).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
                logger.info("페이지 로드 완료")
            except Exception:
                logger.warning("페이지 로드 타임아웃")
            
            # 검색 결과가 나타날 때까지 대기 (테이블 또는 그리드가 로드될 때까지)
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: len(d.find_elements(By.CSS_SELECTOR, 
                        "table.st_list tbody tr, .w2grid_row, .gridBodyDefault, a.link_txt")) > 0
                )
                logger.info("검색 결과 확인됨")
                return True
            except Exception as e:
                logger.warning(f"검색 결과 테이블 확인 실패: {str(e)}")
                
                # 페이지 소스 저장 (디버깅용)
                with open('search_results_page.html', 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                logger.warning("페이지 소스를 'search_results_page.html'에 저장했습니다.")
                
                # 스크린샷 찍기 제거
                
                return False
            
        except Exception as e:
            logger.error(f"키워드 검색 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
    
    async def extract_search_results(self):
        """
        검색 결과 페이지에서 입찰 목록을 추출

        Returns:
            추출된 입찰 항목 리스트
        """
        try:
            # 현재 날짜 기록
            current_date = datetime.now()
            logger.info(f"현재 날짜 및 시간: {current_date.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 검색 결과 테이블 찾기
            try:
                # 여러 유형의 결과 컨테이너 시도
                result_elements = []
                
                # 1. 테이블 행 찾기 시도
                table_rows = self.driver.find_elements(By.CSS_SELECTOR, 
                    "table.table_list tr, table.bid_table tr, table.board_list tr, .results_table tr")
                if table_rows and len(table_rows) > 1:  # 헤더 행 제외
                    logger.info(f"테이블 형식 검색 결과 {len(table_rows)-1}개 발견")
                    result_elements = table_rows[1:]  # 헤더 행 제외
                
                # 2. 그리드 행 찾기 시도
                if not result_elements:
                    grid_rows = self.driver.find_elements(By.CSS_SELECTOR, 
                        ".w2grid_row, .gridBodyDefault tr, [id*='row_'], [id*='_row_']")
                    if grid_rows:
                        logger.info(f"그리드 형식 검색 결과 {len(grid_rows)}개 발견")
                        result_elements = grid_rows
                
                # 3. 그리드 셀 찾기 시도
                if not result_elements:
                    grid_cells = self.driver.find_elements(By.CSS_SELECTOR, 
                        "[id*='_cell_'][id*='_6'], [id*='_cell_'][onclick], [class*='cell'][onclick]")
                    if grid_cells:
                        logger.info(f"그리드 셀 형식 검색 결과 {len(grid_cells)}개 발견")
                        result_elements = grid_cells
                
                # 4. 링크 목록 찾기 시도
                if not result_elements:
                    links = self.driver.find_elements(By.CSS_SELECTOR, 
                        ".search_result a, .result_list a, .bid_list a")
                    if links:
                        logger.info(f"링크 형식 검색 결과 {len(links)}개 발견")
                        result_elements = links
                
                if not result_elements:
                    logger.warning("검색 결과를 찾을 수 없습니다. 인식할 수 없는 페이지 구조입니다.")
                    # 디버깅을 위해 현재 페이지 소스 저장
                    with open("search_results_debug.html", "w", encoding="utf-8") as f:
                        f.write(self.driver.page_source)
                    logger.info("디버깅을 위해 페이지 소스를 search_results_debug.html에 저장했습니다.")
                    return []
                
                logger.info(f"총 {len(result_elements)}개의 검색 결과 발견")
                
                # 각 행에서 데이터 추출
                items = []
                valid_items = []
                
                # 데이터가 존재하는 행만 처리 (일부 구분자, 빈 행 제외)
                processed_count = 0
                for index, row in enumerate(result_elements):
                    try:
                        # 최대 항목 수 제한 확인
                        if processed_count >= 10:
                            logger.info(f"최대 항목 수({10}개)에 도달하여 처리 중단")
                            break
                            
                        # 행 텍스트 검사 (빈 행 또는 구분자 건너뛰기)
                        row_text = row.text.strip()
                        if not row_text or row_text == '::' or row_text == '---':
                            continue
                        
                        # 행 데이터 추출
                        item_data = await self._extract_item_from_row(row, index, current_date)
                        
                        if item_data:
                            items.append(item_data)
                            
                            # AI로 검색어와 공고명의 연관성 판단
                            is_relevant = await check_relevance_with_ai(item_data['title'], self.keyword)
                            
                            # 연관성이 없는 경우 건너뛰기
                            if not is_relevant:
                                logger.info(f"입찰 {item_data['bid_number']}: 검색어 '{self.keyword}'와 연관성이 없어 건너뜁니다.")
                                continue
                            
                            # 7일 이내 마감인 경우 건너뛰기
                            if item_data['is_within_7days']:
                                logger.info(f"입찰 {item_data['bid_number']}: 마감일이 7일 이내이므로 건너뜁니다.")
                                continue
                            
                            # 유효한 항목 추가
                            valid_items.append(item_data)
                            processed_count += 1
                            logger.info(f"입찰 항목 #{len(valid_items)} 추출: {item_data['title']}")
                    except Exception as e:
                        logger.error(f"행 {index} 처리 중 오류: {str(e)}")
                        logger.debug(traceback.format_exc())
                
                logger.info(f"총 {len(items)}개 항목 발견, 그 중 {len(valid_items)}개 처리 대상")
                return valid_items
                
            except Exception as e:
                logger.error(f"검색 결과 테이블을 찾는 중 오류: {str(e)}")
                logger.debug(traceback.format_exc())
                return []
            
        except Exception as e:
            logger.error(f"검색 결과 추출 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return []
    
    async def _extract_item_from_row(self, row, index, current_date):
        """
        검색 결과의 단일 행에서 데이터 추출
        
        Args:
            row: 검색 결과 행 요소
            index: 행 인덱스
            current_date: 현재 날짜
            
        Returns:
            추출된 데이터 딕셔너리
        """
        try:
            item_data = {
                'index': index,
                'title': '',
                'bid_number': '',
                'department': '',
                'deadline': '',
                'is_within_7days': False,
                'url': '',
                'detail_url': ''
            }
            
            # 행 타입 확인 (CSS 클래스 또는 태그명으로)
            row_tag = row.tag_name.lower()
            row_class = row.get_attribute('class') or ''
            
            # 테이블 행인 경우
            if row_tag == 'tr':
                logger.info(f"테이블 행 형식 데이터 추출 (인덱스: {index})")
                
                # 셀 가져오기
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 3:
                    logger.warning(f"행 {index}의 셀 수가 충분하지 않음: {len(cells)}")
                    return None
                
                # 제목과 링크 추출
                try:
                    # 제목 셀 (보통 2번 또는 3번 셀)
                    title_cell_index = 2  # 기본 인덱스
                    
                    # 데이터 구조를 확인하고 인덱스 조정
                    for i, cell in enumerate(cells):
                        if '공고명' in cell.text or '공고제목' in cell.text:
                            title_cell_index = i
                            break
                    
                    # 제목 셀 확인
                    title_cell = cells[min(title_cell_index, len(cells)-1)]
                    
                    # 제목 셀에서 링크 요소 찾기
                    link = title_cell.find_element(By.TAG_NAME, "a")
                    item_data['title'] = link.text.strip()
                    item_data['url'] = link.get_attribute('href') or ''
                    
                    # 상세 페이지 URL이 없는 경우, onClick 속성 확인
                    if not item_data['url'] or item_data['url'] == '#' or 'javascript:' in item_data['url']:
                        onclick = link.get_attribute('onclick')
                        if onclick:
                            item_data['detail_url'] = onclick
                    else:
                        item_data['detail_url'] = item_data['url']
                    
                    logger.info(f"제목 추출: {item_data['title']}")
                    
                except Exception as e:
                    logger.warning(f"제목 추출 실패: {str(e)}")
                
                # 입찰 번호 추출
                try:
                    bid_number_cell = cells[1]  # 일반적으로 두 번째 셀
                    item_data['bid_number'] = bid_number_cell.text.strip()
                    logger.info(f"입찰 번호 추출: {item_data['bid_number']}")
                except Exception as e:
                    logger.warning(f"입찰 번호 추출 실패: {str(e)}")
                
                # 부서명 추출
                try:
                    dept_cell = cells[0]  # 일반적으로 첫 번째 셀
                    item_data['department'] = dept_cell.text.strip()
                    logger.info(f"부서명 추출: {item_data['department']}")
                except Exception as e:
                    logger.warning(f"부서명 추출 실패: {str(e)}")
                
                # 마감일시 추출
                try:
                    deadline_cell_index = 4  # 일반적으로 다섯 번째 셀
                    
                    # 데이터 구조 확인하고 인덱스 조정
                    for i, cell in enumerate(cells):
                        if '마감일시' in cell.text:
                            deadline_cell_index = i
                            break
                    
                    if deadline_cell_index < len(cells):
                        deadline_cell = cells[deadline_cell_index]
                        deadline_text = deadline_cell.text.strip()
                        item_data['deadline'] = deadline_text
                        
                        logger.info(f"마감일시 텍스트: {deadline_text}")
                        
                        # 마감일시 문자열 형식 변환 시도
                        try:
                            # 여러 날짜 형식 처리
                            date_formats = [
                                "%Y/%m/%d", "%Y-%m-%d", 
                                "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S",
                                "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M",
                                "%Y년 %m월 %d일", "%Y년%m월%d일"
                            ]
                            
                            deadline_date = None
                            for fmt in date_formats:
                                try:
                                    deadline_date = datetime.strptime(deadline_text, fmt)
                                    break
                                except ValueError:
                                    continue
                            
                            if deadline_date:
                                # 마감일과 현재 날짜 사이의 차이 계산
                                days_difference = (deadline_date - current_date).days
                                logger.info(f"마감까지 남은 일수: {days_difference}일")
                                
                                # 7일 이내 마감 여부 확인
                                item_data['is_within_7days'] = days_difference <= 7
                                
                                if item_data['is_within_7days']:
                                    logger.info(f"입찰 {item_data['bid_number']}의 마감일시가 7일 이내입니다. (마감일: {deadline_date.strftime('%Y-%m-%d')})")
                                else:
                                    logger.info(f"입찰 {item_data['bid_number']}의 마감일시가 7일보다 더 남았습니다. (마감일: {deadline_date.strftime('%Y-%m-%d')})")
                            else:
                                logger.warning(f"마감일시 '{deadline_text}' 형식을 파싱할 수 없습니다.")
                                
                        except Exception as e:
                            logger.warning(f"마감일시 파싱 실패: {str(e)}")
                except Exception as e:
                    logger.warning(f"마감일시 추출 실패: {str(e)}")
            
            # 그리드 행/셀인 경우
            elif 'w2grid_row' in row_class or 'gridBodyDefault' in row_class or 'cell' in row.get_attribute('id', ''):
                logger.info(f"그리드 형식 데이터 추출 (인덱스: {index})")
                
                try:
                    # ID를 이용한 접근 시도
                    row_id = row.get_attribute('id') or ''
                    
                    # 셀 ID인 경우 ('_cell_숫자_숫자' 패턴)
                    if '_cell_' in row_id:
                        # 직접 셀을 처리
                        item_data['title'] = row.text.strip()
                        onclick = row.get_attribute('onclick')
                        if onclick:
                            item_data['detail_url'] = onclick
                        logger.info(f"셀 ID 기반 데이터 추출: {item_data['title']}")
                        
                        # 행 번호와 열 번호 추출 시도
                        try:
                            id_parts = row_id.split('_cell_')
                            if len(id_parts) > 1:
                                row_col = id_parts[1].split('_')
                                if len(row_col) > 1:
                                    row_num, col_num = row_col
                                    
                                    # 다른 셀 찾기 시도
                                    base_id = id_parts[0]
                                    
                                    # 입찰 번호 (일반적으로 1번 열)
                                    try:
                                        bid_cell = self.driver.find_element(By.ID, f"{base_id}_cell_{row_num}_1")
                                        item_data['bid_number'] = bid_cell.text.strip()
                                    except:
                                        pass
                                    
                                    # 부서명 (일반적으로 0번 열)
                                    try:
                                        dept_cell = self.driver.find_element(By.ID, f"{base_id}_cell_{row_num}_0")
                                        item_data['department'] = dept_cell.text.strip()
                                    except:
                                        pass
                                    
                                    # 마감일 (일반적으로 4번 열)
                                    try:
                                        deadline_cell = self.driver.find_element(By.ID, f"{base_id}_cell_{row_num}_4")
                                        deadline_text = deadline_cell.text.strip()
                                        item_data['deadline'] = deadline_text
                                        
                                        # 마감일 확인 로직은 테이블 행과 동일
                                        # 여러 날짜 형식 처리
                                        date_formats = [
                                            "%Y/%m/%d", "%Y-%m-%d", 
                                            "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S",
                                            "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M",
                                            "%Y년 %m월 %d일", "%Y년%m월%d일"
                                        ]
                                        
                                        deadline_date = None
                                        for fmt in date_formats:
                                            try:
                                                deadline_date = datetime.strptime(deadline_text, fmt)
                                                break
                                            except ValueError:
                                                continue
                                        
                                        if deadline_date:
                                            days_difference = (deadline_date - current_date).days
                                            item_data['is_within_7days'] = days_difference <= 7
                                    except:
                                        pass
                        except Exception as e:
                            logger.warning(f"셀 ID에서 행/열 정보 추출 실패: {str(e)}")
                    
                    # 일반 그리드 행인 경우
                    else:
                        # 셀 요소들 찾기
                        cells = row.find_elements(By.CSS_SELECTOR, ".w2grid_cell, .gridCellDefault")
                        if cells:
                            logger.info(f"그리드 행에서 {len(cells)}개 셀 발견")
                            
                            # 제목 (일반적으로 2번 셀)
                            if len(cells) > 2:
                                item_data['title'] = cells[2].text.strip()
                                
                                # 클릭 이벤트 확인
                                onclick = cells[2].get_attribute('onclick')
                                if onclick:
                                    item_data['detail_url'] = onclick
                            
                            # 입찰 번호 (일반적으로 1번 셀)
                            if len(cells) > 1:
                                item_data['bid_number'] = cells[1].text.strip()
                            
                            # 부서명 (일반적으로 0번 셀)
                            if len(cells) > 0:
                                item_data['department'] = cells[0].text.strip()
                            
                            # 마감일 (일반적으로 4번 셀)
                            if len(cells) > 4:
                                deadline_text = cells[4].text.strip()
                                item_data['deadline'] = deadline_text
                                
                                # 마감일 확인 로직은 테이블 행과 동일
                                # 여러 날짜 형식 처리
                                date_formats = [
                                    "%Y/%m/%d", "%Y-%m-%d", 
                                    "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S",
                                    "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M",
                                    "%Y년 %m월 %d일", "%Y년%m월%d일"
                                ]
                                
                                deadline_date = None
                                for fmt in date_formats:
                                    try:
                                        deadline_date = datetime.strptime(deadline_text, fmt)
                                        break
                                    except ValueError:
                                        continue
                                
                                if deadline_date:
                                    days_difference = (deadline_date - current_date).days
                                    item_data['is_within_7days'] = days_difference <= 7
                except Exception as e:
                    logger.warning(f"그리드 행 데이터 추출 실패: {str(e)}")
            
            # 링크 요소인 경우
            elif row_tag == 'a':
                logger.info(f"링크 형식 데이터 추출 (인덱스: {index})")
                
                item_data['title'] = row.text.strip()
                item_data['url'] = row.get_attribute('href') or ''
                
                # 상세 페이지 URL이 없는 경우
                if not item_data['url'] or item_data['url'] == '#' or 'javascript:' in item_data['url']:
                    onclick = row.get_attribute('onclick')
                    if onclick:
                        item_data['detail_url'] = onclick
                else:
                    item_data['detail_url'] = item_data['url']
                
                # 링크 요소에는 추가 데이터가 없을 수 있음
                item_data['bid_number'] = f"Link{index}"  # 임시 번호
                
                # 부모 요소에서 마감일 등 추가 정보 찾기 시도
                try:
                    parent = row.find_element(By.XPATH, "./..")
                    
                    # 부모의 다른 자식 요소 확인
                    siblings = parent.find_elements(By.XPATH, "./*")
                    
                    for sibling in siblings:
                        text = sibling.text.strip()
                        
                        # 마감일 포함 여부 확인
                        if '마감' in text and ('/' in text or '-' in text):
                            item_data['deadline'] = text
                            
                            # 마감일 확인 로직은 테이블 행과 동일
                            # 여러 날짜 형식 추출 시도
                            date_pattern = r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})'
                            date_matches = re.search(date_pattern, text)
                            
                            if date_matches:
                                date_str = date_matches.group(1)
                                try:
                                    deadline_date = datetime.strptime(date_str, "%Y/%m/%d")
                                except ValueError:
                                    try:
                                        deadline_date = datetime.strptime(date_str, "%Y-%m-%d")
                                    except:
                                        deadline_date = None
                                
                                if deadline_date:
                                    days_difference = (deadline_date - current_date).days
                                    item_data['is_within_7days'] = days_difference <= 7
                except Exception as e:
                    logger.warning(f"링크의 부모 요소에서 추가 정보 추출 실패: {str(e)}")
            
            # 유효한 데이터인지 확인
            if not item_data['title']:
                logger.warning(f"행 {index}에서 제목을 추출할 수 없음")
                return None
            
            # JSON 직렬화를 위해 WebElement 객체가 있는지 확인하고 제거
            for key in list(item_data.keys()):
                if hasattr(item_data[key], 'tag_name'):  # WebElement 객체 확인
                    item_data[key] = str(item_data[key])  # 문자열로 변환
                elif isinstance(item_data[key], datetime):
                    item_data[key] = item_data[key].isoformat()  # 날짜/시간 객체를 ISO 형식으로 변환
                elif isinstance(item_data[key], (set, frozenset)):
                    item_data[key] = list(item_data[key])  # 집합을 리스트로 변환
            
            return item_data
            
        except Exception as e:
            logger.error(f"행 {index} 데이터 추출 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return None
    
    async def run(self):
        """
        전체 크롤링 작업 실행
        """
        try:
            logger.info("=== 나라장터 크롤링 테스트 시작 ===")
            
            # 초기화
            if not await self.initialize():
                logger.error("크롤러 초기화 실패")
                return False
            
            # 입찰 목록 페이지로 이동
            if not await self.navigate_to_bid_list():
                logger.error("입찰 목록 페이지 이동 실패")
                return False
            
            # 키워드 검색
            if not await self.search_keyword():
                logger.error("키워드 검색 실패")
                return False
            
            # 검색 결과 추출 (모든 항목 처리하도록 max_items 제거)
            search_results = await self.extract_search_results()
            if not search_results:
                logger.error("검색 결과 추출 실패 또는 결과 없음")
                return False
            
            logger.info(f"총 {len(search_results)}개 항목 처리 시작")
            
            # 각 항목에 대해 상세 페이지 처리
            detailed_results = []
            for index, item in enumerate(search_results):
                try:
                    logger.info(f"항목 {index+1}/{len(search_results)} 상세 페이지 처리 시작: {item['title']}")
                    
                    # 상세 페이지 처리
                    detail_data = await self.process_detail_page(item)
                    
                    if detail_data:
                        item.update(detail_data)
                        detailed_results.append(item)
                        logger.info(f"항목 {index+1} 상세 페이지 처리 성공")
                    else:
                        logger.warning(f"항목 {index+1} 상세 페이지 처리 실패")
                except Exception as e:
                    logger.error(f"항목 {index+1} 처리 중 오류: {str(e)}")
                    logger.debug(traceback.format_exc())
            
            # 결과 저장 - WebElement 객체 필터링 함수
            def filter_web_elements(obj):
                """JSON 직렬화 불가능한 객체 처리"""
                if hasattr(obj, 'tag_name') or 'selenium.webdriver.remote.webelement' in str(type(obj)):
                    return str(obj)  # WebElement 객체를 문자열로 변환
                elif isinstance(obj, datetime):
                    return obj.isoformat()  # 날짜/시간 객체를 ISO 형식으로 변환
                elif isinstance(obj, (set, frozenset)):
                    return list(obj)  # 집합을 리스트로 변환
                return str(obj)  # 그 외 직렬화 불가능 객체를 문자열로 변환
            
            # 결과 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            search_result_file = RESULTS_DIR / f"search_results_{self.keyword}_{timestamp}.json"
            
            # 결과 데이터 전처리 - 모든 WebElement 객체 제거
            cleaned_results = []
            for item in detailed_results:
                # 각 항목에서 WebElement 객체 필터링
                cleaned_item = {}
                for key, value in item.items():
                    if hasattr(value, 'tag_name') or 'selenium.webdriver.remote.webelement' in str(type(value)):
                        cleaned_item[key] = str(value)
                    else:
                        cleaned_item[key] = value
                cleaned_results.append(cleaned_item)
            
            # JSON 저장
            with open(search_result_file, 'w', encoding='utf-8') as f:
                json.dump(cleaned_results, f, ensure_ascii=False, indent=2, default=filter_web_elements)
            
            logger.info(f"검색 결과 저장 완료: {search_result_file}")
            
            logger.info("=== 나라장터 크롤링 테스트 완료 ===")
            return True
            
        except Exception as e:
            logger.error(f"크롤링 실행 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
        finally:
            # 리소스 정리
            await self.close()

    async def process_detail_page(self, item):
        """
        항목의 상세 페이지 처리
        
        Args:
            item: 처리할 항목 데이터
            
        Returns:
            상세 정보 (성공 시) 또는 None (실패 시)
        """
        try:
            logger.info(f"상세 페이지 처리 시작 - {item['title']}")
            
            # 실제 행 인덱스 값 획득
            row_index = item.get('index', 0)
            
            # 상세 페이지 이동 - 셀 ID를 사용하여 직접 접근
            try:
                # 현재 페이지의 행에 맞는 셀 ID를 생성
                cell_id = f"mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_cell_{row_index}_6"
                title_element = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.ID, cell_id))
                )
                
                # 셀 내부의 링크 찾기
                link_element = title_element.find_element(By.TAG_NAME, "a")
                
                # 직접 클릭
                link_element.click()
                logger.info("셀 ID로 링크 클릭 성공")
            except Exception as e:
                logger.error(f"상세 페이지 이동 실패: {str(e)}")
                return None
            
            # 상세 페이지 로딩 대기
            await asyncio.sleep(3)
            
            # 상세 페이지에서 정보 추출
            detail_data = await self._extract_detail_page_data(item['bid_number'], item['title'])
            
            # 목록으로 돌아가기 - 항상 브라우저 뒤로가기 사용
            self.driver.back()
            logger.info("브라우저 뒤로가기로 목록 페이지 복귀")
            
            # 목록 페이지 로딩 대기
            await asyncio.sleep(3)
            
            return detail_data
            
        except Exception as e:
            logger.error(f"상세 페이지 처리 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            
            # 오류 발생 시 브라우저 뒤로가기 시도
            try:
                self.driver.back()
                await asyncio.sleep(2)
                logger.info("오류 복구: 브라우저 뒤로가기 실행")
            except Exception as back_error:
                logger.error(f"뒤로가기 실패: {str(back_error)}")
            
                # 입찰 목록 페이지로 다시 이동 시도
                await self.navigate_to_bid_list()
                await self.search_keyword()
            
            return None

    async def _extract_detail_page_data(self, bid_number, bid_title):
        """
        상세 페이지에서 데이터 추출 (HTML 파서 중심)
        
        Args:
            bid_number: 입찰 번호
            bid_title: 입찰 제목
            
        Returns:
            추출된 데이터
        """
        try:
            logger.info(f"상세 페이지 데이터 추출 시작: {bid_number}")
            
            # HTML 소스 가져오기
            html_source = self.driver.page_source
            
            # BeautifulSoup 파싱
            soup = BeautifulSoup(html_source, 'html.parser')
            
            # 결과 데이터 초기화
            detail_data = {
                "bid_number": bid_number,
                "title": bid_title,
                "organization": None,
                "division": None,
                "contract_method": None,
                "bid_type": None,
                "estimated_price": None,
                "qualification": None,
                "description": None,
                "raw_tables": {}  # 원시 테이블 데이터 저장
            }
            
            # 모든 테이블과 tbody 요소 추출하여 저장
            try:
                all_tables = soup.find_all('table')
                for i, table in enumerate(all_tables):
                    # 테이블 캡션 또는 제목 찾기
                    caption = table.find('caption')
                    caption_text = caption.get_text(strip=True) if caption else f"테이블_{i+1}"
                    
                    # 테이블 내 tbody 요소 찾기
                    tbody = table.find('tbody')
                    if tbody:
                        # tbody 내 모든 행과 셀을 추출하여 구조화된 데이터로 저장
                        rows_data = []
                        rows = tbody.find_all('tr')
                        for row in rows:
                            cells_data = {}
                            th_cells = row.find_all('th')
                            td_cells = row.find_all('td')
                            
                            # th 셀 처리
                            for j, cell in enumerate(th_cells):
                                header_key = f"th_{j+1}"
                                cells_data[header_key] = {
                                    "text": cell.get_text(strip=True),
                                    "attributes": dict(cell.attrs)
                                }
                            
                            # td 셀 처리
                            for j, cell in enumerate(td_cells):
                                cell_key = f"td_{j+1}"
                                # 셀 내 링크 추출
                                links = cell.find_all('a')
                                links_data = []
                                for link in links:
                                    link_data = {
                                        "text": link.get_text(strip=True),
                                        "href": link.get('href', ''),
                                        "onclick": link.get('onclick', ''),
                                        "attributes": dict(link.attrs)
                                    }
                                    links_data.append(link_data)
                                
                                cells_data[cell_key] = {
                                    "text": cell.get_text(strip=True),
                                    "links": links_data,
                                    "attributes": dict(cell.attrs)
                                }
                            
                            rows_data.append(cells_data)
                        
                        detail_data["raw_tables"][caption_text] = rows_data
                    
                logger.info(f"{len(detail_data['raw_tables'])}개의 원시 테이블 데이터 저장 완료")
                
                # 원시 테이블 데이터를 텍스트로 변환하여 Gemini 모델에 전달
                if detail_data["raw_tables"]:
                    table_text = ""
                    
                    # 테이블 데이터를 텍스트로 변환
                    for table_name, rows in detail_data["raw_tables"].items():
                        table_text += f"[테이블: {table_name}]\n"
                        
                        for row_data in rows:
                            header_texts = []
                            value_texts = []
                            
                            # 헤더 텍스트 추출
                            for key, cell in row_data.items():
                                if key.startswith('th_'):
                                    header_texts.append(cell["text"])
                                elif key.startswith('td_'):
                                    value_texts.append(cell["text"])
                            
                            # 행 정보 추가
                            if header_texts and value_texts:
                                for i, header in enumerate(header_texts):
                                    if i < len(value_texts):
                                        table_text += f"{header}: {value_texts[i]}\n"
                            elif header_texts:
                                table_text += f"{', '.join(header_texts)}\n"
                            elif value_texts:
                                table_text += f"{', '.join(value_texts)}\n"
                        
                        table_text += "\n"
                    
                    # 파일 첨부 섹션 찾기
                    file_links = soup.select("a[href*='download'], a[href*='fileDown'], a.file")
                    file_info = ""
                    if file_links:
                        file_info += "[파일첨부]\n"
                        for link in file_links:
                            file_name = link.get_text(strip=True) or link.get("title") or "첨부파일"
                            file_info += f"- {file_name}\n"
                    
                    # Gemini 프롬프트 구성
                    prompt_template = """
입찰 상세 정보 추출 전문가로서, 다음 HTML 정보에서 중요 정보를 추출해주세요.

다음은 입찰공고 상세페이지의 테이블 데이터와 전체 페이지 텍스트입니다:

{content}

다음 중요 정보를 확인하여 저장해주세요.(JSON 형식으로 응답 X)
1. 게시일시 
2. 입찰공고번호 
3. 공고명 
4. 입찰방식
5. 낙찰방법
6. 계약방법
7. 계약구분
8. 공동계약 및 구성방식(컨소시엄 여부)
9. 실적제한 여부, 제한여부
10. 가격과 관련된 모든정보(예가방법, 사업금액, 배정에산, 추정에산)
11. 기관담당자정보(담당자 이름, 팩스번호, 전화번호)
12. 연관정보(이건 링크임)
13. 파일첨부

위 형식대로 각 항목에 해당하는 정보를 추출해주세요. 정보가 없는 경우 "정보 없음"으로 표시해주세요.
JSON 형식이 아닌 일반 텍스트로 응답해주세요.
"""
                    
                    combined_text = f"{table_text}\n\n{file_info}"
                    
                    # Gemini API 호출
                    try:
                        gemini_response = await extract_with_gemini_text(combined_text, prompt_template)
                        
                        # Gemini 응답을 문자열로 변환하여 저장
                        if isinstance(gemini_response, dict):
                            # 딕셔너리인 경우 문자열로 변환
                            detail_data["prompt_result"] = json.dumps(gemini_response, ensure_ascii=False)
                        else:
                            # 이미 문자열인 경우 그대로 저장
                            detail_data["prompt_result"] = str(gemini_response)
                        
                        logger.info("Gemini API를 통한 상세 정보 추출 완료")
                    except Exception as gemini_err:
                        logger.error(f"Gemini API 호출 오류: {str(gemini_err)}")
                
            except Exception as raw_tables_err:
                logger.warning(f"원시 테이블 데이터 추출 실패: {str(raw_tables_err)}")
            
            # 1. 주요 섹션별 데이터 추출 (추가 데이터 확보용)
            section_names = ["공고일반", "입찰자격", "투찰제한", "제안요청정보", "협상에 의한 계약", "가격", 
                           "기관담당자정보", "수요기관 담당자정보", "연관정보", "파일첨부"]
            
            # 1-1. 공고기관 정보 추출 (기관담당자정보 섹션)
            try:
                # 기관담당자정보 섹션 찾기
                org_section = None
                for heading in soup.find_all(['h3', 'h4', 'div', 'span', 'strong']):
                    if "기관담당자" in heading.get_text() or "공고기관" in heading.get_text():
                        org_section = heading.find_parent('div') or heading.find_parent('table') or heading.find_parent('section')
                        break
                
                if org_section:
                    # 테이블 내용 추출
                    org_tables = org_section.find_all('table')
                    if org_tables:
                        for table in org_tables:
                            rows = table.find_all('tr')
                            for row in rows:
                                cells = row.find_all(['th', 'td'])
                                if len(cells) >= 2:
                                    header = cells[0].get_text(strip=True)
                                    value = cells[1].get_text(strip=True)
                                    
                                    if any(keyword in header for keyword in ["수요기관", "공고기관"]):
                                        detail_data["organization"] = value
                                    elif any(keyword in header for keyword in ["담당자", "담당부서"]):
                                        detail_data["division"] = value
            except Exception as org_err:
                logger.warning(f"기관정보 추출 실패: {str(org_err)}")
            
            # 여기에 더 많은 섹션별 추출 로직이 있지만 Gemini API 결과가 있으면 충분함
            
            return detail_data
            
        except Exception as e:
            logger.error(f"상세 페이지 데이터 추출 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return {}

    async def _extract_contract_details(self, soup, logger):
        """
        세부 계약 정보 추출 함수
        
        Args:
            soup: BeautifulSoup 객체
            logger: 로깅 객체
            
        Returns:
            dict: 추출된 계약 상세 정보
        """
        try:
            logger.info("계약 상세 정보 추출 중...")
            contract_details = {}
            
            # 모든 테이블 콘텐츠 추출
            all_tables_html = ""
            tables = soup.find_all('table')
            for table in tables:
                all_tables_html += str(table) + "\n\n"
                
            # 테이블과 raw_tables 데이터 분석
            # 계약 상세 정보를 raw_tables에서 추출
            raw_tables_data = {}
            for i, table in enumerate(tables):
                caption = table.find('caption')
                caption_text = caption.get_text(strip=True) if caption else f"테이블_{i+1}"
                
                # 테이블 내 tbody 요소 찾기
                tbody = table.find('tbody')
                if tbody:
                    # tbody 내 모든 행과 셀 데이터 수집
                    rows_data = []
                    rows = tbody.find_all('tr')
                    for row in rows:
                        cells_data = {}
                        th_cells = row.find_all('th')
                        td_cells = row.find_all('td')
                        
                        # th 셀 처리
                        for j, cell in enumerate(th_cells):
                            header_key = f"th_{j+1}"
                            cells_data[header_key] = {
                                "text": cell.get_text(strip=True),
                                "attributes": dict(cell.attrs)
                            }
                        
                        # td 셀 처리
                        for j, cell in enumerate(td_cells):
                            cell_key = f"td_{j+1}"
                            # 셀 내 input 필드 확인 (readonly 포함)
                            input_fields = cell.find_all('input')
                            input_data = []
                            for input_field in input_fields:
                                input_data.append({
                                    "value": input_field.get('value', ''),
                                    "title": input_field.get('title', ''),
                                    "id": input_field.get('id', ''),
                                    "readonly": input_field.get('readonly', False),
                                    "class": input_field.get('class', [])
                                })
                                
                            # 셀 내 링크 추출
                            links = cell.find_all('a')
                            links_data = []
                            for link in links:
                                link_data = {
                                    "text": link.get_text(strip=True),
                                    "href": link.get('href', ''),
                                    "onclick": link.get('onclick', ''),
                                    "attributes": dict(link.attrs)
                                }
                                links_data.append(link_data)
                            
                            cells_data[cell_key] = {
                                "text": cell.get_text(strip=True),
                                "links": links_data,
                                "inputs": input_data,
                                "attributes": dict(cell.attrs)
                            }
                        
                        rows_data.append(cells_data)
                    
                    raw_tables_data[caption_text] = rows_data
            
            # 저장된 raw_tables 데이터에서 필요한 정보 추출
            for table_name, rows in raw_tables_data.items():
                for row in rows:
                    for key, cell in row.items():
                        if key.startswith('th_'):
                            header_text = cell["text"]
                            # 해당 헤더에 매칭되는 value 셀 찾기
                            header_idx = int(key.split('_')[1])
                            value_key = f"td_{header_idx}"
                            
                            if value_key in row:
                                value_cell = row[value_key]
                                value_text = value_cell["text"]
                                
                                # 계약방법 추출
                                if any(keyword in header_text for keyword in ["계약방법", "계약형태", "계약구분"]):
                                    contract_details["contract_method"] = value_text
                                    logger.info(f"계약방법 추출: {value_text}")
                                
                                # 입찰방법 추출
                                elif any(keyword in header_text for keyword in ["입찰방법", "입찰형태", "경쟁방법", "낙찰방법"]):
                                    # 텍스트 값이 있으면 사용, 없으면 input 필드 확인
                                    if value_text and value_text.strip():
                                        contract_details["bidding_method"] = value_text
                                        logger.info(f"입찰방법 추출: {value_text}")
                                    elif 'inputs' in value_cell and value_cell['inputs']:
                                        # input 필드 확인
                                        for input_field in value_cell['inputs']:
                                            # 낙찰방법 관련 input 필드인 경우
                                            if input_field.get('title') == '낙찰방법':
                                                input_value = input_field.get('value')
                                                if input_value:
                                                    contract_details["bidding_method"] = input_value
                                                    logger.info(f"입찰방법(input 필드에서 추출): {input_value}")
                                                else:
                                                    # 값이 없는 경우 일반적으로 JavaScript로 동적 설정되는 값
                                                    contract_details["bidding_method"] = "최저가낙찰제"  # 기본값 (필요에 따라 수정)
                                                    logger.info(f"낙찰방법 기본값 설정: 최저가낙찰제")
                                
                                # 추정가격 추출
                                elif any(keyword in header_text for keyword in ["추정가격", "기초금액", "예정가격", "사업금액"]):
                                    contract_details["estimated_price"] = value_text
                                    logger.info(f"추정가격 추출: {value_text}")
                                
                                # 계약기간 추출
                                elif any(keyword in header_text for keyword in ["계약기간", "이행기간", "납품기한", "완료기한"]):
                                    contract_details["contract_period"] = value_text
                                    logger.info(f"계약기간 추출: {value_text}")
                                
                                # 납품장소 추출
                                elif any(keyword in header_text for keyword in ["납품장소", "이행장소", "설치장소"]):
                                    contract_details["delivery_location"] = value_text
                                    logger.info(f"납품장소 추출: {value_text}")
                                
                                # 참가자격 추출
                                elif any(keyword in header_text for keyword in ["참가자격", "참가제한", "입찰참가자격", "참가조건"]):
                                    contract_details["qualification"] = value_text
                                    logger.info(f"참가자격 추출: {value_text}")
            
            # 참가자격이 별도의 div나 텍스트 블록에 있는 경우 추출
            if "qualification" not in contract_details or not contract_details["qualification"]:
                # 자격 관련 섹션 찾기
                qualification_sections = []
                for heading in soup.find_all(['h3', 'h4', 'div', 'strong', 'p']):
                    heading_text = heading.get_text(strip=True)
                    if any(keyword in heading_text for keyword in ["참가자격", "참가제한", "입찰참가", "자격요건"]):
                        # 해당 헤딩의 부모 또는 다음 형제 요소 찾기
                        parent = heading.find_parent('div') or heading.find_parent('section')
                        if parent:
                            qualification_text = parent.get_text(strip=True).replace(heading_text, "", 1)
                            qualification_sections.append(qualification_text)
                        
                        # 또는 다음 형제 요소가 내용인 경우
                        next_sibling = heading.find_next_sibling()
                        if next_sibling and next_sibling.name in ['div', 'p', 'ul']:
                            qualification_sections.append(next_sibling.get_text(strip=True))
                
                if qualification_sections:
                    contract_details["qualification"] = "\n".join(qualification_sections)
                    logger.info(f"별도 섹션에서 참가자격 추출: {contract_details['qualification'][:50]}...")
            
            # 전체 페이지에서 모든 input 필드 검색하여 중요 필드 추출
            all_input_fields = soup.find_all('input')
            important_fields = {}
            for input_field in all_input_fields:
                field_title = input_field.get('title')
                field_value = input_field.get('value')
                field_id = input_field.get('id')
                
                # 이미 값이 추출된 필드는 건너뛰기
                if field_title and field_title in ['낙찰방법', '계약방법', '참가자격'] and field_id:
                    important_fields[field_title] = {
                        'id': field_id,
                        'value': field_value or "값 없음(JavaScript로 설정됨)"
                    }
            
            # 원시 데이터 저장 (디버깅 및 분석용)
            contract_details['raw_input_fields'] = important_fields
            
            # 파일 첨부 정보 추출
            file_attachments = []
            file_links = soup.select("a[href*='fileDown']")
            for link in file_links:
                file_name = link.get_text(strip=True)
                if file_name:
                    file_attachments.append(file_name)
            
            contract_details["file_attachments"] = file_attachments
            logger.info(f"첨부파일 {len(file_attachments)}개 추출 완료")
            
            # Gemini API 호출을 위한 모든 테이블 HTML
            # Gemini API 프롬프트 템플릿
            prompt_template = """
            아래는 한국 정부 입찰 및 계약에 관한 테이블 데이터입니다. 테이블 내용을 분석하여 다음 정보를 추출하세요:

            1. 입찰 공고일 (bid_date)
            2. 입찰 번호 (bid_number) 
            3. 입찰 제목 (bid_title)
            4. 입찰 방식 (bidding_method) - 예: 일반경쟁, 제한경쟁, 지명경쟁 등
            5. 낙찰 방식 (award_method) - 예: 적격심사, 최저가, 종합평가 등
            6. 계약 방식 (contract_method) - 예: 총액, 단가 등
            7. 계약 종류 (contract_type) - 예: 공사, 용역, 물품 등
            8. 컨소시엄 가능 여부 (consortium_status)
            9. 실적 제한 조건 (performance_restriction)
            10. 예가 방식 (pricing_method) - 예: 복수예가, 단일예가 등
            11. 기초금액 및 추정가격 (estimated_price)
            12. 담당자 연락처 (contact_info)
            13. 계약기간/납품기한 (contract_period)
            14. 납품 장소 (delivery_location)

            가능한 상세히 답변해주시고, 해당 정보가 없는 경우 "정보 없음"으로 표시해주세요.

            테이블 데이터:
            {content}

            첨부 파일 목록: {files}
            """
            
            formatted_prompt = prompt_template.format(
                content=all_tables_html,
                files=", ".join(file_attachments) if file_attachments else "첨부 파일 없음"
            )
            
            # Gemini API 호출
            gemini_response = await extract_with_gemini_text(
                text_content=all_tables_html, 
                prompt_template=formatted_prompt
            )
            
            # 응답 저장
            contract_details["gemini_analysis"] = gemini_response
            
            # 디버깅을 위해 전체 raw_tables 데이터도 저장
            contract_details["raw_tables_data"] = raw_tables_data
            
            logger.info(f"계약 상세 정보 추출 완료: {list(contract_details.keys())}")
            return contract_details
            
        except Exception as e:
            logger.error(f"계약 상세 정보 추출 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return {}

    async def extract_detail_page_info(self, detail_url):
        """
        상세 페이지 정보 추출
        
        Args:
            detail_url: 상세 페이지 URL
            
        Returns:
            추출된 상세 페이지 데이터
        """
        # 현재 윈도우 핸들 저장
        main_window = self.driver.current_window_handle
        detail_data = {}
        
        try:
            logger.info(f"상세 페이지 정보 추출 시작: {detail_url}")
            
            # 새 탭에서 URL 열기
            if detail_url.startswith("javascript:"):
                # JavaScript 함수 호출 처리
                try:
                    # JavaScript 코드 실행
                    js_code = detail_url.replace("javascript:", "")
                    self.driver.execute_script(js_code)
                    logger.info(f"JavaScript 실행: {js_code[:50]}...")
                except Exception as js_err:
                    logger.error(f"JavaScript 실행 실패: {str(js_err)}")
                    return detail_data
            else:
                logger.error(f"인식할 수 없는 URL 형식: {detail_url}")
                return detail_data
            
            # 페이지 로딩 대기
            await asyncio.sleep(3)
            
            # 팝업창 처리 (필요한 경우)
            self._handle_detail_page_popups()
            
            # HTML 소스 가져오기
            html_source = self.driver.page_source
            
            # BeautifulSoup 파싱
            soup = BeautifulSoup(html_source, 'html.parser')
            
            # 계약 세부 정보 추출
            contract_details = await self._extract_contract_details(soup, logger)
            
            # 다른 페이지 정보 추출 (기존 메서드 활용)
            other_details = await self._extract_detail_page_data(
                bid_number=detail_data.get('bid_number', ''), 
                bid_title=detail_data.get('title', '')
            )
            
            # 결과 병합
            detail_data.update(contract_details)
            if other_details:
                detail_data.update(other_details)
            
            logger.info(f"상세 페이지 정보 추출 완료: {list(detail_data.keys())}")
            return detail_data
            
        except Exception as e:
            logger.error(f"상세 페이지 정보 추출 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            
            # 오류 발생 시 원래 윈도우로 복귀 시도
            try:
                if self.driver.current_window_handle != main_window:
                    self.driver.close()
                    self.driver.switch_to.window(main_window)
                    logger.info("오류 발생 후 메인 윈도우 복귀")
            except Exception as recovery_err:
                logger.error(f"윈도우 복구 실패: {str(recovery_err)}")
                
                # 브라우저 재시작이 필요할 수 있음
                # 이 부분은 필요에 따라 구현
                
            return {}
            
        finally:
            # 현재 탭 닫기
            self.driver.close()
            
            # 메인 탭으로 복귀
            self.driver.switch_to.window(main_window)
            logger.info("메인 윈도우로 복귀 완료")

    def _handle_detail_page_popups(self):
        """상세 페이지 내 팝업 처리"""
        try:
            # 알림창(alert) 확인
            try:
                alert = self.driver.switch_to.alert
                alert_text = alert.text
                logger.info(f"알림창 감지: {alert_text}")
                alert.accept()
                logger.info("알림창 확인 완료")
            except Exception:
                pass  # 알림창이 없는 경우 무시
            
            # 모달 팝업 확인 및 닫기
            try:
                modal_close_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                                                              ".modal .close, .popup .close, [aria-label='닫기']")
                for button in modal_close_buttons:
                    button.click()
                    logger.info("모달 팝업 닫기 버튼 클릭")
                    time.sleep(0.5)
            except Exception:
                pass  # 모달이 없는 경우 무시
        
        except Exception as e:
            logger.warning(f"팝업 처리 중 오류 (무시): {str(e)}")

    async def _extract_detail_page_data(self, bid_number, bid_title):
        """
        상세 페이지에서 데이터 추출 (HTML 파서 중심)
        
        Args:
            bid_number: 입찰 번호
            bid_title: 입찰 제목
            
        Returns:
            추출된 데이터
        """
        try:
            logger.info(f"상세 페이지 데이터 추출 시작: {bid_number}")
            
            # HTML 소스 가져오기
            html_source = self.driver.page_source
            
            # BeautifulSoup 파싱
            soup = BeautifulSoup(html_source, 'html.parser')
            
            # 결과 데이터 초기화
            detail_data = {
                "bid_number": bid_number,
                "title": bid_title,
                "organization": None,
                "division": None,
                "contract_method": None,
                "bid_type": None,
                "estimated_price": None,
                "qualification": None,
                "description": None,
                "raw_tables": {}  # 원시 테이블 데이터 저장
            }
            
            # 모든 테이블과 tbody 요소 추출하여 저장
            try:
                all_tables = soup.find_all('table')
                for i, table in enumerate(all_tables):
                    # 테이블 캡션 또는 제목 찾기
                    caption = table.find('caption')
                    caption_text = caption.get_text(strip=True) if caption else f"테이블_{i+1}"
                    
                    # 테이블 내 tbody 요소 찾기
                    tbody = table.find('tbody')
                    if tbody:
                        # tbody 내 모든 행과 셀을 추출하여 구조화된 데이터로 저장
                        rows_data = []
                        rows = tbody.find_all('tr')
                        for row in rows:
                            cells_data = {}
                            th_cells = row.find_all('th')
                            td_cells = row.find_all('td')
                            
                            # th 셀 처리
                            for j, cell in enumerate(th_cells):
                                header_key = f"th_{j+1}"
                                cells_data[header_key] = {
                                    "text": cell.get_text(strip=True),
                                    "attributes": dict(cell.attrs)
                                }
                            
                            # td 셀 처리
                            for j, cell in enumerate(td_cells):
                                cell_key = f"td_{j+1}"
                                # 셀 내 링크 추출
                                links = cell.find_all('a')
                                links_data = []
                                for link in links:
                                    link_data = {
                                        "text": link.get_text(strip=True),
                                        "href": link.get('href', ''),
                                        "onclick": link.get('onclick', ''),
                                        "attributes": dict(link.attrs)
                                    }
                                    links_data.append(link_data)
                                
                                cells_data[cell_key] = {
                                    "text": cell.get_text(strip=True),
                                    "links": links_data,
                                    "attributes": dict(cell.attrs)
                                }
                            
                            rows_data.append(cells_data)
                        
                        detail_data["raw_tables"][caption_text] = rows_data
                    
                logger.info(f"{len(detail_data['raw_tables'])}개의 원시 테이블 데이터 저장 완료")
                
                # 원시 테이블 데이터를 텍스트로 변환하여 Gemini 모델에 전달
                if detail_data["raw_tables"]:
                    table_text = ""
                    
                    # 테이블 데이터를 텍스트로 변환
                    for table_name, rows in detail_data["raw_tables"].items():
                        table_text += f"[테이블: {table_name}]\n"
                        
                        for row_data in rows:
                            header_texts = []
                            value_texts = []
                            
                            # 헤더 텍스트 추출
                            for key, cell in row_data.items():
                                if key.startswith('th_'):
                                    header_texts.append(cell["text"])
                                elif key.startswith('td_'):
                                    value_texts.append(cell["text"])
                            
                            # 행 정보 추가
                            if header_texts and value_texts:
                                for i, header in enumerate(header_texts):
                                    if i < len(value_texts):
                                        table_text += f"{header}: {value_texts[i]}\n"
                            elif header_texts:
                                table_text += f"{', '.join(header_texts)}\n"
                            elif value_texts:
                                table_text += f"{', '.join(value_texts)}\n"
                        
                        table_text += "\n"
                    
                    # 파일 첨부 섹션 찾기
                    file_links = soup.select("a[href*='download'], a[href*='fileDown'], a.file")
                    file_info = ""
                    if file_links:
                        file_info += "[파일첨부]\n"
                        for link in file_links:
                            file_name = link.get_text(strip=True) or link.get("title") or "첨부파일"
                            file_info += f"- {file_name}\n"
                    
                    # Gemini 프롬프트 구성
                    prompt_template = """
입찰 상세 정보 추출 전문가로서, 다음 HTML 정보에서 중요 정보를 추출해주세요.

다음은 입찰공고 상세페이지의 테이블 데이터와 전체 페이지 텍스트입니다:

{content}

다음 중요 정보를 확인하여 저장해주세요.(JSON 형식으로 응답 X)
1. 게시일시 
2. 입찰공고번호 
3. 공고명 
4. 입찰방식
5. 낙찰방법
6. 계약방법
7. 계약구분
8. 공동계약 및 구성방식(컨소시엄 여부)
9. 실적제한 여부, 제한여부
10. 가격과 관련된 모든정보(예가방법, 사업금액, 배정에산, 추정에산)
11. 기관담당자정보(담당자 이름, 팩스번호, 전화번호)
12. 연관정보(이건 링크임)
13. 파일첨부

위 형식대로 각 항목에 해당하는 정보를 추출해주세요. 정보가 없는 경우 "정보 없음"으로 표시해주세요.
JSON 형식이 아닌 일반 텍스트로 응답해주세요.
"""
                    
                    combined_text = f"{table_text}\n\n{file_info}"
                    
                    # Gemini API 호출
                    try:
                        gemini_response = await extract_with_gemini_text(combined_text, prompt_template)
                        
                        # Gemini 응답을 문자열로 변환하여 저장
                        if isinstance(gemini_response, dict):
                            # 딕셔너리인 경우 문자열로 변환
                            detail_data["prompt_result"] = json.dumps(gemini_response, ensure_ascii=False)
                        else:
                            # 이미 문자열인 경우 그대로 저장
                            detail_data["prompt_result"] = str(gemini_response)
                        
                        logger.info("Gemini API를 통한 상세 정보 추출 완료")
                    except Exception as gemini_err:
                        logger.error(f"Gemini API 호출 오류: {str(gemini_err)}")
                
            except Exception as raw_tables_err:
                logger.warning(f"원시 테이블 데이터 추출 실패: {str(raw_tables_err)}")
            
            # 1. 주요 섹션별 데이터 추출 (추가 데이터 확보용)
            section_names = ["공고일반", "입찰자격", "투찰제한", "제안요청정보", "협상에 의한 계약", "가격", 
                           "기관담당자정보", "수요기관 담당자정보", "연관정보", "파일첨부"]
            
            # 1-1. 공고기관 정보 추출 (기관담당자정보 섹션)
            try:
                # 기관담당자정보 섹션 찾기
                org_section = None
                for heading in soup.find_all(['h3', 'h4', 'div', 'span', 'strong']):
                    if "기관담당자" in heading.get_text() or "공고기관" in heading.get_text():
                        org_section = heading.find_parent('div') or heading.find_parent('table') or heading.find_parent('section')
                        break
                
                if org_section:
                    # 테이블 내용 추출
                    org_tables = org_section.find_all('table')
                    if org_tables:
                        for table in org_tables:
                            rows = table.find_all('tr')
                            for row in rows:
                                cells = row.find_all(['th', 'td'])
                                if len(cells) >= 2:
                                    header = cells[0].get_text(strip=True)
                                    value = cells[1].get_text(strip=True)
                                    
                                    if any(keyword in header for keyword in ["수요기관", "공고기관"]):
                                        detail_data["organization"] = value
                                    elif any(keyword in header for keyword in ["담당자", "담당부서"]):
                                        detail_data["division"] = value
            except Exception as org_err:
                logger.warning(f"기관정보 추출 실패: {str(org_err)}")
            
            # 여기에 더 많은 섹션별 추출 로직이 있지만 Gemini API 결과가 있으면 충분함
            
            return detail_data
            
        except Exception as e:
            logger.error(f"상세 페이지 데이터 추출 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return {}

    async def _process_search_results(self, search_items):
        """
        검색 결과 페이지에서 아이템 데이터 처리
        
        Args:
            search_items: 기본 정보가 추출된 검색 결과 항목 리스트
            
        Returns:
            처리된 항목 리스트
        """
        try:
            logger.info(f"검색 결과 처리 시작 ({len(search_items)}개 항목)")
            
            # 결과 컨테이너 생성
            results_container = self.driver.find_element(By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_body")
            if not results_container:
                logger.error("결과 컨테이너를 찾을 수 없음")
                return []
            
            processed_items = []
            
            # 각 검색 결과 행 처리
            for index, item in enumerate(search_items):
                try:
                    # 처리할 최대 항목 수 제한
                    if index >= 5:  # 예시: 최대 5개 항목만 처리
                        logger.info(f"최대 처리 항목 수 제한에 도달 ({index})")
                        break
                    
                    logger.info(f"항목 {index+1}/{len(search_items)} 처리 중: {item['title']}")
                    
                    # 기본 정보 추출 (이미 search_items에 포함됨)
                    item_data = item.copy()
                    
                    # 상세 URL이 있는 경우 상세 정보 추출
                    if item.get('detail_url'):
                        detail_data = await self.extract_detail_page_info(item['detail_url'])
                        if detail_data:
                            # 상세 정보를 기본 정보와 병합
                            item_data.update(detail_data)
                            logger.info(f"항목 {index+1} 상세 정보 추출 성공")
                        else:
                            logger.warning(f"항목 {index+1} 상세 정보 추출 실패")
                    
                    # 처리된 항목 추가
                    processed_items.append(item_data)
                    
                except Exception as e:
                    logger.error(f"항목 {index+1} 처리 중 오류: {str(e)}")
                    logger.debug(traceback.format_exc())
            
            logger.info(f"검색 결과 처리 완료 ({len(processed_items)}개 항목 처리됨)")
            return processed_items
            
        except Exception as e:
            logger.error(f"검색 결과 처리 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return []

if __name__ == "__main__":
    # Windows에서 올바른 이벤트 루프 정책 설정
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # 비동기 메인 함수 정의
    async def main():
        # 크롤러 객체 생성 (헤드리스 모드 사용 여부 설정)
        crawler = G2BCrawlerTest(headless=False)
        
        try:
            # 크롤러 초기화
            await crawler.initialize()
            
            # 크롤러 실행
            results = await crawler.run()
            
            # 결과 저장
            if results:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = RESULTS_DIR / f"results_{timestamp}.json"
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                
                logger.info(f"결과 저장 완료: {output_file}")
                print(f"결과가 {output_file}에 저장되었습니다.")
            
        except Exception as e:
            logger.error(f"크롤러 실행 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
        finally:
            # 크롤러 종료
            await crawler.close()
    
    # 비동기 메인 함수 실행
    asyncio.run(main()) 