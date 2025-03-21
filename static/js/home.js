// home.js - 개선된 홈페이지 기능

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
            loginForm.addEventListener('submit', handleLogin);
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
    
    // 자동 저장 시작
    startAutoSave();
});

// UI 초기화 함수
function initHomeUI() {
    // 사용자 정보 로드 및 UI 업데이트
    loadUserInfo();
    
    // 이벤트 리스너 설정
    setupEventListeners();
    
    // WebSocket 연결 초기화
    initializeWebSocket();

    setupChatHistoryRefresh();
}

// 이벤트 리스너 설정 함수
function setupEventListeners() {
    // 로그아웃 버튼
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }
    
    // 모델 선택 버튼들
    const modelButtons = document.querySelectorAll('.model-btn');
    if (modelButtons.length > 0) {
        modelButtons.forEach(btn => {
            btn.addEventListener('click', () => handleModelChange(btn));
        });
    }
    
    // 파일 업로드 버튼
    const uploadBtn = document.getElementById('uploadBtn');
    const fileInput = document.getElementById('fileInput');
    if (uploadBtn && fileInput) {
        uploadBtn.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', handleFileSelection);
    }
    
    // 메시지 전송
    const sendBtn = document.getElementById('sendBtn');
    const messageInput = document.getElementById('messageInput');
    if (sendBtn && messageInput) {
        sendBtn.addEventListener('click', sendMessage);
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        
        // 텍스트 영역 자동 크기 조절
        messageInput.addEventListener('input', autoResizeTextarea);
    }
    
    // 새 채팅 버튼
    const newChatBtn = document.getElementById('newChatBtn');
    if (newChatBtn) {
        newChatBtn.addEventListener('click', startNewChat);
    }
    
    // 사이드바 새 채팅 버튼
    const newChatBtnSidebar = document.getElementById('newChatBtnSidebar');
    if (newChatBtnSidebar) {
        newChatBtnSidebar.addEventListener('click', () => {
            startNewChat();
            toggleChatHistory(); // 사이드바 닫기
        });
    }
    
    // 대화 기록 검색
    const chatHistorySearch = document.getElementById('chatHistorySearch');
    if (chatHistorySearch) {
        chatHistorySearch.addEventListener('input', filterChatHistories);
    }
    
    // 관리자 기능 - 사용자 관리
    const getUsersBtn = document.getElementById('getUsersBtn');
    const closeUsersList = document.getElementById('closeUsersList');
    if (getUsersBtn) {
        getUsersBtn.addEventListener('click', toggleUsersList);
    }
    if (closeUsersList) {
        closeUsersList.addEventListener('click', toggleUsersList);
    }
    
    // 페이지 가시성 변경 감지
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
            initializeWebSocket();
        }
    });
    
    // 윈도우 포커스 감지
    window.addEventListener('focus', focusMessageInput);
    
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
                if (validateFile(file)) {
                    uploadFile(file);
                }
            });
        });
    }

    // 대화 기록 버튼
    const chatHistoryBtn = document.getElementById('chatHistoryBtn');
    const closeChatHistory = document.getElementById('closeChatHistory');
    
    if (chatHistoryBtn) {
        chatHistoryBtn.addEventListener('click', toggleChatHistory);
    }
    if (closeChatHistory) {
        closeChatHistory.addEventListener('click', toggleChatHistory);
    }

    // 페이지 새로고침/종료 시 대화 저장
    window.addEventListener('beforeunload', async (e) => {
        if (currentSessionId) {
            await saveChatHistory();
        }
    });
}

// 사용자 정보 로드 및 UI 업데이트
async function loadUserInfo() {
    const token = localStorage.getItem('access_token');
    const userRole = localStorage.getItem('user_role');
    const userId = localStorage.getItem('user_id');
    
    console.log('토큰 확인:', token ? token.substring(0, 10) + '...' : 'null');
    console.log('사용자 역할:', userRole);
    console.log('사용자 ID:', userId);
    
    if (!token || !userRole || !userId) {
        console.warn('필요한 사용자 정보가 없습니다. 로그아웃합니다.');
        handleLogout();
        return;
    }
    
    // 사용자 정보 표시
    const userInfo = document.getElementById('userInfo');
    if (userInfo) {
        userInfo.textContent = `${userId} (${userRole})`;
    }
    
    // 관리자 메뉴 표시 설정
    const adminSection = document.getElementById('adminSection');
    if (adminSection && userRole === 'admin') {
        adminSection.classList.remove('hidden');
    }
    
    // 서버에서 현재 사용자 정보 검증
    try {
        console.log('서버에 인증 요청 보내는 중...');
        const response = await fetch('/api/me', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        console.log('서버 응답 상태:', response.status);
        
        if (!response.ok) {
            console.warn('토큰이 유효하지 않습니다. 로그아웃합니다.');
            handleLogout();
        } else {
            const userData = await response.json();
            console.log('사용자 데이터:', userData);
        }
    } catch (error) {
        console.error('Error verifying user:', error);
        showToast('error', '사용자 인증에 실패했습니다');
    }
}

// 로그인 처리 함수
async function handleLogin(event) {
    event.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorMessage = document.getElementById('errorMessage');
    
    if (!username || !password) {
        showError('아이디와 비밀번호를 모두 입력해주세요.');
        return;
    }
    
    try {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);
        
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: formData
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            showError(data.detail || '로그인에 실패했습니다.');
            return;
        }
        
        // 로그인 성공
        localStorage.setItem('access_token', data.access_token);
        
        // JWT 토큰에서 사용자 정보 추출
        const tokenPayload = parseJwt(data.access_token);
        localStorage.setItem('user_id', tokenPayload.sub);
        localStorage.setItem('user_role', tokenPayload.role);
        
        console.log('로그인 성공:', {
            token: data.access_token.substring(0, 10) + '...',
            user_id: tokenPayload.sub,
            role: tokenPayload.role
        });
        
        // 대시보드로 리디렉션
        window.location.href = '/home';
        
    } catch (error) {
        showError('서버 연결에 문제가 있습니다. 잠시 후 다시 시도해주세요.');
        console.error('Login error:', error);
    }
}

