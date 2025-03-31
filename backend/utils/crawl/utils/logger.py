"""
크롤링 로깅 유틸리티 모듈

이 모듈은 크롤링 관련 로깅 및 디버깅을 위한 유틸리티를 제공합니다.
"""

import logging
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any

# 로그 디렉토리 설정
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR, exist_ok=True)

# 로그 포맷 정의
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEBUG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"

# 현재 날짜/시간 기준 로그 파일명 생성
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = os.path.join(LOG_DIR, f"crawler_{TIMESTAMP}.log")
ERROR_LOG_FILE = os.path.join(LOG_DIR, f"crawler_error_{TIMESTAMP}.log")


def setup_logger(name: str, level: int = logging.INFO, debug: bool = False) -> logging.Logger:
    """
    로거 설정 및 인스턴스 반환
    
    Args:
        name: 로거 이름
        level: 로그 레벨
        debug: 디버그 모드 활성화 여부
    
    Returns:
        설정된 로거 인스턴스
    """
    # 로거 인스턴스 생성
    logger = logging.getLogger(name)
    logger.setLevel(level if not debug else logging.DEBUG)
    
    # 핸들러가 없는 경우에만 추가
    if not logger.handlers:
        # 콘솔 핸들러
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level if not debug else logging.DEBUG)
        console_format = logging.Formatter(DEBUG_FORMAT if debug else LOG_FORMAT)
        console_handler.setFormatter(console_format)
        
        # 파일 핸들러 (일반)
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setLevel(level)
        file_format = logging.Formatter(LOG_FORMAT)
        file_handler.setFormatter(file_format)
        
        # 파일 핸들러 (에러)
        error_file_handler = logging.FileHandler(ERROR_LOG_FILE, encoding="utf-8")
        error_file_handler.setLevel(logging.ERROR)
        error_format = logging.Formatter(DEBUG_FORMAT)
        error_file_handler.setFormatter(error_format)
        
        # 핸들러 추가
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        logger.addHandler(error_file_handler)
    
    return logger


# 주요 로거 인스턴스
crawler_logger = setup_logger("crawler")
ai_agent_logger = setup_logger("ai_agent")
debug_logger = setup_logger("debug", logging.DEBUG, True)


class CrawlLogger:
    """크롤링 로거 클래스"""
    
    def __init__(self, name: str, debug: bool = False):
        """
        로거 초기화
        
        Args:
            name: 로거 이름
            debug: 디버그 모드 활성화 여부
        """
        self.logger = setup_logger(name, logging.INFO if not debug else logging.DEBUG, debug)
        self.debug_mode = debug
    
    def info(self, message: str, **kwargs):
        """정보 로깅"""
        self.logger.info(message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """디버그 정보 로깅"""
        if self.debug_mode:
            self.logger.debug(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """경고 로깅"""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, exc_info: bool = False, **kwargs):
        """오류 로깅"""
        self.logger.error(message, exc_info=exc_info, **kwargs)
    
    def exception(self, message: str, **kwargs):
        """예외 로깅"""
        self.logger.exception(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """치명적 오류 로깅"""
        self.logger.critical(message, **kwargs)
    
    def log_http_request(self, method: str, url: str, status_code: Optional[int] = None, 
                        response_time: Optional[float] = None, details: Optional[Dict[str, Any]] = None):
        """HTTP 요청 로깅"""
        log_message = f"HTTP {method} {url}"
        
        if status_code is not None:
            log_message += f" (Status: {status_code})"
        
        if response_time is not None:
            log_message += f" - {response_time:.2f}s"
        
        self.debug(log_message)
        
        if details and self.debug_mode:
            for key, value in details.items():
                self.debug(f"  {key}: {value}")
    
    def log_selenium_action(self, action: str, selector: str, selector_type: str, 
                           success: bool = True, details: Optional[str] = None):
        """Selenium 동작 로깅"""
        status = "성공" if success else "실패"
        log_message = f"Selenium {action} [{selector_type}] '{selector}' - {status}"
        
        if details:
            log_message += f" - {details}"
        
        if success:
            self.debug(log_message)
        else:
            self.warning(log_message)
    
    def log_ai_request(self, model: str, prompt_length: int, response_length: Optional[int] = None,
                      response_time: Optional[float] = None, success: bool = True, details: Optional[str] = None):
        """AI API 요청 로깅"""
        status = "성공" if success else "실패"
        log_message = f"AI 요청 ({model}) - 프롬프트 길이: {prompt_length} 문자 - {status}"
        
        if response_length is not None:
            log_message += f" - 응답 길이: {response_length} 문자"
        
        if response_time is not None:
            log_message += f" - {response_time:.2f}s"
        
        if details:
            log_message += f" - {details}"
        
        if success:
            self.debug(log_message)
        else:
            self.error(log_message)


# 기본 로거 인스턴스 생성
default_logger = CrawlLogger("crawler") 