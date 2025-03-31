"""
AI 에이전트 크롤링 프롬프트 템플릿 모듈

이 모듈은 Gemini API에 전송할 프롬프트 템플릿을 정의합니다.
"""

# 스크린샷 기반 요소 찾기 프롬프트
ELEMENT_LOCATOR_PROMPT = """
당신은 웹 크롤링을 도와주는 AI 에이전트입니다. 
제공된 스크린샷에서 다음 요소를 찾아 해당 요소의 위치나 특성을 자세히 설명해주세요:

찾을 요소: {element_description}

최대한 정확하게 요소의 위치를 설명해주세요. 가능하다면 다음과 같은 정보를 포함해주세요:
1. 요소의 대략적인 x, y 좌표 위치 (이미지 왼쪽 상단 기준)
2. 요소의 텍스트 내용
3. 요소의 유형 (버튼, 입력 필드, 링크 등)
4. 인접한 요소나 랜드마크를 기준으로 한 상대적 위치

요소가 보이지 않는 경우, "요소를 찾을 수 없음"이라고 명확히, 한 줄로만 답변해주세요.
"""

# 테이블 데이터 추출 프롬프트
TABLE_EXTRACTOR_PROMPT = """
당신은 웹 크롤링을 도와주는 AI 에이전트입니다.
제공된 스크린샷에서 테이블 데이터를 추출해주세요.

이 스크린샷은 나라장터 입찰공고 목록 페이지의 테이블을 보여줍니다.
테이블에서 다음 형식으로 데이터를 추출해주세요:

```json
[
  {
    "bid_id": "입찰공고번호",
    "title": "공고명",
    "announce_agency": "공고기관",
    "post_date": "게시일자",
    "deadline_date": "마감일시",
    "estimated_amount": "추정가격",
    "progress_stage": "진행단계",
    "url": "(URL 정보가 있다면)"
  },
  ...
]
```

- 테이블의 모든 행 데이터를 추출해주세요.
- 데이터가 명확하지 않은 경우 "null"로 표시하세요.
- 특수문자나 공백은 그대로 유지해주세요.
- 반드시 JSON 형식으로 응답해주세요.
- JSON 외에 다른 설명이나 주석은 포함하지 마세요.
"""

# 공고 상세 페이지 파싱 프롬프트
DETAIL_EXTRACTOR_PROMPT = """
당신은 웹 크롤링을 도와주는 AI 에이전트입니다.
제공된 스크린샷은 나라장터 입찰공고 상세 페이지입니다.
이 페이지에서 다음 형식으로 상세 정보를 추출해주세요:

```json
{
  "contract_method": "계약체결방법 (예: 일반경쟁, 제한경쟁 등)",
  "contract_type": "계약방식 (예: 총액, 단가 등)",
  "general_notice": "일반 공고 내용(요약)",
  "specific_notice": "특수 조건 내용(요약)",
  "bidding_method": "입찰방식 (예: 전자입찰, 직접입찰 등)",
  "budget_year": "집행년도",
  "digital_bid": true/false,
  "additional_info": {
    // 그 외 중요하다고 판단되는 정보
  }
}
```

- 가능한 많은 정보를 추출해주세요.
- 정보가 없는 경우 해당 필드를 null로 설정하세요.
- 정보가 불확실한 경우 가장 그럴듯한 값을 추출하되, additional_info에 불확실성을 표시해주세요.
- 반드시 JSON 형식으로 응답해주세요.
- JSON 외에 다른 설명이나 주석은 포함하지 마세요.
"""

# 오류 해결 프롬프트
ERROR_RECOVERY_PROMPT = """
당신은 웹 크롤링을 수행하는 Selenium 기반 크롤러의 오류를 해결하는 AI 에이전트입니다.
다음 오류 상황과 스크린샷을 분석하여 해결 방법을 제시해주세요:

오류 정보:
{error_message}

발생 위치: {error_location}
작업: {current_task}

다음 형식으로 응답해주세요:

```json
{
  "error_analysis": "오류 원인 분석",
  "solution": "해결 방법",
  "action": {
    "type": "CLICK | INPUT | SELECT | WAIT | NAVIGATE | RETRY | SKIP | ABORT",
    "target": "대상 요소의 선택자 또는 설명",
    "value": "입력할 값 (INPUT 타입인 경우)",
    "wait_time": 숫자 (초 단위, WAIT 타입인 경우)
  },
  "confidence": 0.0 ~ 1.0
}
```

- error_analysis: 오류의 가능한 원인을 분석합니다.
- solution: 사람이 이해할 수 있는 해결 방법을 설명합니다.
- action: 크롤러가 취해야 할 다음 단계를 지정합니다.
  - type: 수행할 액션의 유형 (위 옵션 중 하나)
  - target: 액션을 수행할 대상 요소 (해당하는 경우)
  - value: 입력할 값 (해당하는 경우)
  - wait_time: 대기 시간 (해당하는 경우)
- confidence: 해결책에 대한 신뢰도 (0.0~1.0)

스크린샷을 주의 깊게 분석하고, 가장 적절한 해결 방법을 제시해주세요.
"""

# 스크린샷 분석 프롬프트
SCREENSHOT_ANALYSIS_PROMPT = """
당신은 웹 크롤링을 돕는 AI 에이전트입니다. 
제공된 스크린샷을 분석하여 현재 페이지의 상태와 다음에 취할 수 있는 액션을 알려주세요.

다음 형식으로 응답해주세요:

```json
{
  "page_type": "페이지 유형(예: 로그인, 목록, 상세)",
  "page_state": "페이지 상태(예: 로딩중, 오류, 정상, 캡차)",
  "page_elements": [
    {
      "type": "요소 유형(예: 버튼, 입력필드, 링크, 테이블)",
      "description": "요소 설명",
      "location": "대략적인 위치",
      "importance": 1-10 (중요도)
    },
    ...
  ],
  "recommended_actions": [
    {
      "action": "CLICK | INPUT | SELECT | WAIT | NAVIGATE",
      "target": "대상 요소 설명",
      "value": "입력값 (해당되는 경우)",
      "reason": "이 액션을 권장하는 이유"
    },
    ...
  ],
  "search_keyword_found": true/false,
  "pagination_available": true/false,
  "captcha_detected": true/false,
  "error_message": "에러 메시지 (있는 경우)"
}
```

현재 검색 중인 키워드: {search_keyword}

가능한 한 객관적으로 페이지 상태를 분석하고, 크롤링 목적에 맞는 다음 단계를 제안해주세요.
"""

# 공고 내용 요약 프롬프트
CONTENT_SUMMARY_PROMPT = """
당신은 AI 데이터 분석가입니다. 다음 입찰공고 정보를 분석하고 간결하게 요약해주세요.

공고 데이터:
{bid_data}

다음 형식으로 응답해주세요:

```json
{
  "summary": "공고 내용 요약 (최대 150자)",
  "keywords": ["키워드1", "키워드2", ...],
  "category": "분류 (예: SW개발, 시스템 구축, 용역, 물품)",
  "relevance": 0.0~1.0 (관련성 점수, 키워드 '{search_keyword}'와의 관련성)
}
```

요약은 간결하게 하되, 공고의 핵심 내용을 포함해야 합니다.
키워드는 공고에서 중요한 기술 용어나 핵심 단어를 추출하세요.
""" 