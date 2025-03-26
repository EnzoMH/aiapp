export class UIManager {
    constructor() {
        this.isProcessing = false;
    }

    // 사용자 메시지 UI에 추가
    addUserMessage(content) {
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
        this.scrollToBottom();
    }

    // 어시스턴트 메시지 프레임 추가
    addAssistantMessageFrame(model) {
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
        avatarImg.src = `/static/image/${model}.png`;
        avatarImg.alt = `${model} 아바타`;
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
        this.scrollToBottom();
    }

    // 스트리밍 메시지 업데이트
    updateStreamingMessage(content, model) {
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
        
        this.scrollToBottom();
    }

    // 스트리밍 메시지 완료 처리
    completeStreamingMessage(model) {
        console.log('스트리밍 메시지 완료');
        const messageDiv = document.getElementById('current-ai-message');
        if (!messageDiv) {
            console.warn('완료할 현재 AI 메시지를 찾을 수 없습니다');
            this.isProcessing = false;
            this.enableMessageInput();
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
        let modelName = model;
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
            modelIndicator.textContent = this.capitalizeFirstLetter(modelName);
            contentDiv.appendChild(modelIndicator);
        }
        
        // ID 제거 (더 이상 현재 메시지가 아님)
        messageDiv.removeAttribute('id');
        
        // 처리 상태 초기화
        this.isProcessing = false;
        this.enableMessageInput();
    }

    // 메시지 입력창 비활성화
    disableMessageInput() {
        const messageInput = document.getElementById('messageInput');
        const sendBtn = document.getElementById('sendBtn');
        
        if (messageInput) messageInput.disabled = true;
        if (sendBtn) sendBtn.disabled = true;
    }

    // 메시지 입력창 활성화
    enableMessageInput() {
        const messageInput = document.getElementById('messageInput');
        const sendBtn = document.getElementById('sendBtn');
        
        if (messageInput) {
            messageInput.disabled = false;
            messageInput.focus();
        }
        if (sendBtn) sendBtn.disabled = false;
    }

    // 채팅창 스크롤 함수
    scrollToBottom() {
        const chatMessages = document.getElementById('chat-messages');
        if (chatMessages) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    // 토스트 알림 표시
    showToast(type, message) {
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
    showError(message) {
        const errorMessage = document.getElementById('errorMessage');
        if (errorMessage) {
            errorMessage.textContent = message;
            errorMessage.classList.remove('hidden');
        }
    }

    // 웰컴 메시지 추가
    addWelcomeMessage() {
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

    // 웰컴 메시지 제거
    removeWelcomeMessage() {
        console.log('Removing welcome message');
        const welcomeMessage = document.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.remove();
            console.log('Welcome message removed');
        } else {
            console.log('No welcome message found to remove');
        }
    }

    // 대화 기록 패널 토글
    toggleChatHistory() {
        console.log('토글 대화 기록 패널 호출됨');
        const panel = document.getElementById('chatHistoryPanel');
        
        if (!panel) {
            console.error('chatHistoryPanel 요소를 찾을 수 없습니다');
            return false;
        }
        
        console.log('현재 transform 상태:', panel.style.transform);
        
        const isHidden = panel.style.transform === 'translateX(-100%)' || panel.style.transform === '';
        console.log('isHidden 상태:', isHidden);
        
        panel.style.transform = isHidden ? 'translateX(0)' : 'translateX(-100%)';
        console.log('변경 후 transform 상태:', panel.style.transform);
        
        return isHidden; // 패널이 보여지는지 여부를 반환
    }

    // 대화 기록 패널 렌더링
    renderChatHistory(sessions, currentSessionId) {
        const historyList = document.getElementById('chatHistoryList');
        if (!historyList) {
            console.error('chatHistoryList 요소를 찾을 수 없습니다');
            return;
        }
        
        if (!sessions || sessions.length === 0) {
            historyList.innerHTML = '<div class="p-4 text-center text-gray-500">저장된 대화 기록이 없습니다</div>';
            return;
        }
        
        historyList.innerHTML = '';
        
        // 세션 그룹화
        const groupedSessions = this.groupSessionsByDate(sessions);
        
        // 그룹별 렌더링
        Object.keys(groupedSessions).forEach(dateGroup => {
            // 날짜 헤더 생성
            const dateHeader = document.createElement('div');
            dateHeader.className = 'text-xs font-semibold text-gray-500 uppercase p-2 mt-2';
            dateHeader.textContent = dateGroup;
            historyList.appendChild(dateHeader);
            
            // 해당 날짜의 세션들 렌더링
            groupedSessions[dateGroup].forEach(session => {
                this.renderSessionItem(session, historyList, currentSessionId);
            });
        });
    }

    // 개별 세션 항목 렌더링
    renderSessionItem(session, container, currentSessionId) {
        const isActive = session.active && session.session_id === currentSessionId;
        
        const sessionItem = document.createElement('div');
        sessionItem.className = `chat-history-item p-2 hover:bg-gray-100 rounded-md ${isActive ? 'active' : ''}`;
        sessionItem.setAttribute('data-session-id', session.session_id);
        
        const title = session.title || "새 대화";
        const date = new Date(session.created_at).toLocaleString();
        const modelTag = this.getModelTag(session.model);
        const statusText = isActive ? "현재 대화 중" : (session.active ? "활성화됨" : "");
        
        sessionItem.innerHTML = `
            <div class="flex justify-between items-center">
                <span class="text-sm font-medium text-gray-800">${title}</span>
                <span class="text-xs px-2 py-1 rounded-full bg-gray-100 text-gray-600">${modelTag}</span>
            </div>
            <div class="text-xs text-gray-500 mt-1">${date}</div>
            <div class="flex justify-between items-center mt-1">
                <span class="text-xs text-gray-500 ${isActive ? 'text-blue-500 font-medium' : ''}">${statusText}</span>
                <button class="delete-session-btn text-gray-400 hover:text-red-500 hidden group-hover:block">
                    <i class="fas fa-trash-alt"></i>
                </button>
            </div>
        `;
        
        container.appendChild(sessionItem);
        
        // 삭제 버튼 이벤트 핸들러 (반환하여 외부에서 설정)
        return sessionItem.querySelector('.delete-session-btn');
    }

    // 모델 태그 생성
    getModelTag(model) {
        switch (model) {
            case 'meta': return 'Meta';
            case 'claude': return 'Claude';
            case 'gemini': return 'Gemini';
            default: return 'AI';
        }
    }

    // 대화 기록을 날짜별로 그룹화
    groupSessionsByDate(sessions) {
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
            
            if (this.isSameDay(sessionDate, today)) {
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

    // 같은 날짜인지 확인
    isSameDay(date1, date2) {
        return date1.getFullYear() === date2.getFullYear() &&
               date1.getMonth() === date2.getMonth() &&
               date1.getDate() === date2.getDate();
    }

    // 모델 버튼 상태 업데이트
    updateModelButtonState(model) {
        document.querySelectorAll('.model-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.model === model);
        });
    }

    // 채팅 세션 메시지 렌더링
    renderChatSessionMessages(session) {
        const chatMessages = document.getElementById('chat-messages');
        
        if (!chatMessages) {
            console.error('채팅 메시지 컨테이너를 찾을 수 없습니다');
            return;
        }
        
        // 메시지 영역 초기화
        chatMessages.innerHTML = '';
        
        // 메시지 컨테이너 생성
        const messageContainer = document.createElement('div');
        messageContainer.className = 'message-container';
        chatMessages.appendChild(messageContainer);
        
        // 메시지가 없는 경우 웰컴 메시지 표시
        if (!session.messages || session.messages.length === 0) {
            this.addWelcomeMessage();
            return;
        }
        
        // 메시지 복원
        session.messages.forEach(msg => {
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
                avatarImg.src = `/static/image/${msg.model || session.model || 'meta'}.png`;
                avatarImg.alt = `${msg.model || session.model || 'meta'} 아바타`;
                avatarImg.className = 'w-8 h-8 rounded-full';
                
                avatar.appendChild(avatarImg);
                
                // 메시지 컨텐츠 영역
                const contentDiv = document.createElement('div');
                contentDiv.className = 'message-content flex-grow';
                contentDiv.textContent = msg.content;
                
                // 모델 표시
                const modelIndicator = document.createElement('div');
                modelIndicator.className = 'text-xs text-gray-500 mt-1 text-right';
                modelIndicator.textContent = this.capitalizeFirstLetter(msg.model || session.model || 'meta');
                contentDiv.appendChild(modelIndicator);
                
                messageDiv.appendChild(avatar);
                messageDiv.appendChild(contentDiv);
                messageContainer.appendChild(messageDiv);
            }
        });
        
        // 맨 아래로 스크롤
        this.scrollToBottom();
    }

    // 첫 글자 대문자로 변환
    capitalizeFirstLetter(string) {
        return string.charAt(0).toUpperCase() + string.slice(1);
    }

    // 파일 업로드 UI 요소 추가
    addUploadedFileUI(filename) {
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
        
        progressContainer.appendChild(progressBar);
        fileElement.appendChild(fileIcon);
        fileElement.appendChild(fileName);
        fileElement.appendChild(progressContainer);
        fileElement.appendChild(removeButton);
        
        uploadedFilesContainer.appendChild(fileElement);
        
        // 삭제 버튼 반환 (이벤트 핸들러 외부에서 설정)
        return removeButton;
    }

    // 파일 업로드 진행 상태 표시
    updateUploadProgress(filename, progress) {
        const fileElement = document.querySelector(`.uploaded-file[data-filename="${filename}"]`);
        if (fileElement) {
            const progressBar = fileElement.querySelector('.progress-bar');
            if (progressBar) {
                progressBar.style.width = `${progress}%`;
            }
        }
    }

    // 채팅 영역 초기화
    clearChatArea() {
        const chatMessages = document.getElementById('chat-messages');
        if (chatMessages) {
            chatMessages.innerHTML = '';
        }
        
        // 업로드된 파일 초기화
        const uploadedFiles = document.getElementById('uploadedFiles');
        if (uploadedFiles) {
            uploadedFiles.innerHTML = '';
        }
    }

    // 관리자 사용자 목록 패널 토글
    toggleUsersList() {
        const usersList = document.getElementById('usersList');
        
        if (usersList) {
            usersList.classList.toggle('hidden');
            return !usersList.classList.contains('hidden');
        }
        
        return false;
    }

    // 관리자 사용자 목록 렌더링
    renderUsersList(users) {
        const usersListContent = document.getElementById('usersListContent');
        
        if (!usersListContent) {
            console.error('사용자 목록 컨테이너를 찾을 수 없습니다');
            return;
        }
        
        if (!users || users.length === 0) {
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
    }

    // 텍스트 영역 자동 크기 조절 이벤트 핸들러
    setupAutoResizeTextarea() {
        const textarea = document.getElementById('messageInput');
        if (textarea) {
            textarea.addEventListener('input', function() {
                this.style.height = 'auto';
                this.style.height = Math.min(this.scrollHeight, 200) + 'px'; // 최대 높이 200px 제한
            });
        }
    }
} 