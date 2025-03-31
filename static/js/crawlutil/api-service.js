/**
 * API 서비스 유틸리티
 * 서버 API 호출을 위한 유틸리티 함수들
 */

// API 서비스 - 백엔드 API와의 통신 담당
import { Debug } from './logger.js';

/**
 * 크롤링 시작 API 호출
 * @param {string[]} keywords - 검색할 키워드 배열
 * @param {string} startDate - 시작 날짜 (YYYY-MM-DD)
 * @param {string} endDate - 종료 날짜 (YYYY-MM-DD)
 * @returns {Promise<Object>} - API 응답 객체
 */
export async function startCrawling(keywords, startDate, endDate) {
    try {
        Debug.info(`크롤링 시작 API 호출 - 키워드: ${keywords.join(', ')}, 기간: ${startDate} ~ ${endDate}`);
        
        // API 요청 데이터 구성
        const requestData = {
            keywords: keywords,
            start_date: startDate,
            end_date: endDate
        };
        
        // API 호출
        const response = await fetch('/api/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        // 응답 처리
        const data = await response.json();
        Debug.info('크롤링 시작 API 응답:', data);
        
        return {
            success: response.ok,
            status: response.status,
            message: data.message || '알 수 없는 응답',
            ...data
        };
    } catch (error) {
        Debug.error('크롤링 시작 API 호출 오류:', error);
        return {
            success: false,
            message: '네트워크 오류 또는 서버 응답 처리 실패',
            error: error.message
        };
    }
}

/**
 * 크롤링 중지 API 호출
 * @returns {Promise<Object>} - API 응답 객체
 */
export async function stopCrawling() {
    try {
        Debug.info('크롤링 중지 API 호출');
        
        // API 호출
        const response = await fetch('/api/stop', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        // 응답 처리
        const data = await response.json();
        Debug.info('크롤링 중지 API 응답:', data);
        
        return {
            success: response.ok,
            status: response.status,
            message: data.message || '알 수 없는 응답',
            ...data
        };
    } catch (error) {
        Debug.error('크롤링 중지 API 호출 오류:', error);
        return {
            success: false,
            message: '네트워크 오류 또는 서버 응답 처리 실패',
            error: error.message
        };
    }
}

/**
 * 크롤링 결과 다운로드 API 호출
 * @returns {Promise<Object>} - API 응답 객체
 */
export async function downloadResults() {
    try {
        Debug.info('크롤링 결과 다운로드 API 호출');
        
        // API 호출
        const response = await fetch('/api/results/download', {
            method: 'GET'
        });
        
        // 응답 처리
        if (response.ok) {
            // 다운로드 URL 생성
            const blob = await response.blob();
            const downloadUrl = URL.createObjectURL(blob);
            
            // 파일명 가져오기
            let filename = 'crawling_results.xlsx';
            const contentDisposition = response.headers.get('Content-Disposition');
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
                if (filenameMatch && filenameMatch[1]) {
                    filename = filenameMatch[1];
                }
            }
            
            Debug.info('크롤링 결과 다운로드 준비 완료:', { downloadUrl, filename });
            
            return {
                success: true,
                downloadUrl,
                filename,
                message: '다운로드 준비 완료'
            };
        } else {
            const errorData = await response.json();
            Debug.warn('크롤링 결과 다운로드 실패:', errorData);
            
            return {
                success: false,
                status: response.status,
                message: errorData.message || '결과 다운로드 실패'
            };
        }
    } catch (error) {
        Debug.error('크롤링 결과 다운로드 API 호출 오류:', error);
        return {
            success: false,
            message: '네트워크 오류 또는 서버 응답 처리 실패',
            error: error.message
        };
    }
}

/**
 * 크롤링 상태 확인 API 호출
 * @returns {Promise<Object>} - API 응답 객체
 */
export async function getCrawlingStatus() {
    try {
        Debug.info('크롤링 상태 확인 API 호출');
        
        // API 호출
        const response = await fetch('/api/status', {
            method: 'GET'
        });
        
        // 응답 처리
        const data = await response.json();
        Debug.info('크롤링 상태 확인 API 응답:', data);
        
        return {
            success: response.ok,
            status: response.status,
            message: data.message || '알 수 없는 응답',
            ...data
        };
    } catch (error) {
        Debug.error('크롤링 상태 확인 API 호출 오류:', error);
        return {
            success: false,
            message: '네트워크 오류 또는 서버 응답 처리 실패',
            error: error.message
        };
    }
}

/**
 * AI 에이전트 크롤링 시작 API 호출
 * @returns {Promise<Object>} - API 응답 객체
 */
export async function startAgentCrawling() {
    try {
        Debug.info('AI 에이전트 크롤링 시작 API 호출');
        
        // API 호출
        const response = await fetch('/api/agent/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        // 응답 처리
        const data = await response.json();
        Debug.info('AI 에이전트 크롤링 시작 API 응답:', data);
        
        return {
            success: response.ok,
            status: response.status,
            message: data.message || '알 수 없는 응답',
            ...data
        };
    } catch (error) {
        Debug.error('AI 에이전트 크롤링 시작 API 호출 오류:', error);
        return {
            success: false,
            message: '네트워크 오류 또는 서버 응답 처리 실패',
            error: error.message
        };
    }
}

/**
 * AI 에이전트 크롤링 중지 API 호출
 * @returns {Promise<Object>} - API 응답 객체
 */
export async function stopAgentCrawling() {
    try {
        Debug.info('AI 에이전트 크롤링 중지 API 호출');
        
        // API 호출
        const response = await fetch('/api/agent/stop', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        // 응답 처리
        const data = await response.json();
        Debug.info('AI 에이전트 크롤링 중지 API 응답:', data);
        
        return {
            success: response.ok,
            status: response.status,
            message: data.message || '알 수 없는 응답',
            ...data
        };
    } catch (error) {
        Debug.error('AI 에이전트 크롤링 중지 API 호출 오류:', error);
        return {
            success: false,
            message: '네트워크 오류 또는 서버 응답 처리 실패',
            error: error.message
        };
    }
}

/**
 * AI 에이전트 크롤링 결과 가져오기 API 호출
 * @returns {Promise<Object>} - API 응답 객체
 */
export async function getAgentResults() {
    try {
        Debug.info('AI 에이전트 크롤링 결과 API 호출');
        
        // API 호출
        const response = await fetch('/api/agent/results', {
            method: 'GET'
        });
        
        // 응답 처리
        const data = await response.json();
        Debug.info('AI 에이전트 크롤링 결과 API 응답:', data);
        
        return {
            success: response.ok,
            status: response.status,
            message: data.message || '알 수 없는 응답',
            results: data.results || [],
            ...data
        };
    } catch (error) {
        Debug.error('AI 에이전트 크롤링 결과 API 호출 오류:', error);
        return {
            success: false,
            message: '네트워크 오류 또는 서버 응답 처리 실패',
            error: error.message,
            results: []
        };
    }
} 