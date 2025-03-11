from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys

import asyncio
import logging
from dotenv import load_dotenv
import os

import chromedriver_autoinstaller
from playwright.async_api import async_playwright
import requests

import time
import json
from datetime import datetime
from typing import Dict, List

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
        self.driver = None
        self.wait = None
        self.base_url = "https://www.g2b.go.kr"
        self.playwright_page = None
        self.browser = None
        
    def setup_driver(self):
        chrome_ver = chromedriver_autoinstaller.get_chrome_version().split('.')[0]
        try:
            service = Service(f'./{chrome_ver}/chromedriver.exe')
            driver = webdriver.Chrome(service=service)
        except:
            chromedriver_autoinstaller.install(True)
            service = Service(f'./{chrome_ver}/chromedriver.exe')
            driver = webdriver.Chrome(service=service)
        
        self.driver = driver
        self.wait = WebDriverWait(self.driver, 10)
        
    def print_frame_info(self):
        """현재 페이지의 모든 프레임 정보 출력"""
        frames = self.driver.find_elements(By.TAG_NAME, "iframe")
        logger.info(f"총 프레임 수: {len(frames)}")
        for i, frame in enumerate(frames):
            frame_id = frame.get_attribute('id')
            frame_name = frame.get_attribute('name')
            logger.info(f"Frame {i}: ID={frame_id}, Name={frame_name}")
            
    async def setup_playwright(self):
        """Playwright 설정"""
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=False)
            self.playwright_page = await self.browser.new_page()
            self.playwright_page.set_default_timeout(10000)
            logger.info("Playwright 브라우저 설정 완료")
        except Exception as e:
            logger.error(f"Playwright 설정 실패: {str(e)}")
            raise
        
    async def get_detail_with_playwright(self, bid_number: str, title: str):
        """Playwright로 상세 페이지 접근"""
        try:
            detail_url = f"https://www.g2b.go.kr:8101/ep/offer/detail/{bid_number}"
            await self.playwright_page.goto(detail_url)
            await self.playwright_page.wait_for_load_state('networkidle')
            
            # 여기서 상세 정보 추출 로직 구현
            logger.info(f"상세 페이지 접속 성공: {bid_number}")
            
            # 첨부파일 정보 추출
            files = await self.playwright_page.query_selector_all("table.fileTable tr")
            attachments = []
            
            for file in files:
                try:
                    file_name = await file.query_selector("a")
                    if file_name:
                        name_text = await file_name.text_content()
                        attachments.append({
                            'name': name_text.strip(),
                            'url': detail_url
                        })
                except Exception as e:
                    logger.error(f"첨부파일 정보 추출 실패: {str(e)}")
            
            return {'url': detail_url, 'attachments': attachments}
            
        except Exception as e:
            logger.error(f"Playwright 상세 페이지 접근 실패: {str(e)}")
            return None
        
    async def navigate_and_analyze(self):
        try:
            self.driver.get(self.base_url)
            logger.info("메인 페이지 접속")
            await asyncio.sleep(3)
            
            menu_id = "mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_genDepth2_0_genDepth3_0_btn_menuLvl3_span"
            try:
                parent_menus = [
                    "mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_btn_menuLvl1_span",  # 입찰
                    "mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_genDepth2_0_btn_menuLvl2_span"  # 입찰공고
                ]
                
                for parent_id in parent_menus:
                    try:
                        parent = self.wait.until(
                            EC.presence_of_element_located((By.ID, parent_id))
                        )
                        self.driver.execute_script("arguments[0].click();", parent)
                        logger.info(f"상위 메뉴 클릭: {parent_id}")
                        await asyncio.sleep(1)
                    except Exception as e:
                        logger.error(f"상위 메뉴 클릭 실패: {parent_id}, 오류: {str(e)}")
                
                menu_element = self.wait.until(
                    EC.presence_of_element_located((By.ID, menu_id))
                )
                self.driver.execute_script("arguments[0].click();", menu_element)
                logger.info("입찰공고목록 메뉴 클릭 완료")
                
                await asyncio.sleep(2)
                
                logger.info("검색 요소 분석 시작")
                self.analyze_search_elements()
                await asyncio.sleep(2)
                
                search_keywords = [
                    "VR", "AR", "실감", "가상현실", "증강현실", "혼합현실", "XR", 
                    "메타버스", "LMS", "학습관리시스템", "콘텐츠 개발", "콘텐츠 제작",
                    "교재 개발", "교육과정 개발", "교육 콘텐츠"
                ]
                
                for keyword in search_keywords:
                    try:
                        logger.info(f"\n{'='*30}\n{keyword} 검색 시작\n{'='*30}")
                        await self.perform_search(keyword)
                        await asyncio.sleep(3)
                    except Exception as e:
                        logger.error(f"{keyword} 검색 중 오류 발생: {str(e)}")
                        continue
                
            except TimeoutException:
                logger.error("메뉴를 찾거나 클릭하는데 시간 초과")
            except Exception as e:
                logger.error(f"메뉴 클릭 중 오류: {str(e)}")
                
        except Exception as e:
            logger.error(f"전체 프로세스 중 오류: {str(e)}")
        finally:
            input("계속하려면 아무 키나 누르세요...")
            await self.cleanup()

    async def perform_search(self, keyword: str, page: int = 1):
        """검색 실행 및 결과 확인"""
        try:
            logger.info(f"'{keyword}' 검색 시도 (페이지: {page})")
            
            if page == 1:
                search_input = self.wait.until(EC.presence_of_element_located(
                    (By.XPATH, "/html/body/div[1]/div[3]/div/div[2]/div/div[2]/div[2]/div/div/div[2]/div/div[1]/div[1]/div[1]/div[1]/table/tbody/tr[1]/td[3]/input")
                ))
                
                search_input.clear()
                search_input.send_keys(keyword)
                search_input.send_keys(Keys.RETURN)
                logger.info("검색 실행")
                
            else:
                try:
                    page_input = self.wait.until(EC.presence_of_element_located((
                        By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_page_input"
                    )))
                    page_input.clear()
                    page_input.send_keys(str(page))
                    page_input.send_keys(Keys.RETURN)
                    logger.info(f"페이지 {page}로 이동")
                except Exception as e:
                    logger.error(f"페이지 이동 실패: {str(e)}")
                    return False
            
            await asyncio.sleep(2)
            await self.extract_search_results()
            return True
            
        except Exception as e:
            logger.error(f"검색 중 오류 발생: {str(e)}")
            return False

    def analyze_search_elements(self):
        """검색 관련 요소들의 정보를 출력"""
        logger.info("검색 요소 분석 시작")
        try:
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            logger.info(f"총 input 요소 수: {len(inputs)}")
            for i, input_elem in enumerate(inputs):
                input_id = input_elem.get_attribute('id')
                input_name = input_elem.get_attribute('name')
                input_type = input_elem.get_attribute('type')
                logger.info(f"Input {i}: ID={input_id}, Name={input_name}, Type={input_type}")
                
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            logger.info(f"총 button 요소 수: {len(buttons)}")
            for i, button in enumerate(buttons):
                button_id = button.get_attribute('id')
                button_text = button.text
                logger.info(f"Button {i}: ID={button_id}, Text={button_text}")
                
        except Exception as e:
            logger.error(f"검색 요소 분석 중 오류: {str(e)}")

    async def extract_search_results(self):
        """검색 결과 추출"""
        try:
            logger.info("\n" + "="*50 + "\n검색 결과 추출 시작\n" + "="*50)
            
            # 1. 초기 설정
            table_id = "mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_dataLayer"
            table = self.wait.until(EC.presence_of_element_located((By.ID, table_id)))
            logger.info("메인 테이블 요소 찾음")
            
            # API 크롤러 초기화
            api_crawler = NaraMarketCrawler()
            if not await api_crawler.initialize_session():
                logger.error("API 세션 초기화 실패")
                return
            
            all_results = []
            current_page = 1
            max_pages = 5  # 수집할 최대 페이지 수
            
            while current_page <= max_pages:
                logger.info(f"\n{'='*30}\n{current_page} 페이지 처리 시작\n{'='*30}")
                
                # 2. 페이지별 결과 수집
                rows = self.wait.until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, f"#{table_id} > div[id^='mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_row_']")
                    )
                )
                
                for row_num, row in enumerate(rows):
                    try:
                        # 3. 기본 정보 추출
                        cells = await self._extract_row_data(row_num)
                        if not cells:
                            continue
                        
                        # 4. API 상세 정보 조회
                        bid_number = cells.get('bid_number')
                        if bid_number:
                            api_detail = await api_crawler.get_bid_detail(bid_number)
                            if api_detail:
                                cells['api_detail'] = api_detail
                        
                        # 5. 상세 페이지 접근 (공고명 클릭)
                        title_element = self.wait.until(
                            EC.element_to_be_clickable(
                                (By.ID, f"mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_cell_{row_num}_6")
                            )
                        )
                        
                        # 현재 URL 저장
                        current_url = self.driver.current_url
                        
                        # 클릭 이벤트 실행
                        self.driver.execute_script("arguments[0].click();", title_element)
                        await asyncio.sleep(2)
                        
                        try:
                            # 6. 상세 페이지 데이터 추출
                            detail_data = await self._extract_detail_page_data()
                            cells.update(detail_data)
                            
                        except Exception as e:
                            logger.error(f"상세 페이지 처리 중 오류: {str(e)}")
                            
                        finally:
                            # 7. 목록 페이지로 복귀
                            logger.info("목록 페이지로 복귀")
                            self.driver.get(current_url)
                            await asyncio.sleep(2)
                        
                        all_results.append(cells)
                        # 중간 저장
                        self._save_intermediate_results(all_results, current_page, row_num)
                        
                    except Exception as e:
                        logger.error(f"{row_num + 1}번째 행 처리 중 오류: {str(e)}")
                        continue
                
                # 8. 다음 페이지 이동
                if not await self._move_to_next_page(current_page):
                    break
                current_page += 1
                
            # 9. 최종 결과 저장
            self.save_results(all_results)
                
        except Exception as e:
            logger.error(f"전체 결과 추출 중 오류 발생: {str(e)}")

    async def _extract_row_data(self, row_num):
        """행 데이터 추출"""
        cells = {}
        cell_names = ['no', 'business_type', 'business_status', '', 'bid_category', 
                    'bid_number', 'title', 'announce_agency', 'agency', 'post_date', 
                    'progress_stage', 'detail_process', 'process_status', '', 'bid_progress']
        
        for col, name in enumerate(cell_names):
            if name:
                try:
                    cell_id = f"mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_cell_{row_num}_{col}"
                    cell_element = self.wait.until(EC.presence_of_element_located((By.ID, cell_id)))
                    cells[name] = cell_element.text.strip()
                except Exception as e:
                    logger.error(f"컬럼 '{name}' 추출 실패: {str(e)}")
        return cells

    async def _extract_detail_page_data(self):
        """상세 페이지 데이터 추출"""
        detail_data = {}
        
        try:
            # 페이지 전체 텍스트 추출
            body_element = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
            detail_data['detail_text'] = body_element.text
            
            # 첨부파일 정보 추출
            file_table = self.driver.find_elements(By.CSS_SELECTOR, "table.fileTable tr")
            files = []
            for file_row in file_table:
                try:
                    link = file_row.find_element(By.TAG_NAME, "a")
                    files.append({
                        'name': link.text.strip(),
                        'link': link.get_attribute('href') or link.get_attribute('onclick')
                    })
                except Exception as e:
                    logger.error(f"파일 정보 추출 실패: {str(e)}")
            detail_data['files'] = files
            
        except Exception as e:
            logger.error(f"상세 페이지 데이터 추출 중 오류: {str(e)}")
            
        return detail_data

    def _save_intermediate_results(self, results, page, row):
        """중간 결과 저장"""
        try:
            filename = f"intermediate_results_page{page}_row{row}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"중간 결과 저장 실패: {str(e)}")

    async def _move_to_next_page(self, current_page):
        """다음 페이지로 이동"""
        try:
            page_input = self.wait.until(EC.presence_of_element_located((
                By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_page_input"
            )))
            page_input.clear()
            page_input.send_keys(str(current_page + 1))
            page_input.send_keys(Keys.RETURN)
            await asyncio.sleep(2)
            return True
        except Exception as e:
            logger.error(f"페이지 이동 실패: {str(e)}")
            return False
    
    
            
    def save_results(self, results: List[Dict]):
        """결과 저장"""
        try:
            filename = f"bid_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"결과 저장 완료: {filename}")
        except Exception as e:
            logger.error(f"결과 저장 실패: {str(e)}")
            
    async def analyze_page_structure(self):
        """페이지 구조 분석"""
        try:
            logger.info("\n=== 페이지 구조 분석 시작 ===")
            
            # 1. iframe 확인
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            logger.info(f"발견된 iframe 수: {len(iframes)}")
            for iframe in iframes:
                logger.info(f"iframe ID: {iframe.get_attribute('id')}")
                logger.info(f"iframe Name: {iframe.get_attribute('name')}")
                logger.info(f"iframe Source: {iframe.get_attribute('src')}")
            
            # 2. JavaScript 이벤트 리스너 확인
            js_elements = self.driver.execute_script("""
                return Array.from(document.querySelectorAll('*')).filter(el => {
                    return el.onclick || el.onmouseover || el.onmousedown || 
                        el.addEventListener || el.attachEvent;
                }).map(el => {
                    return {
                        id: el.id,
                        tagName: el.tagName,
                        eventTypes: {
                            onclick: !!el.onclick,
                            onmouseover: !!el.onmouseover,
                            onmousedown: !!el.onmousedown
                        }
                    };
                });
            """)
            logger.info(f"JavaScript 이벤트가 있는 요소 수: {len(js_elements)}")
            for elem in js_elements:
                logger.info(f"Element: {elem}")
            
            # 3. 동적 로딩 관련 요소 확인
            ajax_elements = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "[data-ajax], [data-load], .ajax-content, .dynamic-content"
            )
            logger.info(f"동적 로딩 관련 요소 수: {len(ajax_elements)}")
            
            # 4. 주요 컨테이너 및 테이블 구조 확인
            containers = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "div.container, div.content, div.main, table.data-table"
            )
            logger.info(f"주요 컨테이너 수: {len(containers)}")
            for container in containers:
                logger.info(f"Container ID: {container.get_attribute('id')}")
                logger.info(f"Container Class: {container.get_attribute('class')}")
            
            # 5. 페이지 소스 분석
            page_source = self.driver.page_source
            logger.info(f"페이지 소스 길이: {len(page_source)}")
            
            # BeautifulSoup로 구조 분석
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # 주요 태그 통계
            tag_stats = {}
            for tag in soup.find_all():
                tag_name = tag.name
                tag_stats[tag_name] = tag_stats.get(tag_name, 0) + 1
            
            logger.info("HTML 태그 통계:")
            for tag, count in tag_stats.items():
                logger.info(f"{tag}: {count}개")
                
            return {
                "iframes": len(iframes),
                "js_elements": len(js_elements),
                "ajax_elements": len(ajax_elements),
                "containers": len(containers),
                "tag_stats": tag_stats
            }
                
        except Exception as e:
            logger.error(f"페이지 구조 분석 중 오류: {str(e)}")
            return None
            
    def switch_to_frame(self, frame_locator):
        try:
            frame = self.wait.until(EC.presence_of_all_elements_located(frame_locator))
            self.driver.switch_to.frame(frame)
        except Exception as e:
            logger.error(f"프레임 전환 중 오류: {str(e)}")
            
    def switch_to_default_content(self):
        self.driver.switch_to.default_content()
    
    async def cleanup(self):
        """리소스 정리"""
        if self.driver:
            self.driver.quit()
            logger.info("ChromeDriver 브라우저 종료")
        
        if self.browser:
            await self.browser.close()
            logger.info("Playwright 브라우저 종료")

async def main():
    crawler = BidCrawlerTest()
    try:
        crawler.setup_driver()
        await crawler.setup_playwright()  # Playwright 설정 추가
        await crawler.navigate_and_analyze()
    except Exception as e:
        logger.error(f"메인 프로세스 오류: {str(e)}")
    finally:
        await crawler.cleanup()  # 확실한 리소스 정리를 위해 finally 블록으로 이동

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())