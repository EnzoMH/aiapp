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
        return new Promise((resolve, reject) => {
            if (this.socket && this.isConnected) {
                resolve(this.socket);
                return;
            }
            
            // 이전 재연결 시간 확인
            const lastReconnectTime = parseInt(sessionStorage.getItem('lastReconnectTime') || '0');
            const now = Date.now();
            
            // 너무 빈번한 재연결 방지 (500ms 이내)
            if (lastReconnectTime > 0 && (now - lastReconnectTime) < 500) {
                logger.warn('너무 빠른 웹소켓 재연결 시도 감지');
                const reconnectCount = parseInt(sessionStorage.getItem('websocketReconnectCount') || '0') + 1;
                sessionStorage.setItem('websocketReconnectCount', reconnectCount.toString());
                
                // 과도한 재연결 시도 시 대기 시간 증가
                if (reconnectCount > 5) {
                    logger.error('과도한 웹소켓 재연결 시도. 재연결 지연 증가');
                    this.reconnectInterval = Math.min(30000, this.reconnectInterval * 2); // 최대 30초까지 지연 증가
                    reject(new Error('Too many reconnection attempts'));
                    return;
                }
            } else {
                // 정상 시간 간격으로 재연결 시 카운터 초기화
                sessionStorage.setItem('websocketReconnectCount', '0');
            }
            
            // 재연결 시간 기록
            sessionStorage.setItem('lastReconnectTime', now.toString());
            
            try {
                this.socket = new WebSocket(this.url);
                
                this.socket.onopen = (event) => {
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
                    
                    // 연결 후 인증 정보 전송
                    this.sendInitMessage();
                    
                    // 연결 핸들러 호출
                    if (typeof this.onMessageHandler === 'function') {
                        this.onMessageHandler(event.data, event);
                    }
                    
                    resolve(this.socket);
                };
                
                this.socket.onclose = (event) => {
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
                    if (event.code !== 1000 && event.code !== 1001 && this.reconnectAttempts < this.MAX_RECONNECT_ATTEMPTS) {
                        this.attemptReconnect();
                    }
                    
                    reject(new Error(`WebSocket closed with code: ${event.code}, reason: ${event.reason}`));
                };
                
                this.socket.onerror = (error) => {
                    logger.error(`WebSocket 오류: ${this.url}`, error);
                    
                    this.updateConnectionStatus('연결 오류', 'danger');
                    
                    // 커스텀 에러 핸들러 호출
                    if (typeof this.onErrorHandler === 'function') {
                        this.onErrorHandler(error);
                    }
                    
                    reject(error);
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
                reject(error);
            }
        });
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
            this.reconnectTimer = setTimeout(() => this.connect(), delay);
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

    /**
     * 초기화 메시지 전송 (인증 처리)
     */
    sendInitMessage() {
        // 로컬 스토리지에서 사용자 ID와 역할 가져오기
        const userId = localStorage.getItem('user_id');
        const userRole = localStorage.getItem('user_role');
        
        if (userId) {
            logger.info('사용자 인증 정보 전송:', { userId, userRole });
            this.send({
                type: 'init',
                user_id: userId,
                user_role: userRole || 'user',
                timestamp: new Date().toISOString()
            });
        } else {
            logger.warn('인증 정보 없음');
            this.send({
                type: 'init',
                anonymous: true,
                timestamp: new Date().toISOString()
            });
        }
    }
}

/**
 * 채팅 웹소켓 관리자
 */
export class ChatWebSocketManager {
    /**
     * 채팅 웹소켓 관리자 생성
     * @param {string} url 웹소켓 URL
     */
    constructor(url = '/chat') {
        this.url = url;
        this.socket = null;
        this.isConnected = false;
        this.isAuth = false;
        this.handlers = new Map();
        this.connectionChangeHandler = null;
        this.errorHandler = null;
        this.reconnectTimer = null;
        this.reconnectAttempts = 0;
        this.MAX_RECONNECT_ATTEMPTS = 3;
        this.connectionId = null;
        
        // 이전 웹소켓 인스턴스 초기화를 위한 연결 식별자
        this.socketInstanceId = `ws_chat_${Date.now()}`;
        
        this.initConnectionState();
        
        logger.info(`ChatWebSocketManager 초기화: ${this.url}`);
    }
    
