/**
 * 통합 웹소켓 관리 모듈
 * 
 * 이 모듈은 애플리케이션 전체에서 사용하는 웹소켓 연결을 관리합니다.
 * - 채팅
 * - 크롤링
 * - AI 에이전트
 */

// 디버그 로깅 설정
const isDebug = true;
const logger = {
    info: (...args) => isDebug && console.info('[WebSocket]', ...args),
    warn: (...args) => isDebug && console.warn('[WebSocket]', ...args),
    error: (...args) => isDebug && console.error('[WebSocket]', ...args),
    debug: (...args) => isDebug && console.debug('[WebSocket]', ...args),
    log: (...args) => isDebug && console.log('[WebSocket]', ...args)
};

// 전역 웹소켓 인스턴스 관리
const activeConnections = new Map();

/**
 * 웹소켓 연결 관리 클래스
 */
class WebSocketManager {
    /**
     * 웹소켓 관리자 생성
     * @param {Object} config 설정 객체
     * @param {string} config.url 웹소켓 URL
     * @param {Function} config.onMessage 메시지 수신 핸들러
     * @param {string|HTMLElement} [config.statusElement] 상태 표시 요소 ID 또는 DOM 요소
     * @param {Function} [config.onError] 오류 처리 핸들러
     * @param {Function} [config.onOpen] 연결 성공 핸들러
     * @param {Function} [config.onClose] 연결 종료 핸들러
     * @param {Object} [config.params] URL에 추가할 쿼리 파라미터
     */
    constructor(config) {
        this.url = config.url;
        this.onMessageHandler = config.onMessage;
        this.statusElement = config.statusElement;
        this.onErrorHandler = config.onError;
        this.onOpenHandler = config.onOpen;
        this.onCloseHandler = config.onClose;
        this.params = config.params || {};
        
        this.socket = null;
        this.isConnected = false;
        this.reconnectTimer = null;
        this.reconnectInterval = 1000; // 재연결 시도 간격 (1초)
        this.reconnectAttempts = 0;
        this.MAX_RECONNECT_ATTEMPTS = 3; // 재연결 시도 횟수 감소
        this.connectionId = `${this.url}_${Date.now()}`;
        
        logger.info(`WebSocketManager 초기화: ${this.url}`);
    }

    /**
     * WebSocket 연결 초기화
     */
    connect() {
        try {
            // 기존 활성 연결 확인
            if (activeConnections.has(this.url)) {
                const existingConnection = activeConnections.get(this.url);
                if (existingConnection && existingConnection !== this && existingConnection.isConnected) {
                    logger.warn(`URL ${this.url}에 이미 활성 연결이 있습니다. 기존 연결을 재사용합니다.`);
                    
                    // 기존 연결이 있는 경우 새 연결 시도 전에 해제
                    existingConnection.disconnect();
                    
                    // 짧은 지연 후 연결 (리소스 해제를 위한 시간)
                    setTimeout(() => this._createConnection(), 500);
                    return;
                }
            }
            
            // 연결 생성
            this._createConnection();
        } catch (error) {
            logger.error('WebSocket 연결 초기화 오류:', error);
            
            // 에러 핸들러 호출
            if (typeof this.onErrorHandler === 'function') {
                this.onErrorHandler(error);
            }
        }
    }
    
