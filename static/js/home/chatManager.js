// chatManager.js - 채팅 관련 기능

import { showToast } from './utils.js';

// WebSocket 관련 변수
let ws = null;
let isProcessing = false;
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;

// WebSocket 초기화 함수
function initializeWebSocket(onMessage) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        return ws;
    }
    
    // 토큰 가져오기
    const token = localStorage.getItem('access_token');
    const tokenParam = token ? `?token=${token}` : '';
    
    ws = new WebSocket(`ws://${window.location.host}/chat${tokenParam}`);
    
    ws.onopen = () => {
        console.log('WebSocket connected');
        showToast('success', '서버에 연결되었습니다');
        reconnectAttempts = 0;
    };
    
    ws.onclose = () => {
        console.log('WebSocket disconnected');
        if (reconnectAttempts < maxReconnectAttempts) {
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
            showToast('info', `재연결 시도 중... (${reconnectAttempts + 1}/${maxReconnectAttempts})`);
            setTimeout(() => initializeWebSocket(onMessage), delay);
            reconnectAttempts++;
        } else {
            showToast('error', '서버 연결에 실패했습니다. 페이지를 새로고침해주세요.');
        }
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        showToast('error', '서버 연결에 문제가 발생했습니다');
    };
    
    if (typeof onMessage === 'function') {
        ws.onmessage = onMessage;
    }
    
    return ws;
}

// WebSocket 메시지 수신 처리 (기본 핸들러)
function handleWebSocketMessage(event, callbacks) {
    try {
        const data = JSON.parse(event.data);
        console.log('WebSocket 메시지 수신:', data);
        
        const {
            onAssistantMessage,
            onMessageComplete,
            onProcessing,
            onConnectionEstablished,
            onError
        } = callbacks || {};
        
        switch (data.type) {
            case 'assistant':
                if (data.streaming && typeof onAssistantMessage === 'function') {
                    onAssistantMessage(data.content, data.model);
                } else if (data.isFullResponse && typeof onMessageComplete === 'function') {
                    onMessageComplete(data);
                }
                break;
                
            case 'message_complete':
                // 메시지 처리 완료 신호 처리
                if (typeof onMessageComplete === 'function') {
                    onMessageComplete(data);
                }
                break;
                
            case 'processing':
                // 메시지 처리 중 신호
                if (typeof onProcessing === 'function') {
                    onProcessing(data);
                }
                break;
                
            case 'connection_established':
                console.log('WebSocket 연결 성공:', data.data);
                if (typeof onConnectionEstablished === 'function') {
                    onConnectionEstablished(data);
                }
                break;
                
            case 'error':
                console.error('WebSocket 오류:', data.data?.message || '알 수 없는 오류');
                if (typeof onError === 'function') {
                    onError(data);
                }
                break;
                
            default:
                console.warn('알 수 없는 메시지 유형:', data.type, data);
        }
    } catch (error) {
        console.error('WebSocket 메시지 처리 오류:', error);
    }
}

// WebSocket 메시지 전송 함수
function sendWebSocketMessage(message, onError) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(message));
        return true;
    } else {
        console.error('WebSocket이 연결되어 있지 않습니다');
        if (typeof onError === 'function') {
            onError('서버 연결이 끊어졌습니다');
        }
        return false;
    }
}

// 메시지 전송 함수
function sendMessage(options) {
    const {
        content,
        model,
        sessionId,
        files,
        onStart,
        onComplete,
        onError
    } = options || {};
    
    if (isProcessing) return false;
    
    if (!content || content.trim() === '') {
        if (typeof onError === 'function') {
            onError('메시지를 입력해주세요');
        }
        return false;
    }
    
    // 전송 중 상태 설정
    isProcessing = true;
    
    // 시작 콜백 호출
    if (typeof onStart === 'function') {
        onStart();
    }
    
    // 메시지 전송
    const messageSent = sendWebSocketMessage(
        {
            type: 'message',
            content: content,
            model: model,
            session_id: sessionId,
            files: files
        },
        (error) => {
            isProcessing = false;
            if (typeof onError === 'function') {
                onError(error);
            }
        }
    );
    
    // 전송 실패 시 처리
    if (!messageSent) {
        isProcessing = false;
        return false;
    }
    
    return true;
}

// 새 채팅 시작
function startNewChat(callbacks) {
    const {
        onStart,
        onComplete
    } = callbacks || {};
    
    // 처리 상태 초기화
    isProcessing = false;
    
    // 시작 콜백 호출
    if (typeof onStart === 'function') {
        onStart();
    }
    
    // 완료 콜백 호출
    if (typeof onComplete === 'function') {
        onComplete();
    }
    
    return true;
}

// 메시지 전송 완료 처리
function completeMessageProcessing() {
    isProcessing = false;
}

// 메시지 전송 전 유효성 검사
function validateMessage(content) {
    if (!content.trim()) {
        return {
            valid: false,
            message: '메시지를 입력해주세요'
        };
    }
    return {
        valid: true
    };
}

// 진행 중인지 확인하는 함수
function isMessageProcessing() {
    return isProcessing;
}

// 모듈 내보내기
export {
    initializeWebSocket,
    handleWebSocketMessage,
    sendWebSocketMessage,
    sendMessage,
    startNewChat,
    completeMessageProcessing,
    validateMessage,
    isMessageProcessing
}; 