/**
 * WebSocketManager 클래스
 * WebSocket 연결 및 상태 관리를 담당하는 유틸리티 클래스
 */
class WebSocketManager {
    constructor(url, statusElementId, messageHandler) {
        this.url = url;
        this.statusElementId = statusElementId;
        this.messageHandler = messageHandler;
        this.socket = null;
        this.isConnected = false;
        this.reconnectTimer = null;
        this.reconnectInterval = 1000; // 재연결 시도 간격 (1초)
        this.reconnectAttempts = 0;
        this.MAX_RECONNECT_ATTEMPTS = 5;
    }

    /**
     * WebSocket 연결 초기화
     */
    connect() {
        try {
            this.socket = new WebSocket(this.url);
            
            this.socket.onopen = () => {
                console.log(`WebSocket 연결 성공: ${this.url}`);
                this.isConnected = true;
                this.reconnectAttempts = 0;
                clearTimeout(this.reconnectTimer);
                try {
                    this.updateConnectionStatus('연결됨', 'success');
                } catch (error) {
                    console.error('상태 업데이트 오류:', error);
                }
            };
            
            this.socket.onclose = (event) => {
                console.log(`WebSocket 연결 종료: ${this.url}`, event.reason);
                this.isConnected = false;
                try {
                    this.updateConnectionStatus('연결 종료됨', 'warning');
                } catch (error) {
                    console.error('상태 업데이트 오류:', error);
                }
                
                // 자동 재연결
                clearTimeout(this.reconnectTimer);
                this.attemptReconnect();
            };
            
            this.socket.onerror = (error) => {
                console.error(`WebSocket 오류: ${this.url}`, error);
                try {
                    this.updateConnectionStatus('연결 오류', 'danger');
                } catch (error) {
                    console.error('상태 업데이트 오류:', error);
                }
            };
            
            this.socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    console.log('WebSocket message:', data);
                    
                    if (this.messageHandler) {
                        this.messageHandler(data);
                    }
                } catch (error) {
                    console.error('메시지 처리 오류:', error);
                }
            };
        } catch (error) {
            console.error('WebSocket 연결 초기화 오류:', error);
        }
    }

    /**
     * 연결 상태 업데이트
     */
    updateConnectionStatus(status, type = 'info') {
        // statusElementId가 없는 경우 일찍 반환
        if (!this.statusElementId) {
            console.error('상태 요소 ID가 설정되지 않았습니다');
            return;
        }
        
        // DOM 요소가 존재하는지 확인
        const statusElement = document.getElementById(this.statusElementId);
        if (!statusElement) {
            console.error(`상태 요소를 찾을 수 없음: ${this.statusElementId}`);
            return;
        }
        
        try {
            // classList가 존재하는지 확인
            if (statusElement.classList) {
                statusElement.classList.remove('bg-success', 'bg-warning', 'bg-danger', 'bg-info');
                statusElement.classList.add(`bg-${type}`);
            } else {
                console.warn(`요소에 classList 속성이 없음: ${this.statusElementId}`);
                // 대체 방법으로 className 사용
                statusElement.className = `badge bg-${type}`;
            }
            
            // 텍스트 내용 설정
            statusElement.textContent = status;
        } catch (error) {
            console.error('상태 업데이트 DOM 조작 오류:', error);
        }
    }

    /**
     * 재연결 시도
     */
    attemptReconnect() {
        if (this.reconnectAttempts < this.MAX_RECONNECT_ATTEMPTS) {
            this.reconnectAttempts++;
            console.log(`재연결 시도 ${this.reconnectAttempts}/${this.MAX_RECONNECT_ATTEMPTS}`);
            this.reconnectTimer = setTimeout(() => this.connect(), this.reconnectInterval);
        } else {
            console.log('최대 재연결 시도 횟수 도달');
        }
    }

    /**
     * 메시지 전송
     */
    send(message) {
        if (!this.isConnected || !this.socket) {
            console.error('WebSocket이 연결되어 있지 않습니다.');
            return false;
        }
        
        try {
            if (typeof message === 'object') {
                this.socket.send(JSON.stringify(message));
            } else {
                this.socket.send(message);
            }
            return true;
        } catch (error) {
            console.error('메시지 전송 오류:', error);
            return false;
        }
    }

    /**
     * 연결 종료
     */
    disconnect() {
        clearTimeout(this.reconnectTimer);
        
        if (this.socket) {
            try {
                this.socket.close();
            } catch (error) {
                console.error('WebSocket 연결 종료 오류:', error);
            }
        }
        
        this.socket = null;
        this.isConnected = false;
    }
}

export default WebSocketManager; 