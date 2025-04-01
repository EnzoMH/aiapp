/**
 * WebSocketManager 클래스
 * WebSocket 연결 및 상태 관리를 담당하는 유틸리티 클래스
 */
import { Debug } from './logger.js';

class WebSocketManager {
    constructor(url, messageHandler, statusElement, errorHandler) {
        this.url = url;
        this.messageHandler = messageHandler;
        this.statusElement = statusElement;
        this.errorHandler = errorHandler;
        this.socket = null;
        this.isConnected = false;
        this.reconnectTimer = null;
        this.reconnectInterval = 1000; // 재연결 시도 간격 (1초)
        this.reconnectAttempts = 0;
        this.MAX_RECONNECT_ATTEMPTS = 5;
        
        Debug.info(`WebSocketManager 초기화: ${url}`);
    }

    /**
     * WebSocket 연결 초기화
     */
    connect() {
        try {
            Debug.info(`WebSocket 연결 시도: ${this.url}`);
            
            // 이미 연결된 소켓이 있으면 종료
            if (this.socket) {
                Debug.info('기존 WebSocket 연결 닫기');
                this.socket.close();
            }
            
            this.socket = new WebSocket(this.url);
            
            this.socket.onopen = (event) => {
                Debug.highlight(`WebSocket 연결 성공: ${this.url}`);
                console.info('WebSocket 연결 이벤트:', event);
                
                this.isConnected = true;
                this.reconnectAttempts = 0;
                clearTimeout(this.reconnectTimer);
                
                try {
                    this.updateConnectionStatus('연결됨', 'success');
                } catch (error) {
                    Debug.error('상태 업데이트 오류:', error);
                }
            };
            
            this.socket.onclose = (event) => {
                Debug.warn(`WebSocket 연결 종료: ${this.url}`, {
                    code: event.code,
                    reason: event.reason,
                    wasClean: event.wasClean
                });
                
                this.isConnected = false;
                
                try {
                    this.updateConnectionStatus('연결 종료됨', 'warning');
                } catch (error) {
                    Debug.error('상태 업데이트 오류:', error);
                }
                
                // 자동 재연결
                clearTimeout(this.reconnectTimer);
                this.attemptReconnect();
            };
            
            this.socket.onerror = (error) => {
                Debug.error(`WebSocket 오류: ${this.url}`, error);
                console.error('WebSocket 오류 상세:', error);
                
                try {
                    this.updateConnectionStatus('연결 오류', 'danger');
                } catch (error) {
                    Debug.error('상태 업데이트 오류:', error);
                }
                
                // 에러 핸들러가 있으면 호출
                if (this.errorHandler) {
                    try {
                        this.errorHandler(error);
                    } catch (handlerError) {
                        Debug.error('에러 핸들러 실행 중 오류:', handlerError);
                    }
                }
            };
            
            this.socket.onmessage = (event) => {
                try {
                    // 메시지 크기 로깅
                    const messageSize = event.data.length;
                    Debug.info(`WebSocket 메시지 수신 (${messageSize} bytes)`);
                    
                    // 메시지 파싱
                    const data = JSON.parse(event.data);
                    Debug.info('WebSocket 메시지 데이터:', data);
                    
                    // 메시지 핸들러가 있으면 호출
                    if (this.messageHandler) {
                        this.messageHandler(data);
                    }
                } catch (error) {
                    Debug.error('메시지 처리 오류:', error);
                    console.error('메시지 처리 상세 오류:', error);
                    console.error('원본 메시지:', event.data);
                }
            };
        } catch (error) {
            Debug.error('WebSocket 연결 초기화 오류:', error);
            console.error('WebSocket 초기화 상세 오류:', error);
            
            // 에러 핸들러가 있으면 호출
            if (this.errorHandler) {
                try {
                    this.errorHandler(error);
                } catch (handlerError) {
                    Debug.error('에러 핸들러 실행 중 오류:', handlerError);
                }
            }
        }
    }

