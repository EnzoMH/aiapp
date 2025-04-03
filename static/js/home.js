// home.js - 개선된 홈페이지 기능
// 모듈 구조로 리팩토링 됨 - /static/js/home/ 폴더의 모듈 참조

// 전역 변수
// 폴백: WebSocket 대신 ChatWebSocketManager 사용
import { ChatWebSocketManager } from '/static/js/websocket.js';

let isProcessing = false; // 메시지 처리 중 상태
let currentModel = 'claude'; // 현재 선택된 모델
let currentSessionId = null; // 현재 세션 ID
let uploadedFiles = new Map(); // 업로드된 파일 목록
let userLoggedIn = false; // 사용자 로그인 상태

// ChatWebSocketManager 인스턴스 생성
let chatWs = null;

// 페이지 로드 이벤트 리스너
document.addEventListener('DOMContentLoaded', function() {
    // 사용자의 로그인 상태를 먼저 확인
    const userId = localStorage.getItem('user_id');
    if (!userId) {
        console.error('로그인되지 않은 사용자. 로그인 페이지로 이동해야 합니다.');
        // 페이지 로드 중지
        return;
    }
    
    // 리디렉션 루프 방지를 위한 체크
    let loadCount = parseInt(sessionStorage.getItem('home_load_count') || '0');
    loadCount++;
    sessionStorage.setItem('home_load_count', loadCount.toString());
    
    // 과도한 로드 감지 시 중지
    if (loadCount > 3) {
        console.error('과도한 페이지 로드 감지. 초기화 중지.');
        sessionStorage.removeItem('home_load_count');
        sessionStorage.removeItem('homeLoaded');
        
        document.body.innerHTML = `
            <div class="min-h-screen flex items-center justify-center bg-gray-100">
                <div class="bg-white p-8 rounded-lg shadow-md max-w-md w-full text-center">
                    <h2 class="text-2xl font-bold mb-4 text-red-600">오류가 발생했습니다</h2>
                    <p class="mb-4">페이지 로드 중 문제가 발생했습니다.</p>
                    <button id="resetBtn" class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
                        다시 시도
                    </button>
                </div>
            </div>
        `;
        
        document.getElementById('resetBtn').addEventListener('click', function() {
            // 세션 스토리지 초기화
            sessionStorage.clear();
            // 페이지 새로고침
            window.location.reload();
        });
        
        return;
    }
    
    const currentPath = window.location.pathname;
    
    // 홈 페이지 로직
    if (currentPath === '/home') {
        // UI 초기화 (중복 초기화 방지 로직은 initHomeUI 내부에 구현됨)
        initHomeUI();
    }
});

// 홈 UI 초기화
function initHomeUI() {
    // 초기화 플래그 확인 - 중복 초기화 방지
    if (window.homeInitialized) {
        console.log('홈 UI가 이미 초기화됨');
        return;
    }
    
    // 초기화 플래그 설정
    window.homeInitialized = true;
    
    // 사용자 정보 로드
    loadUserInfo()
        .then((userData) => {
            if (!userData) {
                // 로드 실패 시 오류 메시지 표시하고 종료
                showError('사용자 정보를 로드할 수 없습니다. 다시 로그인해주세요.');
                document.getElementById('errorContainer').classList.remove('hidden');
                return;
            }
            
            // UI 초기화 및 이벤트 리스너 설정
            setupEventListeners();
            
            // 웹소켓 초기화
            initializeWebSocket();
            
            // 메시지 입력창 포커스
            focusMessageInput();
            
            // 성공적으로 초기화 완료 - 세션 스토리지 정리
            sessionStorage.removeItem('home_load_count');
        })
        .catch(error => {
            console.error('사용자 정보 로드 실패:', error);
            
            // 오류 종류에 따른 다른 메시지 표시
            if (error.message === '세션이 만료되었습니다') {
                showError('세션이 만료되었습니다. 로그아웃 후 다시 로그인해주세요.');
            } else {
                showError('사용자 인증에 문제가 발생했습니다. 로그아웃 후 다시 로그인해주세요.');
            }
            
            document.getElementById('errorContainer').classList.remove('hidden');
            document.getElementById('logoutBtn').classList.add('animate-pulse');
        });
}

