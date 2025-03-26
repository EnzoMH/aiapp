export class WebSocketManager {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.currentModel = 'meta';
        this.currentSessionId = null;
        this.isProcessing = false;
        this.callbacks = {
            onMessage: null,
            onConnectionEstablished: null,
            onError: null,
            onComplete: null,
            onModelUpdate: null
        };
    }

    setCallbacks(callbacks) {
        this.callbacks = { ...this.callbacks, ...callbacks };
    }

    initialize() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            console.log('WebSocket already connected');
            return;
        }
        
        // 토큰 가져오기
        const token = localStorage.getItem('access_token');
        const tokenParam = token ? `?token=${token}` : '';
        
        this.ws = new WebSocket(`ws://${window.location.host}/chat${tokenParam}`);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
            if (this.callbacks.onConnectionEstablished) {
                this.callbacks.onConnectionEstablished();
            }
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000);
                console.log(`재연결 시도 중... (${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`);
                setTimeout(() => this.initialize(), delay);
                this.reconnectAttempts++;
            } else {
                console.error('서버 연결에 실패했습니다. 페이지를 새로고침해주세요.');
            }
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            if (this.callbacks.onError) {
                this.callbacks.onError('서버 연결에 문제가 발생했습니다');
            }
        };
        
        this.ws.onmessage = (event) => this.handleWebSocketMessage(event);
    }

    handleWebSocketMessage(event) {
        try {
            const data = JSON.parse(event.data);
            console.log('WebSocket message received:', data);
            
            // 연결 성공 메시지 처리
            if (data.type === 'connection_established') {
                console.log('연결 성공:', data.data);
                this.currentSessionId = data.data.session_id;
                // 모델 정보가 있으면 업데이트
                if (data.data.model) {
                    this.currentModel = data.data.model;
                    if (this.callbacks.onModelUpdate) {
                        this.callbacks.onModelUpdate(this.currentModel);
                    }
                }
                if (this.callbacks.onConnectionEstablished) {
                    this.callbacks.onConnectionEstablished();
                }
                return;
            }
            
            // 메시지 완료 신호 처리
            if (data.type === 'message_complete') {
                console.log('메시지 완료 신호 수신');
                if (this.callbacks.onComplete) {
                    this.callbacks.onComplete();
                }
                return;
            }
            
            // 어시스턴트 메시지 처리 - 다양한 형식 지원
            if (data.type === 'assistant') {
                // 모델 정보 확인 및 설정
                const model = data.model || this.currentModel;
                console.log('어시스턴트 메시지 수신 - 모델:', model);
                
                // 전체 응답 신호가 있고 내용이 없는 경우 (Meta 모델 처리)
                if (data.isFullResponse === true && !data.content) {
                    console.log('완료 신호만 받음 (내용 없음) - 모델:', model);
                    if (this.callbacks.onComplete) {
                        this.callbacks.onComplete();
                    }
                    return;
                }
                
                // 내용이 있는 경우
                if (data.content) {
                    console.log('어시스턴트 메시지 내용:', data.content);
                    if (this.callbacks.onMessage) {
                        this.callbacks.onMessage(data.content, model);
                    }
                    
                    // 스트리밍이 아니거나 완료 신호가 있는 경우
                    if (data.isFullResponse === true || data.streaming !== true) {
                        if (this.callbacks.onComplete) {
                            this.callbacks.onComplete();
                        }
                    }
                }
                return;
            }
            
            // 예전 형식의 메시지 처리 (역호환성 유지)
            if (data.message && (data.message.role === 'assistant' || data.message.role === 'MessageRole.ASSISTANT')) {
                console.log('기존 형식의 어시스턴트 메시지 수신');
                const content = data.message.content;
                const model = data.message.model || data.model || this.currentModel;
                
                if (content) {
                    console.log('메시지 내용:', content, '모델:', model);
                    if (this.callbacks.onMessage) {
                        this.callbacks.onMessage(content, model);
                    }
                    if (this.callbacks.onComplete) {
                        this.callbacks.onComplete();
                    }
                }
                return;
            }
            
            // 오류 메시지 처리
            if (data.type === 'error') {
                console.error('서버 오류:', data.data && data.data.message ? data.data.message : '알 수 없는 오류');
                if (this.callbacks.onError) {
                    this.callbacks.onError(data.data && data.data.message ? data.data.message : '서버 오류가 발생했습니다');
                }
                this.isProcessing = false;
                return;
            }
            
            // 기타 알 수 없는 메시지 유형 처리
            console.log('처리되지 않은 메시지 유형:', data);
            
            // 메시지 내용이 있다면 일단 표시 시도
            if (data.content || (data.message && data.message.content)) {
                const content = data.content || data.message.content;
                const model = data.model || (data.message && data.message.model) || this.currentModel;
                console.log('메시지 내용 있음, 업데이트 시도:', content, '모델:', model);
                if (this.callbacks.onMessage) {
                    this.callbacks.onMessage(content, model);
                }
            }
        } catch (error) {
            console.error('WebSocket 메시지 처리 오류:', error);
            console.error('원본 데이터:', event.data);
            this.isProcessing = false;
            if (this.callbacks.onError) {
                this.callbacks.onError('메시지 처리 중 오류가 발생했습니다');
            }
        }
    }

    sendMessage(content, model = null) {
        if (!content.trim() || this.isProcessing) {
            return false;
        }
        
        this.isProcessing = true;
        
        if (!model) {
            model = this.currentModel;
        }
        
        this.sendWebSocketMessage({
            type: 'message',
            content: content,
            model: model,
            session_id: this.currentSessionId
        });
        
        return true;
    }

    sendWebSocketMessage(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
            return true;
        } else {
            console.error('서버 연결이 끊어졌습니다');
            this.isProcessing = false;
            if (this.callbacks.onError) {
                this.callbacks.onError('서버 연결이 끊어졌습니다');
            }
            return false;
        }
    }

    checkStatus() {
        return this.ws ? this.ws.readyState : undefined;
    }

    setModel(model) {
        this.currentModel = model;
    }

    getModel() {
        return this.currentModel;
    }

    setSessionId(sessionId) {
        this.currentSessionId = sessionId;
    }

    getSessionId() {
        return this.currentSessionId;
    }

    setProcessing(isProcessing) {
        this.isProcessing = isProcessing;
    }

    isActiveProcessing() {
        return this.isProcessing;
    }
} 