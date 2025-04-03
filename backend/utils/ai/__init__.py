"""
AI 기능 패키지

다양한 AI 모델을 활용한 기능들을 제공하는 패키지입니다.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ai.log", mode="a", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# 환경 변수에서 Gemini API 키 가져오기
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Gemini API를 사용하기 위한 기본 URL
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# 현재 API 키가 없으면 모의 데이터 사용
USE_MOCK_DATA = not GEMINI_API_KEY

# 모의 영업 인사이트 분석 생성
def generate_mock_sales_insight(analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    모의 영업 인사이트 데이터 생성
    
    Args:
        analysis_data: 분석 요청 데이터
        
    Returns:
        모의 분석 결과 데이터
    """
    logger.info(f"모의 영업 인사이트 생성: {analysis_data['bid_number']}")
    
    # 업종 분석
    industry = analysis_data.get('industry_type', '미상')
    title = analysis_data.get('title', '')
    
    # 사용자 검색 키워드를 최우선으로 활용
    user_keywords = analysis_data.get('search_keywords', [])
    if isinstance(user_keywords, str):
        user_keywords = [user_keywords]
    
    # 키워드 추출
    keywords = list(user_keywords) if user_keywords else []
    
    # 검색 키워드가 부족한 경우에만 추가 추출
    if len(keywords) < 5:
        # 공고명에서 키워드 추출
        if title:
            title_words = title.split(' ')
            for word in title_words:
                if len(word) >= 2 and word not in ['및', '의', '등', '와', '을', '를', '이', '가'] and word not in keywords:
                    keywords.append(word)
                    if len(keywords) >= 5:
                        break
    
        # 업종 키워드 추가
        if industry and industry not in keywords and len(keywords) < 5:
            keywords.append(industry)
    
    # 키워드가 부족한 경우를 대비한 최소 키워드 보장
    if len(keywords) == 0:
        # 공고명에서 자동 추출 실패한 경우 공고명의 첫 단어만 추가
        if title:
            first_word = title.split(' ')[0]
            if len(first_word) >= 2:
                keywords.append(first_word)
        
        # 그래도 없으면 기본값 1개만 추가
        if len(keywords) == 0:
            keywords.append("용역")
    
    # 호환성 점수 계산
    compatibility_score = 50
    
    # 업종 제한 확인
    industry_restriction = analysis_data.get('restrictions', {}).get('industry_restriction', '')
    if industry_restriction and any(kw in industry_restriction for kw in ["소프트웨어", "정보통신", "IT", "전산"]):
        compatibility_score += 20
    
    # 지역 제한 확인
    region_restriction = analysis_data.get('restrictions', {}).get('region_restriction', '')
    if not region_restriction or "제한없음" in region_restriction:
        compatibility_score += 10
    
    # 중소기업 제한 확인
    small_business = analysis_data.get('restrictions', {}).get('small_business_restriction', '')
    if small_business and "중소기업" in small_business:
        compatibility_score += 10
    
    # 호환성 점수 제한
    compatibility_score = min(max(compatibility_score, 30), 90)
    
    # 기회 요소
    opportunity_points = [
        "참여 가능한 사업 규모입니다.",
        "기술적 요구사항이 귀사의 역량과 일치합니다."
    ]
    
    # 지역 제한 기회
    if not region_restriction or "제한없음" in region_restriction:
        opportunity_points.append("지역 제한이 없어 참여가 용이합니다.")
    
    # 위험 요소
    risk_points = [
        "유사 프로젝트 수행 실적이 요구될 수 있습니다.",
        "가격 경쟁이 치열할 것으로 예상됩니다."
    ]
    
    # 업종 제한 위험
    if industry_restriction and not any(kw in industry_restriction for kw in ["소프트웨어", "정보통신", "IT", "전산"]):
        risk_points.append(f"업종 제한사항 ({industry_restriction})이 귀사의 주력 분야와 일치하지 않을 수 있습니다.")
    
    # 영업 전략
    sales_strategy = {
        "headline": "차별화된 기술력과 실적을 강조하는 맞춤형 제안",
        "content": f"이 입찰({title})에서는 귀사의 고유한 기술력과 유사 프로젝트 경험을 강조하는 것이 중요합니다. 경쟁사와 차별화된 접근 방식과 혁신적 솔루션을 제안하세요. 발주처의 주요 관심사를 파악하고 이에 초점을 맞춘 제안서를 준비하는 것이 좋습니다."
    }
    
    return {
        "compatibility_score": compatibility_score,
        "keywords": keywords[:5],
        "opportunity_points": opportunity_points,
        "risk_points": risk_points,
        "sales_strategy": sales_strategy
    }

# Gemini API 호출
async def call_gemini_api(prompt: str, max_tokens: int = 1024) -> Optional[str]:
    """
    Gemini API 호출
    
    Args:
        prompt: 프롬프트 텍스트
        max_tokens: 최대 토큰 수
        
    Returns:
        API 응답 텍스트 또는 None (오류 발생 시)
    """
    try:
        if not GEMINI_API_KEY:
            logger.warning("Gemini API 키가 설정되지 않았습니다")
            return None
        
        import aiohttp
        
        # API 엔드포인트
        url = f"{GEMINI_API_BASE_URL}/models/gemini-1.5-pro:generateContent?key={GEMINI_API_KEY}"
        
        # 요청 데이터
        request_data = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.4,
                "topP": 0.8,
                "topK": 40,
                "maxOutputTokens": max_tokens
            }
        }
        
        # API 요청
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=request_data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Gemini API 오류 (상태 코드: {response.status}): {error_text}")
                    return None
                
                result = await response.json()
                
                # 응답 파싱
                if "candidates" in result and len(result["candidates"]) > 0:
                    content = result["candidates"][0].get("content", {})
                    parts = content.get("parts", [])
                    
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]
                
                logger.error(f"Gemini API 응답 파싱 오류: {result}")
                return None
                
    except Exception as e:
        logger.error(f"Gemini API 호출 중 오류 발생: {str(e)}")
        return None

