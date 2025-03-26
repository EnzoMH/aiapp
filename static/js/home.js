// home.js - 개선된 홈페이지 기능 (모듈화 버전)
import { WebSocketManager } from './homeutil/websocket.js';
import { AuthManager } from './homeutil/auth.js';
import { ChatHistoryManager } from './homeutil/chat-history.js';
import { UIManager } from './homeutil/ui-manager.js';
import { FileHandler } from './homeutil/file-handler.js';

// 전역 인스턴스 선언
let wsManager, authManager, chatHistoryManager, uiManager, fileHandler;

document.addEventListener('DOMContentLoaded', function() {
    // 모듈 인스턴스 초기화
    authManager = new AuthManager();
    wsManager = new WebSocketManager();
    chatHistoryManager = new ChatHistoryManager();
    uiManager = new UIManager();
    fileHandler = new FileHandler();
    
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
        
        // 대화 기록 패널 위치 초기화
        const chatHistoryPanel = document.getElementById('chatHistoryPanel');
        if (chatHistoryPanel) {
            chatHistoryPanel.style.transform = 'translateX(-100%)';
        }
    }

    // 자동 저장 시작
    chatHistoryManager.startAutoSave();
});

// 로그인 처리 함수
async function handleLogin(event) {
    event.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    if (!username || !password) {
        uiManager.showError('아이디와 비밀번호를 모두 입력해주세요.');
        return;
    }
    
    try {
        const result = await AuthManager.login(username, password);
        
        if (!result.success) {
            uiManager.showError(result.error);
            return;
        }
        
        // 대시보드로 리디렉션
        window.location.href = '/home';
    } catch (error) {
        uiManager.showError('서버 연결에 문제가 있습니다. 잠시 후 다시 시도해주세요.');
        console.error('Login error:', error);
    }
}

// UI 초기화 함수
function initHomeUI() {
    // 사용자 정보 로드 및 UI 업데이트
    loadUserInfo();
    
    // 이벤트 리스너 설정
    setupEventListeners();
    
    // WebSocket 연결 초기화
    initializeWebSocket();

    // 대화 기록 자동 갱신 설정
    setupChatHistoryRefresh();
}

// 사용자 정보 로드 및 UI 업데이트
async function loadUserInfo() {
    const userInfo = document.getElementById('userInfo');
    if (userInfo) {
        const userData = authManager.getUserInfo();
        userInfo.textContent = `${userData.id} (${userData.role})`;
    }
    
    // 관리자 메뉴 표시 설정
    const adminSection = document.getElementById('adminSection');
    if (adminSection && authManager.isAdmin()) {
        adminSection.classList.remove('hidden');
    }
    
    // 서버에서 현재 사용자 정보 검증
    try {
        const userData = await authManager.loadUserInfo();
        if (!userData) {
            uiManager.showToast('error', '사용자 인증에 실패했습니다');
        }
    } catch (error) {
        console.error('Error verifying user:', error);
        uiManager.showToast('error', '사용자 인증에 실패했습니다');
    }
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
        fileHandler.setupDragAndDrop(dropZone, handleFileUpload);
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
        if (chatHistoryManager.getSessionId()) {
            await chatHistoryManager.saveChatHistory();
        }
    });
}

// 로그아웃 처리
function handleLogout() {
    AuthManager.logout();
}

// WebSocket 초기화 함수
function initializeWebSocket() {
    // 콜백 함수 설정
    wsManager.setCallbacks({
        onMessage: (content, model) => {
            uiManager.updateStreamingMessage(content, model);
        },
        onConnectionEstablished: () => {
            uiManager.showToast('success', '서버에 연결되었습니다');
        },
        onError: (message) => {
            uiManager.showToast('error', message);
            uiManager.enableMessageInput();
        },
        onComplete: () => {
            uiManager.completeStreamingMessage(wsManager.getModel());
            chatHistoryManager.saveChatHistory();
        },
        onModelUpdate: (model) => {
            uiManager.updateModelButtonState(model);
        }
    });
    
    // WebSocket 연결
    wsManager.initialize();
}

// 모델 변경 처리
function handleModelChange(button) {
    const model = button.dataset.model;
    if (model === wsManager.getModel()) return;
    
    // 현재 모델 업데이트
    wsManager.setModel(model);
    
    // UI 업데이트
    uiManager.updateModelButtonState(model);
    
    // 알림
    uiManager.showToast('info', `${capitalizeFirstLetter(model)} 모델로 전환되었습니다`);
}

