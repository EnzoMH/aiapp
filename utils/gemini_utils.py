import json
import re
import traceback
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from genai.generative_model import GenerativeModel

# 로깅 설정
logger = logging.getLogger(__name__)

async def extract_with_gemini_text(text_content, prompt):
    """
    Gemini 텍스트 모델을 사용하여 입찰 데이터 추출
    
    Args:
        text_content: 분석할 HTML 텍스트 내용
        prompt: Gemini에 전달할 프롬프트
        
    Returns:
        추출된 데이터 (딕셔너리)
    """
    try:
        # Gemini 모델 설정
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Gemini 요청
        text_response = await model.generate_content_async(prompt)
        
        # 응답 텍스트 추출
        if text_response and text_response.text:
            response_text = text_response.text.strip()
            
            # JSON 부분만 추출 시도
            json_pattern = r'({[\s\S]*})'
            json_matches = re.search(json_pattern, response_text)
            
            if json_matches:
                json_text = json_matches.group(1)
                
                try:
                    # JSON 파싱
                    extracted_data = json.loads(json_text)
                    logger.info(f"Gemini 텍스트 API 추출 성공: {list(extracted_data.keys())}")
                    
                    # 데이터 검증
                    if not isinstance(extracted_data, dict):
                        logger.warning("Gemini 텍스트 API 결과가 유효한 딕셔너리가 아님")
                        return None
                    
                    # 필드 정제 및 유효성 검증
                    valid_fields = ["organization", "division", "contract_method", "bid_type", 
                                    "qualification", "description", "estimated_price"]
                    
                    result = {}
                    for field in valid_fields:
                        if field in extracted_data and extracted_data[field] not in (None, "null", "NULL", "None", "없음"):
                            result[field] = extracted_data[field]
                    
                    return result
                
                except json.JSONDecodeError as json_err:
                    logger.warning(f"JSON 파싱 실패: {str(json_err)}")
                    
                    # JSON 파싱 실패 시 키-값 패턴 기반 추출 시도
                    try:
                        result = {}
                        pattern = r'"([^"]+)":\s*"([^"]+)"'
                        matches = re.findall(pattern, json_text)
                        
                        for key, value in matches:
                            if key in ["organization", "division", "contract_method", "bid_type", 
                                      "qualification", "description", "estimated_price"]:
                                if value not in ("null", "NULL", "None", "없음"):
                                    result[key] = value
                        
                        if result:
                            logger.info(f"정규식 기반 데이터 추출 성공: {list(result.keys())}")
                            return result
                    except Exception as regex_err:
                        logger.warning(f"정규식 기반 추출 실패: {str(regex_err)}")
            
            else:
                logger.warning("JSON 패턴을 찾을 수 없음")
        
        else:
            logger.warning("Gemini 텍스트 API 응답이 없거나 비어있음")
        
        return None
    
    except Exception as e:
        logger.error(f"Gemini 텍스트 API 처리 중 오류: {str(e)}")
        logger.debug(traceback.format_exc())
        return None 