# 영업 기회 분석
async def analyze_sales_opportunity(analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    입찰 정보 기반 영업 기회 분석
    
    Args:
        analysis_data: 분석 요청 데이터
        
    Returns:
        영업 인사이트 분석 결과
    """
    try:
        logger.info(f"영업 기회 분석 시작: {analysis_data['bid_number']} - {analysis_data['title']}")
        
        # 사용자 검색 키워드 처리
        user_keywords = analysis_data.get('search_keywords', [])
        if isinstance(user_keywords, str):
            user_keywords = [user_keywords]
        
        # 검색 키워드 로깅
        if user_keywords:
            logger.info(f"사용자 검색 키워드: {', '.join(user_keywords)}")
        
        # 모의 데이터 사용 여부 확인
        if USE_MOCK_DATA:
            logger.info("Gemini API 키가 없어 모의 데이터 사용")
            return generate_mock_sales_insight(analysis_data)
        
        # 분석 프롬프트 생성
        search_keywords_text = ', '.join(user_keywords) if user_keywords else '없음'
        
        prompt = f"""
        당신은 입찰공고 분석 전문가입니다. 다음의 입찰 정보를 분석하여 영업 기회를 평가해주세요.
        
        입찰번호: {analysis_data.get('bid_number', '정보 없음')}
        공고명: {analysis_data.get('title', '정보 없음')}
        업종구분: {analysis_data.get('industry_type', '정보 없음')}
        입찰방식: {analysis_data.get('bid_method', '정보 없음')}
        계약방식: {analysis_data.get('contract_method', '정보 없음')}
        사용자 검색 키워드: {search_keywords_text}
        
        자격요건:
        - 사업자등록증: {analysis_data.get('qualifications', {}).get('business_license', '정보 없음')}
        - 면허/자격 제한: {analysis_data.get('qualifications', {}).get('license_requirements', '정보 없음')}
        - 기술능력: {analysis_data.get('qualifications', {}).get('technical_capability', '정보 없음')}
        
        제한사항:
        - 업종제한: {analysis_data.get('restrictions', {}).get('industry_restriction', '정보 없음')}
        - 지역제한: {analysis_data.get('restrictions', {}).get('region_restriction', '정보 없음')}
        - 중소기업 참여제한: {analysis_data.get('restrictions', {}).get('small_business_restriction', '정보 없음')}
        
        가격정보:
        - 추정가격: {analysis_data.get('price_info', {}).get('estimated_price', '정보 없음')}
        
        마감일시: {analysis_data.get('deadline', '정보 없음')}
        
        위 입찰 정보를 바탕으로 다음 형식에 맞게 영업 인사이트를 JSON 형식으로 제공해주세요.
        특히 사용자가 검색한 키워드를 중심으로 분석하되, 키워드가 없는 경우 공고 내용에서 핵심 키워드를 추출해주세요:
        
        1. compatibility_score: 업종 적합성 점수 (0-100 사이의 숫자)
        2. keywords: 핵심 키워드 (최대 5개, 사용자 검색 키워드가 있다면 이를 우선 활용)
        3. opportunity_points: 기회 요소 (3-5개의 항목)
        4. risk_points: 위험 요소 (3-5개의 항목)
        5. sales_strategy: {"headline": "전략 제목", "content": "상세 전략 내용"}
        
        소프트웨어/IT 기업 관점에서 분석하되, 한국어로 작성해주세요.
        JSON 구조만 반환하고, 다른 설명이나 주석은 포함하지 마세요.
        """
        
        # API 호출 및 응답 파싱
        response_text = await call_gemini_api(prompt)
        
        if not response_text:
            logger.warning("Gemini API 응답 없음, 모의 데이터 사용")
            return generate_mock_sales_insight(analysis_data)
        
        try:
            # JSON 형식 응답 추출
            # JSON 블록 찾기
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if json_match:
                json_text = json_match.group(0)
                analysis_result = json.loads(json_text)
                
                # 필수 필드 확인
                required_fields = ['compatibility_score', 'keywords', 'opportunity_points', 'risk_points', 'sales_strategy']
                if all(field in analysis_result for field in required_fields):
                    logger.info(f"영업 인사이트 분석 완료: {analysis_data['bid_number']}")
                    return analysis_result
            
            logger.warning(f"Gemini API 응답 형식 오류: {response_text}")
            return generate_mock_sales_insight(analysis_data)
            
        except json.JSONDecodeError:
            logger.error(f"JSON 파싱 오류: {response_text}")
            return generate_mock_sales_insight(analysis_data)
        
    except Exception as e:
        logger.error(f"영업 기회 분석 중 오류 발생: {str(e)}")
        return generate_mock_sales_insight(analysis_data)

# 외부로 노출되는 함수들
__all__ = ['analyze_sales_opportunity'] 