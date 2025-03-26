export class ChatHistoryManager {
    constructor() {
        this.currentSessionId = null;
        this.autoSaveInterval = null;
    }

    setSessionId(sessionId) {
        this.currentSessionId = sessionId;
    }

    getSessionId() {
        return this.currentSessionId;
    }

    // 주기적 자동 저장 설정
    startAutoSave() {
        // 기존 인터벌 클리어
        if (this.autoSaveInterval) {
            clearInterval(this.autoSaveInterval);
        }
        
        // 30초마다 자동 저장
        this.autoSaveInterval = setInterval(async () => {
            if (this.currentSessionId) {
                await this.saveChatHistory();
            }
        }, 30000);
    }

    // 자동 저장 중지
    stopAutoSave() {
        if (this.autoSaveInterval) {
            clearInterval(this.autoSaveInterval);
            this.autoSaveInterval = null;
        }
    }

    // 대화 저장 함수
    async saveChatHistory() {
        if (!this.currentSessionId) {
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
                let modelName = 'meta'; // 기본값
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
            console.log('세션 ID에 대한 대화 저장:', this.currentSessionId);
            
            const response = await fetch('/api/chat/history', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                },
                body: JSON.stringify({
                    session_id: this.currentSessionId,
                    messages: messageData,
                    model: document.querySelector('.model-btn.active')?.dataset.model || 'meta'
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

    // 세션 상태 업데이트
    async updateSessionStatus(isActive) {
        if (!this.currentSessionId) return false;
        
        try {
            const response = await fetch(`/api/chat/session/${this.currentSessionId}/status`, {
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

    // 대화 기록 불러오기
    async loadChatHistories() {
        try {
            const token = localStorage.getItem('access_token');
            if (!token) {
                return { success: false, error: '로그인이 필요합니다' };
            }

            console.log('대화 기록 API 호출 시도');
            const response = await fetch('/api/chat/recent-sessions', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            console.log('API 응답 상태:', response.status);
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error('API 오류 응답:', errorText);
                throw new Error('대화 기록을 불러올 수 없습니다');
            }

            const sessions = await response.json();
            console.log('받은 세션 데이터:', sessions);
            
            if (!Array.isArray(sessions)) {
                console.error('세션 데이터가 배열이 아닙니다:', sessions);
                return { success: false, error: '잘못된 데이터 형식' };
            }
            
            return { success: true, data: sessions };
        } catch (error) {
            console.error('대화 기록 로드 오류:', error);
            return { success: false, error: error.message };
        }
    }

    // 특정 대화 세션 불러오기
    async loadChatSession(sessionId) {
        try {
            const token = localStorage.getItem('access_token');
            if (!token) {
                return { success: false, error: '로그인이 필요합니다' };
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
            
            this.currentSessionId = sessionId;
            
            // 세션 활성화 상태로 변경
            await this.updateSessionStatus(true);
            
            return { success: true, data: session };
        } catch (error) {
            console.error('대화 세션 로드 오류:', error);
            return { success: false, error: error.message };
        }
    }

    // 세션 삭제
    async deleteSession(sessionId) {
        try {
            const token = localStorage.getItem('access_token');
            if (!token) {
                return { success: false, error: '로그인이 필요합니다' };
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

            return { success: true };
        } catch (error) {
            console.error('대화 세션 삭제 오류:', error);
            return { success: false, error: error.message };
        }
    }

    // 제목 업데이트
    async updateTitle(title) {
        if (!this.currentSessionId) {
            return { success: false, error: '현재 세션이 없습니다' };
        }

        try {
            const response = await fetch(`/api/chat/session/${this.currentSessionId}/title`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                },
                body: JSON.stringify({ title: title })
            });

            if (!response.ok) {
                throw new Error('제목 업데이트에 실패했습니다');
            }

            return { success: true };
        } catch (error) {
            console.error('제목 업데이트 오류:', error);
            return { success: false, error: error.message };
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

    // 제목 자동 생성
    async generateChatTitle() {
        if (!this.currentSessionId) return "새 대화";
        
        try {
            // 첫 번째 사용자 메시지 가져오기
            const messages = document.querySelectorAll('.message.user');
            if (messages.length === 0) return "새 대화";
            
            // 첫 번째 메시지의 내용 (너무 길면 잘라내기)
            const firstMessage = messages[0].textContent.trim();
            const title = firstMessage.length > 30 ? 
                firstMessage.substring(0, 30) + "..." : 
                firstMessage;
                
            // 세션 제목 업데이트
            await this.updateTitle(title);
            
            return title;
        } catch (error) {
            console.error('대화 제목 생성 오류:', error);
            return "새 대화";
        }
    }
} 