    /**
     * 실제 웹소켓 연결 생성
     * @private
     */
    _createConnection() {
        // URL 쿼리 파라미터 추가
        let fullUrl = this.url;
        if (Object.keys(this.params).length > 0) {
            const queryParams = new URLSearchParams();
            for (const [key, value] of Object.entries(this.params)) {
                if (value !== null && value !== undefined) {
                    queryParams.append(key, value);
                }
            }
            fullUrl = `${this.url}?${queryParams.toString()}`;
        }
        
        logger.info(`WebSocket 연결 시도: ${fullUrl}`);
        
        // 이미 연결된 소켓이 있으면 종료
        if (this.socket) {
            logger.info('기존 WebSocket 연결 닫기');
            try {
                this.socket.close();
            } catch (e) {
                logger.error('소켓 닫기 오류:', e);
            }
            this.socket = null;
        }
        
        // 새 웹소켓 연결 생성
        try {
            this.socket = new WebSocket(fullUrl);
            
            // 메모리 누수 방지를 위한 타임아웃 설정
            const connectionTimeout = setTimeout(() => {
                if (this.socket && this.socket.readyState === WebSocket.CONNECTING) {
                    logger.warn('연결 타임아웃, 소켓 닫기');
                    this.socket.close();
                    
                    if (typeof this.onErrorHandler === 'function') {
                        this.onErrorHandler(new Error('연결 시간 초과'));
                    }
                }
            }, 10000); // 10초 타임아웃
            
            this.socket.onopen = (event) => {
                clearTimeout(connectionTimeout);
                logger.info(`WebSocket 연결 성공: ${this.url}`);
                
                this.isConnected = true;
                this.reconnectAttempts = 0;
                clearTimeout(this.reconnectTimer);
                
                // 활성 연결 등록
                activeConnections.set(this.url, this);
                
                this.updateConnectionStatus('연결됨', 'success');
                
                // 커스텀 핸들러 호출
                if (typeof this.onOpenHandler === 'function') {
                    this.onOpenHandler(event);
                }
            };
            
            this.socket.onclose = (event) => {
                clearTimeout(connectionTimeout);
                logger.warn(`WebSocket 연결 종료: ${this.url}`, {
                    code: event.code,
                    reason: event.reason,
                    wasClean: event.wasClean
                });
                
                this.isConnected = false;
                
                // 활성 연결에서 제거
                if (activeConnections.get(this.url) === this) {
                    activeConnections.delete(this.url);
                }
                
                this.updateConnectionStatus('연결 종료됨', 'warning');
                
                // 커스텀 핸들러 호출
                if (typeof this.onCloseHandler === 'function') {
                    this.onCloseHandler(event);
                }
                
                // 자동 재연결
                clearTimeout(this.reconnectTimer);
                if (event.code !== 1000) { // 정상 종료가 아닌 경우에만 재연결
                    this.attemptReconnect();
                }
            };
            
            this.socket.onerror = (error) => {
                clearTimeout(connectionTimeout);
                logger.error(`WebSocket 오류: ${this.url}`, error);
                
                this.updateConnectionStatus('연결 오류', 'danger');
                
                // 커스텀 에러 핸들러 호출
                if (typeof this.onErrorHandler === 'function') {
                    this.onErrorHandler(error);
                }
            };
            
            this.socket.onmessage = (event) => {
                try {
                    // 메시지 크기 로깅
                    const messageSize = event.data.length;
                    logger.debug(`WebSocket 메시지 수신 (${messageSize} bytes)`);
                    
                    // 메시지 파싱
                    const data = JSON.parse(event.data);
                    logger.debug('WebSocket 메시지 데이터:', data);
                    
                    // 메시지 핸들러 호출
                    if (typeof this.onMessageHandler === 'function') {
                        this.onMessageHandler(data, event);
                    }
                } catch (error) {
                    logger.error('메시지 처리 오류:', error);
                    console.error('원본 메시지:', event.data);
                }
            };
        } catch (error) {
            logger.error('소켓 생성 중 오류:', error);
            if (typeof this.onErrorHandler === 'function') {
                this.onErrorHandler(error);
            }
        }
    }

    /**
     * 연결 상태 업데이트
     */
    updateConnectionStatus(status, type = 'info') {
        logger.debug(`WebSocket 상태 업데이트: ${status} (${type})`);
        
        // statusElement가 없는 경우 종료
        if (!this.statusElement) {
            return;
        }
        
        try {
            // statusElement가 문자열인 경우 DOM 요소 탐색
            let element = this.statusElement;
            if (typeof this.statusElement === 'string') {
                element = document.getElementById(this.statusElement);
                if (!element) {
                    return;
                }
            }
            
            // 요소에 상태 정보 설정
            if (element.classList) {
                element.classList.remove('bg-success', 'bg-warning', 'bg-danger', 'bg-info');
                element.classList.add(`bg-${type}`);
            } else {
                element.className = `badge bg-${type}`;
            }
            
            element.textContent = status;
        } catch (error) {
            logger.error('상태 업데이트 DOM 조작 오류:', error);
        }
    }