// 사용자 정보 로드
async function loadUserInfo() {
    try {
        // 재시도 횟수 체크 - 무한 리디렉션 방지
        const redirectAttempts = parseInt(localStorage.getItem('redirect_attempts') || '0');
        if (redirectAttempts > 3) {
            console.error('너무 많은 리디렉션 시도. 사용자 로그아웃.');
            // 모든 저장 데이터 삭제
            localStorage.clear();
            sessionStorage.clear();
            window.location.replace('/');
            return null;
        }
        
        // 세션 기반 인증을 사용하여 사용자 정보 요청
        const response = await fetch('/api/me', {
            method: 'GET',
            credentials: 'include', // 세션 쿠키 포함
            headers: {
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache'
            }
        });
        
        if (!response.ok) {
            console.error('사용자 정보 요청 실패:', response.status);
            
            // 사용자 인증 실패 - 로그아웃 처리 및 로그인 페이지로 이동
            console.warn('인증 실패 - 로그아웃 처리 중');
            
            // 로컬 스토리지 및 세션 스토리지 정리
            localStorage.clear();
            sessionStorage.clear();
            
            // 백엔드에 로그아웃 요청
            try {
                await fetch('/api/logout', {
                    method: 'POST',
                    credentials: 'include'
                });
            } catch (logoutError) {
                console.error('로그아웃 처리 중 오류:', logoutError);
            }
            
            // 로그인 페이지로 즉시 이동
            console.log('로그인 페이지로 이동');
            window.location.replace('/');
            return null;
        }
        
        // 성공 시 재시도 횟수 초기화
        localStorage.removeItem('redirect_attempts');
        
        const userData = await response.json();
        console.log('사용자 정보 로드 완료:', userData);
        
        // 사용자 정보 저장
        localStorage.setItem('user_info', JSON.stringify(userData));
        
        // 사용자 역할에 따른 UI 처리
        if (userData.role === 'admin') {
            const adminSection = document.getElementById('adminSection');
            if (adminSection) adminSection.classList.remove('hidden');
        }
        
        // 사용자 정보 UI 업데이트
        const userInfoElement = document.getElementById('userInfo');
        if (userInfoElement) {
            userInfoElement.textContent = `${userData.id} (${userData.role})`;
        }
        
        userLoggedIn = true;
        return userData;
    } catch (error) {
        console.error('사용자 정보 요청 오류:', error);
        // 예외 발생 시 로그아웃 처리
        localStorage.clear();
        sessionStorage.clear();
        window.location.replace('/');
        return null;
    }
}

// 오류 메시지 표시
function showError(message) {
    const errorMessageElement = document.getElementById('errorMessage');
    if (errorMessageElement) {
        errorMessageElement.textContent = message;
        errorMessageElement.classList.remove('hidden');
    }
}

// 토스트 메시지 표시
function showToast(type, message) {
    // 토스트 컨테이너 가져오기 또는 생성
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container';
        document.body.appendChild(toastContainer);
    }
    
    // 토스트 요소 생성
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toastContainer.appendChild(toast);
    
    // 3초 후 토스트 제거
    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => {
            toastContainer.removeChild(toast);
        }, 300);
    }, 3000);
}

// 로그아웃 처리
async function handleLogout() {
    try {
        // 서버에 로그아웃 요청
        const response = await fetch('/api/logout', {
            method: 'POST',
            credentials: 'include'
        });
        
        // 로컬 스토리지 정리
        localStorage.removeItem('user_id');
        localStorage.removeItem('user_role');
        localStorage.removeItem('user_info');
        
        // 로그인 페이지로 리디렉션
        window.location.href = '/';
    } catch (error) {
        console.error('로그아웃 오류:', error);
        // 오류가 발생해도 로그인 페이지로 리디렉션
        window.location.href = '/';
    }
}

// 이벤트 리스너 설정
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

// 웹소켓 초기화
function initializeWebSocket() {
    try {
        // 새로운 ChatWebSocketManager 인스턴스 생성
        chatWs = new ChatWebSocketManager('/chat');
        
        // 메시지 핸들러 등록
        chatWs.registerHandler('chat_message', handleChatMessage);
        chatWs.registerHandler('error', handleError);
        
        // 연결 상태 변화 핸들러 등록
        chatWs.onConnectionChange((connected) => {
            if (connected) {
                console.log('채팅 서버에 연결되었습니다.');
            } else {
                console.log('채팅 서버와의 연결이 끊어졌습니다.');
            }
        });
        
        // 오류 핸들러 등록
        chatWs.onError((error) => {
            console.error('웹소켓 오류:', error);
            showToast('error', '서버 연결 중 오류가 발생했습니다');
        });
        
        // 웹소켓 연결
        chatWs.connect()
            .then(() => {
                console.log('웹소켓 연결 성공');
            })
            .catch(error => {
                console.error('웹소켓 연결 실패:', error);
                showToast('error', '서버에 연결할 수 없습니다');
            });
    } catch (error) {
        console.error('웹소켓 초기화 오류:', error);
        showToast('error', '웹소켓 초기화 중 오류가 발생했습니다');
    }
}