// JWT 토큰 디코딩 함수 추가
function parseJwt(token) {
    try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
        
        return JSON.parse(jsonPayload);
    } catch (e) {
        console.error('JWT 파싱 오류:', e);
        return { sub: '', role: '' };
    }
}

// 로그아웃 처리
function handleLogout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_id');
    localStorage.removeItem('user_role');
    window.location.href = '/';
}

// WebSocket 관련 변수
let ws = null;
let currentModel = 'meta';
let uploadedFiles = new Map();
let isProcessing = false;
let currentSessionId = null;

// WebSocket 초기화 함수
function initializeWebSocket() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        return;
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
            setTimeout(initializeWebSocket, delay);
            reconnectAttempts++;
        } else {
            showToast('error', '서버 연결에 실패했습니다. 페이지를 새로고침해주세요.');
        }
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        showToast('error', '서버 연결에 문제가 발생했습니다');
    };
    
    ws.onmessage = handleWebSocketMessage;
}


// WebSocket 상태 확인 함수
function checkWebSocketStatus() {
    console.log('WebSocket 상태:', ws ? ws.readyState : 'undefined');
    // 0: CONNECTING, 1: OPEN, 2: CLOSING, 3: CLOSED
    
    if (ws && ws.readyState === WebSocket.OPEN) {
        console.log('WebSocket이 정상적으로 연결되어 있습니다.');
    } else if (ws && ws.readyState === WebSocket.CLOSED) {
        console.log('WebSocket 연결이 종료되었습니다. 다시 연결을 시도합니다.');
        initializeWebSocket();
    }
    
    return ws ? ws.readyState : 'undefined';
}

// 마지막으로 받은 메시지 확인 함수
function checkLastMessage() {
    const messageDiv = document.getElementById('current-ai-message');
    if (messageDiv) {
        const contentDiv = messageDiv.querySelector('.message-content');
        if (contentDiv) {
            console.log('현재 메시지 내용:', contentDiv.textContent);
            return contentDiv.textContent;
        }
    }
    console.log('현재 활성화된 메시지가 없습니다.');
    return null;
}

// 메시지 수동 업데이트 테스트 함수
function testMessageUpdate(content, model) {
    console.log('메시지 수동 업데이트 테스트');
    
    // 현재 AI 메시지가 없다면 새로 생성
    let messageDiv = document.getElementById('current-ai-message');
    if (!messageDiv) {
        addAssistantMessageFrame();
        messageDiv = document.getElementById('current-ai-message');
    }
    
    if (messageDiv) {
        const contentDiv = messageDiv.querySelector('.message-content');
        if (contentDiv) {
            // 로딩 인디케이터 제거
            const loadingDiv = contentDiv.querySelector('.animate-pulse');
            if (loadingDiv) {
                contentDiv.removeChild(loadingDiv);
            }
            
            // 내용 업데이트
            contentDiv.textContent = content;
            console.log('메시지가 성공적으로 업데이트되었습니다.');
            return true;
        }
    }
    
    console.log('메시지 업데이트 실패: 메시지 요소를 찾을 수 없습니다.');
    return false;
}

// WebSocket 메시지 핸들러 개선
function handleWebSocketMessage(event) {
    try {
        const data = JSON.parse(event.data);
        console.log('WebSocket message received:', data);
        console.log('원본 데이터:', event.data);
        
        // 디버깅을 위한 추가 로그
        if (data.model) console.log('모델 정보:', data.model);
        if (data.streaming) console.log('스트리밍 여부:', data.streaming);
        if (data.isFullResponse) console.log('전체 응답 여부:', data.isFullResponse);
        
        // 연결 성공 메시지 처리
        if (data.type === 'connection_established') {
            console.log('연결 성공:', data.data);
            currentSessionId = data.data.session_id;
            // 모델 정보가 있으면 업데이트
            if (data.data.model) {
                currentModel = data.data.model;
                updateModelButtonState(currentModel);
            }
            showToast('success', '서버에 연결되었습니다');
            return;
        }
        
        // 메시지 완료 신호 처리
        if (data.type === 'message_complete') {
            console.log('메시지 완료 신호 수신');
            completeStreamingMessage();
            saveChatHistory();
            return;
        }
        
        // 어시스턴트 메시지 처리 - 다양한 형식 지원
        if (data.type === 'assistant') {
            // 모델 정보 확인 및 설정
            const model = data.model || currentModel;
            console.log('어시스턴트 메시지 수신 - 모델:', model);
            
            // 전체 응답 신호가 있고 내용이 없는 경우 (Meta 모델 처리)
            if (data.isFullResponse === true && !data.content) {
                console.log('완료 신호만 받음 (내용 없음) - 모델:', model);
                completeStreamingMessage();
                return;
            }
            
            // 내용이 있는 경우
            if (data.content) {
                console.log('어시스턴트 메시지 내용:', data.content);
                updateStreamingMessage(data.content, model);
                
                // 스트리밍이 아니거나 완료 신호가 있는 경우
                if (data.isFullResponse === true || data.streaming !== true) {
                    completeStreamingMessage();
                }
            }
            return;
        }
        
        // 예전 형식의 메시지 처리 (역호환성 유지)
        if (data.message && (data.message.role === 'assistant' || data.message.role === 'MessageRole.ASSISTANT')) {
            console.log('기존 형식의 어시스턴트 메시지 수신');
            const content = data.message.content;
            const model = data.message.model || data.model || currentModel;
            
            if (content) {
                console.log('메시지 내용:', content, '모델:', model);
                updateStreamingMessage(content, model);
                completeStreamingMessage();
            }
            return;
        }
        
        // 오류 메시지 처리
        if (data.type === 'error') {
            console.error('서버 오류:', data.data && data.data.message ? data.data.message : '알 수 없는 오류');
            showToast('error', data.data && data.data.message ? data.data.message : '서버 오류가 발생했습니다');
            enableMessageInput(); // 오류 발생 시 입력 가능하게 설정
            isProcessing = false;
            return;
        }
        
        // 기타 알 수 없는 메시지 유형 처리
        console.log('처리되지 않은 메시지 유형:', data);
        
        // 메시지 내용이 있다면 일단 표시 시도
        if (data.content || (data.message && data.message.content)) {
            const content = data.content || data.message.content;
            const model = data.model || (data.message && data.message.model) || currentModel;
            console.log('메시지 내용 있음, 업데이트 시도:', content, '모델:', model);
            updateStreamingMessage(content, model);
        }
    } catch (error) {
        console.error('WebSocket 메시지 처리 오류:', error);
        console.error('원본 데이터:', event.data);
        enableMessageInput(); // 오류 발생 시 입력 가능하게 설정
        isProcessing = false;
    }
}

