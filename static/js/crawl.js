// crawl.js - 나라장터 크롤링 모듈
import { Debug } from './crawlutil/logger.js';
import { CrawlWebSocketManager, AgentWebSocketManager } from './websocket.js';
import DomUtils from './crawlutil/dom-helper.js';
import * as ApiService from './crawlutil/api-service.js';

// 애플리케이션 시작 로그
Debug.highlight('크롤링 애플리케이션 로드 시작');

document.addEventListener('DOMContentLoaded', () => {
    Debug.info("DOM 로드됨 - 초기화 시작");

    // WebSocket 연결
    let standardWebSocketManager = null;
    let agentWebSocketManager = null;
    
    // 초기화 함수 선언
    function initialize() {
        Debug.info('initialize 함수 실행 시작');
        try {
            // 필수 DOM 요소 참조 가져오기
            let missingElements = [];
            
            // 버튼 요소 확인
            const requiredButtons = {
                startBtn: document.getElementById('startBtn'),
                stopBtn: document.getElementById('stopBtn'),
                downloadBtn: document.getElementById('downloadBtn'),
                startAgentBtn: document.getElementById('startAgentBtn'),
                stopAgentBtn: document.getElementById('stopAgentBtn')
            };
            
            // 상태 및 결과 표시 요소 확인
            const requiredElements = {
                keywordInput: document.getElementById('keywordInput'),
                statusMessages: document.getElementById('statusMessages'),
                agentStatus: document.getElementById('agentStatus'),
                progressBar: document.getElementById('progressBar'),
                progressPercent: document.getElementById('progressPercent'),
                progressStatus: document.getElementById('progressStatus'),
                resultsTable: document.getElementById('resultsTable'),
                resultCount: document.getElementById('resultCount'),
                keywordList: document.getElementById('keywordList'),
                startDate: document.getElementById('startDate'),
                endDate: document.getElementById('endDate'),
                connectionStatus: document.getElementById('connectionStatus'),
                agentConnectionStatus: document.getElementById('agentConnectionStatus')
            };
            
            // 누락된 버튼 요소 확인
            for (const [name, element] of Object.entries(requiredButtons)) {
                if (!element) {
                    missingElements.push(name);
                    Debug.warn(`필수 버튼 요소 없음: ${name}`);
                }
            }
            
            // 누락된 일반 요소 확인
            for (const [name, element] of Object.entries(requiredElements)) {
                if (!element) {
                    missingElements.push(name);
                    Debug.warn(`필수 UI 요소 없음: ${name}`);
                }
            }
            
            // 누락된 요소가 있으면 경고 로그
            if (missingElements.length > 0) {
                Debug.error(`필수 DOM 요소를 찾을 수 없음: ${missingElements.join(', ')}`);
                Debug.warn('일부 기능이 작동하지 않을 수 있습니다');
            }
            
            // 날짜 입력 필드 설정
            setupDateInputs();
            
            // 이벤트 리스너 설정 - 각 버튼이 있는 경우에만 리스너 추가
            setupEventListeners(requiredButtons);
            
            // 초기 상태 조회
            loadInitialStatus();
            
            Debug.info('initialize 함수 실행 완료');
            
            // 모든 필수 요소가 존재하는 경우에만 true 반환
            return missingElements.length === 0;
        } catch (error) {
            Debug.error('initialize 함수 실행 중 오류 발생:', error);
            Debug.error('오류 스택:', error.stack);
            return false;
        }
    }
    
    // 초기 상태 로드
    async function loadInitialStatus() {
        try {
            Debug.info('초기 크롤링 상태 조회 중...');
            
            const statusMessages = document.getElementById('statusMessages');
            if (statusMessages) {
                DomUtils.appendMessage(statusMessages, '현재 크롤링 상태 확인 중...', 'info');
            }
            
            // 서버에서 크롤링 상태 조회
            const response = await ApiService.getCrawlingStatus();
            
            if (response && response.success) {
                Debug.info('초기 상태 조회 성공:', response);
                
                // 상태 메시지 표시
                if (statusMessages) {
                    if (response.data && response.data.is_running) {
                        DomUtils.appendMessage(statusMessages, `크롤링이 실행 중입니다. (${response.data.processed_keywords || 0}/${response.data.total_keywords || 0} 키워드 처리됨)`, 'info');
                    } else {
                        DomUtils.appendMessage(statusMessages, '크롤링이 실행 중이 아닙니다.', 'info');
                    }
                }
                
                // 결과가 있으면 테이블에 표시
                if (response.results && response.results.length > 0) {
                    Debug.info(`${response.results.length}개의 기존 결과 표시`);
                    updateResultsTable(response.results);
                    
                    // 결과 카운트 업데이트
                    const resultCount = document.getElementById('resultCount');
                    if (resultCount) {
                        resultCount.textContent = response.results.length;
                    }
                }
                
                // 상태 바 업데이트
                updateStatusBar(response.data);
            } else {
                Debug.warn('초기 상태 조회 실패:', response);
                if (statusMessages) {
                    DomUtils.appendMessage(statusMessages, '크롤링 상태 조회 실패. 서버 연결을 확인하세요.', 'warning');
                }
            }
        } catch (error) {
            Debug.error('초기 상태 조회 중 오류 발생:', error);
            const statusMessages = document.getElementById('statusMessages');
            if (statusMessages) {
                DomUtils.appendMessage(statusMessages, '서버 연결 오류. 서버가 실행 중인지 확인하세요.', 'error');
            }
        }
    }
    
    // 상태 바 업데이트
    function updateStatusBar(data) {
        try {
            if (!data) return;
            
            const progressBar = document.getElementById('progressBar');
            const progressPercent = document.getElementById('progressPercent');
            const progressStatus = document.getElementById('progressStatus');
            
            if (progressBar && progressPercent && progressStatus) {
                let percentValue = 0;
                
                if (data.is_running && data.total_keywords > 0) {
                    percentValue = Math.min(Math.round((data.processed_keywords / data.total_keywords) * 100), 100);
                } else if (data.completed_at) {
                    percentValue = 100;
                }
                
                progressBar.style.width = `${percentValue}%`;
                progressPercent.textContent = `${percentValue}%`;
                
                if (data.is_running) {
                    progressStatus.textContent = `크롤링 진행 중... (${data.processed_keywords || 0}/${data.total_keywords || 0})`;
                } else if (data.completed_at) {
                    progressStatus.textContent = '크롤링 완료';
                } else {
                    progressStatus.textContent = '준비 중...';
                }
            }
        } catch (error) {
            Debug.error('상태 바 업데이트 중 오류 발생:', error);
        }
    }
    
    // 날짜 입력 필드 설정
    function setupDateInputs() {
        try {
            Debug.info('날짜 입력 필드 설정 시작');
            
            const startDate = document.getElementById('startDate');
            const endDate = document.getElementById('endDate');
            
            if (!startDate || !endDate) {
                Debug.warn('날짜 입력 필드를 찾을 수 없습니다');
                return;
            }
            
            // 오늘 날짜 설정
            const today = new Date();
            const oneMonthAgo = new Date();
            oneMonthAgo.setMonth(today.getMonth() - 1);
            
            // 날짜 형식 변환 (YYYY-MM-DD)
            const formatDate = (date) => {
                const year = date.getFullYear();
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const day = String(date.getDate()).padStart(2, '0');
                return `${year}-${month}-${day}`;
            };
            
            // 초기 날짜 설정
            startDate.value = formatDate(oneMonthAgo);
            endDate.value = formatDate(today);
            
            Debug.info('날짜 입력 필드 설정 완료');
        } catch (error) {
            Debug.error('날짜 입력 필드 설정 중 오류 발생:', error);
        }
    }

    // 이벤트 리스너 설정
    function setupEventListeners(buttons) {
        Debug.info('이벤트 리스너 설정 시작');
        
        try {
            // API 검색 버튼
            const apiSearchBtn = document.getElementById('apiSearchBtn');
            if (apiSearchBtn) {
                apiSearchBtn.addEventListener('click', () => {
                    searchAPI();
                });
                Debug.info('API 검색 버튼 이벤트 리스너 설정 완료');
            }
            
            // 크롤링 시작 버튼
            if (buttons.startBtn) {
                buttons.startBtn.addEventListener('click', () => {
                    startCrawling();
                });
                Debug.info('크롤링 시작 버튼 이벤트 리스너 설정 완료');
            }
            
            // 크롤링 중지 버튼
            if (buttons.stopBtn) {
                buttons.stopBtn.addEventListener('click', () => {
                    stopCrawling();
                });
                Debug.info('크롤링 중지 버튼 이벤트 리스너 설정 완료');
            }
            
            // 다운로드 버튼
            if (buttons.downloadBtn) {
                buttons.downloadBtn.addEventListener('click', () => {
                    downloadResults();
                });
                Debug.info('다운로드 버튼 이벤트 리스너 설정 완료');
            }
            
            // AI 에이전트 시작 버튼
            if (buttons.startAgentBtn) {
                buttons.startAgentBtn.addEventListener('click', () => {
                    startAgentCrawling();
                });
                Debug.info('AI 에이전트 시작 버튼 이벤트 리스너 설정 완료');
            }
            
            // AI 에이전트 중지 버튼
            if (buttons.stopAgentBtn) {
                buttons.stopAgentBtn.addEventListener('click', () => {
                    stopAgentCrawling();
                });
                Debug.info('AI 에이전트 중지 버튼 이벤트 리스너 설정 완료');
            }
            
            Debug.info('모든 이벤트 리스너 설정 완료');
        } catch (error) {
            Debug.error('이벤트 리스너 설정 중 오류 발생:', error);
        }
    }

    // WebSocket 연결 함수
    function connectWebSocket() {
        try {
            Debug.info('표준 WebSocket 연결 시작');
            
            // DOM 요소 확인
            const connectionStatusElement = document.getElementById('connectionStatus');
            if (!connectionStatusElement) {
                Debug.warn('연결 상태 표시 요소를 찾을 수 없습니다');
            }
            
            // 디버깅 정보 - 현재 URL
            Debug.debug(`현재 URL: ${window.location.href}`);
            
            // CrawlWebSocketManager 인스턴스 생성
            standardWebSocketManager = new CrawlWebSocketManager({
                onMessage: updateStatus,
                statusElement: 'connectionStatus',
                onError: handleWebSocketError,
                onOpen: () => {
                    Debug.info('표준 WebSocket 연결 성공');
                    const connectionStatus = document.getElementById('connectionStatus');
                    if (connectionStatus) {
                        connectionStatus.textContent = '연결됨';
                        connectionStatus.className = 'badge bg-success';
                    }
                },
                onClose: () => {
                    Debug.info('표준 WebSocket 연결 종료');
                    const connectionStatus = document.getElementById('connectionStatus');
                    if (connectionStatus) {
                        connectionStatus.textContent = '연결 종료됨';
                        connectionStatus.className = 'badge bg-secondary';
                    }
                }
            });
            
            // WebSocket 연결 시작
            standardWebSocketManager.connect();
            Debug.info('표준 WebSocket 연결 요청 완료');
            
        } catch (error) {
            Debug.error('표준 WebSocket 연결 중 오류 발생:', error);
            console.error('WebSocket 연결 상세 오류:', error);
        }
    }
    
    // AI 에이전트 WebSocket 연결 함수
    function connectAgentWebSocket() {
        try {
            Debug.info('에이전트 WebSocket 연결 시작');
            
            // DOM 요소 확인
            const agentConnectionStatusElement = document.getElementById('agentConnectionStatus');
            if (!agentConnectionStatusElement) {
                Debug.warn('에이전트 연결 상태 표시 요소를 찾을 수 없습니다');
            }
            
            // 디버깅 정보 - 현재 URL
            Debug.debug(`현재 URL: ${window.location.href}`);
            
            // AgentWebSocketManager 인스턴스 생성
            agentWebSocketManager = new AgentWebSocketManager({
                onMessage: updateAgentStatus,
                statusElement: 'agentConnectionStatus',
                onError: handleAgentWebSocketError,
                onOpen: () => {
                    Debug.info('에이전트 WebSocket 연결 성공');
                    const agentConnectionStatus = document.getElementById('agentConnectionStatus');
                    if (agentConnectionStatus) {
                        agentConnectionStatus.textContent = '연결됨';
                        agentConnectionStatus.className = 'badge bg-success';
                    }
                },
                onClose: () => {
                    Debug.info('에이전트 WebSocket 연결 종료');
                    const agentConnectionStatus = document.getElementById('agentConnectionStatus');
                    if (agentConnectionStatus) {
                        agentConnectionStatus.textContent = '연결 종료됨';
                        agentConnectionStatus.className = 'badge bg-secondary';
                    }
                }
            });
            
            // WebSocket 연결 시작
            agentWebSocketManager.connect();
            Debug.info('에이전트 WebSocket 연결 요청 완료');
            
        } catch (error) {
            Debug.error('에이전트 WebSocket 연결 중 오류 발생:', error);
            console.error('에이전트 WebSocket 연결 상세 오류:', error);
        }
    }
    
    // WebSocket 오류 처리
    function handleWebSocketError(error) {
        Debug.error('WebSocket 오류 발생:', error);
        console.error('WebSocket 오류 상세:', error);
        
        const statusMessages = document.getElementById('statusMessages');
        if (statusMessages) {
            DomUtils.appendMessage(statusMessages, '서버 연결 오류가 발생했습니다. 다시 시도하세요.', 'error');
        }
        
        // 오류 발생 시 5초 후 재연결 시도
        setTimeout(() => {
            Debug.info('WebSocket 재연결 시도 (오류 후)');
            connectWebSocket();
        }, 5000);
    }
    
    // 에이전트 WebSocket 오류 처리
    function handleAgentWebSocketError(error) {
        Debug.error('에이전트 WebSocket 오류 발생:', error);
        console.error('에이전트 WebSocket 오류 상세:', error);
        
        const agentStatus = document.getElementById('agentStatus');
        if (agentStatus) {
            DomUtils.appendMessage(agentStatus, 'AI 에이전트 연결 오류가 발생했습니다. 다시 시도하세요.', 'error');
        }
        
        // 오류 발생 시 5초 후 재연결 시도
        setTimeout(() => {
            Debug.info('에이전트 WebSocket 재연결 시도 (오류 후)');
            connectAgentWebSocket();
        }, 5000);
    }
    
    // 크롤링 상태 업데이트
    function updateStatus(data) {
        try {
            Debug.info('상태 업데이트 수신:', data);
            
            // DOM 요소 가져오기
            const statusMessages = document.getElementById('statusMessages');
            const progressBar = document.getElementById('progressBar');
            const progressPercent = document.getElementById('progressPercent');
            const progressStatus = document.getElementById('progressStatus');
            const resultsTable = document.getElementById('resultsTable');
            const resultCount = document.getElementById('resultCount');
            
            // 메시지 처리
            if (data.message && statusMessages) {
                DomUtils.appendMessage(statusMessages, data.message, data.type || 'info');
            }
            
            // 진행 상태 처리
            if (data.progress !== undefined && progressBar && progressPercent) {
                const percentValue = Math.min(Math.round(data.progress * 100), 100);
                progressBar.style.width = `${percentValue}%`;
                progressPercent.textContent = `${percentValue}%`;
                
                if (progressStatus) {
                    progressStatus.textContent = data.status || '';
                }
            }
            
            // 결과 처리
            if (data.results && resultsTable) {
                // 결과 테이블 업데이트
                updateResultsTable(data.results);
                
                // 결과 개수 업데이트
                if (resultCount) {
                    resultCount.textContent = data.results.length;
                }
            }
            
        } catch (error) {
            Debug.error('상태 업데이트 처리 중 오류 발생:', error);
        }
    }
    
    // 에이전트 상태 업데이트
    function updateAgentStatus(data) {
        try {
            Debug.info('에이전트 상태 업데이트 수신:', data);
            
            // DOM 요소 확인
            const agentStatus = document.getElementById('agentStatus');
            if (!agentStatus) {
                Debug.warn('에이전트 상태 표시 요소를 찾을 수 없습니다');
                return;
            }
            
            // 에이전트 메시지 처리
            if (data.message) {
                DomUtils.appendMessage(agentStatus, data.message, data.type || 'info');
            }
            
        } catch (error) {
            Debug.error('에이전트 상태 업데이트 처리 중 오류 발생:', error);
        }
    }
    
    // 결과 테이블 업데이트
    function updateResultsTable(results) {
        try {
            Debug.info(`결과 테이블 업데이트 (${results.length}개 항목)`);
            
            const resultsTable = document.getElementById('resultsTable');
            if (!resultsTable) {
                Debug.warn('결과 테이블 요소를 찾을 수 없습니다');
                return;
            }
            
            // 테이블 본문 참조
            const tbody = resultsTable.querySelector('tbody');
            if (!tbody) {
                Debug.warn('결과 테이블 본문을 찾을 수 없습니다');
                return;
            }
            
            // 테이블 내용 초기화
            tbody.innerHTML = '';
            
            // 결과 없음 처리
            if (results.length === 0) {
                const noDataRow = document.createElement('tr');
                const noDataCell = document.createElement('td');
                noDataCell.colSpan = 6;
                noDataCell.textContent = '검색 결과가 없습니다.';
                noDataCell.className = 'text-center';
                noDataRow.appendChild(noDataCell);
                tbody.appendChild(noDataRow);
                return;
            }
            
            Debug.debug('결과 첫번째 항목:', results[0]);
            
            // 각 결과 행 생성
            results.forEach((item, index) => {
                const row = document.createElement('tr');
                
                // 번호 셀
                const indexCell = document.createElement('td');
                indexCell.textContent = index + 1;
                row.appendChild(indexCell);
                
                // 입찰번호 셀
                const bidIdCell = document.createElement('td');
                bidIdCell.textContent = item.bid_number || item.bid_info?.number || '-';
                row.appendChild(bidIdCell);
                
                // 공고명 셀
                const titleCell = document.createElement('td');
                const titleLink = document.createElement('a');
                titleLink.href = item.url || '#';
                titleLink.textContent = item.bid_name || item.title || item.bid_info?.title || '제목 없음';
                titleLink.target = '_blank';
                titleCell.appendChild(titleLink);
                row.appendChild(titleCell);
                
                // 발주처 셀
                const organizationCell = document.createElement('td');
                organizationCell.textContent = item.org_name || item.organization || item.bid_info?.agency || '-';
                row.appendChild(organizationCell);
                
                // 입찰유형 셀
                const bidTypeCell = document.createElement('td');
                bidTypeCell.textContent = item.bid_type || '-';
                row.appendChild(bidTypeCell);
                
                // 공고일자 셀
                const dateCell = document.createElement('td');
                dateCell.textContent = item.date || item.deadline || item.bid_info?.date || '-';
                row.appendChild(dateCell);
                
                // 행 추가
                tbody.appendChild(row);
            });
            
            Debug.info('결과 테이블 업데이트 완료');
            
        } catch (error) {
            Debug.error('결과 테이블 업데이트 중 오류 발생:', error);
        }
    }
    
    // 크롤링 시작
    async function startCrawling() {
        try {
            Debug.info('크롤링 시작 요청');
            Debug.debug('크롤링 시작 함수 진입');
            
            // DOM 요소 참조 가져오기
            const keywordInput = document.getElementById('keywordInput');
            const startDate = document.getElementById('startDate');
            const endDate = document.getElementById('endDate');
            const statusMessages = document.getElementById('statusMessages');
            const keywordList = document.getElementById('keywordList');
            
            Debug.debug('DOM 요소 참조 확인:', { 
                keywordInput: !!keywordInput, 
                startDate: !!startDate, 
                endDate: !!endDate, 
                statusMessages: !!statusMessages, 
                keywordList: !!keywordList 
            });
            
            // 입력 확인
            if (!keywordInput || !keywordInput.value.trim()) {
                Debug.warn('키워드가 입력되지 않았습니다');
                if (statusMessages) {
                    DomUtils.appendMessage(statusMessages, '키워드를 입력해주세요.', 'warning');
                }
                return;
            }
            
            // 키워드 처리 (쉼표로 구분)
            const keywordsText = keywordInput.value.trim();
            const keywords = keywordsText.split(',').map(k => k.trim()).filter(k => k);
            
            Debug.debug('입력된 키워드:', keywords);
            
            if (keywords.length === 0) {
                Debug.warn('유효한 키워드가 없습니다');
                if (statusMessages) {
                    DomUtils.appendMessage(statusMessages, '유효한 키워드를 입력해주세요.', 'warning');
                }
                return;
            }
            
            // 키워드 목록 표시
            if (keywordList) {
                keywordList.innerHTML = '';
                keywords.forEach(keyword => {
                    const keywordItem = document.createElement('span');
                    keywordItem.className = 'badge bg-primary me-1 mb-1';
                    keywordItem.textContent = keyword;
                    keywordList.appendChild(keywordItem);
                });
                Debug.debug('키워드 목록 UI 업데이트 완료');
            }
            
            // 시작 및 종료 날짜 가져오기
            const startDateValue = startDate ? startDate.value : null;
            const endDateValue = endDate ? endDate.value : null;
            
            Debug.debug('날짜 범위:', { startDate: startDateValue, endDate: endDateValue });
            
            // 상태 메시지 표시
            if (statusMessages) {
                statusMessages.innerHTML = '';
                DomUtils.appendMessage(
                    statusMessages, 
                    `키워드 [${keywords.join(', ')}]에 대한 크롤링을 시작합니다.`, 
                    'info'
                );
                Debug.debug('상태 메시지 UI 업데이트 완료');
            }
            
            // 버튼 상태 업데이트
            const startBtn = document.getElementById('startBtn');
            const stopBtn = document.getElementById('stopBtn');
            
            if (startBtn) startBtn.disabled = true;
            if (stopBtn) stopBtn.disabled = false;
            
            // API 요청
            Debug.debug('ApiService.startCrawling 호출 전');
            const response = await ApiService.startCrawling(keywords, startDateValue, endDateValue);
            Debug.debug('ApiService.startCrawling 호출 완료:', response);
            
            // 응답 확인
            if (response && response.success) {
                Debug.info('크롤링 시작 요청 성공:', response);
                if (statusMessages) {
                    DomUtils.appendMessage(statusMessages, '크롤링이 성공적으로 시작되었습니다.', 'success');
                }
            } else {
                Debug.warn('크롤링 시작 요청 실패:', response);
                if (statusMessages) {
                    DomUtils.appendMessage(
                        statusMessages, 
                        `크롤링 시작 실패: ${response.message || '알 수 없는 오류'}`, 
                        'error'
                    );
                }
                
                // 버튼 상태 원복
                if (startBtn) startBtn.disabled = false;
                if (stopBtn) stopBtn.disabled = true;
            }
        } catch (error) {
            Debug.error('크롤링 시작 중 오류 발생:', error);
            console.error('크롤링 시작 상세 오류:', error);
            
            const statusMessages = document.getElementById('statusMessages');
            if (statusMessages) {
                DomUtils.appendMessage(statusMessages, '크롤링 요청 중 오류가 발생했습니다.', 'error');
            }
            
            // 버튼 상태 원복
            const startBtn = document.getElementById('startBtn');
            const stopBtn = document.getElementById('stopBtn');
            
            if (startBtn) startBtn.disabled = false;
            if (stopBtn) stopBtn.disabled = true;
        }
    }
    
    // 크롤링 중지
    async function stopCrawling() {
        try {
            Debug.info('크롤링 중지 요청');
            
            const statusMessages = document.getElementById('statusMessages');
            
            // API 요청
            const response = await ApiService.stopCrawling();
            
            // 응답 확인
            if (response && response.success) {
                Debug.info('크롤링 중지 요청 성공:', response);
                if (statusMessages) {
                    DomUtils.appendMessage(statusMessages, '크롤링이 중지되었습니다.', 'info');
                }
            } else {
                Debug.warn('크롤링 중지 요청 실패:', response);
                if (statusMessages) {
                    DomUtils.appendMessage(
                        statusMessages, 
                        `크롤링 중지 실패: ${response.message || '알 수 없는 오류'}`, 
                        'error'
                    );
                }
            }
        } catch (error) {
            Debug.error('크롤링 중지 중 오류 발생:', error);
            const statusMessages = document.getElementById('statusMessages');
            if (statusMessages) {
                DomUtils.appendMessage(statusMessages, '크롤링 중지 요청 중 오류가 발생했습니다.', 'error');
            }
        }
    }
    
    // 결과 다운로드
    async function downloadResults() {
        try {
            Debug.info('결과 다운로드 요청');
            
            const statusMessages = document.getElementById('statusMessages');
            
            // API 요청
            const response = await ApiService.downloadResults();
            
            // 응답 확인
            if (response && response.success) {
                Debug.info('결과 다운로드 성공:', response);
                
                // 다운로드 URL이 있는 경우
                if (response.downloadUrl) {
                    // 다운로드 링크 생성 및 클릭
                    const downloadLink = document.createElement('a');
                    downloadLink.href = response.downloadUrl;
                    downloadLink.download = response.filename || 'crawling_results.xlsx';
                    document.body.appendChild(downloadLink);
                    downloadLink.click();
                    document.body.removeChild(downloadLink);
                    
                    if (statusMessages) {
                        DomUtils.appendMessage(statusMessages, '결과 다운로드가 시작되었습니다.', 'success');
                    }
                } else {
                    if (statusMessages) {
                        DomUtils.appendMessage(statusMessages, '다운로드 URL이 제공되지 않았습니다.', 'warning');
                    }
                }
            } else {
                Debug.warn('결과 다운로드 요청 실패:', response);
                if (statusMessages) {
                    DomUtils.appendMessage(
                        statusMessages, 
                        `결과 다운로드 실패: ${response.message || '알 수 없는 오류'}`, 
                        'error'
                    );
                }
            }
        } catch (error) {
            Debug.error('결과 다운로드 중 오류 발생:', error);
            const statusMessages = document.getElementById('statusMessages');
            if (statusMessages) {
                DomUtils.appendMessage(statusMessages, '결과 다운로드 요청 중 오류가 발생했습니다.', 'error');
            }
        }
    }
    
    // AI 에이전트 크롤링 시작
    async function startAgentCrawling() {
        try {
            Debug.info('AI 에이전트 크롤링 시작 요청');
            
            const agentStatus = document.getElementById('agentStatus');
            
            // 상태 메시지 표시
            if (agentStatus) {
                agentStatus.innerHTML = '';
                DomUtils.appendMessage(agentStatus, 'AI 에이전트 크롤링을 시작합니다...', 'info');
            }
            
            // API 요청
            const response = await ApiService.startAgentCrawling();
            
            // 응답 확인
            if (response && response.success) {
                Debug.info('AI 에이전트 크롤링 시작 요청 성공:', response);
                if (agentStatus) {
                    DomUtils.appendMessage(agentStatus, 'AI 에이전트 크롤링이 성공적으로 시작되었습니다.', 'success');
                }
            } else {
                Debug.warn('AI 에이전트 크롤링 시작 요청 실패:', response);
                if (agentStatus) {
                    DomUtils.appendMessage(
                        agentStatus, 
                        `AI 에이전트 크롤링 시작 실패: ${response.message || '알 수 없는 오류'}`, 
                        'error'
                    );
                }
            }
        } catch (error) {
            Debug.error('AI 에이전트 크롤링 시작 중 오류 발생:', error);
            const agentStatus = document.getElementById('agentStatus');
            if (agentStatus) {
                DomUtils.appendMessage(agentStatus, 'AI 에이전트 크롤링 요청 중 오류가 발생했습니다.', 'error');
            }
        }
    }
    
    // AI 에이전트 크롤링 중지
    async function stopAgentCrawling() {
        try {
            Debug.info('AI 에이전트 크롤링 중지 요청');
            
            const agentStatus = document.getElementById('agentStatus');
            
            // API 요청
            const response = await ApiService.stopAgentCrawling();
            
            // 응답 확인
            if (response && response.success) {
                Debug.info('AI 에이전트 크롤링 중지 요청 성공:', response);
                if (agentStatus) {
                    DomUtils.appendMessage(agentStatus, 'AI 에이전트 크롤링이 중지되었습니다.', 'info');
                }
            } else {
                Debug.warn('AI 에이전트 크롤링 중지 요청 실패:', response);
                if (agentStatus) {
                    DomUtils.appendMessage(
                        agentStatus, 
                        `AI 에이전트 크롤링 중지 실패: ${response.message || '알 수 없는 오류'}`, 
                        'error'
                    );
                }
            }
        } catch (error) {
            Debug.error('AI 에이전트 크롤링 중지 중 오류 발생:', error);
            const agentStatus = document.getElementById('agentStatus');
            if (agentStatus) {
                DomUtils.appendMessage(agentStatus, 'AI 에이전트 크롤링 중지 요청 중 오류가 발생했습니다.', 'error');
            }
        }
    }
    
    // API 검색 수행
    async function searchAPI() {
        try {
            Debug.info('나라장터 API 검색 시작');
            
            // DOM 요소 참조 가져오기
            const statusMessages = document.getElementById('statusMessages');
            
            // 상태 메시지 표시
            if (statusMessages) {
                statusMessages.innerHTML = '';
                DomUtils.appendMessage(statusMessages, "나라장터 API 기능이 비활성화되었습니다. (SERVICE ERROR)", 'error');
                DomUtils.appendMessage(statusMessages, "해당 기능은 현재 지원되지 않습니다. 다른 검색 방법을 이용해주세요.", 'warning');
            }
            
            // 결과 테이블 초기화
            updateResultsTable([]);
            
            // 결과 개수 업데이트
            const resultCountElement = document.getElementById('resultCount');
            if (resultCountElement) {
                resultCountElement.textContent = 0;
            }
            
            return false;
        } catch (error) {
            Debug.error('API 검색 중 오류:', error);
            
            // 상태 메시지 표시
            const statusMessages = document.getElementById('statusMessages');
            if (statusMessages) {
                DomUtils.appendMessage(statusMessages, `오류가 발생했습니다: ${error.message}`, 'error');
            }
            
            return false;
        }
    }
    
    // 초기화 실행
    const initializationComplete = initialize();
    Debug.info(`초기화 완료 상태: ${initializationComplete ? '성공' : '일부 실패'}`);
    
    // 초기화 성공 시 WebSocket 연결 시작
    if (initializationComplete) {
        setTimeout(() => {
            connectWebSocket();
            connectAgentWebSocket();
            Debug.info('WebSocket 연결 타이머 시작됨');
        }, 500); // 약간의 지연을 두어 DOM이 완전히 로드되도록 함
    } else {
        Debug.warn('초기화가 완전히 성공적이지 않아 일부 기능이 제한됩니다');
    }
});

export {
    // 필요한 경우 여기에 외부로 노출할 함수 추가
};