    /**
     * 연결 상태 업데이트
     */
    updateConnectionStatus(status, type = 'info') {
        Debug.info(`WebSocket 상태 업데이트: ${status} (${type})`);
        
        // statusElement가 없는 경우 일찍 반환
        if (!this.statusElement) {
            Debug.warn('상태 요소가 설정되지 않았습니다');
            return;
        }
        
        // DOM 요소가 존재하는지 확인
        const statusElement = document.getElementById(this.statusElement);
        if (!statusElement) {
            Debug.error(`상태 요소를 찾을 수 없음: ${this.statusElement}`);
            return;
        }
        
        try {
            // classList가 존재하는지 확인
            if (statusElement.classList) {
                statusElement.classList.remove('bg-success', 'bg-warning', 'bg-danger', 'bg-info');
                statusElement.classList.add(`bg-${type}`);
            } else {
                Debug.warn(`요소에 classList 속성이 없음: ${this.statusElement}`);
                // 대체 방법으로 className 사용
                statusElement.className = `badge bg-${type}`;
            }
            
            // 텍스트 내용 설정
            statusElement.textContent = status;
            Debug.info(`WebSocket 상태 UI 업데이트 완료: ${status}`);
        } catch (error) {
            Debug.error('상태 업데이트 DOM 조작 오류:', error);
            console.error('DOM 조작 상세 오류:', error);
        }
    }

    /**
     * 재연결 시도
     */
    attemptReconnect() {
        if (this.reconnectAttempts < this.MAX_RECONNECT_ATTEMPTS) {
            this.reconnectAttempts++;
            Debug.info(`WebSocket 재연결 시도 ${this.reconnectAttempts}/${this.MAX_RECONNECT_ATTEMPTS}`);
            
            // 연결 상태 업데이트
            try {
                this.updateConnectionStatus(`재연결 중... (${this.reconnectAttempts}/${this.MAX_RECONNECT_ATTEMPTS})`, 'warning');
            } catch (error) {
                Debug.error('재연결 상태 업데이트 오류:', error);
            }
            
            this.reconnectTimer = setTimeout(() => this.connect(), this.reconnectInterval);
        } else {
            Debug.error('최대 재연결 시도 횟수 도달');
            
            // 연결 상태 업데이트
            try {
                this.updateConnectionStatus('재연결 실패', 'danger');
            } catch (error) {
                Debug.error('재연결 실패 상태 업데이트 오류:', error);
            }
        }
    }

    /**
     * 메시지 전송
     */
    send(message) {
        if (!this.isConnected || !this.socket) {
            Debug.error('WebSocket이 연결되어 있지 않습니다.');
            return false;
        }
        
        try {
            let payload;
            
            if (typeof message === 'object') {
                payload = JSON.stringify(message);
                Debug.info('WebSocket 메시지 전송 (JSON):', message);
            } else {
                payload = message;
                Debug.info(`WebSocket 메시지 전송 (문자열, ${message.length} bytes)`);
            }
            
            this.socket.send(payload);
            return true;
        } catch (error) {
            Debug.error('메시지 전송 오류:', error);
            console.error('메시지 전송 상세 오류:', error);
            return false;
        }
    }

    /**
     * 연결 종료
     */
    disconnect() {
        Debug.info('WebSocket 연결 종료 요청');
        
        clearTimeout(this.reconnectTimer);
        
        if (this.socket) {
            try {
                this.socket.close();
                Debug.info('WebSocket 연결 성공적으로 종료');
            } catch (error) {
                Debug.error('WebSocket 연결 종료 오류:', error);
                console.error('연결 종료 상세 오류:', error);
            }
        }
        
        this.socket = null;
        this.isConnected = false;
        
        // 연결 상태 업데이트
        try {
            this.updateConnectionStatus('연결 종료됨', 'secondary');
        } catch (error) {
            Debug.error('연결 종료 상태 업데이트 오류:', error);
        }
        
        Debug.info('WebSocket 연결 종료 처리 완료');
    }
}

export default WebSocketManager; 