// 더 높은 z-index 적용
const chatHistoryPanel = document.getElementById('chatHistoryPanel');
if (chatHistoryPanel) {
    chatHistoryPanel.className = 'fixed left-0 top-0 h-full w-80 bg-white border-r border-gray-200 shadow-lg z-50 transform transition-transform duration-300';
    chatHistoryPanel.style.transform = 'translateX(-100%)'; 
}

// 컨텐츠 스타일 개선
function createChatHistoryPanel() {
    const panel = document.createElement('div');
    panel.id = 'chatHistoryPanel';
    panel.className = 'fixed right-0 top-0 h-full w-80 bg-white border-l border-gray-200 shadow-lg z-30 transform transition-transform duration-300';
    panel.style.transform = 'translateX(100%)';  // 초기에는 숨김
    
    // 날짜 포맷팅
    const date = new Date(history.created_at);
    const timeStr = date.toLocaleTimeString('ko-KR', { 
        hour: '2-digit', 
        minute: '2-digit'
    });
    
    // 미리보기 텍스트 가공 (너무 길면 자르기)
    const previewText = history.preview ? 
        (history.preview.length > 65 ? history.preview.substring(0, 65) + '...' : history.preview) :
        "새 대화";
    
    item.innerHTML = `
        <div class="flex justify-between items-start">
            <span class="text-sm font-medium text-gray-800 truncate max-w-[70%]">${previewText}</span>
            <span class="text-xs text-gray-500">${timeStr}</span>
        </div>
        <div class="flex justify-between items-center mt-2">
            <span class="text-xs text-gray-500">${history.message_count || 0}개 메시지</span>
            <span class="text-xs px-1.5 py-0.5 rounded bg-gray-200 text-gray-700">${history.model}</span>
        </div>
        <button class="delete-history-btn absolute top-2 right-2 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-opacity">
            <i class="fas fa-trash-alt"></i>
        </button>
    `;
    
    // 삭제 버튼에 이벤트 리스너 추가
    const deleteBtn = item.querySelector('.delete-history-btn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', (e) => deleteSession(history.session_id, e));
    }
    
    return item;
}

// 대화 기록 패널 생성 함수 수정
function createChatHistoryPanel() {
    const chatArea = document.querySelector('.flex-grow');
    if (!chatArea) return;

    const panel = document.createElement('div');
    panel.id = 'chatHistoryPanel';
    panel.className = 'fixed right-0 top-0 h-full w-80 bg-white border-l border-gray-200 shadow-lg z-30 transform transition-transform duration-300';
    panel.style.transform = 'translateX(100%)';  // 초기에는 숨김
    
    panel.innerHTML = `
        <div class="p-4 border-b border-gray-200 flex justify-between items-center">
            <h3 class="text-lg font-semibold">대화 기록</h3>
            <button class="text-gray-500 hover:text-gray-700" onclick="toggleChatHistory()">
                <i class="fas fa-times"></i>
            </button>
        </div>
        <div id="chatHistoryList" class="overflow-y-auto h-[calc(100%-4rem)] p-4">
        </div>
    `;
    
    document.body.appendChild(panel);
    return panel;
}

// 메시지 전송 함수 개선
function sendMessage() {
    if (isProcessing) {
        console.log('Already processing a message, ignoring send request');
        return;
    }
    
    const messageInput = document.getElementById('messageInput');
    const content = messageInput.value.trim();
    
    if (!content) {
        console.log('Empty message, not sending');
        return;
    }
    
    console.log('Sending message:', content);
    
    // 전송 중 상태 설정
    isProcessing = true;
    disableMessageInput();
    
    // 웰컴 메시지 제거
    removeWelcomeMessage();
    
    // 사용자 메시지 UI에 추가
    addUserMessage(content);
    
    // 입력창 초기화
    messageInput.value = '';
    messageInput.style.height = 'auto';
    
    // 메시지 전송
    sendWebSocketMessage({
        type: 'message',
        content: content,
        model: currentModel,
        session_id: currentSessionId
    });
    
    // 어시스턴트 메시지 프레임 미리 추가
    addAssistantMessageFrame();
}

// WebSocket 메시지 전송 함수
function sendWebSocketMessage(message) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(message));
    } else {
        showToast('error', '서버 연결이 끊어졌습니다');
        isProcessing = false;
        enableMessageInput();
    }
}

