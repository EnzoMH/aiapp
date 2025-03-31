# AI 에이전트 크롤러

나라장터 웹사이트에서 입찰 정보를 크롤링하기 위한 AI 기반 크롤러입니다. 이 크롤러는 Google Gemini API를 사용하여 웹페이지의 구조가 변경되더라도 지능적으로 데이터를 추출할 수 있습니다.

## 구조

```
crawl/
├── ai_agent/                   # AI 에이전트 크롤러
│   ├── api_client.py           # Gemini API 클라이언트
│   ├── crawler.py              # 메인 크롤러 클래스
│   ├── crawler_helper.py       # 크롤러 헬퍼 함수
│   ├── detail_extractor.py     # 상세 정보 추출기
│   ├── prompts.py              # AI 프롬프트 템플릿
│   ├── search_processor.py     # 검색 결과 처리기
│   └── websocket_manager.py    # 웹소켓 관리자
├── core/                       # 핵심 모듈
│   └── models.py               # 데이터 모델
├── utils/                      # 유틸리티
│   ├── config.py               # 설정 관리
│   └── logger.py               # 로깅 유틸리티
└── README.md                   # 이 문서
```

## 필요 패키지

- Python 3.8 이상
- Selenium
- chromedriver-autoinstaller
- Pillow
- requests
- pydantic
- fastapi (웹소켓 사용 시)

## 설치 방법

환경 설정:

```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 필요 패키지 설치
pip install selenium chromedriver-autoinstaller pillow requests pydantic fastapi
```

## 사용 방법

### 기본 사용법

```python
import asyncio
import os
from backend.utils.crawl.ai_agent import create_crawler

# Gemini API 키 설정
os.environ["GEMINI_API_KEY"] = "your_api_key_here"

async def run_crawler():
    # 크롤러 생성
    crawler = create_crawler(
        keywords=["인공지능", "소프트웨어 개발"],
        max_pages=2,
        headless=True
    )
    
    # 크롤링 시작
    result = await crawler.start()
    
    # 결과 출력
    print(f"크롤링 완료: {len(result.items)}개 항목")

# 비동기 함수 실행
asyncio.run(run_crawler())
```

### 웹소켓 사용 예시 (FastAPI)

```python
from fastapi import FastAPI, WebSocket
from backend.utils.crawl.ai_agent import create_crawler

app = FastAPI()

@app.websocket("/ws/crawl")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # 웹소켓과 함께 크롤러 생성
    crawler = create_crawler(
        keywords=["인공지능", "소프트웨어 개발"],
        websocket=websocket
    )
    
    # 크롤링 시작
    await crawler.start()
```

## 기능

1. **AI 기반 요소 인식**: Gemini Vision API를 사용하여 웹페이지에서 필요한 요소를 인식하고 추출합니다.
2. **자동 오류 복구**: 페이지 구조 변경이나 로딩 지연 등의 문제가 발생해도 자동으로 복구를 시도합니다.
3. **실시간 모니터링**: 웹소켓을 통해 크롤링 진행 상황과 결과를 실시간으로 전송합니다.
4. **모듈화된 설계**: 유지보수와 확장이 용이한 모듈화된 구조로 설계되었습니다.
5. **상세 로깅**: 모든 과정과 오류를 상세히 기록하여 디버깅을 쉽게 합니다.

## 구성 파일

크롤러 설정은 `utils/config.py`에서 관리됩니다. 주요 설정:

- **crawler_config**: 기본 URL, 타임아웃, 재시도 횟수 등 크롤러 기본 설정
- **ai_agent_config**: Gemini API 키, 모델 설정, 병렬 요청 수 등
- **search_config**: 기본 키워드, 페이지당 항목 수 등

## 주의사항

1. 웹사이트 이용약관을 준수하세요.
2. 과도한 요청은 IP 차단을 초래할 수 있습니다.
3. API 키는 안전하게 관리하고, 환경 변수나 시크릿 매니저를 통해 주입하세요.
4. 스크린샷에 민감한 정보가 포함되지 않도록 주의하세요.

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 