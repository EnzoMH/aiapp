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
});

// UI 초기화 함수
function initHomeUI() {
    // 사용자 정보 로드 및 UI 업데이트
    loadUserInfo();
    
    // 이벤트 리스너 설정
    setupEventListeners();
    
    // WebSocket 연결 초기화
    initializeWebSocket();
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

// WebSocket 메시지 수신 처리
function handleWebSocketMessage(event) {
    try {
        const data = JSON.parse(event.data);
        console.log('WebSocket 메시지 수신:', data);
        
        switch (data.type) {
            case 'assistant':
                if (data.streaming) {
                    updateStreamingMessage(data.content, data.model);
                } else if (data.isFullResponse) {
                    completeStreamingMessage();
                }
                break;
                
            case 'message_complete':
                // 메시지 처리 완료 신호 처리
                completeStreamingMessage();
                // 세션 ID 저장 (있는 경우)
                if (data.data && data.data.session_id) {
                    currentSessionId = data.data.session_id;
                }
                break;
                
            case 'processing':
                // 메시지 처리 중 신호 - 이미 UI에 반영되어 있으므로 추가 작업 불필요
                break;
                
            case 'connection_established':
                console.log('WebSocket 연결 성공:', data.data);
                break;
                
            case 'error':
                showToast('error', data.data?.message || '오류가 발생했습니다');
                isProcessing = false;
                enableMessageInput();
                break;
                
            default:
                console.warn('알 수 없는 메시지 유형:', data.type, data);
        }
    } catch (error) {
        console.error('WebSocket 메시지 처리 오류:', error);
    }
}

// 메시지 전송 함수
function sendMessage() {
    if (isProcessing) return;
    
    const messageInput = document.getElementById('messageInput');
    const content = messageInput.value.trim();
    
    if (!content) return;
    
    // 전송 중 상태 설정
    isProcessing = true;
    disableMessageInput();
    
    // 사용자 메시지 UI에 추가
    addUserMessage(content);
    
    // 입력창 초기화
    messageInput.value = '';
    messageInput.style.height = 'auto';
    
    // 웰컴 메시지 제거
    removeWelcomeMessage();
    
    // 메시지 전송
    sendWebSocketMessage({
        type: 'message',
        content: content,
        model: currentModel,
        session_id: currentSessionId,  // 이미 올바르게 구현되어 있음
        files: Array.from(uploadedFiles.values())
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

// 어시스턴트 메시지 프레임 미리 추가
function addAssistantMessageFrame() {
    const chatMessages = document.getElementById('chat-messages');
    
    // 메시지 컨테이너 찾기 또는 생성
    let messageContainer = document.querySelector('.message-container');
    if (!messageContainer) {
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

// 스트리밍 메시지 업데이트
function updateStreamingMessage(content, model) {
    // 현재 AI 메시지 컨테이너 찾기
    const messageDiv = document.getElementById('current-ai-message');
    if (!messageDiv) return;
    
    const contentDiv = messageDiv.querySelector('.message-content');
    if (!contentDiv) return;
    
    // 로딩 인디케이터 제거
    const loadingDiv = contentDiv.querySelector('.animate-pulse');
    if (loadingDiv) {
        contentDiv.removeChild(loadingDiv);
    }
    
    // 데이터 속성에 원본 텍스트 누적 저장
    if (!contentDiv.dataset.originalText) {
        contentDiv.dataset.originalText = '';
    }
    
    contentDiv.dataset.originalText += content;
    
    // 모델이 Gemini인 경우 마크다운 처리
    if (model === 'gemini' && typeof marked !== 'undefined') {
        try {
            contentDiv.innerHTML = marked.parse(contentDiv.dataset.originalText);
        } catch (error) {
            console.error('마크다운 처리 오류:', error);
            contentDiv.textContent = contentDiv.dataset.originalText;
        }
    } else {
        contentDiv.textContent = contentDiv.dataset.originalText;
    }
    
    scrollToBottom();
}

// 스트리밍 메시지 완료 처리
function completeStreamingMessage() {
    const messageDiv = document.getElementById('current-ai-message');
    if (!messageDiv) return;
    
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

// 웰컴 메시지 제거
function removeWelcomeMessage() {
    const welcomeMessage = document.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.remove();
    }
}

// 새 채팅 시작
function startNewChat() {
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