    /**
     * 초기 연결 상태 설정
     */
    initConnectionState() {
        this.isConnected = false;
        this.isAuth = false;
        this.reconnectAttempts = 0;
        clearTimeout(this.reconnectTimer);
    }
    
    /**
     * 웹소켓 연결
     * @returns {Promise} 연결 결과 프로미스
     */
    connect() {
        return new Promise((resolve, reject) => {
            try {
                // 이미 연결되어 있으면 재사용
                if (this.socket && this.isConnected) {
                    resolve(this.socket);
                    return;
                }
                
                // 존재하는 소켓이 있으면 닫기
                if (this.socket) {
                    try {
                        this.socket.close();
                    } catch (e) {
                        // 무시
                    }
                }
                
                // 빠른 재연결 감지 및 방지
                const lastConnectTime = parseInt(sessionStorage.getItem('ws_last_connect') || '0');
                const now = Date.now();
                
                if (lastConnectTime > 0 && (now - lastConnectTime) < 1000) {
                    // 너무 빠른 재연결 시도 감지
                    const connectCount = parseInt(sessionStorage.getItem('ws_connect_count') || '0') + 1;
                    sessionStorage.setItem('ws_connect_count', connectCount.toString());
                    
                    if (connectCount > 5) {
                        console.error('과도한 웹소켓 연결 시도 감지. 연결 시도 중단');
                        // 연결 중단 및 폴백 처리
                        sessionStorage.removeItem('ws_connect_count');
                        reject(new Error('Too many connection attempts'));
                        return;
                    }
                } else {
                    // 정상 시도 - 카운터 리셋
                    sessionStorage.setItem('ws_connect_count', '0');
                }
                
                // 연결 시간 기록
                sessionStorage.setItem('ws_last_connect', now.toString());
                sessionStorage.setItem('ws_instance_id', this.socketInstanceId);
                
                // 기존 인스턴스와 충돌 감지
                const activeInstanceId = sessionStorage.getItem('ws_active_instance');
                if (activeInstanceId && activeInstanceId !== this.socketInstanceId) {
                    console.warn('기존 웹소켓 인스턴스 감지');
                }
                
                // 연결 시작
                this.initConnectionState();
                const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}${this.url}`;
                this.socket = new WebSocket(wsUrl);
                
                // 세션 정보 추출 - 서버에서 쿠키로 자동 처리되므로 여기서는 로깅만
                const sessionCookie = document.cookie.split('; ').find(row => row.startsWith('user_session='));
                if (sessionCookie) {
                    logger.debug('세션 쿠키 감지: 서버에서 자동으로 처리됨');
                }
                
                // 연결 핸들러
                this.socket.onopen = (event) => {
                    logger.info(`웹소켓 연결 성공: ${wsUrl}`);
                    this.isConnected = true;
                    this.reconnectAttempts = 0;
                    clearTimeout(this.reconnectTimer);
                    
                    // 활성 인스턴스 기록
                    sessionStorage.setItem('ws_active_instance', this.socketInstanceId);
                    
                    // 연결 변경 이벤트 호출
                    if (this.connectionChangeHandler) {
                        this.connectionChangeHandler(true);
                    }
                    
                    resolve(this.socket);
                };
                
                // 오류 핸들러
                this.socket.onerror = (error) => {
                    logger.error(`웹소켓 오류: ${wsUrl}`, error);
                    
                    // 오류 핸들러 호출
                    if (this.errorHandler) {
                        this.errorHandler(error);
                    }
                    
                    reject(error);
                };
                
                // 연결 종료 핸들러
                this.socket.onclose = (event) => {
                    // 상태 업데이트
                    this.isConnected = false;
                    
                    // 활성 인스턴스 확인
                    const currentActiveId = sessionStorage.getItem('ws_active_instance');
                    if (currentActiveId === this.socketInstanceId) {
                        sessionStorage.removeItem('ws_active_instance');
                    }
                    
                    // 사용자에게 통보
                    if (this.connectionChangeHandler) {
                        this.connectionChangeHandler(false);
                    }
                    
                    // 정상적인 종료가 아니면 재연결 시도
                    clearTimeout(this.reconnectTimer);
                    if (event.code !== 1000 && event.code !== 1001 && this.reconnectAttempts < this.MAX_RECONNECT_ATTEMPTS) {
                        this.scheduleReconnect();
                    }
                };
                
                // 메시지 수신 핸들러
                this.socket.onmessage = this.handleMessage.bind(this);
                
            } catch (error) {
                logger.error(`웹소켓 연결 생성 오류: ${error.message}`, error);
                reject(error);
            }
        });
    }
    
    /**
     * 초기화 메시지 전송
     */
    sendInitMessage() {
        // 사용자가 인증되어 있지 않으면 초기화 메시지를 보내지 않음
        if (!this.isConnected) {
            return;
        }
        
        // 로컬 스토리지에서 사용자 정보 가져오기
        const userId = localStorage.getItem('user_id');
        const userRole = localStorage.getItem('user_role');
        
        // 인증 정보 전송
        if (userId) {
            this.send({
                type: 'init',
                user_id: userId,
                user_role: userRole || 'user',
                client_info: {
                    browser: navigator.userAgent,
                    url: window.location.pathname,
                    timestamp: new Date().toISOString()
                }
            });
        }
    }
    
    /**
     * 연결 성공 처리
     * @param {Object} data 서버에서 받은 응답 데이터
     */
    handleConnectionEstablished(data) {
        this.connectionId = data.connection_id;
        logger.info(`웹소켓 연결 ID: ${this.connectionId}`);
        
        // 인증 필요하면 초기화 메시지 전송
        if (data.requires_auth) {
            setTimeout(() => this.sendInitMessage(), 100);
        }
    }
    
    /**
     * 인증 성공 처리
     * @param {Object} data 서버에서 받은 응답 데이터
     */
    handleAuthSuccess(data) {
        this.isAuth = true;
        logger.info(`웹소켓 인증 성공: ${data.user_id}`);
    }
    
    /**
     * 인증 오류 처리
     * @param {Object} data 서버에서 받은 응답 데이터
     */
    handleAuthError(data) {
        this.isAuth = false;
        logger.error(`웹소켓 인증 오류: ${data.message}`);
        
        // 인증 오류시 로그아웃 후 로그인 페이지로 리디렉션
        try {
            // 로컬 스토리지 초기화 
            localStorage.clear();
            sessionStorage.clear();
            
            // 백엔드 로그아웃 요청
            fetch('/api/logout', {
                method: 'POST',
                credentials: 'include'
            }).then(() => {
                // 로그인 페이지로 이동
                window.location.replace('/');
            }).catch(error => {
                console.error('로그아웃 실패:', error);
                window.location.replace('/');
            });
        } catch (e) {
            console.error('인증 오류 처리 중 오류:', e);
            window.location.replace('/');
        }
    }
    
    /**
     * 재연결 스케줄링
     */
    scheduleReconnect() {
        this.reconnectAttempts++;
        logger.info(`웹소켓 재연결 시도 (${this.reconnectAttempts}/${this.MAX_RECONNECT_ATTEMPTS})...`);
        
        setTimeout(() => {
            if (!this.isConnected) {
                this.connect().catch(error => {
                    logger.error('재연결 실패:', error);
                });
            }
        }, this.reconnectDelay);
    }
    
    /**
     * 메시지 처리
     * @param {MessageEvent} event - 웹소켓 메시지 이벤트
     */
    handleMessage(event) {
        try {
            const data = JSON.parse(event.data);
            logger.debug('메시지 수신:', data);
            
            // 메시지 타입에 따른 핸들러 호출
            if (data.type && this.handlers.has(data.type)) {
                this.handlers.get(data.type)(data.data || data, event);
            }
        } catch (error) {
            logger.error('메시지 처리 중 오류:', error);
        }
    }
    
    /**
     * 연결 상태 확인
     * @returns {boolean} 연결 상태
     */
    isConnected() {
        return this.isConnected;
    }
    
    /**
     * 인증 상태 확인
     * @returns {boolean} 인증 상태
     */
    isAuthenticated() {
        return this.isAuth;
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
            
            // 상태 업데이트 콜백 호출
            if (typeof onStatusUpdate === 'function') {
                onStatusUpdate(data);
            }
            
            // 오류 처리
            if (data.type === 'error' && typeof onError === 'function') {
                onError(data);
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
            
            // 상태 업데이트 콜백 호출
            if (typeof onStatusUpdate === 'function') {
                onStatusUpdate(data);
            }
            
            // 오류 처리
            if (data.type === 'error' && typeof onError === 'function') {
                onError(data);
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
    CrawlWebSocketManager,
    AgentWebSocketManager
}; 