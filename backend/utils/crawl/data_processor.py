from typing import List, Dict
import pandas as pd
import os
from datetime import datetime
import logging
import re
from backend.utils.crawl.constants import SEARCH_KEYWORDS


logger = logging.getLogger(__name__)

class DataProcessor:
    def __init__(self):
        # 프로젝트 구조에 맞게 경로 수정
        self.export_path = "C:/Users/MyoengHo Shin/pjt/progen/test"
        os.makedirs(self.export_path, exist_ok=True)
        
    def extract_project_period(self, notice_text: str) -> str:
        """공고 내용에서 사업기간 추출"""
        if not notice_text:
            return ""
        
        patterns = [
            r"사업기간[:\s]*([\d\s~년월일]+)",
            r"계약기간[:\s]*([\d\s~년월일]+)",
            r"수행기간[:\s]*([\d\s~년월일]+)",
            r"용역기간[:\s]*([\d\s~년월일]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, notice_text)
            if match:
                return match.group(1).strip()
        return ""

    def extract_price(self, text: str) -> str:
        """금액 정보 추출 및 포맷팅"""
        if not text:
            return ""
        try:
            # 숫자만 추출하여 정수로 변환
            numbers = re.findall(r'\d+', text.replace(',', ''))
            if numbers:
                amount = int(numbers[0])
                return f"{amount:,}원"
        except:
            pass
        return text

    def extract_submission_method(self, text: str) -> str:
        """제안서 제출 방식 추출"""
        if not text:
            return ""
            
        if '전자' in text:
            return "전자제출"
        elif '직접' in text or '수기' in text:
            return "직접제출"
        return ""

    def process_crawling_results(self, results: List[Dict]) -> pd.DataFrame:
        """크롤링 결과를 DataFrame으로 변환"""
        processed_data = []
        
        for item in results:
            try:
                basic_info = item.get('basic_info', {})
                detail_info = item.get('detail_info', {})
                
                # 공고 내용과 사업기간
                general_notice = detail_info.get('general_notice', '')
                project_period = self.extract_project_period(general_notice)
                
                # 제안서 제출 방식
                bid_progress = detail_info.get('bid_progress', '')
                submission_method = self.extract_submission_method(bid_progress)
                
                # 입찰 마감일
                bid_end_date = ""
                if bid_progress:
                    matches = re.findall(r'입찰서제출.*?(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})', bid_progress)
                    if matches:
                        bid_end_date = matches[-1]  # 가장 마지막 날짜 사용
                
                processed_item = {
                    '키워드목록': ', '.join(SEARCH_KEYWORDS),  # constants.py에서 가져온 전체 키워드 목록
                    '검색키워드': item.get('search_keyword', ''),
                    '공고검색일': datetime.now().strftime('%Y-%m-%d'),
                    '공고명': basic_info.get('title', ''),
                    '공고기관': basic_info.get('announce_agency', ''),
                    '사업기간': project_period,
                    '금액(VAT포함)': '',  # 제안요청서에서 추출 필요
                    '입찰마감일': bid_end_date,
                    '제안서 제출 방식': submission_method,
                    '정량평가점수': '',  # 제안요청서에서 추출 필요
                    '내용': general_notice
                }
                
                # 특수문자 및 개행문자 정리
                for key, value in processed_item.items():
                    if isinstance(value, str):
                        # 여러 개의 개행문자를 하나로 통일
                        value = re.sub(r'\n+', '\n', value)
                        # 앞뒤 공백 제거
                        value = value.strip()
                        processed_item[key] = value
                
                processed_data.append(processed_item)
                
            except Exception as e:
                logger.error(f"데이터 처리 중 오류: {str(e)}")
                continue

        df = pd.DataFrame(processed_data)
        return df

    def export_to_excel(self, df: pd.DataFrame, filename: str = None) -> str:
        """DataFrame을 Excel 파일로 저장"""
        if filename is None:
            filename = f"입찰공고분석_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            
        file_path = os.path.join(self.export_path, filename)
        
        try:
            # Excel 스타일 설정
            writer = pd.ExcelWriter(file_path, engine='xlsxwriter')
            df.to_excel(writer, sheet_name='입찰공고', index=False)
            
            # 워크북과 워크시트 가져오기
            workbook = writer.book
            worksheet = writer.sheets['입찰공고']
            
            # 헤더 포맷
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'border': 1,
                'text_wrap': True,
                'valign': 'vcenter',
                'align': 'center'
            })
            
            # 내용 셀 포맷
            content_format = workbook.add_format({
                'text_wrap': True,
                'valign': 'top',
                'align': 'left',
                'border': 1
            })
            
            # 컬럼 너비 설정
            column_widths = {
                '키워드목록': 15,
                '검색키워드': 12,
                '공고검색일': 12,
                '공고명': 40,
                '공고기관': 20,
                '사업기간': 15,
                '금액(VAT포함)': 15,
                '입찰마감일': 12,
                '제안서 제출 방식': 15,
                '정량평가점수': 12,
                '내용': 50
            }
            
            # 포맷 적용
            for idx, (col, width) in enumerate(column_widths.items()):
                worksheet.set_column(idx, idx, width)
                worksheet.write(0, idx, col, header_format)
                
                # 내용 컬럼에 대해 모든 행에 content_format 적용
                if col == '내용':
                    for row in range(1, len(df) + 1):
                        worksheet.write(row, idx, df.iloc[row-1][col], content_format)
            
            # 행 높이 설정
            worksheet.set_default_row(30)  # 기본 행 높이
            worksheet.set_row(0, 40)  # 헤더 행 높이
            
            writer.close()
            logger.info(f"Excel 파일 저장 완료: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Excel 파일 저장 중 오류: {str(e)}")
            raise