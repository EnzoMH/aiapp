"""
문서 처리 및 제안서 생성 모듈
"""
from fastapi import UploadFile
from backend.utils.prop.dc import DocumentProcessor

# 문서 처리 함수 (app.py에서 사용)
async def process_file(file: UploadFile) -> str:
    """
    파일을 처리하여 텍스트 추출
    
    Args:
        file: 업로드된 파일
        
    Returns:
        str: 추출된 텍스트
    """
    return await DocumentProcessor.process_file(file)

# 텍스트 정리 함수 (app.py에서 사용)
def clean_text(text: str) -> str:
    """
    추출된 텍스트 정리
    
    Args:
        text: 정리할 텍스트
        
    Returns:
        str: 정리된 텍스트
    """
    return DocumentProcessor.clean_text(text)