// 사용자 메시지 UI에 추가
function addUserMessage(content) {
    const chatMessages = document.getElementById('chat-messages');
    
    // 메시지 컨테이너 추가 (중앙 정렬을 위함)
    let messageContainer = document.querySelector('.message-container');
    if (!messageContainer) {
        messageContainer = document.createElement('div');
        messageContainer.className = 'message-container';
        chatMessages.appendChild(messageContainer);
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user';
    messageDiv.textContent = content;
    
    messageContainer.appendChild(messageDiv);
    scrollToBottom();
}

// 어시스턴트 메시지 프레임 추가 함수 개선
function addAssistantMessageFrame() {
    console.log('Adding assistant message frame');
    const chatMessages = document.getElementById('chat-messages');
    
    // 메시지 컨테이너 찾기 또는 생성
    let messageContainer = document.querySelector('.message-container');
    if (!messageContainer) {
        console.log('Creating new message container');
        messageContainer = document.createElement('div');
        messageContainer.className = 'message-container';
        chatMessages.appendChild(messageContainer);
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant flex items-start';
    messageDiv.id = 'current-ai-message';
    
    // 아바타 이미지 (모델에 따라 다른 이미지 사용)
    const avatar = document.createElement('div');
    avatar.className = 'shrink-0 mr-3';
    
    const avatarImg = document.createElement('img');
    avatarImg.src = `/static/image/${currentModel}.png`;
    avatarImg.alt = `${currentModel} 아바타`;
    avatarImg.className = 'w-8 h-8 rounded-full';
    
    avatar.appendChild(avatarImg);
    
    // 메시지 컨텐츠 영역
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content flex-grow';
    
    // 로딩 인디케이터
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'animate-pulse';
    loadingDiv.textContent = '...';
    
    contentDiv.appendChild(loadingDiv);
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    
    messageContainer.appendChild(messageDiv);
    scrollToBottom();
}

// 스트리밍 메시지 업데이트 함수 개선
function updateStreamingMessage(content, model) {
    console.log('메시지 업데이트:', content, '모델:', model);
    
    // 현재 AI 메시지 찾기
    const messageDiv = document.getElementById('current-ai-message');
    if (!messageDiv) {
        console.error('현재 AI 메시지 요소를 찾을 수 없습니다');
        return;
    }
    
    // 아바타 이미지 업데이트 (모델에 따라)
    const avatarImg = messageDiv.querySelector('img');
    if (avatarImg && model) {
        avatarImg.src = `/static/image/${model}.png`;
        avatarImg.alt = `${model} 아바타`;
    }
    
    const contentDiv = messageDiv.querySelector('.message-content');
    if (!contentDiv) {
        console.error('메시지 내용 요소를 찾을 수 없습니다');
        return;
    }
    
    // 로딩 인디케이터 제거
    const loadingDiv = contentDiv.querySelector('.animate-pulse');
    if (loadingDiv) {
        contentDiv.removeChild(loadingDiv);
    }
    
    // 내용 업데이트
    if (!contentDiv.textContent || contentDiv.textContent === '...') {
        contentDiv.textContent = content;
    } else {
        contentDiv.textContent += content;
    }
    
    scrollToBottom();
}

// 스트리밍 메시지 완료 처리 함수 개선
function completeStreamingMessage() {
    console.log('스트리밍 메시지 완료');
    const messageDiv = document.getElementById('current-ai-message');
    if (!messageDiv) {
        console.warn('완료할 현재 AI 메시지를 찾을 수 없습니다');
        isProcessing = false;
        enableMessageInput();
        return;
    }
    
    // 내용이 있는지 확인
    const contentDiv = messageDiv.querySelector('.message-content');
    if (contentDiv && (!contentDiv.textContent || contentDiv.textContent === '...')) {
        console.warn('메시지 내용이 비어 있습니다');
        contentDiv.textContent = "메시지를 생성하지 못했습니다.";
    }
    
    // 모델 표시 추가
    const avatarImg = messageDiv.querySelector('img');
    let modelName = currentModel;
    if (avatarImg) {
        const src = avatarImg.src;
        if (src.includes('meta')) modelName = 'meta';
        else if (src.includes('claude')) modelName = 'claude';
        else if (src.includes('gemini')) modelName = 'gemini';
    }
    
    // 모델 표시가 없으면 추가
    if (contentDiv && !contentDiv.querySelector('.text-xs.text-gray-500')) {
        const modelIndicator = document.createElement('div');
        modelIndicator.className = 'text-xs text-gray-500 mt-1 text-right';
        modelIndicator.textContent = capitalizeFirstLetter(modelName);
        contentDiv.appendChild(modelIndicator);
    }
    
    // ID 제거 (더 이상 현재 메시지가 아님)
    messageDiv.removeAttribute('id');
    
    // 처리 상태 초기화
    isProcessing = false;
    enableMessageInput();
}

// 메시지 입력창 비활성화
function disableMessageInput() {
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    
    if (messageInput) messageInput.disabled = true;
    if (sendBtn) sendBtn.disabled = true;
}

// 메시지 입력창 활성화
function enableMessageInput() {
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    
    if (messageInput) {
        messageInput.disabled = false;
        messageInput.focus();
    }
    if (sendBtn) sendBtn.disabled = false;
}

// 채팅창 스크롤 함수
function scrollToBottom() {
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

// 텍스트 영역 자동 높이 조절
function autoResizeTextarea() {
    const textarea = this;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px'; // 최대 높이 200px 제한
}

// 모델 변경 처리
function handleModelChange(button) {
    const model = button.dataset.model;
    if (model === currentModel) return;
    
    // 현재 모델 업데이트
    currentModel = model;
    
    // UI 업데이트
    document.querySelectorAll('.model-btn').forEach(btn => {
        btn.classList.toggle('active', btn === button);
    });
    
    // 알림
    showToast('info', `${capitalizeFirstLetter(model)} 모델로 전환되었습니다`);
}

// 파일 선택 처리
function handleFileSelection(event) {
    const files = Array.from(event.target.files);
    if (!files.length) return;
    
    files.forEach(file => {
        // 파일 유효성 검사
        if (!validateFile(file)) return;
        
        // 파일 업로드 처리
        uploadFile(file);
    });
    
    // 파일 입력 초기화
    event.target.value = '';
}

// 파일 유효성 검사
function validateFile(file) {
    const allowedTypes = ['.pdf', '.hwp', '.hwpx', '.doc', '.docx'];
    const extension = '.' + file.name.split('.').pop().toLowerCase();
    
    if (!allowedTypes.includes(extension)) {
        showToast('error', '지원하지 않는 파일 형식입니다');
        return false;
    }
    
    if (file.size > 10 * 1024 * 1024) { // 10MB
        showToast('error', '파일 크기는 10MB를 초과할 수 없습니다');
        return false;
    }
    
    return true;
}

// 파일 업로드 처리
async function uploadFile(file) {
    try {
        showToast('info', '파일 분석 중...');
        
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch('/mainupload', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '업로드 실패');
        }
        
        const result = await response.json();
        
        // 업로드된 파일 목록에 추가
        uploadedFiles.set(file.name, result);
        
        // UI에 파일 추가
        addUploadedFileUI(file.name);
        
        showToast('success', '파일이 성공적으로 분석되었습니다');
    } catch (error) {
        console.error('File upload error:', error);
        showToast('error', `파일 업로드 오류: ${error.message}`);
    }
}

// 업로드된 파일 UI에 추가
function addUploadedFileUI(filename) {
    const uploadedFilesContainer = document.getElementById('uploadedFiles');
    if (!uploadedFilesContainer) return;
    
    const fileElement = document.createElement('div');
    fileElement.className = 'uploaded-file flex items-center gap-2 bg-gray-50 p-2 rounded';
    fileElement.setAttribute('data-filename', filename);
    
    const fileIcon = document.createElement('i');
    fileIcon.className = 'fas fa-file-alt text-gray-500';
    
    const fileName = document.createElement('span');
    fileName.className = 'file-name text-sm text-gray-700 flex-grow';
    fileName.textContent = filename;
    
    const progressContainer = document.createElement('div');
    progressContainer.className = 'progress-container w-20 h-1 bg-gray-200 rounded';
    
    const progressBar = document.createElement('div');
    progressBar.className = 'progress-bar h-full bg-blue-500 rounded';
    progressBar.style.width = '0%';
    
    const removeButton = document.createElement('button');
    removeButton.className = 'remove-file text-gray-400 hover:text-gray-600';
    removeButton.innerHTML = '<i class="fas fa-times"></i>';
    removeButton.addEventListener('click', () => {
        uploadedFiles.delete(filename);
        fileElement.remove();
    });
    
    progressContainer.appendChild(progressBar);
    fileElement.appendChild(fileIcon);
    fileElement.appendChild(fileName);
    fileElement.appendChild(progressContainer);
    fileElement.appendChild(removeButton);
    
    uploadedFilesContainer.appendChild(fileElement);
}

// 웰컴 메시지 제거 함수 개선
function removeWelcomeMessage() {
    console.log('Removing welcome message');
    const welcomeMessage = document.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.remove();
        console.log('Welcome message removed');
    } else {
        console.log('No welcome message found to remove');
    }
}

// 세션 상태 업데이트 함수 추가
async function updateSessionStatus(sessionId, isActive) {
    if (!sessionId) return;
    
    try {
        const response = await fetch(`/api/chat/session/${sessionId}/status`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify({ active: isActive })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            console.error('세션 상태 업데이트 실패:', errorData);
            return false;
        }
        
        return true;
    } catch (error) {
        console.error('세션 상태 업데이트 오류:', error);
        return false;
    }
}
// 새 채팅 시작
// startNewChat 함수 수정
function startNewChat() {
    // 현재 세션이 있으면 비활성화
    if (currentSessionId) {
        // 저장 먼저 수행
        saveChatHistory().then(() => {
            // 그 다음 세션 비활성화
            updateSessionStatus(currentSessionId, false);
        });
    }
    
    // 채팅 영역 초기화
    const chatMessages = document.getElementById('chat-messages');
    chatMessages.innerHTML = '';
    
    // 세션 ID 초기화
    currentSessionId = null;
    
    // 업로드된 파일 초기화
    uploadedFiles.clear();
    const fileList = document.getElementById('file-list');
    if (fileList) {
        fileList.innerHTML = '';
    }
    
    // 웰컴 메시지 추가
    addWelcomeMessage();
    
    // 입력창 초기화 및 활성화
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.value = '';
        messageInput.style.height = 'auto';
    }
    
    isProcessing = false;
    enableMessageInput();
}