    /**
     * 재연결 시도
     */
    attemptReconnect() {
        if (this.reconnectAttempts < this.MAX_RECONNECT_ATTEMPTS) {
            this.reconnectAttempts++;
            logger.info(`WebSocket 재연결 시도 ${this.reconnectAttempts}/${this.MAX_RECONNECT_ATTEMPTS}`);
            
            this.updateConnectionStatus(`재연결 중... (${this.reconnectAttempts}/${this.MAX_RECONNECT_ATTEMPTS})`, 'warning');
            
            // 지수 백오프 적용 (최대 10초)
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), 10000);
            this.reconnectTimer = setTimeout(() => this._createConnection(), delay);
        } else {
            logger.error('최대 재연결 시도 횟수 도달');
            
            this.updateConnectionStatus('재연결 실패', 'danger');
        }
    }

    /**
     * 메시지 전송
     * @param {Object|string} message 전송할 메시지
     * @returns {boolean} 전송 성공 여부
     */
    send(message) {
        if (!this.isConnected || !this.socket || this.socket.readyState !== WebSocket.OPEN) {
            logger.error('WebSocket이 연결되어 있지 않습니다.');
            return false;
        }
        
        try {
            let payload;
            
            if (typeof message === 'object') {
                payload = JSON.stringify(message);
                logger.debug('WebSocket 메시지 전송 (JSON):', message);
            } else {
                payload = message;
                logger.debug(`WebSocket 메시지 전송 (문자열, ${message.length} bytes)`);
            }
            
            this.socket.send(payload);
            return true;
        } catch (error) {
            logger.error('메시지 전송 오류:', error);
            return false;
        }
    }

    /**
     * 연결 종료
     */
    disconnect() {
        logger.info('WebSocket 연결 종료 요청');
        
        clearTimeout(this.reconnectTimer);
        
        if (this.socket) {
            try {
                this.socket.close(1000, "정상 종료");
                logger.info('WebSocket 연결 종료됨');
            } catch (error) {
                logger.error('WebSocket 연결 종료 오류:', error);
            }
        }
        
        this.socket = null;
        this.isConnected = false;
        
        // 활성 연결에서 제거
        if (activeConnections.get(this.url) === this) {
            activeConnections.delete(this.url);
        }
        
        this.updateConnectionStatus('연결 종료됨', 'secondary');
    }
}

/**
 * 채팅 웹소켓 관리자
 */
class ChatWebSocketManager {
    /**
     * 채팅 웹소켓 관리자 생성
     * @param {Object} config 설정 객체
     */
    constructor(config = {}) {
        // 토큰 가져오기
        const token = localStorage.getItem('access_token');
        
        this.wsManager = new WebSocketManager({
            url: `ws://${window.location.host}/chat`,
            params: { token },
            onMessage: (data, event) => this.handleMessage(data, event),
            onOpen: config.onOpen,
            onClose: config.onClose,
            onError: config.onError,
            statusElement: config.statusElement
        });
        
        this.messageCallbacks = {
            onAssistantMessage: config.onAssistantMessage,
            onMessageComplete: config.onMessageComplete,
            onProcessing: config.onProcessing,
            onConnectionEstablished: config.onConnectionEstablished,
            onError: config.onError
        };
        
        this.currentSessionId = null;
        this.isProcessing = false;
        
        // 설정에서 제공된 경우 세션 ID 설정
        if (config.sessionId) {
            this.currentSessionId = config.sessionId;
        }
    }
    
    /**
     * 웹소켓 연결 시작
     */
    connect() {
        this.wsManager.connect();
    }
    
