"""
나라장터 (G2B) 공공데이터 API 클라이언트

조달청 나라장터 입찰공고정보서비스(공공데이터포털)를 활용하여 입찰정보를 수집하는 클라이언트
https://www.data.go.kr/data/15129394/openapi.do
"""

import os
import base64
import logging
import traceback
import asyncio
import json
import requests
import xml.etree.ElementTree as ET  # XML 파싱을 위한 라이브러리
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
import aiohttp
import pandas as pd
from dotenv import load_dotenv
from urllib.parse import quote_plus, quote, urlencode

# 로깅 설정
logger = logging.getLogger(__name__)

# 환경변수 로드
load_dotenv()


# API 키 설정 - G2B_API_KEY를 우선적으로 사용
api_key = os.getenv("G2B_API_KEY", "")  # 첫 번째 시도
if not api_key:
    # 두 번째로 G2B_API_KEY_ENCODING 사용
    api_key = os.getenv("G2B_API_KEY_ENCODING", "")
if not api_key:
    # 세 번째로 G2B_API_KEY_DECODING 사용하되 URL 인코딩 필요
    decoded_api_key = os.getenv("G2B_API_KEY_DECODING", "")
    if decoded_api_key:
        api_key = quote(decoded_api_key)

if not api_key:
    print("API 키가 설정되지 않았습니다. 환경변수 G2B_API_KEY, G2B_API_KEY_ENCODING 또는 G2B_API_KEY_DECODING를 확인하세요.")
else:
    print(f"G2B API 키 로드 완료 - 길이: {len(api_key)} 문자")

# G2B API 설정과 관련된 전역 변수
USE_API = os.getenv("USE_G2B_API", "false").lower() in ["true", "1", "yes"]
API_KEY = os.getenv("G2B_API_KEY", "")

def set_use_api(use_api: bool):
    """
    G2B API 사용 여부 설정
    
    Args:
        use_api: API 사용 여부 (True/False)
    """
    global USE_API
    USE_API = use_api
    logger.info(f"G2B API 사용 설정이 변경되었습니다: {use_api}")
    
    # 환경 변수도 함께 설정 (다른 프로세스에서도 참조 가능하도록)
    os.environ["USE_G2B_API"] = "true" if use_api else "false"