// 웰컴 메시지 추가
function addWelcomeMessage() {
    const chatMessages = document.getElementById('chat-messages');
    chatMessages.innerHTML = ''; // 기존 메시지 제거
    
    const welcomeDiv = document.createElement('div');
    welcomeDiv.className = 'welcome-message text-center py-10';
    welcomeDiv.innerHTML = `
        <h2 class="text-2xl font-bold text-gray-800 mb-3">AI 어시스턴트에 오신 것을 환영합니다</h2>
        <p class="text-gray-600 mb-6 max-w-md mx-auto">질문하거나 파일을 업로드하여 시작하세요</p>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl mx-auto">
            <div class="p-4 bg-white rounded-lg border border-gray-200 text-left">
                <h3 class="font-medium text-gray-800 mb-2">RFP 문서 분석</h3>
                <p class="text-sm text-gray-600">RFP 문서를 업로드하여 핵심 내용을 분석하고 통찰력을 얻으세요.</p>
            </div>
            <div class="p-4 bg-white rounded-lg border border-gray-200 text-left">
                <h3 class="font-medium text-gray-800 mb-2">제안서 작성 지원</h3>
                <p class="text-sm text-gray-600">AI가 제안서 작성을 도와 경쟁력 있는 내용을 구성하세요.</p>
            </div>
        </div>
    `;
    
    chatMessages.appendChild(welcomeDiv);
    
    // 기존 메시지 컨테이너 제거
    const existingContainer = document.querySelector('.message-container');
    if (existingContainer) {
        existingContainer.remove();
    }
}

// 관리자 기능 - 사용자 목록 표시 토글
function toggleUsersList() {
    const usersList = document.getElementById('usersList');
    
    if (usersList.classList.contains('hidden')) {
        loadAllUsers();
        usersList.classList.remove('hidden');
    } else {
        usersList.classList.add('hidden');
    }
}

