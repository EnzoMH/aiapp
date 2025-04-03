// crawl.js - 나라장터 크롤링 모듈
import { Debug } from './crawlutil/logger.js';
// 중복 export 오류를 해결하기 위해 이름 변경
import { CrawlWebSocketManager as BaseCrawlWebSocketManager, AgentWebSocketManager as BaseAgentWebSocketManager } from './websocket.js';
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
            standardWebSocketManager = new BaseCrawlWebSocketManager({
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
            agentWebSocketManager = new BaseAgentWebSocketManager({
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
                titleLink.href = "#";
                titleLink.textContent = item.bid_name || item.title || item.bid_info?.title || '제목 없음';
                titleLink.className = "bid-title-link";
                titleLink.dataset.bidId = item.bid_number || item.bid_id || '';
                titleLink.dataset.url = item.url || '#';
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
            
            // 제목 링크에 이벤트 리스너 추가
            setupBidTitleLinks();
            
            Debug.info('결과 테이블 업데이트 완료');
            
        } catch (error) {
            Debug.error('결과 테이블 업데이트 중 오류 발생:', error);
        }
    }
    
    // 제목 링크 이벤트 리스너 설정
    function setupBidTitleLinks() {
        try {
            const titleLinks = document.querySelectorAll('.bid-title-link');
            Debug.info(`제목 링크 이벤트 리스너 설정 (${titleLinks.length}개 링크)`);
            
            titleLinks.forEach(link => {
                link.addEventListener('click', async (event) => {
                    event.preventDefault();
                    
                    const bidId = link.dataset.bidId;
                    const url = link.dataset.url;
                    
                    Debug.info(`입찰 상세 정보 요청: ${bidId}`);
                    
                    // 상세 정보 모달 표시
                    showDetailModal(bidId, url);
                });
            });
            
        } catch (error) {
            Debug.error('제목 링크 이벤트 리스너 설정 중 오류 발생:', error);
        }
    }
    
    // 상세 정보 모달 표시
    async function showDetailModal(bidId, url) {
        try {
            Debug.info(`상세 정보 모달 표시: ${bidId}`);
            
            // 모달 요소 생성 또는 가져오기
            let detailModal = document.getElementById('detailModal');
            
            if (!detailModal) {
                // 모달 요소 생성
                detailModal = document.createElement('div');
                detailModal.id = 'detailModal';
                detailModal.className = 'modal fade';
                detailModal.tabIndex = -1;
                detailModal.setAttribute('aria-labelledby', 'detailModalLabel');
                detailModal.setAttribute('aria-hidden', 'true');
                
                // 모달 내용 생성
                detailModal.innerHTML = `
                    <div class="modal-dialog modal-xl modal-dialog-scrollable">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="detailModalLabel">입찰 상세 정보</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <div class="modal-body" id="detailModalContent">
                                <div class="text-center">
                                    <div class="spinner-border text-primary" role="status">
                                        <span class="visually-hidden">로딩 중...</span>
                                    </div>
                                    <p class="mt-2">입찰 상세 정보를 불러오는 중입니다...</p>
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">닫기</button>
                            </div>
                        </div>
                    </div>
                `;
                
                // 모달 요소 추가
                document.body.appendChild(detailModal);
            }
            
            // 모달 콘텐츠 요소
            const detailModalContent = document.getElementById('detailModalContent');
            
            if (detailModalContent) {
                // 로딩 표시
                detailModalContent.innerHTML = `
                    <div class="text-center">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">로딩 중...</span>
                        </div>
                        <p class="mt-2">입찰 상세 정보를 불러오는 중입니다...</p>
                    </div>
                `;
            }
            
            // 모달 표시
            const bootstrapModal = new bootstrap.Modal(detailModal);
            bootstrapModal.show();
            
            // 상세 정보 요청
            try {
                const response = await fetchBidDetail(bidId, url);
                
                if (response.success && response.detail) {
                    // 모달 콘텐츠 업데이트
                    updateDetailModalContent(detailModalContent, response.detail);
                } else {
                    // 오류 표시
                    if (detailModalContent) {
                        detailModalContent.innerHTML = `
                            <div class="alert alert-danger">
                                <h5 class="alert-heading">상세 정보 로드 실패</h5>
                                <p>${response.message || '상세 정보를 불러오는 데 실패했습니다.'}</p>
                            </div>
                        `;
                    }
                }
            } catch (error) {
                Debug.error('상세 정보 요청 중 오류 발생:', error);
                
                // 오류 표시
                if (detailModalContent) {
                    detailModalContent.innerHTML = `
                        <div class="alert alert-danger">
                            <h5 class="alert-heading">오류 발생</h5>
                            <p>${error.message || '상세 정보를 불러오는 중 오류가 발생했습니다.'}</p>
                        </div>
                    `;
                }
            }
            
        } catch (error) {
            Debug.error('상세 정보 모달 표시 중 오류 발생:', error);
        }
    }
    
    // 입찰 상세 정보 가져오기
    async function fetchBidDetail(bidNumber, url) {
        try {
            Debug.info(`입찰 상세 정보 요청: ${bidNumber}, URL: ${url}`);
            
            // API 요청
            const response = await fetch('/api/crawl/detail', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    bid_number: bidNumber,
                    url: url !== '#' ? url : null
                })
            });
            
            // 응답 확인
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`API 요청 실패: ${response.status} ${response.statusText} - ${errorText}`);
            }
            
            const result = await response.json();
            
            return result;
            
        } catch (error) {
            Debug.error('입찰 상세 정보 요청 중 오류 발생:', error);
            return {
                success: false,
                message: `오류 발생: ${error.message}`
            };
        }
    }
    
    // 상세 정보 모달 내용 업데이트
    function updateDetailModalContent(contentElement, detail) {
        // 탭 구조 생성
        let tabsHtml = `
            <nav>
                <div class="nav nav-tabs" id="detail-tab" role="tablist">
                    <button class="nav-link active" id="general-tab" data-bs-toggle="tab" data-bs-target="#general" type="button" role="tab" aria-controls="general" aria-selected="true">공고 일반</button>
                    <button class="nav-link" id="qualification-tab" data-bs-toggle="tab" data-bs-target="#qualification" type="button" role="tab" aria-controls="qualification" aria-selected="false">입찰자격</button>
                    <button class="nav-link" id="restriction-tab" data-bs-toggle="tab" data-bs-target="#restriction" type="button" role="tab" aria-controls="restriction" aria-selected="false">투찰제한</button>
                    <button class="nav-link" id="progress-tab" data-bs-toggle="tab" data-bs-target="#progress" type="button" role="tab" aria-controls="progress" aria-selected="false">입찰진행정보</button>
                    <button class="nav-link" id="price-tab" data-bs-toggle="tab" data-bs-target="#price" type="button" role="tab" aria-controls="price" aria-selected="false">가격 부문</button>
                    <button class="nav-link" id="contact-tab" data-bs-toggle="tab" data-bs-target="#contact" type="button" role="tab" aria-controls="contact" aria-selected="false">담당자 정보</button>
                    <button class="nav-link" id="attachments-tab" data-bs-toggle="tab" data-bs-target="#attachments" type="button" role="tab" aria-controls="attachments" aria-selected="false">첨부파일</button>
                    <button class="nav-link" id="ai-insight-tab" data-bs-toggle="tab" data-bs-target="#ai-insight" type="button" role="tab" aria-controls="ai-insight" aria-selected="false">AI 영업분석</button>
                </div>
            </nav>
        `;
        
        // 탭 콘텐츠 생성
        let tabContentHtml = `<div class="tab-content p-3" id="detail-tabContent">`;
        
        // 공고 일반 탭
        tabContentHtml += `
            <div class="tab-pane fade show active" id="general" role="tabpanel" aria-labelledby="general-tab">
                ${generateGeneralInfoHtml(detail)}
            </div>
        `;
        
        // 입찰자격 탭
        tabContentHtml += `
            <div class="tab-pane fade" id="qualification" role="tabpanel" aria-labelledby="qualification-tab">
                ${generateQualificationHtml(detail)}
            </div>
        `;
        
        // 투찰제한 탭
        tabContentHtml += `
            <div class="tab-pane fade" id="restriction" role="tabpanel" aria-labelledby="restriction-tab">
                ${generateRestrictionHtml(detail)}
            </div>
        `;
        
        // 입찰진행정보 탭
        tabContentHtml += `
            <div class="tab-pane fade" id="progress" role="tabpanel" aria-labelledby="progress-tab">
                ${generateProgressInfoHtml(detail)}
            </div>
        `;
        
        // 가격 부문 탭
        tabContentHtml += `
            <div class="tab-pane fade" id="price" role="tabpanel" aria-labelledby="price-tab">
                ${generatePriceInfoHtml(detail)}
            </div>
        `;
        
        // 담당자 정보 탭
        tabContentHtml += `
            <div class="tab-pane fade" id="contact" role="tabpanel" aria-labelledby="contact-tab">
                ${generateContactInfoHtml(detail)}
            </div>
        `;
        
        // 첨부파일 탭
        tabContentHtml += `
            <div class="tab-pane fade" id="attachments" role="tabpanel" aria-labelledby="attachments-tab">
                ${generateAttachmentsHtml(detail)}
            </div>
        `;
        
        // AI 영업분석 탭
        tabContentHtml += `
            <div class="tab-pane fade" id="ai-insight" role="tabpanel" aria-labelledby="ai-insight-tab">
                <div id="sales-insight-content">
                    ${generateSalesInsightLoadingHtml()}
                </div>
            </div>
        `;
        
        tabContentHtml += `</div>`;
        
        // 모달 내용 업데이트
        contentElement.innerHTML = tabsHtml + tabContentHtml;
        
        // AI 영업분석 탭 이벤트 리스너 추가
        const aiInsightTab = contentElement.querySelector('#ai-insight-tab');
        if (aiInsightTab) {
            aiInsightTab.addEventListener('click', async () => {
                const salesInsightContent = contentElement.querySelector('#sales-insight-content');
                if (salesInsightContent) {
                    // 영업 인사이트 요청
                    requestSalesInsight(salesInsightContent, detail);
                }
            });
        }
    }
    
    // 영업 인사이트 로딩 HTML 생성
    function generateSalesInsightLoadingHtml() {
        return `
            <div class="card">
                <div class="card-header bg-dark text-white">
                    <h5 class="mb-0">AI 영업 인사이트 분석</h5>
                </div>
                <div class="card-body text-center">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">분석 중...</span>
                    </div>
                    <p class="mt-2">입찰 정보를 분석 중입니다. 잠시만 기다려주세요...</p>
                </div>
            </div>
        `;
    }
    
    // 영업 인사이트 요청
    async function requestSalesInsight(contentElement, detail) {
        try {
            Debug.info('영업 인사이트 분석 요청:', detail.bid_number);
            
            // 사용자 검색 키워드 가져오기
            const keywordInput = document.getElementById('keywordInput');
            let userKeywords = [];
            
            if (keywordInput && keywordInput.value.trim()) {
                userKeywords = keywordInput.value.trim().split(',').map(k => k.trim()).filter(k => k);
                Debug.info('사용자 검색 키워드:', userKeywords);
            }
            
            // 분석에 필요한 데이터 추출
            const analysisData = {
                bid_number: detail.bid_number,
                title: detail.title,
                general_info: detail.general_info || {},
                qualification: detail.qualification || {},
                restriction: detail.restriction || {},
                price_info: detail.price_info || {},
                progress_info: detail.progress_info || {},
                search_keywords: userKeywords  // 사용자 검색 키워드 추가
            };
            
            // API 요청
            const response = await fetch('/api/analysis/sales-insight', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(analysisData)
            });
            
            // 응답 확인
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`API 요청 실패: ${response.status} ${response.statusText} - ${errorText}`);
            }
            
            const result = await response.json();
            
            if (result.success && result.data) {
                // 분석 결과 표시
                updateSalesInsightContent(contentElement, result.data);
            } else {
                throw new Error(result.message || '분석 결과가 없습니다');
            }
            
        } catch (error) {
            Debug.error('영업 인사이트 분석 중 오류:', error);
            
            // 오류 표시
            contentElement.innerHTML = `
                <div class="card">
                    <div class="card-header bg-dark text-white">
                        <h5 class="mb-0">AI 영업 인사이트 분석</h5>
                    </div>
                    <div class="card-body">
                        <div class="alert alert-danger mb-0">
                            <h5 class="alert-heading">분석 중 오류가 발생했습니다</h5>
                            <p>${error.message || '서버 연결에 실패했습니다. 다시 시도해주세요.'}</p>
                        </div>
                        <div class="text-center mt-3">
                            <button class="btn btn-primary retry-analysis-btn">다시 시도</button>
                        </div>
                    </div>
                </div>
            `;
            
            // 재시도 버튼 이벤트 리스너
            const retryBtn = contentElement.querySelector('.retry-analysis-btn');
            if (retryBtn) {
                retryBtn.addEventListener('click', () => {
                    contentElement.innerHTML = generateSalesInsightLoadingHtml();
                    requestSalesInsight(contentElement, detail);
                });
            }
        }
    }
    
    // 영업 인사이트 내용 업데이트
    function updateSalesInsightContent(contentElement, insightData) {
        try {
            // 업종 적합성 표시
            const getCompatibilityBadge = (score) => {
                if (score >= 80) return '<span class="badge bg-success">매우 높음</span>';
                if (score >= 60) return '<span class="badge bg-primary">높음</span>';
                if (score >= 40) return '<span class="badge bg-info">보통</span>';
                if (score >= 20) return '<span class="badge bg-warning">낮음</span>';
                return '<span class="badge bg-danger">매우 낮음</span>';
            };
            
            // 핵심 키워드 표시
            const generateKeywordsHtml = (keywords) => {
                if (!keywords || keywords.length === 0) return '<p>분석된 키워드가 없습니다.</p>';
                
                return `
                    <div class="d-flex flex-wrap gap-1 mb-3">
                        ${keywords.map(keyword => `<span class="badge bg-primary">${keyword}</span>`).join('')}
                    </div>
                `;
            };
            
            // 기회/위험 요소 표시
            const generatePointsHtml = (points, type) => {
                if (!points || points.length === 0) return '<p>분석된 내용이 없습니다.</p>';
                
                const bgClass = type === 'opportunity' ? 'bg-success' : 'bg-danger';
                const icon = type === 'opportunity' ? 'bi-check-circle-fill' : 'bi-exclamation-triangle-fill';
                
                return `
                    <ul class="list-group mb-3">
                        ${points.map(point => `
                            <li class="list-group-item d-flex">
                                <i class="bi ${icon} me-2 ${type === 'opportunity' ? 'text-success' : 'text-danger'}"></i>
                                <span>${point}</span>
                            </li>
                        `).join('')}
                    </ul>
                `;
            };
            
            // 영업 전략 표시
            const generateStrategyHtml = (strategy) => {
                if (!strategy || !strategy.headline) return '<p>분석된 전략이 없습니다.</p>';
                
                return `
                    <div class="card bg-light mb-3">
                        <div class="card-body">
                            <h5 class="card-title">${strategy.headline}</h5>
                            <p class="card-text">${strategy.content}</p>
                        </div>
                    </div>
                `;
            };
            
            // 전체 인사이트 HTML 생성
            const insightHtml = `
                <div class="card">
                    <div class="card-header bg-dark text-white d-flex justify-content-between align-items-center">
                        <h5 class="mb-0">AI 영업 인사이트 분석</h5>
                        <span class="badge bg-light text-dark">분석 완료: ${new Date().toLocaleString()}</span>
                    </div>
                    <div class="card-body">
                        <div class="row mb-4">
                            <div class="col-md-6">
                                <h5>업종 적합성</h5>
                                <div class="d-flex align-items-center mb-3">
                                    <div class="progress flex-grow-1 me-2" style="height: 25px;">
                                        <div class="progress-bar bg-success" role="progressbar" style="width: ${insightData.compatibility_score}%"></div>
                                    </div>
                                    <div>${getCompatibilityBadge(insightData.compatibility_score)}</div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <h5>핵심 키워드</h5>
                                ${generateKeywordsHtml(insightData.keywords)}
                            </div>
                        </div>
                        
                        <div class="row mb-4">
                            <div class="col-md-6">
                                <h5 class="text-success"><i class="bi bi-lightbulb-fill me-2"></i>기회 요소</h5>
                                ${generatePointsHtml(insightData.opportunity_points, 'opportunity')}
                            </div>
                            <div class="col-md-6">
                                <h5 class="text-danger"><i class="bi bi-exclamation-triangle-fill me-2"></i>위험 요소</h5>
                                ${generatePointsHtml(insightData.risk_points, 'risk')}
                            </div>
                        </div>
                        
                        <h5 class="mb-3"><i class="bi bi-graph-up-arrow me-2"></i>추천 영업 전략</h5>
                        ${generateStrategyHtml(insightData.sales_strategy)}
                        
                        <div class="alert alert-secondary mt-3">
                            <h6 class="alert-heading"><i class="bi bi-info-circle-fill me-2"></i>적합성 평가 기준</h6>
                            <p class="small mb-0">이 분석은 입찰 정보의 제한사항, 자격요건, 가격 정보 등을 종합적으로 고려하여 기업의 영업 기회를 평가합니다. 업종 적합성 점수는 참고용이며, 실제 입찰 참여 결정 시 추가 분석이 필요합니다.</p>
                        </div>
                    </div>
                </div>
            `;
            
            // 생성된 HTML 업데이트
            contentElement.innerHTML = insightHtml;
            
            Debug.info('영업 인사이트 분석 결과 표시 완료');
            
        } catch (error) {
            Debug.error('영업 인사이트 내용 업데이트 중 오류:', error);
            
            // 오류 표시
            contentElement.innerHTML = `
                <div class="card">
                    <div class="card-header bg-dark text-white">
                        <h5 class="mb-0">AI 영업 인사이트 분석</h5>
                    </div>
                    <div class="card-body">
                        <div class="alert alert-danger mb-0">
                            <h5 class="alert-heading">분석 결과 표시 중 오류가 발생했습니다</h5>
                            <p>${error.message || '알 수 없는 오류가 발생했습니다. 다시 시도해주세요.'}</p>
                        </div>
                    </div>
                </div>
            `;
        }
    }
    
    // 크롤링 시작 함수
    async function startCrawling() {
        try {
            Debug.info('크롤링 시작 요청');
            
            // 버튼 상태 업데이트
            updateButtonState(true);
            
            // 입력값 가져오기
            const keywordInput = document.getElementById('keywordInput');
            const startDate = document.getElementById('startDate');
            const endDate = document.getElementById('endDate');
            
            // 입력값 검증
            if (!keywordInput || !keywordInput.value.trim()) {
                Debug.warn('키워드가 입력되지 않았습니다');
                const statusMessages = document.getElementById('statusMessages');
                if (statusMessages) {
                    DomUtils.appendMessage(statusMessages, '키워드를 입력해주세요.', 'warning');
                }
                updateButtonState(false);
                return;
            }
            
            // 키워드 파싱
            const keywords = keywordInput.value.trim().split(',')
                .map(k => k.trim())
                .filter(k => k.length > 0);
            
            Debug.info(`크롤링 키워드: ${keywords.join(', ')}`);
            
            // 키워드 목록 표시
            updateKeywordList(keywords);
            
            // 시작 및 종료 날짜 가져오기
            const startDateValue = startDate ? startDate.value : '';
            const endDateValue = endDate ? endDate.value : '';
            
            // 상태 메시지 표시
            const statusMessages = document.getElementById('statusMessages');
            if (statusMessages) {
                DomUtils.appendMessage(statusMessages, `크롤링을 시작합니다. 키워드: ${keywords.join(', ')}`, 'info');
            }
            
            // API 호출
            const response = await ApiService.startCrawling(keywords, startDateValue, endDateValue);
            
            if (response.success) {
                Debug.info('크롤링 시작 성공:', response);
                
                // 성공 메시지 표시
                if (statusMessages) {
                    DomUtils.appendMessage(statusMessages, `크롤링이 시작되었습니다: ${response.message || ''}`, 'success');
                }
            } else {
                Debug.warn('크롤링 시작 실패:', response);
                
                // 실패 메시지 표시
                if (statusMessages) {
                    DomUtils.appendMessage(statusMessages, `크롤링 시작 실패: ${response.message || '알 수 없는 오류'}`, 'error');
                }
                
                // 버튼 상태 복원
                updateButtonState(false);
            }
        } catch (error) {
            Debug.error('크롤링 시작 중 오류 발생:', error);
            
            // 오류 메시지 표시
            const statusMessages = document.getElementById('statusMessages');
            if (statusMessages) {
                DomUtils.appendMessage(statusMessages, `크롤링 시작 중 오류 발생: ${error.message || '알 수 없는 오류'}`, 'error');
            }
            
            // 버튼 상태 복원
            updateButtonState(false);
        }
    }
    
    // 크롤링 중지 함수
    async function stopCrawling() {
        try {
            Debug.info('크롤링 중지 요청');
            
            // 상태 메시지 표시
            const statusMessages = document.getElementById('statusMessages');
            if (statusMessages) {
                DomUtils.appendMessage(statusMessages, '크롤링 중지 요청 중...', 'info');
            }
            
            // API 호출
            const response = await ApiService.stopCrawling();
            
            if (response.success) {
                Debug.info('크롤링 중지 성공:', response);
                
                // 성공 메시지 표시
                if (statusMessages) {
                    DomUtils.appendMessage(statusMessages, `크롤링이 중지되었습니다: ${response.message || ''}`, 'success');
                }
                
                // 버튼 상태 업데이트
                updateButtonState(false);
            } else {
                Debug.warn('크롤링 중지 실패:', response);
                
                // 실패 메시지 표시
                if (statusMessages) {
                    DomUtils.appendMessage(statusMessages, `크롤링 중지 실패: ${response.message || '알 수 없는 오류'}`, 'error');
                }
            }
        } catch (error) {
            Debug.error('크롤링 중지 중 오류 발생:', error);
            
            // 오류 메시지 표시
            const statusMessages = document.getElementById('statusMessages');
            if (statusMessages) {
                DomUtils.appendMessage(statusMessages, `크롤링 중지 중 오류 발생: ${error.message || '알 수 없는 오류'}`, 'error');
            }
        }
    }
    
    // AI 에이전트 크롤링 시작 함수
    async function startAgentCrawling() {
        try {
            Debug.info('AI 에이전트 크롤링 시작 요청');
            
            // 버튼 상태 업데이트
            updateAgentButtonState(true);
            
            // 상태 메시지 표시
            const agentStatus = document.getElementById('agentStatus');
            if (agentStatus) {
                DomUtils.appendMessage(agentStatus, 'AI 에이전트 크롤링을 시작하는 중...', 'info');
            }
            
            // API 호출
            const response = await ApiService.startAgentCrawling();
            
            if (response.success) {
                Debug.info('AI 에이전트 크롤링 시작 성공:', response);
                
                // 성공 메시지 표시
                if (agentStatus) {
                    DomUtils.appendMessage(agentStatus, `AI 에이전트 크롤링이 시작되었습니다: ${response.message || ''}`, 'success');
                }
            } else {
                Debug.warn('AI 에이전트 크롤링 시작 실패:', response);
                
                // 실패 메시지 표시
                if (agentStatus) {
                    DomUtils.appendMessage(agentStatus, `AI 에이전트 크롤링 시작 실패: ${response.message || '알 수 없는 오류'}`, 'error');
                }
                
                // 버튼 상태 복원
                updateAgentButtonState(false);
            }
        } catch (error) {
            Debug.error('AI 에이전트 크롤링 시작 중 오류 발생:', error);
            
            // 오류 메시지 표시
            const agentStatus = document.getElementById('agentStatus');
            if (agentStatus) {
                DomUtils.appendMessage(agentStatus, `AI 에이전트 크롤링 시작 중 오류 발생: ${error.message || '알 수 없는 오류'}`, 'error');
            }
            
            // 버튼 상태 복원
            updateAgentButtonState(false);
        }
    }
    
    // AI 에이전트 크롤링 중지 함수
    async function stopAgentCrawling() {
        try {
            Debug.info('AI 에이전트 크롤링 중지 요청');
            
            // 상태 메시지 표시
            const agentStatus = document.getElementById('agentStatus');
            if (agentStatus) {
                DomUtils.appendMessage(agentStatus, 'AI 에이전트 크롤링 중지 요청 중...', 'info');
            }
            
            // API 호출
            const response = await ApiService.stopAgentCrawling();
            
            if (response.success) {
                Debug.info('AI 에이전트 크롤링 중지 성공:', response);
                
                // 성공 메시지 표시
                if (agentStatus) {
                    DomUtils.appendMessage(agentStatus, `AI 에이전트 크롤링이 중지되었습니다: ${response.message || ''}`, 'success');
                }
                
                // 버튼 상태 업데이트
                updateAgentButtonState(false);
            } else {
                Debug.warn('AI 에이전트 크롤링 중지 실패:', response);
                
                // 실패 메시지 표시
                if (agentStatus) {
                    DomUtils.appendMessage(agentStatus, `AI 에이전트 크롤링 중지 실패: ${response.message || '알 수 없는 오류'}`, 'error');
                }
            }
        } catch (error) {
            Debug.error('AI 에이전트 크롤링 중지 중 오류 발생:', error);
            
            // 오류 메시지 표시
            const agentStatus = document.getElementById('agentStatus');
            if (agentStatus) {
                DomUtils.appendMessage(agentStatus, `AI 에이전트 크롤링 중지 중 오류 발생: ${error.message || '알 수 없는 오류'}`, 'error');
            }
        }
    }
    
    // 버튼 상태 업데이트 함수
    function updateButtonState(isRunning) {
        try {
            const startBtn = document.getElementById('startBtn');
            const stopBtn = document.getElementById('stopBtn');
            
            if (startBtn) {
                startBtn.disabled = isRunning;
            }
            
            if (stopBtn) {
                stopBtn.disabled = !isRunning;
            }
        } catch (error) {
            Debug.error('버튼 상태 업데이트 중 오류 발생:', error);
        }
    }
    
    // AI 에이전트 버튼 상태 업데이트 함수
    function updateAgentButtonState(isRunning) {
        try {
            const startAgentBtn = document.getElementById('startAgentBtn');
            const stopAgentBtn = document.getElementById('stopAgentBtn');
            
            if (startAgentBtn) {
                startAgentBtn.disabled = isRunning;
            }
            
            if (stopAgentBtn) {
                stopAgentBtn.disabled = !isRunning;
            }
        } catch (error) {
            Debug.error('AI 에이전트 버튼 상태 업데이트 중 오류 발생:', error);
        }
    }
    
    // 키워드 목록 업데이트
    function updateKeywordList(keywords) {
        try {
            Debug.info(`키워드 목록 업데이트: ${keywords.length}개 키워드`);
            
            const keywordListElement = document.getElementById('keywordList');
            if (!keywordListElement) {
                Debug.warn('키워드 목록 요소를 찾을 수 없습니다');
                return;
            }
            
            // 목록 초기화
            keywordListElement.innerHTML = '';
            
            // 키워드가 없는 경우
            if (!keywords || keywords.length === 0) {
                keywordListElement.innerHTML = '<div class="text-center text-muted"><p>키워드가 없습니다.</p></div>';
                return;
            }
            
            // 각 키워드에 대해 목록 항목 생성
            keywords.forEach((keyword, index) => {
                const keywordItem = document.createElement('div');
                keywordItem.className = 'keyword-item mb-2';
                
                const badge = document.createElement('span');
                badge.className = 'badge bg-primary me-2';
                badge.textContent = index + 1;
                
                const text = document.createElement('span');
                text.textContent = keyword;
                
                keywordItem.appendChild(badge);
                keywordItem.appendChild(text);
                
                keywordListElement.appendChild(keywordItem);
            });
            
            Debug.info('키워드 목록 업데이트 완료');
        } catch (error) {
            Debug.error('키워드 목록 업데이트 중 오류 발생:', error);
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