// 채팅 메시지 처리 핸들러
function handleChatMessage(data, event) {
    console.log('채팅 메시지 수신:', data);
    
    // 메시지 타입에 따라 처리
    if (data.type === 'assistant_message' || data.content) {
        // 어시스턴트 메시지 처리
        updateStreamingMessage(data.content, data.model || currentModel);
        
        // 스트리밍 종료 확인
        if (data.done) {
            completeStreamingMessage();
            enableMessageInput();
        }
    }
}

// 오류 메시지 처리 핸들러
function handleError(data, event) {
    console.error('오류 메시지 수신:', data);
    showToast('error', data.message || '서버에서 오류가 발생했습니다');
    enableMessageInput();
}

// 웹소켓으로 메시지 전송
function sendWebSocketMessage(message) {
    if (!chatWs) {
        console.error('웹소켓이 초기화되지 않았습니다.');
        showToast('error', '서버에 연결되지 않았습니다');
        return false;
    }
    
    // 인증 상태 확인
    if (!chatWs.isAuthenticated()) {
        console.warn('인증되지 않은 웹소켓 연결');
        
        // 로컬 스토리지의 사용자 ID 확인
        const userId = localStorage.getItem('user_id');
        if (!userId) {
            console.error('사용자 인증 정보가 없습니다');
            showToast('error', '로그인이 필요합니다');
            return false;
        }
        
        // 재인증 시도
        setTimeout(() => {
            chatWs.sendInitMessage();
        }, 100);
    }
    
    // 메시지 전송
    return chatWs.send(message);
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
        session_id: currentSessionId,
        files: Array.from(uploadedFiles.values())
    });
    
    // 어시스턴트 메시지 프레임 미리 추가
    addAssistantMessageFrame();
}

// 폴백: 텍스트 영역 자동 높이 조절
function autoResizeTextarea() {
    const textarea = this;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px'; // 최대 높이 200px 제한
}

// 폴백: 메시지 입력창 활성화
function enableMessageInput() {
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    
    if (messageInput) {
        messageInput.disabled = false;
        messageInput.focus();
    }
    if (sendBtn) sendBtn.disabled = false;
}

// 폴백: 메시지 입력창 비활성화
function disableMessageInput() {
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    
    if (messageInput) messageInput.disabled = true;
    if (sendBtn) sendBtn.disabled = true;
}

// 폴백: 메시지 입력창 자동 포커스
function focusMessageInput() {
    const messageInput = document.getElementById('messageInput');
    if (messageInput && !messageInput.disabled) {
        messageInput.focus();
    }
}

// 폴백: 채팅창 스크롤 함수
function scrollToBottom() {
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

// 폴백: 사용자 메시지 UI에 추가
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

// 폴백: 어시스턴트 메시지 프레임 미리 추가
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

// 폴백: 스트리밍 메시지 업데이트
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

// 폴백: 스트리밍 메시지 완료 처리
function completeStreamingMessage() {
    const messageDiv = document.getElementById('current-ai-message');
    if (!messageDiv) return;
    
    // ID 제거 (더 이상 현재 메시지가 아님)
    messageDiv.removeAttribute('id');
    
    // 처리 상태 초기화
    isProcessing = false;
    enableMessageInput();
}

// 폴백: 웰컴 메시지 제거
function removeWelcomeMessage() {
    const welcomeMessage = document.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.remove();
    }
}

// 폴백: 웰컴 메시지 추가
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

// 폴백: 모델 변경 처리
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

// 폴백: 첫 글자 대문자로 변환
function capitalizeFirstLetter(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
}

// 폴백: 파일 유효성 검사
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

// 폴백: 파일 업로드 처리
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

// 폴백: 파일 선택 처리
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

// 폴백: 업로드된 파일 UI에 추가
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

// 폴백: 관리자 기능 - 사용자 목록 표시 토글
function toggleUsersList() {
    const usersList = document.getElementById('usersList');
    
    if (usersList.classList.contains('hidden')) {
        loadAllUsers();
        usersList.classList.remove('hidden');
    } else {
        usersList.classList.add('hidden');
    }
}

// 폴백: 관리자 기능 - 모든 사용자 정보 로드
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

// 폴백: 새 채팅 시작
function startNewChat() {
    // 채팅 영역 초기화
    const chatMessages = document.getElementById('chat-messages');
    chatMessages.innerHTML = '';
    
    // 세션 ID 초기화
    currentSessionId = null;
    
    // 업로드된 파일 초기화
    uploadedFiles.clear();
    const fileList = document.getElementById('uploadedFiles');
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