// 관리자 기능 - 모든 사용자 정보 로드
async function loadAllUsers() {
    const token = localStorage.getItem('access_token');
    const usersListContent = document.getElementById('usersListContent');
    
    if (!token || !usersListContent) return;
    
    try {
        const response = await fetch('/api/admin/users', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            usersListContent.innerHTML = '<p class="text-red-500">권한이 없거나 오류가 발생했습니다.</p>';
            return;
        }
        
        const users = await response.json();
        
        if (users.length === 0) {
            usersListContent.innerHTML = '<p>등록된 사용자가 없습니다.</p>';
            return;
        }
        
        // 사용자 목록 표시
        let html = '<table class="min-w-full divide-y divide-gray-200 mt-2">';
        html += '<thead class="bg-gray-50"><tr>';
        html += '<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>';
        html += '<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">권한</th>';
        html += '</tr></thead>';
        html += '<tbody class="bg-white divide-y divide-gray-200">';
        
        users.forEach(user => {
            html += `<tr>
                <td class="px-4 py-2 whitespace-nowrap text-sm text-gray-900">${user.id}</td>
                <td class="px-4 py-2 whitespace-nowrap text-sm text-gray-900">${user.role}</td>
            </tr>`;
        });
        
        html += '</tbody></table>';
        usersListContent.innerHTML = html;
        
    } catch (error) {
        usersListContent.innerHTML = '<p class="text-red-500">서버 연결에 문제가 있습니다.</p>';
        console.error('Error loading users:', error);
    }
}

// 토스트 알림 표시
function showToast(type, message) {
    // 토스트 컨테이너 확인/생성
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    
    // 토스트 엘리먼트 생성
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    // 컨테이너에 추가
    container.appendChild(toast);
    
    // 자동 제거 타이머 설정
    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// 에러 메시지 표시 (로그인 페이지용)
function showError(message) {
    const errorMessage = document.getElementById('errorMessage');
    if (errorMessage) {
        errorMessage.textContent = message;
        errorMessage.classList.remove('hidden');
    }
}

// 첫 글자 대문자로 변환
function capitalizeFirstLetter(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
}

// 메시지 입력창 자동 포커스
function focusMessageInput() {
    const messageInput = document.getElementById('messageInput');
    if (messageInput && !messageInput.disabled) {
        messageInput.focus();
    }
}

// 파일 업로드 진행 상태 표시
function updateUploadProgress(filename, progress) {
    const fileElement = document.querySelector(`.uploaded-file[data-filename="${filename}"]`);
    if (fileElement) {
        const progressBar = fileElement.querySelector('.progress-bar');
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
        }
    }
}

// 메시지 마크다운 렌더링
function renderMarkdown(content) {
    if (typeof marked !== 'undefined') {
        try {
            // XSS 방지를 위한 설정
            marked.setOptions({
                sanitize: true,
                breaks: true
            });
            return marked.parse(content);
        } catch (error) {
            console.error('마크다운 렌더링 오류:', error);
            return content;
        }
    }
    return content;
}

// 코드 하이라이팅
function highlightCode() {
    if (typeof Prism !== 'undefined') {
        Prism.highlightAll();
    }
}

// 메시지 전송 전 유효성 검사
function validateMessage(content) {
    if (!content.trim()) {
        showToast('error', '메시지를 입력해주세요');
        return false;
    }
    return true;
}

// 웹소켓 재연결 로직 개선
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;

// 대화 기록 패널 토글 함수 수정
function toggleChatHistory() {
    console.log('토글 대화 기록 패널');
    const panel = document.getElementById('chatHistoryPanel');
    if (!panel) {
        console.error('대화 기록 패널을 찾을 수 없습니다');
        return;
    }
    
    const isHidden = panel.style.transform === 'translateX(100%)' || panel.style.transform === '';
    panel.style.transform = isHidden ? 'translateX(0)' : 'translateX(100%)';
    
    if (isHidden) {
        // 패널이 표시될 때 대화 기록 로드
        loadChatHistories();
    }
}

// 대화 기록 불러오기 함수 최적화
async function loadChatHistories() {
    const historyList = document.getElementById('chatHistoryList');
    if (!historyList) return;

    // 로딩 표시
    historyList.innerHTML = '<div class="p-4 text-center text-gray-500"><div class="spinner mx-auto mb-2"></div>대화 기록을 불러오는 중...</div>';

    try {
        const token = localStorage.getItem('access_token');
        if (!token) {
            historyList.innerHTML = '<div class="p-4 text-center text-gray-500">로그인이 필요합니다</div>';
            return;
        }

        // API 호출
        const response = await fetch('/api/chat/recent-sessions', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error('대화 기록을 불러올 수 없습니다');
        }

        const sessions = await response.json();
        
        if (sessions.length === 0) {
            historyList.innerHTML = '<div class="p-4 text-center text-gray-500">저장된 대화 기록이 없습니다</div>';
            return;
        }
        
        // 그룹화 및 렌더링
        const groupedSessions = groupSessionsByDate(sessions);
        renderGroupedSessions(groupedSessions, historyList);
    } catch (error) {
        console.error('대화 기록 로드 오류:', error);
        historyList.innerHTML = `<div class="p-4 text-center text-red-500">대화 기록을 불러올 수 없습니다: ${error.message}</div>`;
    }
}

// 대화 기록을 날짜별로 그룹화하는 함수
// 날짜별 세션 그룹화
function groupSessionsByDate(sessions) {
    const groups = {
        '오늘': [],
        '지난 7일': [],
        '지난 30일': [],
        '2024년': [],
        '2023년': []
    };
    
    const today = new Date();
    const weekAgo = new Date(today);
    weekAgo.setDate(today.getDate() - 7);
    
    const monthAgo = new Date(today);
    monthAgo.setDate(today.getDate() - 30);
    
    sessions.forEach(session => {
        const sessionDate = new Date(session.created_at);
        
        if (isSameDay(sessionDate, today)) {
            groups['오늘'].push(session);
        } else if (sessionDate >= weekAgo) {
            groups['지난 7일'].push(session);
        } else if (sessionDate >= monthAgo) {
            groups['지난 30일'].push(session);
        } else if (sessionDate.getFullYear() === 2024) {
            groups['2024년'].push(session);
        } else if (sessionDate.getFullYear() === 2023) {
            groups['2023년'].push(session);
        }
    });
    
    // 빈 그룹 제거
    Object.keys(groups).forEach(key => {
        if (groups[key].length === 0) {
            delete groups[key];
        }
    });
    
    return groups;
}