// 파일 선택 처리
function handleFileSelection(event) {
    const files = Array.from(event.target.files);
    if (!files.length) return;
    
    files.forEach(file => {
        handleFileUpload(file);
    });
    
    // 파일 입력 초기화
    event.target.value = '';
}

// 파일 업로드 처리
async function handleFileUpload(file) {
    // 유효성 검사
    const validation = fileHandler.validateFile(file);
    if (!validation.valid) {
        uiManager.showToast('error', validation.error);
        return;
    }
    
    // 파일 UI 요소 추가
    const removeButton = uiManager.addUploadedFileUI(file.name);
    if (removeButton) {
        removeButton.addEventListener('click', () => {
            fileHandler.removeFile(file.name);
            removeButton.closest('.uploaded-file').remove();
        });
    }
    
    try {
        // 파일 업로드
        const result = await fileHandler.uploadFile(file, (filename, progress) => {
            uiManager.updateUploadProgress(filename, progress);
        });
        
        if (result.success) {
            uiManager.showToast('success', '파일이 성공적으로 분석되었습니다');
        } else {
            uiManager.showToast('error', `파일 업로드 오류: ${result.error}`);
            if (removeButton) {
                removeButton.closest('.uploaded-file').remove();
            }
        }
    } catch (error) {
        console.error('File upload error:', error);
        uiManager.showToast('error', `파일 업로드 오류: ${error.message}`);
        if (removeButton) {
            removeButton.closest('.uploaded-file').remove();
        }
    }
}

// 메시지 전송 함수
function sendMessage() {
    if (wsManager.isActiveProcessing()) {
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
    wsManager.setProcessing(true);
    uiManager.disableMessageInput();
    
    // 웰컴 메시지 제거
    uiManager.removeWelcomeMessage();
    
    // 사용자 메시지 UI에 추가
    uiManager.addUserMessage(content);
    
    // 입력창 초기화
    messageInput.value = '';
    messageInput.style.height = 'auto';
    
    // 어시스턴트 메시지 프레임 미리 추가
    uiManager.addAssistantMessageFrame(wsManager.getModel());
    
    // 메시지 전송
    const success = wsManager.sendMessage(content);
    if (!success) {
        uiManager.completeStreamingMessage(wsManager.getModel());
    }
}

// 텍스트 영역 자동 높이 조절
function autoResizeTextarea() {
    const textarea = this;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px'; // 최대 높이 200px 제한
}

// 대화 기록 패널 토글
function toggleChatHistory() {
    const isShown = uiManager.toggleChatHistory();
    
    if (isShown) {
        loadChatHistories();
    }
}

// 대화 기록 불러오기
async function loadChatHistories() {
    const historyList = document.getElementById('chatHistoryList');
    
    if (!historyList) {
        console.error('chatHistoryList 요소를 찾을 수 없습니다');
        return;
    }

    // 로딩 표시
    historyList.innerHTML = '<div class="p-4 text-center text-gray-500"><div class="spinner mx-auto mb-2"></div>대화 기록을 불러오는 중...</div>';

    try {
        const result = await chatHistoryManager.loadChatHistories();
        
        if (!result.success) {
            historyList.innerHTML = `<div class="p-4 text-center text-red-500">${result.error}</div>`;
            return;
        }
        
        const sessions = result.data;
        
        // 대화 기록 UI 렌더링
        uiManager.renderChatHistory(sessions, chatHistoryManager.getSessionId());
        
        // 세션 클릭 이벤트 설정
        const sessionItems = document.querySelectorAll('.chat-history-item');
        sessionItems.forEach(item => {
            const sessionId = item.getAttribute('data-session-id');
            item.addEventListener('click', () => loadChatSession(sessionId));
            
            // 삭제 버튼 이벤트
            const deleteBtn = item.querySelector('.delete-session-btn');
            if (deleteBtn) {
                deleteBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    deleteSession(sessionId);
                });
            }
        });
    } catch (error) {
        console.error('대화 기록 로드 오류:', error);
        historyList.innerHTML = '<div class="p-4 text-center text-red-500">대화 기록을 불러오는 중 오류가 발생했습니다</div>';
    }
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
}

