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
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.keys import Keys

import os
import time
import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import asyncio
import chromedriver_autoinstaller

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
                self.driver.quit()
                logger.info("웹드라이버 종료 완료")
            except Exception as e:
                logger.error(f"웹드라이버 종료 중 오류: {str(e)}")
    
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
            for window in all_windows:
                if window != main_window:
                    self.driver.switch_to.window(window)
                    self.driver.close()
                    logger.info("팝업창 닫기 성공")
            
            # 메인 윈도우로 복귀
            self.driver.switch_to.window(main_window)
            
            # 페이지 내 팝업창 닫기 (X 버튼 클릭)
            try:
                # 여러 종류의 팝업창 닫기 버튼 시도
                close_buttons = self.driver.find_elements(By.CSS_SELECTOR, ".w2window_close, .close, [aria-label='창닫기']")
                for button in close_buttons:
                    button.click()
                    logger.info("페이지 내 팝업창 닫기 성공")
                    time.sleep(0.5)  # 약간의 지연
            except Exception as e:
                logger.warning(f"페이지 내 팝업창 닫기 실패 (무시 가능): {str(e)}")
                
        except Exception as e:
            logger.warning(f"팝업창 닫기 중 오류 (계속 진행): {str(e)}")
    
    async def navigate_to_bid_list(self):
        """입찰공고 목록 페이지로 이동"""
        try:
            logger.info("입찰공고 목록 페이지로 이동 중...")
            
            # '입찰' 메뉴 클릭
            await self._click_element_safely(By.ID, "mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_btn_menuLvl1_span")
            await asyncio.sleep(1)
            
            # '입찰공고목록' 클릭
            await self._click_element_safely(By.ID, "mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_genDepth2_0_genDepth3_0_btn_menuLvl3_span")
            
            # 페이지 로딩 대기
            await asyncio.sleep(3)
            
            logger.info("입찰공고 목록 페이지 이동 성공")
            return True
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
    
    async def search_keyword(self, keyword: str) -> List[Dict]:
        """키워드로 검색 수행"""
        results = []
        try:
            logger.info(f"'{keyword}' 키워드 검색 시작")
            
            # 검색어 입력 필드 찾기
            search_input = self.driver.find_element(By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_txtNmInptKwd_inputExt")
            search_input.clear()
            search_input.send_keys(keyword)
            
            # 검색 버튼 클릭
            search_button = self.driver.find_element(By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_btnS0004")
            search_button.click()
            
            # 결과 로딩 대기
            await asyncio.sleep(3)
            
            # 검색 결과 수집
            results = await self._collect_search_results()
            
            # 결과에 키워드 정보 추가
            for result in results:
                result['search_keyword'] = keyword
            
            logger.info(f"'{keyword}' 키워드 검색 완료: {len(results)}건 수집")
            return results
        except Exception as e:
            logger.error(f"'{keyword}' 키워드 검색 실패: {str(e)}")
            return []
    
    async def _collect_search_results(self) -> List[Dict]:
        """검색 결과 수집"""
        results = []
        try:
            # 검색 결과 테이블 찾기
            table = self.driver.find_element(By.CSS_SELECTOR, ".table_list")
            rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
            
            if not rows:
                logger.info("검색 결과가 없습니다.")
                return results
            
            # 각 행 처리
            for row in rows:
                try:
                    # 기본 데이터 추출
                    columns = row.find_elements(By.TAG_NAME, "td")
                    if len(columns) < 6:
                        continue
                    
                    bid_info = {
                        'bid_number': columns[1].text.strip(),
                        'title': columns[2].text.strip(),
                        'announce_agency': columns[3].text.strip(),
                        'post_date': columns[4].text.strip(),
                        'deadline_date': columns[5].text.strip(),
                        'progress_stage': columns[6].text.strip() if len(columns) > 6 else '정보 없음',
                        'collected_at': datetime.now().isoformat(),
                    }
                    
                    # 세부 정보를 위한 링크 찾기
                    detail_link = columns[2].find_element(By.TAG_NAME, "a")
                    bid_info['detail_link'] = detail_link.get_attribute("onclick")
                    
                    results.append(bid_info)
                except Exception as e:
                    logger.warning(f"행 처리 중 오류 (무시): {str(e)}")
                    continue
            
            return results
        except Exception as e:
            logger.error(f"검색 결과 수집 실패: {str(e)}")
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
            
            # 각 키워드에 대해 검색 수행
            for keyword in keywords:
                try:
                    logger.info(f"키워드 '{keyword}' 처리 중...")
                    
                    # 키워드 검색 수행
                    keyword_results = await self.search_keyword(keyword)
                    
                    # 결과 저장
                    all_results.extend(keyword_results)
                    processed_keywords.append(keyword)
                    
                    logger.info(f"키워드 '{keyword}' 처리 완료 ({len(keyword_results)}건)")
                except Exception as e:
                    logger.error(f"키워드 '{keyword}' 처리 중 오류: {str(e)}")
                    failed_keywords.append(keyword)
            
            # 결과 요약
            result_summary = {
                "status": "success",
                "total_keywords": len(keywords),
                "processed_keywords": processed_keywords,
                "failed_keywords": failed_keywords,
                "total_results": len(all_results),
                "results": all_results
            }
            
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