// 그룹화된 세션 렌더링
function renderGroupedSessions(groups, container) {
    container.innerHTML = '';
    
    Object.keys(groups).forEach(dateGroup => {
        // 날짜 헤더 생성
        const dateHeader = document.createElement('div');
        dateHeader.className = 'text-xs font-semibold text-gray-500 uppercase p-2 mt-2';
        dateHeader.textContent = dateGroup;
        container.appendChild(dateHeader);
        
        // 해당 날짜의 세션들 렌더링
        groups[dateGroup].forEach(session => {
            const sessionItem = document.createElement('div');
            sessionItem.className = 'chat-history-item hover:bg-gray-100 rounded-md';
            sessionItem.onclick = () => loadChatSession(session.session_id);
            
            const title = session.title || "새 대화";
            const modelTag = getModelTag(session.model);
            
            sessionItem.innerHTML = `
                <div class="p-2">
                    <div class="flex justify-between items-center">
                        <span class="text-sm font-medium text-gray-800">${title}</span>
                        <span class="model-tag ${session.model}">${modelTag}</span>
                    </div>
                    <div class="text-xs text-gray-500 mt-1">${formatDateTime(session.created_at)}</div>
                </div>
            `;
            
            container.appendChild(sessionItem);
        });
    });
}

// 모델 태그 생성
function getModelTag(model) {
    switch (model) {
        case 'meta': return 'Meta';
        case 'claude': return 'Claude';
        case 'gemini': return 'Gemini';
        default: return 'AI';
    }
}

