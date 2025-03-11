from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

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

from utils.constants import SEARCH_KEYWORDS

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SearchValidator:
    def __init__(self):
        self.seen_bids = set()  # 중복 체크를 위한 bid_number 저장
        self.logger = logging.getLogger(__name__)

    def validate_search_result(self, keyword: str, bid_data: dict) -> bool:
        """검색어와 입찰 데이터 연관성 검증"""
        if not bid_data:
            return False
            
        # 검색어가 제목이나 내용에 포함되어 있는지 확인
        keyword_lower = keyword.lower()
        title = bid_data.get('title', '').lower()
        general_notice = bid_data.get('general_notice', '').lower()
        
        return (keyword_lower in title or keyword_lower in general_notice)

    def remove_duplicates(self, results: list) -> list:
        """중복 데이터 제거"""
        unique_results = []
        for result in results:
            bid_number = result.get('bid_number')
            if bid_number and bid_number not in self.seen_bids:
                self.seen_bids.add(bid_number)
                unique_results.append(result)
        return unique_results

    def validate_required_fields(self, bid_data: dict) -> bool:
        """필수 필드 존재 여부 검증"""
        required_fields = ['bid_number', 'title', 'post_date']
        return all(bid_data.get(field) for field in required_fields)

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
            
            logger.debug(f"상세 정보 요청 - URL: {url}")
            logger.debug(f"상세 정보 Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
            
            response = self.session.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"상세 정보 조회 성공 - 공고번호: {bid_number}")
            return data
            
        except Exception as e:
            logger.error(f"상세 정보 조회 실패 - 공고번호: {bid_number}, 오류: {str(e)}")
            return {}