    /**
     * 메시지 처리
     * @param {Object} data 수신된 메시지 데이터
     * @param {Event} event 원본 메시지 이벤트
     */
    handleMessage(data, event) {
        try {
            const {
                onAssistantMessage,
                onMessageComplete,
                onProcessing,
                onConnectionEstablished,
                onError
            } = this.messageCallbacks;
            
            logger.info('채팅 메시지 수신:', data.type);
            
            switch (data.type) {
                case 'assistant':
                    logger.info('어시스턴트 메시지:', data.streaming ? '스트리밍' : '전체');
                    if (data.streaming && typeof onAssistantMessage === 'function') {
                        onAssistantMessage(data.content, data.model);
                    } else if (data.isFullResponse && typeof onMessageComplete === 'function') {
                        onMessageComplete(data);
                    }
                    break;
                    
                case 'message_complete':
                    logger.info('메시지 처리 완료');
                    // 메시지 처리 완료 신호 처리
                    this.isProcessing = false;
                    
                    // 세션 ID 저장 (있는 경우)
                    if (data.data && data.data.session_id) {
                        this.currentSessionId = data.data.session_id;
                        logger.info('세션 ID 업데이트:', this.currentSessionId);
                    }
                    
                    if (typeof onMessageComplete === 'function') {
                        onMessageComplete(data);
                    }
                    break;
                    
                case 'processing':
                    logger.info('메시지 처리 중');
                    // 메시지 처리 중 신호
                    if (typeof onProcessing === 'function') {
                        onProcessing(data);
                    }
                    break;
                    
                case 'connection_established':
                    logger.info('WebSocket 연결 성공:', data.data);
                    if (typeof onConnectionEstablished === 'function') {
                        onConnectionEstablished(data);
                    }
                    break;
                    
                case 'error':
                    logger.error('WebSocket 오류:', data.data?.message || '알 수 없는 오류');
                    this.isProcessing = false;
                    
                    if (typeof onError === 'function') {
                        onError(data);
                    }
                    break;
                    
                default:
                    logger.warn('알 수 없는 메시지 유형:', data.type, data);
                    // 알 수 없는 메시지 유형이지만 처리 완료로 간주
                    this.isProcessing = false;
            }
        } catch (error) {
            logger.error('메시지 처리 오류:', error);
            this.isProcessing = false;
        }
    }
    
    /**
     * 메시지 전송
     * @param {Object} options 메시지 옵션
     * @returns {boolean} 전송 성공 여부
     */
    sendMessage(options) {
        const {
            message,
            onSuccess,
            onError
        } = options || {};
        
        if (this.isProcessing) {
            logger.warn('이전 메시지 처리 중...');
            return false;
        }
        
        // 메시지 전송
        const sent = this.wsManager.send(message);
        
        if (sent) {
            this.isProcessing = true;
            if (typeof onSuccess === 'function') {
                onSuccess();
            }
        } else {
            if (typeof onError === 'function') {
                onError('메시지 전송 실패');
            }
        }
        
        return sent;
    }
    
    /**
     * 새 채팅 시작
     */
    startNewChat() {
        this.currentSessionId = null;
        this.isProcessing = false;
        return true;
    }
    
    /**
     * 연결 종료
     */
    disconnect() {
        this.wsManager.disconnect();
    }
}

/**
 * 크롤링 웹소켓 관리자
 */
class CrawlWebSocketManager {
    /**
     * 크롤링 웹소켓 관리자 생성
     * @param {Object} config 설정 객체
     */
    constructor(config = {}) {
        this.wsManager = new WebSocketManager({
            url: `ws://${window.location.host}/ws`,
            onMessage: (data, event) => this.handleMessage(data, event),
            onOpen: config.onOpen,
            onClose: config.onClose,
            onError: config.onError,
            statusElement: config.statusElement
        });
        
        this.callbacks = {
            onStatusUpdate: config.onStatusUpdate,
            onError: config.onError
        };
    }
    
    /**
     * 웹소켓 연결 시작
     */
    connect() {
        this.wsManager.connect();
    }
    