// 특정 대화 세션 불러오기
async function loadChatSession(sessionId) {
    try {
        // 로딩 표시
        uiManager.clearChatArea();
        const chatMessages = document.getElementById('chat-messages');
        if (chatMessages) {
            chatMessages.innerHTML = '<div class="flex justify-center items-center h-full"><div class="spinner mr-3"></div><span class="text-gray-500">대화를 불러오는 중...</span></div>';
        }
        
        // 세션 로드
        const result = await chatHistoryManager.loadChatSession(sessionId);

        if (!result.success) {
            uiManager.showToast('error', `대화를 불러올 수 없습니다: ${result.error}`);
            startNewChat();
            return;
        }

        const session = result.data;
        
        // 현재 세션 및 모델 정보 업데이트
        wsManager.setSessionId(sessionId);
        wsManager.setModel(session.model || 'meta');
        
        // UI 업데이트
        uiManager.updateModelButtonState(session.model || 'meta');
        uiManager.renderChatSessionMessages(session);
        
        // 대화 기록 패널 닫기
        uiManager.toggleChatHistory();
        
        uiManager.showToast('success', '대화를 불러왔습니다');
    } catch (error) {
        console.error('대화 세션 로드 오류:', error);
        uiManager.showToast('error', `대화를 불러올 수 없습니다: ${error.message}`);
        
        // 오류 시 새 채팅 시작
        startNewChat();
    }
}

// 세션 삭제
async function deleteSession(sessionId) {
    if (!confirm('이 대화를 삭제하시겠습니까?')) {
        return;
    }
    
    try {
        const result = await chatHistoryManager.deleteSession(sessionId);

        if (result.success) {
            uiManager.showToast('success', '대화가 삭제되었습니다');
            loadChatHistories();
            
            // 현재 보고 있던 세션이 삭제된 세션이라면 새 채팅 시작
            if (chatHistoryManager.getSessionId() === sessionId) {
                startNewChat();
            }
        } else {
            uiManager.showToast('error', result.error);
        }
    } catch (error) {
        console.error('대화 세션 삭제 오류:', error);
        uiManager.showToast('error', error.message);
    }
}

// 새 채팅 시작
function startNewChat() {
    // 현재 세션이 있으면 비활성화
    if (chatHistoryManager.getSessionId()) {
        // 저장 먼저 수행
        chatHistoryManager.saveChatHistory().then(() => {
            // 그 다음 세션 비활성화
            chatHistoryManager.updateSessionStatus(false);
        });
    }
    
    // 채팅 영역 초기화
    uiManager.clearChatArea();
    
    // 세션 ID 초기화
    chatHistoryManager.setSessionId(null);
    wsManager.setSessionId(null);
    
    // 업로드된 파일 초기화
    fileHandler.clearFiles();
    
    // 웰컴 메시지 추가
    uiManager.addWelcomeMessage();
    
    // 입력창 초기화 및 활성화
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.value = '';
        messageInput.style.height = 'auto';
    }
    
    wsManager.setProcessing(false);
    uiManager.enableMessageInput();
    
    // 대화 기록 패널이 열려있으면 최신 상태로 갱신
    const panel = document.getElementById('chatHistoryPanel');
    if (panel && panel.style.transform === 'translateX(0)') {
        loadChatHistories();
    }
}

// 관리자 기능 - 사용자 목록 토글
function toggleUsersList() {
    const isVisible = uiManager.toggleUsersList();
    if (isVisible) {
        loadAllUsers();
    }
}

// 관리자 기능 - 모든 사용자 정보 로드
async function loadAllUsers() {
    const token = localStorage.getItem('access_token');
    
    if (!token) return;
    
    try {
        const response = await fetch('/api/admin/users', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            uiManager.showToast('error', '사용자 목록을 불러올 수 없습니다');
            return;
        }
        
        const users = await response.json();
        uiManager.renderUsersList(users);
    } catch (error) {
        console.error('Error loading users:', error);
        uiManager.showToast('error', '사용자 목록을 불러오는 중 오류가 발생했습니다');
    }
}

// 메시지 입력창 자동 포커스
function focusMessageInput() {
    const messageInput = document.getElementById('messageInput');
    if (messageInput && !messageInput.disabled) {
        messageInput.focus();
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

// 첫 글자 대문자로 변환
function capitalizeFirstLetter(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
}

// 테스트 코드 - 개발/디버깅용
window.testChatHistoryPanel = function() {
    const panel = document.getElementById('chatHistoryPanel');
    if (!panel) {
        console.error('chatHistoryPanel 요소를 찾을 수 없습니다');
        return;
    }
    
    console.log('패널 현재 상태:', {
        display: panel.style.display,
        transform: panel.style.transform,
        visibility: panel.style.visibility,
        opacity: panel.style.opacity,
        zIndex: panel.style.zIndex
    });
    
    // 강제로 표시 시도
    panel.style.transform = 'translateX(0)';
    console.log('패널 표시 시도 후 상태:', panel.style.transform);
    
    // 대화 기록 로드 시도
    loadChatHistories();
}