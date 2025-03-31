"""
Gemini API 클라이언트 모듈

이 모듈은 Google Gemini API와 통신하여 텍스트 및 이미지 처리 요청을 보내는 클라이언트를 구현합니다.
"""

import os
import json
import asyncio
import time
import base64
import logging
from typing import Dict, Any, List, Optional, Union
import requests

# AI 에이전트 설정 로드
from ..utils.config import ai_agent_config
from ..utils.logger import CrawlLogger

# 로거 설정
logger = CrawlLogger("gemini_api_client", debug=True)


class GeminiAPIClient:
    """Gemini API 클라이언트 클래스"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Gemini API 클라이언트 초기화
        
        Args:
            api_key: Gemini API 키 (None인 경우 환경 변수에서 로드)
        """
        self.api_key = api_key or ai_agent_config.gemini_api_key
        
        if not self.api_key:
            raise ValueError("Gemini API 키가 설정되지 않았습니다. 환경 변수 GEMINI_API_KEY를 설정하세요.")
        
        self.vision_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateContent?key={self.api_key}"
        self.text_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={self.api_key}"
        
        # 기본 생성 설정
        self.generation_config = {
            "temperature": ai_agent_config.temperature,
            "topP": ai_agent_config.top_p,
            "topK": 0,
            "maxOutputTokens": ai_agent_config.max_tokens,
        }
        
        # 안전 설정
        self.safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            }
        ]
        
        # 요청 제한 관리
        self.last_request_time = 0
        self.request_delay = ai_agent_config.request_delay  # 초 단위
        
        logger.info(f"Gemini API 클라이언트 초기화 완료 (API 키: {'설정됨' if self.api_key else '설정 안됨'})")
    
    async def _wait_for_rate_limit(self):
        """API 요청 속도 제한 대기"""
        now = time.time()
        elapsed = now - self.last_request_time
        
        if elapsed < self.request_delay:
            wait_time = self.request_delay - elapsed
            logger.debug(f"API 속도 제한: {wait_time:.2f}초 대기")
            await asyncio.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    async def query_vision(self, prompt: str, image_data: Union[str, bytes]) -> Dict[str, Any]:
        """
        Gemini Vision API 쿼리
        
        Args:
            prompt: 프롬프트 텍스트
            image_data: 이미지 데이터 (base64 문자열 또는 바이트)
        
        Returns:
            API 응답 딕셔너리
        """
        await self._wait_for_rate_limit()
        start_time = time.time()
        
        try:
            # 이미지 데이터 전처리
            if isinstance(image_data, bytes):
                image_base64 = base64.b64encode(image_data).decode('utf-8')
            else:
                image_base64 = image_data
            
            # 요청 데이터 구성
            data = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": "image/jpeg",
                                    "data": image_base64
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": self.generation_config,
                "safetySettings": self.safety_settings
            }
            
            # API 요청 전송
            response = requests.post(
                self.vision_api_url,
                json=data,
                headers={"Content-Type": "application/json"}
            )
            
            # 응답 처리
            elapsed_time = time.time() - start_time
            response_size = len(response.text) if response.text else 0
            
            if response.status_code != 200:
                logger.error(f"Gemini Vision API 요청 실패: 상태 코드 {response.status_code}, 응답: {response.text}")
                logger.log_ai_request(
                    model="gemini-pro-vision",
                    prompt_length=len(prompt),
                    response_time=elapsed_time,
                    success=False,
                    details=f"HTTP {response.status_code}: {response.text[:100]}..."
                )
                return {"error": f"API 요청 실패: 상태 코드 {response.status_code}", "response": response.text}
            
            response_data = response.json()
            logger.log_ai_request(
                model="gemini-pro-vision",
                prompt_length=len(prompt),
                response_length=response_size,
                response_time=elapsed_time,
                success=True
            )
            
            # 응답에서 텍스트 추출
            if "candidates" in response_data and len(response_data["candidates"]) > 0:
                content = response_data["candidates"][0]["content"]
                if "parts" in content and len(content["parts"]) > 0:
                    result_text = content["parts"][0]["text"]
                    return {"result": result_text, "raw_response": response_data}
            
            return {"error": "API 응답 형식 오류", "raw_response": response_data}
        
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Gemini Vision API 요청 중 오류: {str(e)}")
            logger.log_ai_request(
                model="gemini-pro-vision",
                prompt_length=len(prompt),
                response_time=elapsed_time,
                success=False,
                details=f"Exception: {str(e)}"
            )
            return {"error": f"API 요청 중 오류: {str(e)}"}
    
    async def query_text(self, prompt: str) -> Dict[str, Any]:
        """
        Gemini Text API 쿼리
        
        Args:
            prompt: 프롬프트 텍스트
        
        Returns:
            API 응답 딕셔너리
        """
        await self._wait_for_rate_limit()
        start_time = time.time()
        
        try:
            # 요청 데이터 구성
            data = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ],
                "generationConfig": self.generation_config,
                "safetySettings": self.safety_settings
            }
            
            # API 요청 전송
            response = requests.post(
                self.text_api_url,
                json=data,
                headers={"Content-Type": "application/json"}
            )
            
            # 응답 처리
            elapsed_time = time.time() - start_time
            response_size = len(response.text) if response.text else 0
            
            if response.status_code != 200:
                logger.error(f"Gemini Text API 요청 실패: 상태 코드 {response.status_code}, 응답: {response.text}")
                logger.log_ai_request(
                    model="gemini-pro",
                    prompt_length=len(prompt),
                    response_time=elapsed_time,
                    success=False,
                    details=f"HTTP {response.status_code}: {response.text[:100]}..."
                )
                return {"error": f"API 요청 실패: 상태 코드 {response.status_code}", "response": response.text}
            
            response_data = response.json()
            logger.log_ai_request(
                model="gemini-pro",
                prompt_length=len(prompt),
                response_length=response_size,
                response_time=elapsed_time,
                success=True
            )
            
            # 응답에서 텍스트 추출
            if "candidates" in response_data and len(response_data["candidates"]) > 0:
                content = response_data["candidates"][0]["content"]
                if "parts" in content and len(content["parts"]) > 0:
                    result_text = content["parts"][0]["text"]
                    return {"result": result_text, "raw_response": response_data}
            
            return {"error": "API 응답 형식 오류", "raw_response": response_data}
        
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Gemini Text API 요청 중 오류: {str(e)}")
            logger.log_ai_request(
                model="gemini-pro",
                prompt_length=len(prompt),
                response_time=elapsed_time,
                success=False,
                details=f"Exception: {str(e)}"
            )
            return {"error": f"API 요청 중 오류: {str(e)}"}
    
    async def extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        """
        응답 텍스트에서 JSON 데이터 추출
        
        Args:
            response_text: API 응답 텍스트
        
        Returns:
            추출된 JSON 객체
        """
        try:
            # JSON 블록 찾기
            json_start = response_text.find("```json")
            if json_start == -1:
                json_start = response_text.find("```")
            
            if json_start != -1:
                # 시작 위치 보정
                json_start = response_text.find("{", json_start)
                if json_start == -1:
                    json_start = response_text.find("[", json_start)
                
                # 종료 위치 찾기
                json_end = response_text.rfind("}")
                if json_end == -1:
                    json_end = response_text.rfind("]")
                
                if json_start != -1 and json_end != -1:
                    json_str = response_text[json_start:json_end+1]
                    return json.loads(json_str)
            
            # JSON 블록을 찾지 못한 경우 전체 텍스트를 파싱
            return json.loads(response_text)
        
        except Exception as e:
            logger.error(f"JSON 추출 오류: {str(e)}")
            logger.error(f"원본 텍스트: {response_text}")
            return {"error": f"JSON 추출 실패: {str(e)}", "text": response_text}


# 전역 API 클라이언트 인스턴스
gemini_client = GeminiAPIClient() 