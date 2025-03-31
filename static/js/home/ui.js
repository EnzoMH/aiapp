// ui.js - 사용자 인터페이스 관련 기능

import { showToast, capitalizeFirstLetter, renderMarkdown, highlightCode } from './utils.js';

// 텍스트 영역 자동 높이 조절
function autoResizeTextarea() {
    const textarea = this;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px'; // 최대 높이 200px 제한
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

// 메시지 입력창 자동 포커스
function focusMessageInput() {
    const messageInput = document.getElementById('messageInput');
    if (messageInput && !messageInput.disabled) {
        messageInput.focus();
    }
}

// 채팅창 스크롤 함수
function scrollToBottom() {
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

// 웰컴 메시지 제거
function removeWelcomeMessage() {
    const welcomeMessage = document.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.remove();
    }
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
function addAssistantMessageFrame(currentModel) {
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
            contentDiv.innerHTML = renderMarkdown(contentDiv.dataset.originalText);
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
        // 파일 삭제 함수 호출 - 콜백 형태로 전달
        removeButton.dispatchEvent(new CustomEvent('removeFile', {
            bubbles: true,
            detail: { filename }
        }));
    });
    
    progressContainer.appendChild(progressBar);
    fileElement.appendChild(fileIcon);
    fileElement.appendChild(fileName);
    fileElement.appendChild(progressContainer);
    fileElement.appendChild(removeButton);
    
    uploadedFilesContainer.appendChild(fileElement);
}

// 모델 변경 처리
function handleModelChange(button, currentModel, onModelChangeCallback) {
    const model = button.dataset.model;
    if (model === currentModel) return;
    
    // UI 업데이트
    document.querySelectorAll('.model-btn').forEach(btn => {
        btn.classList.toggle('active', btn === button);
    });
    
    // 콜백 호출 (모델 변경 이벤트)
    if (typeof onModelChangeCallback === 'function') {
        onModelChangeCallback(model);
    }
    
    // 알림
    showToast('info', `${capitalizeFirstLetter(model)} 모델로 전환되었습니다`);
}

// 모듈 내보내기
export {
    autoResizeTextarea,
    disableMessageInput,
    enableMessageInput,
    focusMessageInput,
    scrollToBottom,
    showToast,
    removeWelcomeMessage,
    addWelcomeMessage,
    capitalizeFirstLetter,
    renderMarkdown,
    highlightCode,
    addUserMessage,
    addAssistantMessageFrame,
    updateStreamingMessage,
    completeStreamingMessage,
    updateUploadProgress,
    addUploadedFileUI,
    handleModelChange
}; 