class G2BApiClient:
    """나라장터 API 클라이언트 클래스"""
    
    # API 기본 URL (HTTPS -> HTTP로 변경)
    BASE_URL = "http://apis.data.go.kr/1230000/BidPublicInfoService"
    
    # API 엔드포인트 정의
    ENDPOINTS = {
        "getBidPblancListInfoCnstwk": "/getBidPblancListInfoCnstwk",  # 공사
        "getBidPblancListInfoThng": "/getBidPblancListInfoThng",      # 물품
        "getBidPblancListInfoServc": "/getBidPblancListInfoServc",    # 용역
        "getBidPblancListInfoFrgcpt": "/getBidPblancListInfoFrgcpt",  # 외자
        
        "getBidPblancDetailInfoCnstwk": "/getBidPblancDetailInfoCnstwk",  # 공사 상세
        "getBidPblancDetailInfoThng": "/getBidPblancDetailInfoThng",      # 물품 상세
        "getBidPblancDetailInfoServc": "/getBidPblancDetailInfoServc",    # 용역 상세
    }
    
    # 결과 저장 경로
    RESULTS_DIR = "crawl/api_results"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        API 클라이언트 초기화
        
        Args:
            api_key: API 키 (None인 경우 환경변수에서 로드)
        """
        # API 키 설정
        self.api_key = api_key or globals().get('api_key', '')
        
        if not self.api_key:
            logger.warning("API 키가 설정되지 않았습니다. 환경변수 G2B_API_KEY_DECODING를 확인하세요.")
            
        # 결과 저장 디렉토리 생성
        os.makedirs(self.RESULTS_DIR, exist_ok=True)
        
        # 세션 관리
        self.session = None
        
        logger.info("나라장터 API 클라이언트 초기화 완료")
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.session:
            await self.session.close()
    
    async def _request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        API 요청 전송
        
        Args:
            endpoint: API 엔드포인트
            params: 요청 파라미터
            
        Returns:
            Dict: API 응답 데이터
        """
        # API URL 구성
        url = f"{self.BASE_URL}{endpoint}"
        
        # 요청 시작 시간 기록
        start_time = datetime.now()
        
        try:
            logger.debug(f"API 요청: {url}")
            logger.debug(f"API 파라미터: {params}")
            
            # 파라미터 복사 (원본 수정 방지)
            query_params = params.copy()
            
            # URL 직접 구성 (URL 인코딩 문제 해결)
            # serviceKey는 이미 인코딩된 상태로 URL에 직접 추가
            query_string = urlencode(query_params)
            full_url = f"{url}?serviceKey={self.api_key}&{query_string}"
            
            logger.info(f"전체 URL: {full_url}")
            
            # 요청 전송 (SSL 검증 비활성화)
            print(f"API 요청 URL: {full_url}")
            response = requests.get(full_url, verify=False)
            response_time = (datetime.now() - start_time).total_seconds()
            
            # 응답 상태 코드 확인
            print(f"응답 상태 코드: {response.status_code}")
            print(f"응답 헤더: {response.headers}")
            print(f"응답 내용 일부: {response.text[:500]}")
            
            if response.status_code != 200:
                logger.error(f"API 요청 실패: 상태 코드 {response.status_code} ({response_time:.2f}초)")
                logger.error(f"응답 내용: {response.text[:200]}...")
                return {
                    "success": False,
                    "error": f"API 요청 실패: 상태 코드 {response.status_code}",
                    "status_code": response.status_code,
                    "response_time": response_time,
                    "response_text": response.text
                }
            
            # 응답 타입 확인
            content_type = response.headers.get('Content-Type', '')
            
            # XML 또는 JSON 응답에 따라 처리
            if 'xml' in content_type.lower():
                # XML 응답
                text = response.text
                logger.warning(f"XML 응답 받음: {text[:200]}")
                
                try:
                    # XML 파싱
                    root = ET.fromstring(text)
                    
                    # 오류 메시지 확인
                    error_msg_elem = root.find(".//errMsg")
                    error_code_elem = root.find(".//returnReasonCode")
                    auth_msg_elem = root.find(".//returnAuthMsg")
                    
                    error_msg = error_msg_elem.text if error_msg_elem is not None else None
                    error_code = error_code_elem.text if error_code_elem is not None else None
                    auth_msg = auth_msg_elem.text if auth_msg_elem is not None else None
                    
                    # 오류 메시지가 있는 경우
                    if error_msg and error_msg != "NORMAL SERVICE":
                        logger.error(f"API 오류: {error_msg} (코드: {error_code}, 인증: {auth_msg})")
                        return {
                            "success": False,
                            "error": error_msg,
                            "error_code": error_code,
                            "auth_msg": auth_msg,
                            "response_time": response_time,
                            "format": "xml",
                            "response_text": text
                        }
                    
                    # 정상 응답이지만 XML 형식
                    logger.info(f"XML 형식 응답 성공 ({response_time:.2f}초)")
                    return {
                        "success": True,
                        "data": {"raw": text},
                        "format": "xml",
                        "response_time": response_time,
                        "xml_root": root
                    }
                    
                except Exception as e:
                    logger.error(f"XML 파싱 오류: {str(e)}")
                    return {
                        "success": False,
                        "error": f"XML 파싱 오류: {str(e)}",
                        "response_text": text,
                        "response_time": response_time,
                        "format": "xml"
                    }
            else:
                # JSON 응답
                try:
                    data = response.json()
                except Exception as e:
                    # JSON 파싱 오류 - 응답 텍스트 반환
                    logger.error(f"JSON 파싱 오류: {str(e)}")
                    logger.error(f"원본 응답: {response.text[:500]}")
                    return {
                        "success": False,
                        "error": f"JSON 파싱 오류: {str(e)}",
                        "response_text": response.text,
                        "response_time": response_time
                    }
                
                # 응답 구조 확인 및 오류 처리
                if 'response' in data:
                    response_data = data['response']
                    header = response_data.get('header', {})
                    
                    if header.get('resultCode') != '00':
                        logger.error(f"API 오류: {header.get('resultMsg')} (코드: {header.get('resultCode')})")
                        return {
                            "success": False,
                            "error": header.get('resultMsg', 'API 오류'),
                            "error_code": header.get('resultCode'),
                            "response_time": response_time,
                            "response_data": data
                        }
                    
                    logger.info(f"API 요청 성공 ({response_time:.2f}초)")
                    return {
                        "success": True,
                        "data": response_data.get('body', {}),
                        "format": "json",
                        "response_time": response_time
                    }
                
                logger.info(f"API 요청 성공 ({response_time:.2f}초)")
                return {
                    "success": True,
                    "data": data,
                    "format": "json",
                    "response_time": response_time
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API 요청 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return {
                "success": False,
                "error": f"API 요청 오류: {str(e)}",
                "response_time": (datetime.now() - start_time).total_seconds()
            }
        except Exception as e:
            logger.error(f"API 요청 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return {
                "success": False,
                "error": f"API 요청 중 오류: {str(e)}",
                "response_time": (datetime.now() - start_time).total_seconds()
            }
    
    async def get_bid_list(
        self, 
        keyword: str, 
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1, 
        rows: int = 10,
        bid_type: str = "공사",
        save_results: bool = True
    ) -> Dict[str, Any]:
        """
        입찰 목록 조회
        
        Args:
            keyword: 검색 키워드
            start_date: 검색 시작일 (YYYYMMDD 형식)
            end_date: 검색 종료일 (YYYYMMDD 형식)
            page: 페이지 번호
            rows: 페이지당 행 수
            bid_type: 입찰 유형 (공사, 물품, 용역, 외자)
            save_results: 결과 저장 여부
            
        Returns:
            Dict: 입찰 목록 데이터
        """
        # 날짜 기본값 설정 (오늘로부터 30일 전 ~ 오늘)
        today = datetime.now()
        if not end_date:
            end_date = today.strftime("%Y%m%d")
        if not start_date:
            start_date = (today - timedelta(days=30)).strftime("%Y%m%d")
        
        # 입찰 유형에 따른 엔드포인트 선택
        if bid_type == "물품":
            endpoint = self.ENDPOINTS["getBidPblancListInfoThng"]
        elif bid_type == "공사":
            endpoint = self.ENDPOINTS["getBidPblancListInfoCnstwk"]
        elif bid_type == "외자":
            endpoint = self.ENDPOINTS["getBidPblancListInfoFrgcpt"]
        else:  # 기본값: 공사
            endpoint = self.ENDPOINTS["getBidPblancListInfoServc"]
        
        # 파라미터 구성
        params = {
            "numOfRows": rows,
            "pageNo": page,
            "inqryDiv": 1,  # 검색 구분 (1: 입찰공고)
            "inqryBgnDt": start_date.replace("-", ""),
            "inqryEndDt": end_date.replace("-", ""),
            "type": "json"
        }
        
        # 키워드가 있는 경우 추가
        if keyword:
            params["bidNtceNm"] = keyword
        
        # API 요청
        response = await self._request(endpoint, params)
        
        if response["success"] and save_results:
            try:
                # 결과 저장
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"g2b_api_{bid_type}_{keyword}_{timestamp}.json"
                filepath = os.path.join(self.RESULTS_DIR, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(response, f, ensure_ascii=False, indent=2)
                
                logger.info(f"API 검색 결과 저장 완료: {filepath}")
                response["saved_file"] = filepath
            except Exception as e:
                logger.error(f"결과 저장 중 오류: {str(e)}")
        
        return response
    
    async def get_bid_detail(
        self,
        bid_id: str,
        bid_type: str = "공사",
        save_results: bool = True
    ) -> Dict[str, Any]:
        """
        입찰 상세 정보 조회
        
        Args:
            bid_id: 입찰 공고 번호
            bid_type: 입찰 유형 (공사, 물품, 용역)
            save_results: 결과 저장 여부
            
        Returns:
            Dict: 입찰 상세 정보 데이터
        """
        # 입찰 유형에 따른 엔드포인트 선택
        if bid_type == "물품":
            endpoint = self.ENDPOINTS["getBidPblancDetailInfoThng"]
        elif bid_type == "용역":
            endpoint = self.ENDPOINTS["getBidPblancDetailInfoServc"]
        else:  # 기본값: 공사
            endpoint = self.ENDPOINTS["getBidPblancDetailInfoCnstwk"]
        
        # 파라미터 구성
        params = {
            "numOfRows": 10,
            "pageNo": 1,
            "bidNtceNo": bid_id,
            "type": "json"
        }
        
        # API 요청
        response = await self._request(endpoint, params)
        
        if response["success"] and save_results:
            try:
                # 결과 저장
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"g2b_api_detail_{bid_id}_{timestamp}.json"
                filepath = os.path.join(self.RESULTS_DIR, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(response, f, ensure_ascii=False, indent=2)
                
                logger.info(f"API 상세 조회 결과 저장 완료: {filepath}")
                response["saved_file"] = filepath
            except Exception as e:
                logger.error(f"결과 저장 중 오류: {str(e)}")
        
        return response
    
    def process_results(self, response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        API 응답 결과 처리
        
        Args:
            response_data: API 응답 데이터
            
        Returns:
            List: 처리된 입찰 목록
        """
        try:
            if not response_data.get("success", False):
                logger.error(f"API 요청 실패: {response_data.get('error', '알 수 없는 오류')}")
                return []
            
            data = response_data.get("data", {})
            items = data.get("items", [])
            
            if not items:
                logger.info("검색 결과가 없습니다.")
                return []
            
            # 항목이 딕셔너리인 경우 리스트로 변환 (항목이 1개인 경우)
            if isinstance(items, dict):
                items = [items]
            
            # 결과 처리
            processed_items = []
            for item in items:
                try:
                    # 기본 정보 추출
                    processed_item = {
                        "bid_number": item.get("bidNtceNo", ""),
                        "bid_name": item.get("bidNtceNm", ""),
                        "org_name": item.get("ntceInsttNm", ""),
                        "deadline": item.get("bidClseDateTime", ""),
                        "registration_date": item.get("bidNtceDt", ""),
                        "opened_date": item.get("opengDt", ""),
                        "contract_type": item.get("cntrctMthd", ""),
                        "bid_method": item.get("bidMthd", ""),
                        "price_evaluation": item.get("presmptPrce", ""),
                        "location": item.get("bsnsDtlsLocplc", ""),
                        "status": item.get("ntceKindNm", "공고중"),
                        "url": f"https://www.g2b.go.kr:8101/ep/invitation/publish/bidInfoDtl.do?bidno={item.get('bidNtceNo', '')}"
                    }
                    
                    processed_items.append(processed_item)
                except Exception as e:
                    logger.error(f"항목 처리 중 오류: {str(e)}")
                    continue
            
            logger.info(f"{len(processed_items)}개 항목 처리 완료")
            return processed_items
            
        except Exception as e:
            logger.error(f"결과 처리 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return []
    
    def save_to_excel(self, results: List[Dict[str, Any]], filename: Optional[str] = None) -> str:
        """
        결과를 엑셀 파일로 저장
        
        Args:
            results: 처리된 입찰 목록
            filename: 저장할 파일명 (None인 경우 자동 생성)
            
        Returns:
            str: 저장된 파일 경로
        """
        try:
            # 데이터프레임 생성
            df = pd.DataFrame(results)
            
            # 파일명 생성
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"g2b_api_results_{timestamp}.xlsx"
            
            # 파일 경로 구성
            filepath = os.path.join(self.RESULTS_DIR, filename)
            
            # 엑셀 파일로 저장
            df.to_excel(filepath, index=False)
            
            logger.info(f"엑셀 파일 저장 완료: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"엑셀 파일 저장 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return ""

    async def test_connection(self) -> Dict[str, Any]:
        """
        API 연결 상태를 테스트합니다.
        
        Returns:
            Dict[str, Any]: 테스트 결과 (성공 여부, 오류 메시지 등)
        """
        logger.info("API 연결 테스트 시작")
        
        # API 키 확인
        if not self.api_key:
            logger.error("API 키가 설정되지 않았습니다.")
            return {
                "success": False,
                "error": "API 키가 설정되지 않았습니다.",
                "details": "환경변수 G2B_API_KEY_ENCODING 또는 G2B_API_KEY_DECODING를 확인하세요."
            }
        
        # 키가 URL 인코딩되었는지 간단히 확인 (퍼센트 기호 포함)
        if "%" not in self.api_key and "+" not in self.api_key:
            logger.warning("API 키가 URL 인코딩되지 않았을 수 있습니다.")
        
        try:
            # 가장 간단한 API 호출로 테스트 (공사 입찰공고 목록)
            endpoint = self.ENDPOINTS["getBidPblancListInfoCnstwk"]
            test_params = {
                "numOfRows": "1",  # 최소한의 데이터만 요청
                "pageNo": "1",
                "inqryDiv": "1",   # 입찰공고
                "type": "json"
            }
            
            logger.info(f"테스트 요청 파라미터: {test_params}")
            logger.info(f"테스트 요청 엔드포인트: {endpoint}")
            
            # API 호출 테스트
            result = await self._request(endpoint, test_params)
            
            # XML 오류 처리
            if result.get("format") == "xml" and not result.get("success", False):
                error_msg = result.get("error", "알 수 없는 오류")
                error_code = result.get("error_code", "")
                auth_msg = result.get("auth_msg", "")
                
                # 오류 코드 12는 서비스 승인 문제 또는 키 잘못됨
                if error_code == "12" and auth_msg == "NO_OPENAPI_SERVICE_ERROR":
                    return {
                        "success": False,
                        "error": "API 서비스 오류",
                        "error_code": error_code,
                        "auth_msg": auth_msg,
                        "details": """
API 서비스 승인이 필요합니다. 다음 사항을 확인해 주세요:
1. 공공데이터포털(data.go.kr)에서 해당 API 서비스에 정상적으로 활용 신청이 되어 있는지 확인
2. 활용 신청 후 승인이 완료되었는지 확인 (최대 2-3일 소요)
3. API 키가 올바르게 등록되었는지 확인
4. 서비스 신청 시 선택한 서비스 유형이 일치하는지 확인 (실시간 조회 등)
                        """,
                        "response_time": result.get("response_time", 0)
                    }
                
                return {
                    "success": False,
                    "error": error_msg,
                    "error_code": error_code,
                    "auth_msg": auth_msg,
                    "details": "API 연결에 실패했습니다. API 키가 올바른지 확인하세요.",
                    "response_time": result.get("response_time", 0)
                }
            
            # JSON 성공 응답
            if result.get("success", False):
                logger.info("API 연결 테스트 성공")
                # 응답 데이터 확인
                data = result.get("data", {})
                total_count = data.get("totalCount", 0)
                items = data.get("items", [])
                
                # 응답 데이터 요약
                summary = {
                    "success": True,
                    "message": "API 연결 테스트 성공",
                    "response_time": result.get("response_time", 0),
                    "total_count": total_count,
                    "has_items": bool(items),
                    "format": result.get("format", "unknown")
                }
                
                logger.info(f"API 응답 요약: {summary}")
                return summary
            else:
                error = result.get("error", "알 수 없는 오류")
                error_code = result.get("error_code", "")
                logger.warning(f"API 연결 테스트 실패: {error} (코드: {error_code})")
                
                # 자세한 오류 정보 반환
                failure = {
                    "success": False,
                    "error": error,
                    "error_code": error_code,
                    "response_time": result.get("response_time", 0),
                    "status_code": result.get("status_code", 0),
                    "details": "API 연결에 실패했습니다. API 키가 올바른지 확인하세요."
                }
                
                # 응답 텍스트가 있으면 일부 포함
                response_text = result.get("response_text", "")
                if response_text:
                    failure["response_sample"] = response_text[:200]
                
                return failure
        except Exception as e:
            logger.error(f"API 연결 테스트 중 예외 발생: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "details": "API 연결 테스트 중 예외가 발생했습니다.",
                "traceback": traceback.format_exc()
            }


# 비동기 함수 예시
async def search_bids(
    keyword: str, 
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    bid_types: List[str] = ["공사", "물품", "용역"],
) -> Dict[str, Any]:
    """
    여러 입찰 유형에 대해 검색 실행
    
    Args:
        keyword: 검색 키워드
        start_date: 검색 시작일 (YYYYMMDD 형식)
        end_date: 검색 종료일 (YYYYMMDD 형식)
        bid_types: 검색할 입찰 유형 목록
        
    Returns:
        Dict: 검색 결과
    """
    all_results = []
    
    # API 클라이언트 초기화
    async with G2BApiClient() as client:
        # 각 입찰 유형에 대해 검색
        for bid_type in bid_types:
            logger.info(f"[{bid_type}] 입찰 검색 시작: {keyword}")
            
            # API 요청
            response = await client.get_bid_list(
                keyword=keyword,
                start_date=start_date,
                end_date=end_date,
                page=1,
                rows=50,  # 최대 50개 결과
                bid_type=bid_type
            )
            
            # 결과 처리
            if response.get("success", False):
                items = client.process_results(response)
                all_results.extend(items)
                logger.info(f"[{bid_type}] {len(items)}개 결과 수집 완료")
            else:
                logger.error(f"[{bid_type}] 검색 실패: {response.get('error', '알 수 없는 오류')}")
    
    # 결과 요약
    result_summary = {
        "keyword": keyword,
        "start_date": start_date,
        "end_date": end_date,
        "total_count": len(all_results),
        "items": all_results,
        "timestamp": datetime.now().isoformat()
    }
    
    # 결과 저장
    if all_results:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"g2b_api_all_{keyword}_{timestamp}.json"
        filepath = os.path.join(G2BApiClient.RESULTS_DIR, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result_summary, f, ensure_ascii=False, indent=2)
        
        logger.info(f"통합 검색 결과 저장 완료: {filepath}")
        result_summary["saved_file"] = filepath
    
    return result_summary


# 스크립트 직접 실행 시 테스트 함수 실행
if __name__ == "__main__":
    # 비동기 함수 실행
    print("\n======= 나라장터 API 테스트 =======\n")
    print(f"API 키: {api_key[:10]}...{api_key[-10:] if len(api_key) > 20 else ''}")
    
    import asyncio
    asyncio.run(test()) 