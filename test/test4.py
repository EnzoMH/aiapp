from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select

from selenium.common.exceptions import (
    TimeoutException, 
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException
)

import asyncio
import logging
from dotenv import load_dotenv
import os

import chromedriver_autoinstaller
import requests

import json
from datetime import datetime
from typing import Dict, List

# from utils.constants import SEARCH_KEYWORDS

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SEARCH_KEYWORDS = ["LMS", "증강현실", "가상현실", "메타버스", "교재 개발", "교육과정 개발"]


class SearchValidator:
    def __init__(self):
        self.seen_bids = set()  # 중복 체크를 위한 bid_number 저장
        self.logger = logging.getLogger(__name__)
        
    def _clean_date(self, date_str: str) -> str:
        """날짜 문자열 정제"""
        if not date_str:
            return ""
        try:
            return date_str.split()[0].replace("/", "-")
        except:
            return date_str

    def _clean_text(self, text: str) -> str:
        """텍스트 정제 (Grid 제거, 개행 정리)"""
        if not text:
            return ""
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
        
        keyword_lower = keyword.lower()
        basic_info = bid_data.get('basic_info', {})
        detail_info = bid_data.get('detail_info', {})
        
        title = basic_info.get('title', '').lower()
        general_notice = detail_info.get('general_notice', '').lower()
        
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
        required_fields = ['title']
        
        is_valid = all(basic_info.get(field) for field in required_fields)
        
        if not is_valid:
            self.logger.warning(f"필수 필드 누락: {bid_data}")
        
        return is_valid


class NaraMarketCrawler:
    def __init__(self):
        self.base_url = "https://www.g2b.go.kr"
        self.session = requests.Session()
        self.default_headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Origin': 'https://www.g2b.go.kr',
            'Referer': 'https://www.g2b.go.kr/'
        }
        
    async def initialize_session(self):
        """세션 초기화 및 기본 설정"""
        logger.info("세션 초기화 시작")
        try:
            url = f"{self.base_url}/co/coz/coza/util/getSession.do"
            headers = {
                **self.default_headers,
                'menu-info': '{"menuNo":"01175","menuCangVal":"PNPE001_01","bsneClsfCd":"%EC%97%85130026","scrnNo":"00941"}'
            }
            
            response = self.session.post(url, headers=headers)
            response.raise_for_status()
            
            session_data = response.json()
            logger.info(f"세션 초기화 성공: {json.dumps(session_data, indent=2, ensure_ascii=False)}")
            return True
            
        except Exception as e:
            logger.error(f"세션 초기화 실패: {str(e)}")
            return False

    async def get_bid_detail(self, bid_number: str) -> Dict:
        """입찰 공고 상세 정보 조회"""
        logger.info(f"상세 정보 조회 시작 - 공고번호: {bid_number}")
        
        try:
            url = f"{self.base_url}/pn/pnp/pnpe/commBidPbac/selectPicInfo.do"
            headers = {
                **self.default_headers,
                'menu-info': '{"menuNo":"01196","menuCangVal":"PNPE027_01","bsneClsfCd":"%EC%97%85130026","scrnNo":"06085"}'
            }
            
            payload = {
                "dlParamM": {
                    "bidPbancNo": bid_number,
                    "bidPbancOrd": "000"
                }
            }
            
            response = self.session.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"상세 정보 조회 성공 - 공고번호: {bid_number}")
            return data
            
        except Exception as e:
            logger.error(f"상세 정보 조회 실패 - 공고번호: {bid_number}, 오류: {str(e)}")
            return {}


