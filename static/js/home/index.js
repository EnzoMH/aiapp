// index.js - 홈페이지 메인 진입점

// 모듈 가져오기
import * as auth from './auth.js';
import * as ui from './ui.js';
import * as fileManager from './fileManager.js';
import * as chatManager from './chatManager.js';

// 전역 상태 변수
const state = {
    currentModel: 'meta',
    currentSessionId: null,
    uploadedFiles: new Map()
};

// 이벤트 리스너 설정 함수
function setupEventListeners() {
    // 로그아웃 버튼
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', auth.handleLogout);
    }
    
    // 모델 선택 버튼들
    const modelButtons = document.querySelectorAll('.model-btn');
    if (modelButtons.length > 0) {
        modelButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                ui.handleModelChange(btn, state.currentModel, (newModel) => {
                    state.currentModel = newModel;
                });
            });
        });
    }
    
    // 파일 업로드 버튼
    const uploadBtn = document.getElementById('uploadBtn');
    const fileInput = document.getElementById('fileInput');
    if (uploadBtn && fileInput) {
        uploadBtn.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', (event) => {
            fileManager.handleFileSelection(
                event,
                (filename, result) => {
                    // 업로드된 파일 목록에 추가
                    state.uploadedFiles.set(filename, result);
                    // UI에 파일 추가
                    ui.addUploadedFileUI(filename);
                    ui.showToast('success', '파일이 성공적으로 분석되었습니다');
                },
                (errorMessage) => {
                    ui.showToast('error', `파일 업로드 오류: ${errorMessage}`);
                }
            );
        });
    }
    
    // 업로드된 파일 삭제 이벤트
    document.addEventListener('removeFile', (e) => {
        const { filename } = e.detail;
        state.uploadedFiles.delete(filename);
    });
    
    // 메시지 전송
    const sendBtn = document.getElementById('sendBtn');
    const messageInput = document.getElementById('messageInput');
    if (sendBtn && messageInput) {
        sendBtn.addEventListener('click', handleSendMessage);
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
            }
        });
        
        // 텍스트 영역 자동 크기 조절
        messageInput.addEventListener('input', ui.autoResizeTextarea);
    }
    
    // 새 채팅 버튼
    const newChatBtn = document.getElementById('newChatBtn');
    if (newChatBtn) {
        newChatBtn.addEventListener('click', handleNewChat);
    }
    
    // 관리자 기능 - 사용자 관리
    const getUsersBtn = document.getElementById('getUsersBtn');
    const closeUsersList = document.getElementById('closeUsersList');
    if (getUsersBtn) {
        getUsersBtn.addEventListener('click', auth.toggleUsersList);
    }
    if (closeUsersList) {
        closeUsersList.addEventListener('click', auth.toggleUsersList);
    }
    
    // 페이지 가시성 변경 감지
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
            initializeChat();
        }
    });
    
    // 윈도우 포커스 감지
    window.addEventListener('focus', ui.focusMessageInput);
    
    // 드래그 앤 드롭 파일 업로드
    const dropZone = document.getElementById('chat-messages');
    if (dropZone) {
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('drag-over');
        });
        
        dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('drag-over');
        });
        
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('drag-over');
            
            const files = Array.from(e.dataTransfer.files);
            files.forEach(file => {
                fileManager.uploadFile(
                    file,
                    (filename, result) => {
                        state.uploadedFiles.set(filename, result);
                        ui.addUploadedFileUI(filename);
                        ui.showToast('success', '파일이 성공적으로 분석되었습니다');
                    },
                    (errorMessage) => {
                        ui.showToast('error', `파일 업로드 오류: ${errorMessage}`);
                    },
                    ui.updateUploadProgress
                );
            });
        });
    }
}

