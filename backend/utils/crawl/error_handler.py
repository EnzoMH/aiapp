import logging
from typing import Callable, Any
from functools import wraps

logger = logging.getLogger(__name__)

class CrawlerException(Exception):
    """크롤러 기본 예외 클래스"""
    pass

class ElementNotFoundException(CrawlerException):
    """요소를 찾을 수 없을 때 발생하는 예외"""
    pass

class ErrorHandler:
    @staticmethod
    def handle_selenium_error(e: Exception, context: str = "") -> None:
        """Selenium 관련 에러 처리"""
        error_msg = f"{context}: {str(e)}" if context else str(e)
        logger.error(error_msg)
        raise CrawlerException(error_msg)

    @staticmethod
    def handle_navigation_error(e: Exception) -> None:
        """페이지 네비게이션 관련 에러 처리"""
        logger.error(f"페이지 이동 중 오류: {str(e)}")
        raise CrawlerException(f"페이지 이동 실패: {str(e)}")

def handle_request_error(retries: int = 3):
    """요청 재시도 데코레이터"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_error = None
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    logger.error(f"시도 {attempt + 1}/{retries} 실패: {str(e)}")
                    if attempt < retries - 1:
                        continue
                    raise last_error
        return wrapper
    return decorator