class BidCrawlerTest4:
    def __init__(self):
        self.all_results = []
        self.last_save_time = datetime.now()
        self.save_interval = 300
        self.driver = None
        self.wait = None
        self.base_url = "https://www.g2b.go.kr"
        self.processed_keywords = set()
        self.download_dir = "E:/smh/crawl/test_downloads"  # 다운로드 디렉토리
        
    def setup_driver(self):
        """크롬 드라이버 설정"""
        # 다운로드 디렉토리 생성
        os.makedirs(self.download_dir, exist_ok=True)
        
        chrome_ver = chromedriver_autoinstaller.get_chrome_version().split('.')[0]
        chrome_options = webdriver.ChromeOptions()
        
        # 다운로드 관련 설정
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        try:
            service = Service(f'./{chrome_ver}/chromedriver.exe')
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except:
            chromedriver_autoinstaller.install(True)
            service = Service(f'./{chrome_ver}/chromedriver.exe')
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
        self.wait = WebDriverWait(self.driver, 10)
        
    async def navigate_to_bid_list(self):
        """입찰공고 목록 페이지로 이동"""
        logger.info("[NAVIGATE] 입찰공고 목록 페이지 이동 시작")
        try:
            self.driver.get(self.base_url)
            logger.info("[NAVIGATE] 메인 페이지 접속 완료")
            await asyncio.sleep(2)
            
            parent_menus = [
                "mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_btn_menuLvl1_span",  # 입찰
                "mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_genDepth2_0_btn_menuLvl2_span",  # 입찰공고
                "mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_genDepth2_0_genDepth3_0_btn_menuLvl3_span"  # 입찰공고목록
            ]
            
            for i, menu_id in enumerate(parent_menus, 1):
                try:
                    logger.info(f"[NAVIGATE] 메뉴 단계 {i}/{len(parent_menus)} 클릭 시도")
                    menu_element = self.wait.until(
                        EC.presence_of_element_located((By.ID, menu_id))
                    )
                    self.driver.execute_script("arguments[0].click();", menu_element)
                    logger.info(f"[NAVIGATE] 메뉴 단계 {i} 클릭 성공")
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"[NAVIGATE] 메뉴 클릭 실패 - 단계: {i}, ID: {menu_id}, 오류: {str(e)}")
                    raise
                    
            logger.info("[NAVIGATE] 입찰공고 목록 페이지 이동 완료")
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"[NAVIGATE] 페이지 이동 실패 - 오류: {str(e)}")
            raise
        
    async def set_results_per_page(self):
        """페이지당 결과 수 설정 (100개로)"""
        logger.info("[FILTER] 페이지당 결과 수 설정 시작")
        try:
            # Select 엘리먼트 찾기
            select_id = "mf_wfm_container_tacBidPbancLst_contents_tab2_body_sbxRecordCountPerPage1"
            select_element = self.wait.until(
                EC.presence_of_element_located((By.ID, select_id))
            )
            
            # Select 객체 생성
            select = Select(select_element)
            
            # 100 옵션 선택
            select.select_by_visible_text("100")
            logger.info("[FILTER] 페이지당 100개 결과 설정 완료")
            await asyncio.sleep(2)  # 변경사항 적용 대기
            
            return True
            
        except TimeoutException:
            logger.error("[FILTER] Select 엘리먼트를 찾을 수 없음")
            return False
        except Exception as e:
            logger.error(f"[FILTER] 페이지당 결과 수 설정 실패 - 오류: {str(e)}")
            return False

    async def navigate_and_analyze(self):
        try:
            await self.navigate_to_bid_list()
            await self.set_results_per_page()
            
            total_keywords = len(SEARCH_KEYWORDS)
            for i, keyword in enumerate(SEARCH_KEYWORDS, 1):
                try:
                    logger.info(f"\n진행 상황: {i}/{total_keywords} ({(i/total_keywords)*100:.1f}%)")
                    logger.info(f"\n{'='*30}\n{keyword} 검색 시작\n{'='*30}")
                    
                    if keyword in self.processed_keywords:
                        logger.warning(f"키워드 '{keyword}' 이미 처리됨, 건너뜀")
                        continue
                    
                    # 페이지 상태 확인 및 복구
                    if not await self._verify_table_exists():
                        logger.warning("테이블이 표시되지 않음. 페이지 복구 시도")
                        if not await self.recover_page_state(keyword):
                            await self.navigate_to_bid_list()
                    
                    # 검색 수행
                    results = await self.perform_search(keyword)
                    
                    if results:
                        logger.info(f"키워드 '{keyword}' 검색 결과: {len(results)}건")
                        
                        # 각 결과에 대해 파일 다운로드 시도
                        for result in results:
                            try:
                                await self.process_bid_detail(result) 
                                
                            except Exception as e:
                                logger.error(f"상세 정보 처리 중 오류: {str(e)}")
                    else:
                        logger.warning(f"키워드 '{keyword}' 검색 결과 없음")
                    
                    self.processed_keywords.add(keyword)
                    await asyncio.sleep(3)
                    await self.navigate_to_bid_list()
                    
                except Exception as e:
                    logger.error(f"{keyword} 검색 중 오류 발생: {str(e)}")
                    await self.navigate_to_bid_list()
                    continue
                    
        except Exception as e:
            logger.error(f"전체 프로세스 중 오류: {str(e)}")
        finally:
            self.save_progress()
            await self.cleanup()

    async def process_bid_detail(self, bid_data: dict):
        """입찰 상세 정보 처리 및 파일 다운로드"""
        bid_number = bid_data.get('basic_info', {}).get('bid_number')
        logger.info(f"[BID_DETAIL] 시작 - 입찰번호: {bid_number}")
        
        try:
            # row_num을 bid_data에서 직접 가져옴
            row_num = bid_data.get('row_num')
            if row_num is None:
                logger.error("행 번호 정보 없음")
                return False
                
            # 상세 페이지 이동 및 데이터 추출
            detail_data = await self._safely_navigate_to_detail(bid_data)
            if detail_data:
                downloaded_files = await self.download_bid_files(bid_data)
                if downloaded_files:
                    bid_data['downloaded_files'] = downloaded_files
                return True
            return False
        except Exception as e:
            logger.error(f"[BID_DETAIL] 처리 실패 - 입찰번호: {bid_number}, 오류: {str(e)}")
            return False
    
    
    # _safely_navigate_to_detail 메서드 수정
    async def _safely_navigate_to_detail(self, bid_data: dict):  # row_num 파라미터 제거
        try:
            # bid_data에서 row_num 가져오기
            row_num = bid_data.get('basic_info', {}).get('row_num')
            if row_num is None:
                logger.error("행 번호 정보 없음")
                return None
                
            # 직접 cell ID로 접근
            title_cell_id = f"mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_cell_{row_num}_6"
            title_element = self.wait.until(
                EC.element_to_be_clickable((By.ID, title_cell_id))
            )
            self.driver.execute_script("arguments[0].click();", title_element)
            logger.info(f"상세 페이지 이동 시도")
            await asyncio.sleep(2)

            detail_data = await self._extract_detail_page_data()
            return detail_data

        except Exception as e:
            logger.error(f"상세 페이지 탐색 중 오류: {str(e)}")
            return None

        finally:
            self.driver.back()
            await asyncio.sleep(2)

    async def _handle_popups(self):
        """팝업창 처리"""
        try:
            # 방법 1: 닫기 버튼으로 처리
            try:
                close_button = self.driver.find_element(
                    By.XPATH, 
                    "//div[contains(@id, '_close') and contains(@class, 'w2window_close')]"
                )
                if close_button:
                    self.driver.execute_script("arguments[0].click();", close_button)
                    logger.info("팝업창 닫기 성공 (close 버튼)")
                    await asyncio.sleep(1)
            except:
                pass
            
            # 방법 2: 확인 버튼으로 처리
            try:
                confirm_button = self.driver.find_element(
                    By.XPATH, 
                    "//input[@type='button' and @value='확인']"
                )
                if confirm_button:
                    self.driver.execute_script("arguments[0].click();", confirm_button)
                    logger.info("팝업창 닫기 성공 (확인 버튼)")
                    await asyncio.sleep(1)
            except:
                pass
                
        except Exception as e:
            logger.error(f"팝업창 처리 중 오류: {str(e)}")
            
    async def _extract_detail_page_data(self):
        """상세 페이지 데이터 추출"""
        def get_section_base_xpath():
            return "/html/body/div[1]/div[3]/div/div[2]/div/div[2]/div[4]/div[1]"
        
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
            'bid_notice_files': {
                'path': f"{base_xpath}/div[35]/div",
                'type': 'document',
                'table_path': ".//table[@id='wq_uuid_30671_grdFile_body_table']//tbody/tr"
            }
        }
        
        try:
            for section_name, info in sections.items():
                try:
                    element = self.driver.find_element(By.XPATH, info['path'])
                    if element.is_displayed():
                        if info['type'] == 'section':
                            detail_data[section_name] = element.text.strip()
                            
                        elif info['type'] == 'document':
                            try:
                                table_rows = element.find_elements(By.XPATH, info['table_path'])
                                documents = []
                                
                                for row in table_rows:
                                    try:
                                        if section_name == 'bid_notice_files':
                                            doc_info = await self._extract_file_info(row)
                                        else:
                                            doc_info = await self._extract_document_info(row)
                                            
                                        if doc_info:
                                            documents.append(doc_info)
                                    except Exception as e:
                                        logger.error(f"문서 정보 추출 실패: {str(e)}")
                                        
                                detail_data[section_name] = documents
                                
                            except Exception as e:
                                logger.error(f"테이블 처리 실패 - {section_name}: {str(e)}")
                                
                except Exception as e:
                    logger.debug(f"{section_name} 섹션 처리 실패: {str(e)}")
                    continue
                    
            return detail_data
            
        except Exception as e:
            logger.error(f"상세 페이지 데이터 추출 중 오류: {str(e)}")
            return {}
        
    async def _extract_document_info(self, element):
        """문서 요소에서 상세 정보 추출"""
        try:
            doc_info = {
                'text': '',
                'file_name': '',
                'download_link': None,
                'onclick': None
            }
            
            try:
                doc_info['text'] = element.text.strip()
            except:
                pass
                
            try:
                link = element.find_element(By.TAG_NAME, "a")
                if link:
                    doc_info['file_name'] = link.text.strip()
                    doc_info['download_link'] = link.get_attribute('href')
                    doc_info['onclick'] = link.get_attribute('onclick')
            except:
                try:
                    button = element.find_element(By.TAG_NAME, "button")
                    if button:
                        doc_info['file_name'] = button.text.strip()
                        doc_info['onclick'] = button.get_attribute('onclick')
                except:
                    pass
                    
            return doc_info if any(doc_info.values()) else None
            
        except Exception as e:
            logger.error(f"문서 정보 추출 실패: {str(e)}")
            return None
        
    async def download_bid_files(self, bid_data: dict) -> List[Dict]:
        """입찰 관련 파일 다운로드"""
        bid_number = bid_data.get('basic_info', {}).get('bid_number')
        logger.info(f"[FILE_DOWNLOAD] 시작 - 입찰번호: {bid_number}")
        downloaded_files = []
        
        try:
            file_table = self.driver.find_element(
                By.XPATH, 
                "//div[contains(@class, 'file_list')]//table"
            )
            file_rows = file_table.find_elements(By.TAG_NAME, "tr")
            logger.info(f"[FILE_DOWNLOAD] 파일 목록 발견 - 입찰번호: {bid_number}, 총 {len(file_rows)}개")
            
            for idx, row in enumerate(file_rows, 1):
                try:
                    logger.info(f"[FILE_DOWNLOAD] {idx}/{len(file_rows)} 파일 처리 중")
                    file_info = await self._process_file_download(row)
                    if file_info:
                        downloaded_files.append(file_info)
                        logger.info(f"[FILE_DOWNLOAD] 파일 다운로드 성공 - {file_info['name']}")
                except Exception as e:
                    logger.error(f"[FILE_DOWNLOAD] 파일 처리 실패 - 행 {idx}, 오류: {str(e)}")
                    continue
            
            return downloaded_files
        except Exception as e:
            logger.error(f"[FILE_DOWNLOAD] 전체 실패 - 입찰번호: {bid_number}, 오류: {str(e)}")
            return downloaded_files

    async def _process_file_download(self, row) -> Dict:
        """개별 파일 다운로드 처리"""
        try:
            # 파일명 추출
            file_name_cell = row.find_element(By.XPATH, ".//td[4]//nobr")
            file_name = file_name_cell.text.strip()
            
            # 파일 크기 추출
            size_cell = row.find_element(By.XPATH, ".//td[5]//nobr")
            file_size = size_cell.text.strip()
            
            # 입찰공고문 파일 체크
            if not any(keyword in file_name.lower() for keyword in ['입찰공고문', '공고서']):
                return None
            
            # 체크박스 선택
            checkbox = row.find_element(By.XPATH, ".//td[1]//input[@type='checkbox']")
            if not checkbox.is_selected():
                self.driver.execute_script("arguments[0].click();", checkbox)
                await asyncio.sleep(1)
            
            # 다운로드 버튼 클릭
            download_button = self.wait.until(
                EC.presence_of_element_located((
                    By.XPATH, 
                    "//input[contains(@id, 'btnFileDown')]"
                ))
            )
            
            if download_button:
                self.driver.execute_script("arguments[0].click();", download_button)
                await asyncio.sleep(2)
                
                return {
                    'name': file_name,
                    'size': file_size,
                    'download_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'status': 'downloaded'
                }
            
        except Exception as e:
            logger.error(f"파일 처리 중 오류: {str(e)}")
            return None

    async def perform_search(self, keyword: str):
        try:
            logger.info(f"'{keyword}' 검색 시도")
            
            # 검색어 입력 및 실행
            search_input = self.wait.until(EC.presence_of_element_located(
                (By.XPATH, "/html/body/div[1]/div[3]/div/div[2]/div/div[2]/div[2]/div/div/div[2]/div/div[1]/div[1]/div[1]/div[1]/table/tbody/tr[1]/td[3]/input")
            ))
            search_input.clear()
            search_input.send_keys(keyword)
            search_input.send_keys(Keys.RETURN)
            await asyncio.sleep(2)

            # 검색 결과 확인
            if await self._check_no_results():
                logger.info(f"키워드 '{keyword}'에 대한 검색 결과가 없습니다.")
                return []

            if not await self._verify_table_exists():
                logger.warning(f"키워드 '{keyword}'에 대한 검색 결과 테이블을 찾을 수 없습니다.")
                return []

            # 검색 결과 추출
            await self.extract_search_results(keyword)
            
            # 검증 및 중복 제거
            validator = SearchValidator()
            validated_results = []
            
            for result in self.all_results:
                if validator.validate_required_fields(result):
                    if validator.validate_search_result(keyword, result):
                        validated_results.append(result)
            
            final_results = validator.remove_duplicates(validated_results)
            
            return final_results
                
        except Exception as e:
            logger.error(f"검색 중 오류 발생: {str(e)}")
            return []

    async def _check_no_results(self):
        """검색 결과 없음 확인"""
        try:
            no_result = self.driver.find_element(
                By.XPATH, 
                "//td[contains(text(), '검색된 데이터가 없습니다')]"
            )
            return no_result.is_displayed()
        except:
            return False

    async def _verify_table_exists(self):
        """테이블 존재 확인"""
        table_id = "mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_dataLayer"
        try:
            table = self.wait.until(EC.presence_of_element_located((By.ID, table_id)))
            return table.is_displayed()
        except:
            return False
            
    async def extract_search_results(self, keyword: str):
        """검색 결과 추출"""
        logger.info(f"[EXTRACT] 검색 결과 추출 시작 - 키워드: {keyword}")
        
        try:
            if await self._check_no_results():
                logger.info(f"[EXTRACT] 검색 결과 없음 - 키워드: {keyword}")
                return
                
            if not await self._verify_table_exists():
                logger.warning(f"[EXTRACT] 테이블 없음 - 키워드: {keyword}")
                return

            total_rows = await self._get_total_rows()
            logger.info(f"[EXTRACT] 총 {total_rows}개 행 발견 - 키워드: {keyword}")

            processed_rows = 0
            success_rows = 0
            
            for row_num in range(min(total_rows, 10)):
                try:
                    logger.info(f"[EXTRACT] 행 처리 중 ({row_num + 1}/{min(total_rows, 10)}) - 키워드: {keyword}")
                    basic_data = await self._extract_row_data(row_num)
                    
                    if basic_data:
                        # row_num 추가
                        basic_data['row_num'] = row_num
                        self.all_results.append({
                        'search_keyword': keyword,
                        'basic_info': basic_data
                        })
                        success_rows += 1
                    
                    processed_rows += 1
                    
                except Exception as e:
                    logger.error(f"[EXTRACT] 행 처리 실패 - 행번호: {row_num}, 키워드: {keyword}, 오류: {str(e)}")
                    continue
                    
            logger.info(f"[EXTRACT] 완료 - 키워드: {keyword}, 처리: {processed_rows}, 성공: {success_rows}")
            
        except Exception as e:
            logger.error(f"[EXTRACT] 전체 실패 - 키워드: {keyword}, 오류: {str(e)}")

    async def _get_total_rows(self):
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
            logger.error(f"행 수 확인 중 오류: {str(e)}")
        return row_count

    async def _extract_row_data(self, row_num):
        """행 데이터 추출"""
        logger.info(f"행 데이터 추출 시작 - 행 번호: {row_num}")
        
        cells = {}
        cell_names = ['no', 'business_type', 'business_status', '', 'bid_category', 
                    'bid_number', 'title', 'announce_agency', 'agency', 'post_date', 
                    'progress_stage', 'detail_process', 'process_status', '', 'bid_progress']
        
        try:
            for col, name in enumerate(cell_names):
                if name:
                    try:
                        cell_id = f"mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_cell_{row_num}_{col}"
                        cell_element = self.wait.until(EC.presence_of_element_located((By.ID, cell_id)))
                        cells[name] = cell_element.text.strip()
                        
                        if name in ['bid_number', 'title']:
                            logger.info(f"{name}: {cells[name]}")
                            
                    except Exception as e:
                        logger.error(f"컬럼 '{name}' 추출 실패 (행: {row_num}, 열: {col}): {str(e)}")
                        cells[name] = None
                        
            return cells
            
        except Exception as e:
            logger.error(f"행 전체 데이터 추출 실패 - 행 번호: {row_num}: {str(e)}")
            return {}

    async def _check_and_save_results(self):
        """주기적 결과 저장"""
        current_time = datetime.now()
        if (current_time - self.last_save_time).seconds >= self.save_interval:
            self.save_progress()
            self.last_save_time = current_time

    def save_progress(self):
        """진행 상황 저장"""
        try:
            save_dir = "E:/smh/crawl/testdata"
            os.makedirs(save_dir, exist_ok=True)
            
            # 데이터 정제
            validator = SearchValidator()
            cleaned_results = [validator.clean_bid_data(result) for result in self.all_results]
            
            save_data = {
                "timestamp": datetime.now().strftime('%Y%m%d_%H%M%S'),
                "summary": {
                    "total_keywords": len(SEARCH_KEYWORDS),
                    "total_results": len(cleaned_results),
                    "processed_count": len(self.processed_keywords)
                },
                "results": cleaned_results
            }
            
            filename = os.path.join(save_dir, f"crawling_progress_{save_data['timestamp']}.json")
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"진행 상황 저장 완료: {filename}")
            
        except Exception as e:
            logger.error(f"진행 상황 저장 실패: {str(e)}")

    async def cleanup(self):
        """리소스 정리"""
        try:
            if self.all_results:
                logger.info(f"전체 크롤링 결과 저장 시작 (총 {len(self.all_results)}건)")
                
                # 데이터 정제
                validator = SearchValidator()
                cleaned_results = [validator.clean_bid_data(result) for result in self.all_results]
                
                # 저장 경로 및 파일명 설정
                save_dir = "E:/smh/crawl/testdata"
                os.makedirs(save_dir, exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = os.path.join(save_dir, f"final_results_{timestamp}.json")
                
                # 저장할 데이터 구조화
                save_data = {
                    "timestamp": timestamp,
                    "summary": {
                        "total_keywords": len(SEARCH_KEYWORDS),
                        "total_results": len(cleaned_results),
                        "processed_count": len(self.processed_keywords),
                        "download_directory": self.download_dir
                    },
                    "results": cleaned_results
                }
                
                # JSON 파일로 저장
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(save_data, f, ensure_ascii=False, indent=2)
                    
                logger.info(f"전체 크롤링 결과 저장 완료: {filename}")
                
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("ChromeDriver 브라우저 종료")

    async def recover_page_state(self, keyword: str, retry_count=0):
        """페이지 상태 복구 시도"""
        MAX_RETRIES = 2
        
        try:
            # 첫 번째: 뒤로가기 시도
            self.driver.back()
            await asyncio.sleep(2)
            
            try:
                if await self._verify_table_exists():
                    logger.info("뒤로가기로 페이지 복구 성공")
                    return True
            except:
                if retry_count < MAX_RETRIES:
                    logger.warning(f"복구 시도 {retry_count + 1} 실패, 처음부터 다시 시도")
                    await self.navigate_to_bid_list()
                    await asyncio.sleep(2)
                    await self.perform_search(keyword)
                    await asyncio.sleep(2)
                    return await self.recover_page_state(keyword, retry_count + 1)
                else:
                    logger.error("최대 복구 시도 횟수 초과")
                    return False
                    
        except Exception as e:
            logger.error(f"페이지 복구 중 오류: {str(e)}")
            return False

async def main():
    crawler = BidCrawlerTest4()
    try:
        crawler.setup_driver()
        await crawler.navigate_and_analyze()
    except Exception as e:
        logger.error(f"메인 프로세스 오류: {str(e)}")
    finally:
        await crawler.cleanup()

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())