    /**
     * 메시지 처리
     * @param {Object} data 수신된 메시지 데이터
     * @param {Event} event 원본 메시지 이벤트
     */
    handleMessage(data, event) {
        try {
            const { onStatusUpdate, onError } = this.callbacks;
            
            logger.info('크롤링 메시지 수신:', data);
            
            // 메시지 타입에 따라 처리
            switch (data.type) {
                case 'status_update':
                    logger.info('크롤링 상태 업데이트:', data.status);
                    if (typeof onStatusUpdate === 'function') {
                        onStatusUpdate(data);
                    }
                    break;
                    
                case 'new_crawl_item':
                    logger.info('새 크롤링 항목 수신:', data.item?.title || '제목 없음');
                    if (typeof onStatusUpdate === 'function') {
                        onStatusUpdate(data);
                    }
                    break;
                    
                case 'crawl_results':
                    logger.info('크롤링 결과 수신:', data.count || 0, '개 항목');
                    if (typeof onStatusUpdate === 'function') {
                        onStatusUpdate(data);
                    }
                    break;
                    
                case 'connection_established':
                    logger.info('크롤링 서버 연결 설정됨');
                    if (typeof onStatusUpdate === 'function') {
                        onStatusUpdate(data);
                    }
                    break;
                    
                case 'error':
                    logger.error('크롤링 오류:', data.message || data.error);
                    if (typeof onError === 'function') {
                        onError(data);
                    }
                    break;
                    
                default:
                    logger.warn('알 수 없는 크롤링 메시지 타입:', data.type);
                    // 기본 상태 업데이트 콜백 호출
                    if (typeof onStatusUpdate === 'function') {
                        onStatusUpdate(data);
                    }
            }
        } catch (error) {
            logger.error('크롤링 메시지 처리 오류:', error);
        }
    }
    
    /**
     * 연결 종료
     */
    disconnect() {
        this.wsManager.disconnect();
    }
}

/**
 * AI 에이전트 웹소켓 관리자
 */
class AgentWebSocketManager {
    /**
     * AI 에이전트 웹소켓 관리자 생성
     * @param {Object} config 설정 객체
     */
    constructor(config = {}) {
        this.wsManager = new WebSocketManager({
            url: `ws://${window.location.host}/ws/agent`,
            onMessage: (data, event) => this.handleMessage(data, event),
            onOpen: config.onOpen,
            onClose: config.onClose,
            onError: config.onError,
            statusElement: config.statusElement
        });
        
        this.callbacks = {
            onStatusUpdate: config.onStatusUpdate,
            onError: config.onError
        };
    }
    
    /**
     * 웹소켓 연결 시작
     */
    connect() {
        this.wsManager.connect();
    }
    
    /**
     * 메시지 처리
     * @param {Object} data 수신된 메시지 데이터
     * @param {Event} event 원본 메시지 이벤트
     */
    handleMessage(data, event) {
        try {
            const { onStatusUpdate, onError } = this.callbacks;
            
            logger.info('에이전트 메시지 수신:', data);
            
            // 메시지 타입에 따라 처리
            switch (data.type) {
                case 'status_update':
                    logger.info('에이전트 상태 업데이트:', data.status);
                    if (typeof onStatusUpdate === 'function') {
                        onStatusUpdate(data);
                    }
                    break;
                    
                case 'error':
                    logger.error('에이전트 오류:', data.message || data.error);
                    if (typeof onError === 'function') {
                        onError(data);
                    }
                    break;
                    
                case 'connection_established':
                    logger.info('에이전트 연결 설정됨');
                    break;
                    
                case 'agent_response':
                    logger.info('에이전트 응답 수신:', data.message);
                    // 에이전트 응답 처리 로직
                    break;
                    
                case 'agent_action':
                    logger.info('에이전트 액션 실행:', data.action);
                    // 에이전트 액션 처리 로직
                    break;
                    
                default:
                    logger.warn('알 수 없는 에이전트 메시지 타입:', data.type);
                    // 기본 상태 업데이트 콜백 호출
                    if (typeof onStatusUpdate === 'function') {
                        onStatusUpdate(data);
                    }
            }
        } catch (error) {
            logger.error('에이전트 메시지 처리 오류:', error);
        }
    }
    
    /**
     * 연결 종료
     */
    disconnect() {
        this.wsManager.disconnect();
    }
}

// 모듈 내보내기
export {
    WebSocketManager,
    ChatWebSocketManager,
    CrawlWebSocketManager,
    AgentWebSocketManager
}; 