// 날짜 시간 형식화
function formatDateTime(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleString('ko-KR', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// 같은 날짜인지 확인하는 함수
function isSameDay(date1, date2) {
    return date1.getFullYear() === date2.getFullYear() &&
           date1.getMonth() === date2.getMonth() &&
           date1.getDate() === date2.getDate();
}

// 특정 대화 세션 불러오기 함수 개선
async function loadChatSession(sessionId) {
    try {
        // 로딩 표시
        const chatMessages = document.getElementById('chat-messages');
        if (chatMessages) {
            chatMessages.innerHTML = '<div class="flex justify-center items-center h-full"><div class="spinner mr-3"></div><span class="text-gray-500">대화를 불러오는 중...</span></div>';
        }
        
        const token = localStorage.getItem('access_token');
        if (!token) {
            showToast('error', '로그인이 필요합니다');
            return;
        }

        const response = await fetch(`/api/chat/session/${sessionId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '대화 세션 로드 실패');
        }

        const session = await response.json();
        console.log('세션 불러오기 성공:', session);
        
        // 현재 대화 초기화
        chatMessages.innerHTML = '';
        currentSessionId = sessionId;
        
        // 세션의 모델 정보 적용
        currentModel = session.model || 'meta';
        console.log('사용 모델:', currentModel);
        
        // UI에 모델 버튼 상태 업데이트
        updateModelButtonState(currentModel);

        // 메시지 컨테이너 생성
        const messageContainer = document.createElement('div');
        messageContainer.className = 'message-container';
        chatMessages.appendChild(messageContainer);

        // 메시지 복원
        if (session.messages && session.messages.length > 0) {
            session.messages.forEach(msg => {
                console.log('메시지 복원:', msg);
                
                if (msg.role === 'user') {
                    // 사용자 메시지
                    const messageDiv = document.createElement('div');
                    messageDiv.className = 'message user';
                    messageDiv.textContent = msg.content;
                    messageContainer.appendChild(messageDiv);
                } else {
                    // AI 응답 메시지
                    const messageDiv = document.createElement('div');
                    messageDiv.className = 'message assistant flex items-start';
                    
                    // 아바타 이미지
                    const avatar = document.createElement('div');
                    avatar.className = 'shrink-0 mr-3';
                    
                    const avatarImg = document.createElement('img');
                    avatarImg.src = `/static/image/${msg.model || currentModel}.png`;
                    avatarImg.alt = `${msg.model || currentModel} 아바타`;
                    avatarImg.className = 'w-8 h-8 rounded-full';
                    
                    avatar.appendChild(avatarImg);
                    
                    // 메시지 컨텐츠 영역
                    const contentDiv = document.createElement('div');
                    contentDiv.className = 'message-content flex-grow';
                    contentDiv.textContent = msg.content;
                    
                    // 모델 표시
                    const modelIndicator = document.createElement('div');
                    modelIndicator.className = 'text-xs text-gray-500 mt-1 text-right';
                    modelIndicator.textContent = capitalizeFirstLetter(msg.model || currentModel);
                    contentDiv.appendChild(modelIndicator);
                    
                    messageDiv.appendChild(avatar);
                    messageDiv.appendChild(contentDiv);
                    messageContainer.appendChild(messageDiv);
                }
            });
        } else {
            // 메시지가 없는 경우 웰컴 메시지 표시
            addWelcomeMessage();
        }

        // 대화 기록 패널 닫기
        toggleChatHistory();
        
        // 맨 아래로 스크롤
        scrollToBottom();
        
        showToast('success', '대화를 불러왔습니다');
    } catch (error) {
        console.error('대화 세션 로드 오류:', error);
        showToast('error', `대화를 불러올 수 없습니다: ${error.message}`);
        
        // 오류 시 새 채팅 시작
        startNewChat();
    }
}

// 모델 버튼 상태 업데이트 함수 추가
function updateModelButtonState(model) {
    document.querySelectorAll('.model-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.model === model);
    });
}

// 대화 기록 검색/필터링 함수
function filterChatHistories() {
    const searchTerm = document.getElementById('chatHistorySearch').value.toLowerCase().trim();
    const historyItems = document.querySelectorAll('.chat-history-item');
    
    let hasResults = false;
    
    historyItems.forEach(item => {
        const parentGroup = item.closest('.group') || item.parentElement;
        const content = item.textContent.toLowerCase();
        
        if (content.includes(searchTerm) || searchTerm === '') {
            parentGroup.style.display = 'block';
            hasResults = true;
        } else {
            parentGroup.style.display = 'none';
        }
    });
    
    // 검색 결과가 없을 때 메시지 표시
    const noResultsEl = document.getElementById('no-search-results');
    if (!hasResults && searchTerm !== '') {
        if (!noResultsEl) {
            const chatHistoryList = document.getElementById('chatHistoryList');
            const noResults = document.createElement('div');
            noResults.id = 'no-search-results';
            noResults.className = 'p-4 text-center text-gray-500';
            noResults.textContent = `"${searchTerm}"에 대한 검색 결과가 없습니다`;
            chatHistoryList.appendChild(noResults);
        }
    } else if (noResultsEl) {
        noResultsEl.remove();
    }
    
    // 날짜 헤더 표시/숨기기
    const dateHeaders = document.querySelectorAll('#chatHistoryList h3');
    dateHeaders.forEach(header => {
        const nextElement = header.nextElementSibling;
        let hasVisibleItem = false;
        
        // 이 날짜 아래에 표시되는 항목이 있는지 확인
        let current = nextElement;
        while (current && !current.matches('h3')) {
            if (current.style.display !== 'none') {
                hasVisibleItem = true;
                break;
            }
            current = current.nextElementSibling;
        }
        
        // 표시되는 항목이 없으면 헤더도 숨김
        header.style.display = hasVisibleItem ? 'block' : 'none';
    });
}

// 주기적 자동 저장 설정
let autoSaveInterval;

function startAutoSave() {
    // 기존 인터벌 클리어
    if (autoSaveInterval) {
        clearInterval(autoSaveInterval);
    }
    
    // 30초마다 자동 저장
    autoSaveInterval = setInterval(async () => {
        if (currentSessionId) {
            await saveChatHistory();
        }
    }, 30000);
}

// 자동 저장 중지
function stopAutoSave() {
    if (autoSaveInterval) {
        clearInterval(autoSaveInterval);
        autoSaveInterval = null;
    }
}

// 대화 저장 함수 추가
async function saveChatHistory() {
    if (!currentSessionId) {
        console.log('세션 ID가 없어 저장할 수 없습니다');
        return false;
    }
    
    // 메시지 컨테이너에서 모든 메시지 수집
    const messageContainer = document.querySelector('.message-container');
    if (!messageContainer) {
        console.log('저장할 메시지가 없습니다');
        return false;
    }
    
    const messages = messageContainer.querySelectorAll('.message');
    if (messages.length === 0) {
        console.log('저장할 메시지가 없습니다');
        return false;
    }
    
    // 메시지 데이터 구성
    const messageData = Array.from(messages).map(msg => {
        if (msg.classList.contains('user')) {
            return {
                role: 'user',
                content: msg.textContent
            };
        } else {
            const contentEl = msg.querySelector('.message-content');
            const modelEl = contentEl ? contentEl.querySelector('.text-xs.text-gray-500') : null;
            
            // 모델 정보 추출 (있을 경우)
            let modelName = currentModel;
            if (modelEl) {
                const modelText = modelEl.textContent.toLowerCase();
                if (modelText.includes('meta')) modelName = 'meta';
                else if (modelText.includes('claude')) modelName = 'claude';
                else if (modelText.includes('gemini')) modelName = 'gemini';
            }
            
            // 컨텐츠에서 모델 표시 텍스트 제외
            let content = contentEl ? contentEl.textContent : msg.textContent;
            if (modelEl && contentEl) {
                content = content.replace(modelEl.textContent, '').trim();
            }
            
            return {
                role: 'assistant',
                content: content,
                model: modelName
            };
        }
    });
    
    try {
        console.log('세션 ID에 대한 대화 저장:', currentSessionId);
        
        const response = await fetch('/api/chat/history', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify({
                session_id: currentSessionId,
                messages: messageData,
                model: currentModel
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            console.error('저장 실패:', errorData);
            return false;
        }
        
        console.log('대화가 성공적으로 저장되었습니다');
        return true;
    } catch (error) {
        console.error('대화 저장 오류:', error);
        return false;
    }
}

// 주기적으로 대화 기록 갱신하는 함수
function setupChatHistoryRefresh() {
    // 5분마다 대화 기록 갱신 (300000ms)
    const refreshInterval = setInterval(() => {
        // 패널이 열려있는 경우에만 갱신
        const panel = document.getElementById('chatHistoryPanel');
        if (panel && panel.style.transform === 'translateX(0)') {
            loadChatHistories();
        }
    }, 300000);
    
    // 페이지 언로드 시 인터벌 정리
    window.addEventListener('beforeunload', () => {
        clearInterval(refreshInterval);
    });
}

// 대화 세션 삭제 함수
async function deleteSession(sessionId, event) {
    // 이벤트 버블링 방지 (부모 요소 클릭 이벤트 전파 방지)
    event.stopPropagation();
    
    if (!confirm('이 대화를 삭제하시겠습니까?')) {
        return;
    }
    
    try {
        const token = localStorage.getItem('access_token');
        if (!token) {
            showToast('error', '로그인이 필요합니다');
            return;
        }

        const response = await fetch(`/api/chat/session/${sessionId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error('대화 삭제에 실패했습니다');
        }

        // 성공 시 목록 갱신
        showToast('success', '대화가 삭제되었습니다');
        loadChatHistories();
        
        // 현재 보고 있던 세션이 삭제된 세션이라면 새 채팅 시작
        if (currentSessionId === sessionId) {
            startNewChat();
        }
    } catch (error) {
        console.error('대화 세션 삭제 오류:', error);
        showToast('error', error.message);
    }
}

// 대화 제목 자동 생성 함수
async function generateChatTitle(sessionId) {
    if (!sessionId) return "새 대화";
    
    try {
        // 첫 번째 사용자 메시지 가져오기
        const messages = document.querySelectorAll('.message.user');
        if (messages.length === 0) return "새 대화";
        
        // 첫 번째 메시지의 내용 (너무 길면 잘라내기)
        const firstMessage = messages[0].textContent.trim();
        const title = firstMessage.length > 30 ? 
            firstMessage.substring(0, 30) + "..." : 
            firstMessage;
            
        // 세션 제목 업데이트 API 호출
        await fetch(`/api/chat/session/${sessionId}/title`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify({ title: title })
        });
        
        return title;
    } catch (error) {
        console.error('대화 제목 생성 오류:', error);
        return "새 대화";
    }
}