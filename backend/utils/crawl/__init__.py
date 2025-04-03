"""
나라장터 크롤링 패키지

이 패키지는 국가종합전자조달 나라장터 웹사이트의 입찰공고를 수집하는 크롤러를 제공합니다.
웹 크롤링, 데이터 추출, 처리를 위한 다양한 모듈이 포함되어 있습니다.
"""

try:
    from .crawl import (
        add_websocket_client,
        remove_websocket_client,
        broadcast_status,
        broadcast_results,
        broadcast_progress,
        crawling_status,
        start_crawling,
        stop_crawling,
        get_crawling_status
    )
    
    from .crawler import g2b_crawler
    from .detail_extractor import detail_extractor
    
    # 성공적으로 임포트 완료
    CRAWL_UTILS_AVAILABLE = True
    
except ImportError as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"크롤링 모듈 로딩 중 오류 발생: {str(e)}. 일부 기능이 제한될 수 있습니다.")
    
    # 더미 클래스 및 함수 정의
    class DummyClass:
        def __init__(self, *args, **kwargs):
            pass
        
        async def __call__(self, *args, **kwargs):
            return None
        
        def __getattr__(self, name):
            return lambda *args, **kwargs: None
    
    # 더미 객체로 대체
    g2b_crawler = DummyClass
    detail_extractor = DummyClass
    
    # 더미 함수 정의
    async def add_websocket_client(*args, **kwargs):
        return None
    
    async def remove_websocket_client(*args, **kwargs):
        return None
    
    async def broadcast_status(*args, **kwargs):
        return None
    
    async def broadcast_results(*args, **kwargs):
        return None
    
    async def broadcast_progress(*args, **kwargs):
        return None
    
    async def crawling_status(*args, **kwargs):
        return None
    
    async def start_crawling(*args, **kwargs):
        return None
    
    async def stop_crawling(*args, **kwargs):
        return None
    
    async def get_crawling_status(*args, **kwargs):
        return None
    
    # 크롤링 기능 사용 불가능 플래그
    CRAWL_UTILS_AVAILABLE = False

# 패키지 추가 속성 정의
__version__ = "0.1.0"
__author__ = "Progen"
__all__ = [
    # crawl 모듈 내보내기
    'add_websocket_client',
    'remove_websocket_client',
    'broadcast_status',
    'broadcast_results',
    'broadcast_progress',
    'crawling_status',
    'start_crawling',
    'stop_crawling',
    'get_crawling_status',
    
    # crawler 모듈 내보내기
    'g2b_crawler',
    
    # detail_extractor 모듈 내보내기
    'detail_extractor',
    
    # 더미 객체 및 함수 내보내기
    'CRAWL_UTILS_AVAILABLE'
]