class BidCrawlerTest:
    def __init__(self):
        self.all_results = []  # 클래스 레벨에서 결과 저장
        self.last_save_time = datetime.now()  # 마지막 저장 시간 추적
        self.save_interval = 300  # 저장 간격 (초 단위, 예: 5분)
        self.driver = None
        self.wait = None
        self.base_url = "https://www.g2b.go.kr"
        self.processed_keywords = set()  # 처리된 키워드 추적
        
        
    def setup_driver(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        
        service = Service(os.getenv('CHROME_DRIVER_PATH'))
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        
        
    async def navigate_to_bid_list(self):
        """입찰공고 목록 페이지로 이동"""
        try:
            self.driver.get(self.base_url)
            logger.info("메인 페이지 접속")
            await asyncio.sleep(2)
            
            parent_menus = [
                "mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_btn_menuLvl1_span",  # 입찰
                "mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_genDepth2_0_btn_menuLvl2_span",  # 입찰공고
                "mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_genDepth2_0_genDepth3_0_btn_menuLvl3_span"  # 입찰공고목록
            ]
            
            for menu_id in parent_menus:
                try:
                    menu_element = self.wait.until(
                        EC.presence_of_element_located((By.ID, menu_id))
                    )
                    self.driver.execute_script("arguments[0].click();", menu_element)
                    logger.info(f"메뉴 클릭 완료: {menu_id}")
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"메뉴 클릭 실패: {menu_id}, 오류: {str(e)}")
                    raise
                    
            logger.info("입찰공고 목록 페이지로 이동 완료")
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"페이지 이동 중 오류: {str(e)}")
            raise
    
        
    async def navigate_and_analyze(self):
        try:
            await self.navigate_to_bid_list()
            
            total_keywords = len(SEARCH_KEYWORDS)
            for i, keyword in enumerate(SEARCH_KEYWORDS, 1):
                try:
                    # 진행 상황 로깅
                    logger.info(f"\n진행 상황: {i}/{total_keywords} ({(i/total_keywords)*100:.1f}%)")
                    logger.info(f"\n{'='*30}\n{keyword} 검색 시작\n{'='*30}")
                    
                    # 이미 처리된 키워드 확인
                    if keyword in self.processed_keywords:
                        logger.warning(f"키워드 '{keyword}' 이미 처리됨, 건너뜀")
                        continue
                    
                    # 페이지 상태 확인
                    table_id = "mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_dataLayer"
                    try:
                        table = self.wait.until(EC.presence_of_element_located((By.ID, table_id)))
                        if not table.is_displayed():
                            logger.warning("테이블이 표시되지 않음. 페이지 복구 시도")
                            if not await self.recover_page_state(keyword):
                                logger.error("페이지 복구 실패")
                                await self.navigate_to_bid_list()
                    except:
                        logger.error("테이블을 찾을 수 없음. 페이지 복구 시도")
                        if not await self.recover_page_state(keyword):
                            logger.error("페이지 복구 실패")
                            await self.navigate_to_bid_list()
                    
                    # 검색 수행
                    results = await self.perform_search(keyword)
                    
                    # 검색 결과 로깅
                    if results:
                        logger.info(f"키워드 '{keyword}' 검색 결과: {len(results)}건")
                    else:
                        logger.warning(f"키워드 '{keyword}' 검색 결과 없음")
                    
                    # 처리 완료 키워드 기록
                    self.processed_keywords.add(keyword)
                    
                    await asyncio.sleep(3)
                    
                    # 다음 검색을 위해 입찰공고 목록 페이지로 새로 이동
                    await self.navigate_to_bid_list()
                    
                except Exception as e:
                    logger.error(f"{keyword} 검색 중 오류 발생: {str(e)}")
                    # 오류 발생 시 페이지 복구
                    self.driver.back()
                    await asyncio.sleep(2)
                    await self.navigate_to_bid_list()
                    continue
                    
        except Exception as e:
            logger.error(f"전체 프로세스 중 오류: {str(e)}")
        finally:
            # 진행 상황 저장
            self.save_progress()
            input("계속하려면 아무 키나 누르세요...")
            await self.cleanup()

    def save_progress(self):
        """진행 상황 저장"""
        try:
            # 저장 경로 설정
            save_dir = "E:/smh/crawl/data"
            os.makedirs(save_dir, exist_ok=True)
            
            progress_data = {
                "timestamp": datetime.now().strftime('%Y%m%d_%H%M%S'),
                "total_keywords": len(SEARCH_KEYWORDS),
                "processed_keywords": list(self.processed_keywords),
                "remaining_keywords": list(set(SEARCH_KEYWORDS) - self.processed_keywords),
                "total_results": len(self.all_results)
            }
            
            filename = os.path.join(save_dir, f"crawling_progress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"진행 상황 저장 완료: {filename}")
            
        except Exception as e:
            logger.error(f"진행 상황 저장 실패: {str(e)}")
            
    async def recover_page_state(self, keyword: str, retry_count=0):
        """페이지 상태 복구 시도"""
        MAX_RETRIES = 2
        table_id = "mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_dataLayer"
        
        try:
            # 첫 번째: 뒤로가기 시도
            self.driver.back()
            await asyncio.sleep(2)
            
            try:
                table = self.wait.until(EC.presence_of_element_located((By.ID, table_id)))
                if table.is_displayed():
                    logger.info("뒤로가기로 페이지 복구 성공")
                    return True
            except:
                if retry_count < MAX_RETRIES:
                    logger.warning(f"복구 시도 {retry_count + 1} 실패, 처음부터 다시 시도")
                    # 입찰공고 목록부터 다시 시작
                    await self.navigate_to_bid_list()
                    await asyncio.sleep(2)
                    # 검색어 다시 입력
                    await self.perform_search(keyword)
                    await asyncio.sleep(2)
                    return await self.recover_page_state(keyword, retry_count + 1)
                else:
                    logger.error("최대 복구 시도 횟수 초과")
                    return False
                    
        except Exception as e:
            logger.error(f"페이지 복구 중 오류: {str(e)}")
            return False


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

            # 검색 결과 없음 확인
            if await self._check_no_results():
                logger.info(f"키워드 '{keyword}'에 대한 검색 결과가 없습니다.")
                return []

            # 테이블 존재 확인
            if not await self._verify_table_exists():
                logger.warning(f"키워드 '{keyword}'에 대한 검색 결과 테이블을 찾을 수 없습니다.")
                return []

            # 결과 초기화 - 반드시 필요
            self.all_results = []
            
            # 검색 결과 추출
            await self.extract_search_results(keyword)
            
            # 검색 결과 검증
            if not self.all_results:
                logger.info(f"키워드 '{keyword}'에 대한 추출된 결과가 없습니다.")
                return []
            
            # 검증 및 중복 제거
            validator = SearchValidator()
            validated_results = []
            
            for result in self.all_results:
                if validator.validate_required_fields(result):
                    if validator.validate_search_result(keyword, result):
                        validated_results.append(result)
            
            final_results = validator.remove_duplicates(validated_results)
            
            # 결과 로깅
            logger.info(f"키워드 '{keyword}' 검색 완료:")
            logger.info(f" - 원본 결과 수: {len(self.all_results)}")
            logger.info(f" - 검증 후 결과 수: {len(validated_results)}")
            logger.info(f" - 중복 제거 후 최종 결과 수: {len(final_results)}")
            
            return final_results
                
        except Exception as e:
            logger.error(f"검색 중 오류 발생: {str(e)}")
            return []
        
    # 1. 검색 결과 없음 확인 부분을 별도 메서드로 분리 제안
    async def _check_no_results(self):
        try:
            no_result = self.driver.find_element(By.XPATH, "//td[contains(text(), '검색된 데이터가 없습니다')]")
            return no_result.is_displayed()
        except:
            return False

    # 2. 테이블 검증 부분도 분리하면 좋을 것 같습니다
    async def _verify_table_exists(self):
        table_id = "mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_dataLayer"
        try:
            table = self.wait.until(EC.presence_of_element_located((By.ID, table_id)))
            return table.is_displayed()
        except:
            return False    

    async def extract_search_results(self, keyword: str):
        try:
            logger.info(f"\n검색 키워드: {keyword}\n" + "="*50 + "\n검색 결과 추출 시작\n" + "="*50)
            
            # 1. 기본 검증 (이전 검증 재사용)
            if await self._check_no_results():
                return
                
            if not await self._verify_table_exists():
                return

            # 2. API 클라이언트 초기화
            api_crawler = NaraMarketCrawler()
            if not await api_crawler.initialize_session():
                logger.error("API 세션 초기화 실패")
                return

            # 3. 데이터 추출 시작
            try:
                # 행 수 확인
                total_rows = await self._get_total_rows()
                logger.info(f"총 {total_rows}개의 행 발견")

                # 각 행 처리
                for row_num in range(min(total_rows, 10)):  # 최대 10개로 제한
                    try:
                        # 3.1 기본 데이터 추출
                        basic_data = await self._extract_row_data(row_num)
                        if not basic_data:
                            continue

                        # 3.2 데이터 보강
                        enriched_data = {
                            'search_keyword': keyword,
                            'basic_info': basic_data
                        }

                        # 3.3 API 상세정보 추출
                        if basic_data.get('bid_number'):
                            api_detail = await api_crawler.get_bid_detail(basic_data['bid_number'])
                            if api_detail:
                                enriched_data['api_detail'] = api_detail

                        # 3.4 상세 페이지 데이터 추출
                        detail_data = await self._safely_navigate_and_extract_detail(row_num)
                        if detail_data:
                            enriched_data['detail_info'] = detail_data

                        # 3.5 결과 저장
                        self.all_results.append(enriched_data)
                        logger.info(f"결과 추가됨: 현재 총 {len(self.all_results)}건")
                        
                        # 3.6 주기적 저장 체크
                        await self._check_and_save_results()

                    except Exception as e:
                        logger.error(f"{row_num + 1}번째 행 처리 중 오류: {str(e)}")
                        continue

            except Exception as e:
                logger.error(f"데이터 추출 중 오류: {str(e)}")

        except Exception as e:
            logger.error(f"전체 프로세스 중 오류: {str(e)}")

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

    async def _safely_navigate_and_extract_detail(self, row_num):
        """안전한 상세 페이지 탐색 및 데이터 추출"""
        try:
            # 1. 상세 페이지 이동
            title_cell_id = f"mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_cell_{row_num}_6"
            title_element = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, title_cell_id))
            )
            self.driver.execute_script("arguments[0].click();", title_element)
            await asyncio.sleep(2)

            # 2. 팝업창 처리 (단순화된 방식)
            try:
                # 방법 1: 직접 close 버튼의 ID로 접근
                close_button = self.driver.find_element(
                    By.XPATH, 
                    "//div[contains(@id, '_close') and contains(@class, 'w2window_close')]"
                )
                if close_button:
                    self.driver.execute_script("arguments[0].click();", close_button)
                    logger.info("팝업창 닫기 성공 (close 버튼)")
                    await asyncio.sleep(1)
            except:
                # 방법 2: 확인 버튼이 있는 경우
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
                    logger.debug("팝업창 없음 또는 처리 불필요")

            # 3. 상세 데이터 추출
            detail_data = await self._extract_detail_page_data()

            # 4. 목록으로 복귀
            self.driver.back()
            await asyncio.sleep(2)
            await self._verify_table_exists()

            return detail_data

        except Exception as e:
            logger.error(f"상세 페이지 처리 중 오류: {str(e)}")
            self.driver.back()
            await asyncio.sleep(2)
            return None

    async def _check_and_save_results(self):
        current_time = datetime.now()
        if (current_time - self.last_save_time).seconds >= self.save_interval:
            # 새로운 방식으로 진행 상황 저장
            self.save_progress()
            self.last_save_time = current_time


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
            return {}  # 빈 딕셔너리 반환하여 상위 메서드에서 처리 가능하도록

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
            # 파일첨부 섹션 추가
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
                                
                            except Exception as e:
                                logger.error(f"테이블 처리 실패 - {section_name}: {str(e)}")
                                
                except Exception as e:
                    logger.debug(f"{section_name} 섹션 처리 실패: {str(e)}")
                    continue
                    
            return detail_data
            
        except Exception as e:
            logger.error(f"상세 페이지 데이터 추출 중 오류: {str(e)}")
            return {}

    async def _extract_file_info(self, row):
        """파일 정보 추출 및 다운로드"""
        try:
            file_info = {
                'name': '',
                'size': '',
                'type': '',
                'download_url': None
            }
            
            # 파일명 추출 - ID 패턴을 사용하지 않고 위치 기반으로 변경
            try:
                # td[4]의 nobr 태그 내용을 가져옴
                name_cell = row.find_element(By.XPATH, ".//td[4]//nobr[contains(@class, 'w2grid_input')]")
                if name_cell:
                    file_info['name'] = name_cell.text.strip()
                    logger.info(f"파일명 추출 성공: {file_info['name']}")
            except Exception as e:
                logger.error(f"파일명 추출 실패: {str(e)}")
                
            # 파일 크기 추출
            try:
                size_cell = row.find_element(By.XPATH, ".//td[5]//nobr[contains(@class, 'w2grid_input')]")
                if size_cell:
                    file_info['size'] = size_cell.text.strip()
                    logger.info(f"파일 크기 추출 성공: {file_info['size']}")
            except Exception as e:
                logger.error(f"파일 크기 추출 실패: {str(e)}")
                
            # 입찰공고문 파일 체크 (pdf나 hwp 확장자 및 이름 패턴 확인)
            if any(keyword in file_info['name'].lower() for keyword in ['입찰공고문', '공고서']):
                try:
                    # 체크박스는 첫 번째 열에 있음
                    checkbox = row.find_element(By.XPATH, ".//td[1]//input[@type='checkbox']")
                    if checkbox and not checkbox.is_selected():
                        # JavaScript로 클릭 실행
                        self.driver.execute_script("arguments[0].click();", checkbox)
                        await asyncio.sleep(1)
                        logger.info("체크박스 선택 성공")
                        
                        # 다운로드 버튼 찾기 - 버튼 ID가 동적으로 변하므로 더 일반적인 속성으로 검색
                        download_button = self.wait.until(
                            EC.presence_of_element_located((
                                By.XPATH, 
                                "//input[contains(@id, 'btnFileDown')]"
                            ))
                        )
                        
                        if download_button:
                            self.driver.execute_script("arguments[0].click();", download_button)
                            await asyncio.sleep(2)
                            logger.info(f"입찰공고문 다운로드 시작: {file_info['name']}")
                            
                except Exception as e:
                    logger.error(f"파일 다운로드 처리 실패: {str(e)}")
                    
            return file_info
                
        except Exception as e:
            logger.error(f"파일 정보 추출 전체 실패: {str(e)}")
            return None

    async def _extract_document_info(self, element):
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
                link = element.find_element(By.TAG_NAME, "a")
                if link:
                    doc_info['file_name'] = link.text.strip()
                    doc_info['download_link'] = link.get_attribute('href')
                    doc_info['onclick'] = link.get_attribute('onclick')
            except:
                # a 태그가 없는 경우 버튼 확인
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
    
    def save_results(self, results: List[Dict], keyword: str):
        """결과 저장 - 중복 방지를 위한 타임스탬프 활용"""
        try:
            os.makedirs('results', exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            filename = f"results/bid_results_{keyword}_{timestamp}.json"
            
            # 결과가 비어있는 경우도 기록
            if not results:
                empty_record = {
                    "keyword": keyword,
                    "timestamp": timestamp,
                    "status": "no_results",
                    "message": f"키워드 '{keyword}'에 대한 검색 결과가 없습니다."
                }
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(empty_record, f, ensure_ascii=False, indent=2)
                logger.info(f"빈 결과 기록 완료: {filename}")
                return
                
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"결과 저장 완료: {filename} (총 {len(results)}건)")
                
        except Exception as e:
            logger.error(f"결과 저장 실패: {str(e)}")
            
    def save_all_crawling_results(self, all_results: List[Dict]):
        """전체 크롤링 결과를 하나의 JSON 파일로 저장"""
        try:
            # 저장 경로 설정
            save_dir = "E:/smh/crawl/data"
            os.makedirs(save_dir, exist_ok=True)
            
            # 현재 시간으로 파일명 생성
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join(save_dir, f"all_crawling_results_{timestamp}.json")
            
            # 저장할 데이터 구조화
            save_data = {
                "timestamp": timestamp,
                "total_keywords": len(SEARCH_KEYWORDS),
                "processed_keywords": list(self.processed_keywords),
                "total_results": len(all_results),
                "results": all_results,  # 실제 크롤링된 데이터
                "metadata": {
                    "version": "1.0",
                    "completion_status": "success",
                    "crawling_duration": str(datetime.now() - self.last_save_time)
                }
            }
            
            # JSON 파일로 저장
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"전체 크롤링 결과 저장 완료: {filename} (총 {len(all_results)}건)")
            return filename
            
        except Exception as e:
            logger.error(f"전체 결과 저장 실패: {str(e)}")
            return None
            
    async def cleanup(self):
        try:
            if self.all_results:
                logger.info(f"전체 크롤링 결과 저장 시작 (총 {len(self.all_results)}건)")
                # 전체 결과 통합 저장
                saved_file = self.save_all_crawling_results(self.all_results)
                if saved_file:
                    logger.info(f"전체 결과 저장 완료: {saved_file}")
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("ChromeDriver 브라우저 종료")

async def main():
    crawler = BidCrawlerTest()
    try:
        crawler.setup_driver()
        await crawler.navigate_and_analyze()
    except Exception as e:
        logger.error(f"메인 프로세스 오류: {str(e)}")
    finally:
        await crawler.cleanup()  # 확실한 리소스 정리를 위해 finally 블록으로 이동

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())