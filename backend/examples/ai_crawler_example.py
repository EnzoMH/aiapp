"""
AI 에이전트 크롤러 사용 예시

이 스크립트는 AI 에이전트 크롤러를 사용하여 나라장터를 크롤링하는 방법을 보여줍니다.
"""

import os
import asyncio
import json
from pathlib import Path

# 환경 변수 설정 (실제 사용 시에는 .env 파일이나 환경 변수로 설정하세요)
os.environ["GEMINI_API_KEY"] = "여기에_실제_API_키_입력"

# 크롤러 모듈 가져오기
from backend.utils.crawl.ai_agent import create_crawler
from backend.utils.crawl.utils.config import crawler_config, search_config
from backend.utils.crawl.core.models import CrawlResult


async def run_crawler():
    """크롤러 실행 함수"""
    # 키워드 설정
    keywords = ["인공지능", "소프트웨어 개발", "시스템 통합"]
    
    # 크롤러 인스턴스 생성
    crawler = create_crawler(
        keywords=keywords,  # 검색할 키워드 목록
        max_pages=2,        # 키워드당 최대 페이지 수
        max_details=5,      # 상세 정보를 추출할 최대 항목 수
        headless=False,     # 브라우저 창 표시 여부 (디버깅 시에는 False로 설정)
        debug_mode=True     # 디버그 모드 활성화
    )
    
    # 크롤링 시작
    print(f"크롤링 시작 (키워드: {keywords})")
    result = await crawler.start()
    
    # 결과 출력
    print("\n" + "="*50)
    print(f"크롤링 완료 (상태: {result.status.value})")
    print(f"총 항목 수: {len(result.items)}")
    print(f"상세 정보 수: {len(result.details)}")
    print(f"소요 시간: {(result.end_time - result.start_time).total_seconds():.2f}초")
    print("="*50 + "\n")
    
    # 최근 크롤링 결과 저장 경로 찾기
    results_dir = Path(crawler_config.results_dir)
    result_files = list(results_dir.glob("ai_crawl_result_*.json"))
    
    if result_files:
        # 가장 최근 파일 찾기
        latest_file = max(result_files, key=lambda f: f.stat().st_mtime)
        print(f"최근 크롤링 결과 파일: {latest_file}")
        
        # 결과 파일 내용 확인 (첫 5개 항목만)
        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
            print("\n항목 샘플:")
            for i, item in enumerate(data.get("items", [])[:5]):
                print(f"  {i+1}. {item['title']} ({item['bid_id']})")
    else:
        print("저장된 결과 파일이 없습니다.")


if __name__ == "__main__":
    # 비동기 함수 실행
    asyncio.run(run_crawler()) 