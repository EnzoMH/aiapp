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
        
        // API 요청 데이터 구성 - 서버에서 기대하는 필드명으로 변경
        const requestData = {
            keywords: keywords,
            startDate: startDate,
            endDate: endDate
        };
        
        // 네트워크 요청 로깅
        Debug.logRequest('POST', '/api/start', requestData);
        
        // 요청 시작 시간 기록
        const startTime = performance.now();
        
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
        
        // 응답 시간 계산
        const responseTime = Math.round(performance.now() - startTime);
        
        // 네트워크 응답 로깅
        Debug.logResponse('POST', '/api/start', response.status, data, responseTime);
        
        Debug.info(`크롤링 시작 API 응답 (${responseTime}ms): ${response.ok ? '성공' : '실패'}`);
        
        return {
            success: response.ok,
            status: response.status,
            message: data.message || '알 수 없는 응답',
            responseTime,
            ...data
        };
    } catch (error) {
        Debug.error('크롤링 시작 API 호출 오류:', error);
        console.error('상세 오류:', error);
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
        
        // 네트워크 요청 로깅
        Debug.logRequest('POST', '/api/stop', null);
        
        // 요청 시작 시간 기록
        const startTime = performance.now();
        
        // API 호출
        const response = await fetch('/api/stop', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        // 응답 처리
        const data = await response.json();
        
        // 응답 시간 계산
        const responseTime = Math.round(performance.now() - startTime);
        
        // 네트워크 응답 로깅
        Debug.logResponse('POST', '/api/stop', response.status, data, responseTime);
        
        Debug.info(`크롤링 중지 API 응답 (${responseTime}ms): ${response.ok ? '성공' : '실패'}`);
        
        return {
            success: response.ok,
            status: response.status,
            message: data.message || '알 수 없는 응답',
            responseTime,
            ...data
        };
    } catch (error) {
        Debug.error('크롤링 중지 API 호출 오류:', error);
        console.error('상세 오류:', error);
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
        
        // 네트워크 요청 로깅
        Debug.logRequest('GET', '/api/results/download', null);
        
        // 요청 시작 시간 기록
        const startTime = performance.now();
        
        // 서버에 추가한 API 엔드포인트 사용
        const response = await fetch('/api/results/download', {
            method: 'GET'
        });
        
        // 응답 시간 계산
        const responseTime = Math.round(performance.now() - startTime);
        
        // 응답 처리
        if (response.ok) {
            // 엑셀 파일 다운로드 처리
            const blob = await response.blob();
            Debug.info(`다운로드 파일 크기: ${(blob.size / 1024).toFixed(2)}KB`);
            
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
            
            // 네트워크 응답 로깅 (파일 다운로드)
            Debug.logResponse('GET', '/api/results/download', response.status, {
                type: blob.type,
                size: blob.size,
                filename: filename
            }, responseTime);
            
            Debug.success(`크롤링 결과 다운로드 준비 완료 (${responseTime}ms): ${filename}`);
            
            return {
                success: true,
                downloadUrl,
                filename,
                message: '다운로드 준비 완료',
                responseTime
            };
        } else {
            // 오류 응답인 경우 JSON으로 파싱 시도
            try {
                const errorData = await response.json();
                Debug.warn('크롤링 결과 다운로드 실패:', errorData);
                
                // 네트워크 응답 로깅 (오류)
                Debug.logResponse('GET', '/api/results/download', response.status, errorData, responseTime);
                
                return {
                    success: false,
                    status: response.status,
                    message: errorData.message || '결과 다운로드 실패',
                    responseTime
                };
            } catch (jsonError) {
                // JSON 파싱 실패시 기본 에러 메시지 반환
                Debug.warn('크롤링 결과 다운로드 실패 (응답 파싱 오류):', response.statusText);
                
                // 네트워크 응답 로깅 (파싱 오류)
                Debug.logResponse('GET', '/api/results/download', response.status, {
                    parseError: true,
                    statusText: response.statusText
                }, responseTime);
                
                return {
                    success: false,
                    status: response.status,
                    message: `결과 다운로드 실패: ${response.statusText}`,
                    responseTime
                };
            }
        }
    } catch (error) {
        Debug.error('크롤링 결과 다운로드 API 호출 오류:', error);
        console.error('상세 오류:', error);
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
        
        // 네트워크 요청 로깅
        Debug.logRequest('GET', '/api/status', null);
        
        // 요청 시작 시간 기록
        const startTime = performance.now();
        
        // 새로 추가된 상태 확인 API 엔드포인트 사용
        const response = await fetch('/api/status', {
            method: 'GET'
        });
        
        // 응답 처리
        const data = await response.json();
        
        // 응답 시간 계산
        const responseTime = Math.round(performance.now() - startTime);
        
        // 네트워크 응답 로깅
        Debug.logResponse('GET', '/api/status', response.status, data, responseTime);
        
        Debug.info(`크롤링 상태 확인 API 응답 (${responseTime}ms): ${response.ok ? '성공' : '실패'}`);
        
        return {
            success: response.ok,
            status: response.status,
            message: data.message || '알 수 없는 응답',
            responseTime,
            ...data
        };
    } catch (error) {
        Debug.error('크롤링 상태 확인 API 호출 오류:', error);
        console.error('상세 오류:', error);
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
        
        // 네트워크 요청 로깅
        Debug.logRequest('POST', '/api/agent/start', null);
        
        // 요청 시작 시간 기록
        const startTime = performance.now();
        
        // API 호출
        const response = await fetch('/api/agent/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        // 응답 처리
        const data = await response.json();
        
        // 응답 시간 계산
        const responseTime = Math.round(performance.now() - startTime);
        
        // 네트워크 응답 로깅
        Debug.logResponse('POST', '/api/agent/start', response.status, data, responseTime);
        
        Debug.info(`AI 에이전트 크롤링 시작 API 응답 (${responseTime}ms): ${response.ok ? '성공' : '실패'}`);
        
        return {
            success: response.ok,
            status: response.status,
            message: data.message || '알 수 없는 응답',
            responseTime,
            ...data
        };
    } catch (error) {
        Debug.error('AI 에이전트 크롤링 시작 API 호출 오류:', error);
        console.error('상세 오류:', error);
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
        
        // 네트워크 요청 로깅
        Debug.logRequest('POST', '/api/agent/stop', null);
        
        // 요청 시작 시간 기록
        const startTime = performance.now();
        
        // API 호출
        const response = await fetch('/api/agent/stop', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        // 응답 처리
        const data = await response.json();
        
        // 응답 시간 계산
        const responseTime = Math.round(performance.now() - startTime);
        
        // 네트워크 응답 로깅
        Debug.logResponse('POST', '/api/agent/stop', response.status, data, responseTime);
        
        Debug.info(`AI 에이전트 크롤링 중지 API 응답 (${responseTime}ms): ${response.ok ? '성공' : '실패'}`);
        
        return {
            success: response.ok,
            status: response.status,
            message: data.message || '알 수 없는 응답',
            responseTime,
            ...data
        };
    } catch (error) {
        Debug.error('AI 에이전트 크롤링 중지 API 호출 오류:', error);
        console.error('상세 오류:', error);
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
        
        // 네트워크 요청 로깅
        Debug.logRequest('GET', '/api/agent/results', null);
        
        // 요청 시작 시간 기록
        const startTime = performance.now();
        
        // API 호출
        const response = await fetch('/api/agent/results', {
            method: 'GET'
        });
        
        // 응답 처리
        const data = await response.json();
        
        // 응답 시간 계산
        const responseTime = Math.round(performance.now() - startTime);
        
        // 네트워크 응답 로깅
        Debug.logResponse('GET', '/api/agent/results', response.status, data, responseTime);
        
        Debug.info(`AI 에이전트 크롤링 결과 API 응답 (${responseTime}ms): ${response.ok ? '성공' : '실패'}`);
        
        return {
            success: response.ok,
            status: response.status,
            message: data.message || '알 수 없는 응답',
            results: data.results || [],
            responseTime,
            ...data
        };
    } catch (error) {
        Debug.error('AI 에이전트 크롤링 결과 API 호출 오류:', error);
        console.error('상세 오류:', error);
        return {
            success: false,
            message: '네트워크 오류 또는 서버 응답 처리 실패',
            error: error.message,
            results: []
        };
    }
} 