// 메시지 전송 처리
function handleSendMessage() {
    const messageInput = document.getElementById('messageInput');
    const content = messageInput.value.trim();
    
    // 메시지 전송
    chatManager.sendMessage({
        content,
        model: state.currentModel,
        sessionId: state.currentSessionId,
        files: Array.from(state.uploadedFiles.values()),
        onStart: () => {
            // UI 업데이트
            ui.disableMessageInput();
            
            // 사용자 메시지 UI에 추가
            ui.addUserMessage(content);
            
            // 입력창 초기화
            messageInput.value = '';
            messageInput.style.height = 'auto';
            
            // 웰컴 메시지 제거
            ui.removeWelcomeMessage();
            
            // 어시스턴트 메시지 프레임 미리 추가
            ui.addAssistantMessageFrame(state.currentModel);
        },
        onError: (error) => {
            ui.showToast('error', error || '메시지 전송에 실패했습니다');
            ui.enableMessageInput();
        }
    });
}

// 새 채팅 시작
function handleNewChat() {
    chatManager.startNewChat({
        onStart: () => {
            // 채팅 영역 초기화
            const chatMessages = document.getElementById('chat-messages');
            chatMessages.innerHTML = '';
            
            // 세션 ID 초기화
            state.currentSessionId = null;
            
            // 업로드된 파일 초기화
            state.uploadedFiles.clear();
            const fileList = document.getElementById('uploadedFiles');
            if (fileList) {
                fileList.innerHTML = '';
            }
        },
        onComplete: () => {
            // 웰컴 메시지 추가
            ui.addWelcomeMessage();
            
            // 입력창 초기화 및 활성화
            const messageInput = document.getElementById('messageInput');
            if (messageInput) {
                messageInput.value = '';
                messageInput.style.height = 'auto';
            }
            
            ui.enableMessageInput();
        }
    });
}

// WebSocket 메시지 핸들러
function handleWebSocketMessage(event) {
    chatManager.handleWebSocketMessage(event, {
        onAssistantMessage: (content, model) => {
            ui.updateStreamingMessage(content, model);
        },
        onMessageComplete: (data) => {
            ui.completeStreamingMessage();
            chatManager.completeMessageProcessing();
            ui.enableMessageInput();
            
            // 세션 ID 저장 (있는 경우)
            if (data.data && data.data.session_id) {
                state.currentSessionId = data.data.session_id;
            }
        },
        onProcessing: () => {
            // 메시지 처리 중 신호 - 이미 UI에 반영되어 있으므로 추가 작업 불필요
        },
        onConnectionEstablished: () => {
            // 연결 성공 시 추가 작업 필요한 경우
        },
        onError: (data) => {
            ui.showToast('error', data.data?.message || '오류가 발생했습니다');
            chatManager.completeMessageProcessing();
            ui.enableMessageInput();
        }
    });
}

// 채팅 초기화
function initializeChat() {
    chatManager.initializeWebSocket(handleWebSocketMessage);
}

// UI 초기화 함수
function initHomeUI() {
    // 사용자 정보 로드 및 UI 업데이트
    auth.loadUserInfo();
    
    // 이벤트 리스너 설정
    setupEventListeners();
    
    // WebSocket 연결 초기화
    initializeChat();
    
    // 초기 화면에 웰컴 메시지 표시
    ui.addWelcomeMessage();
}

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    // 토큰 확인
    const token = localStorage.getItem('access_token');
    const currentPath = window.location.pathname;
    
    // 로그인 페이지 로직
    if (currentPath === '/' || currentPath === '/login') {
        // 이미 로그인된 상태면 대시보드로 리디렉션
        if (token) {
            window.location.href = '/home';
            return;
        }
        
        // 로그인 폼 처리
        const loginForm = document.getElementById('loginForm');
        if (loginForm) {
            loginForm.addEventListener('submit', auth.handleLogin);
        }
    } 
    // 홈 페이지 로직
    else if (currentPath === '/home') {
        // 로그인 안된 상태면 로그인 페이지로 리디렉션
        if (!token) {
            window.location.href = '/';
            return;
        }
        
        // UI 초기화
        initHomeUI();
    }
});

// 모듈 내보내기 (필요한 경우)
export {
    initHomeUI,
    handleSendMessage,
    handleNewChat
}; 