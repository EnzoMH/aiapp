/**
 * index.js - 홈 페이지 초기화 모듈
 * 홈 페이지 UI 초기화 및 이벤트 처리
 */

import { loadUserInfo, handleLogout, startTokenMonitoring } from './auth.js';

// 웹소켓 매니저
let chatWs = null;

/**
 * JWT 토큰 디코딩 함수 (auth.js와 중복되지만 의존성 줄이기 위해 추가)
 */
function parseJwt(token) {
    try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));

        return JSON.parse(jsonPayload);
    } catch (error) {
        console.error('JWT 토큰 파싱 오류:', error);
        return null;
    }
}

/**
 * 홈 페이지 UI 초기화
 */
export function initHomeUI() {
    console.log('홈 페이지 UI 초기화 시작...');
    
    // 초기화 시작 전 토큰 상태 디버깅
    const token = localStorage.getItem('access_token');
    if (token) {
        try {
            const tokenData = parseJwt(token);
            if (tokenData && tokenData.exp) {
                const expDate = new Date(tokenData.exp * 1000);
                const now = new Date();
                const isExpired = expDate < now;
                console.log(`토큰 상태: ${isExpired ? '만료됨' : '유효함'}, 만료시간: ${expDate.toLocaleString()}`);
            } else {
                console.warn('토큰을 파싱할 수 없거나 만료 정보가 없습니다');
            }
        } catch (e) {
            console.error('토큰 상태 확인 중 오류:', e);
        }
    }
    
    // 오류 메시지 표시 영역 확인
    const errorContainer = document.getElementById('error-message-container') || 
                           document.querySelector('.error-container') ||
                           document.getElementById('errorContainer');
    
    // 오류 표시 함수
    const showError = (message) => {
        console.error('UI 오류:', message);
        if (errorContainer) {
            errorContainer.textContent = message;
            errorContainer.style.display = 'block';
            errorContainer.classList.remove('hidden');
        } else {
            alert(message); // 컨테이너가 없는 경우 alert 사용
        }
    };

    // 토큰이 없으면 로그인 페이지로 리디렉션
    if (!token) {
        console.warn('인증 토큰이 없습니다. 로그인 페이지로 이동합니다.');
        window.location.href = '/';
        return;
    }

    // 토큰 모니터링 시작
    try {
        startTokenMonitoring();
        console.log('토큰 모니터링 시작됨');
    } catch (e) {
        console.error('토큰 모니터링 시작 실패:', e);
    }
    
    // 사용자 정보 로드 (자동 토큰 갱신 시도 포함)
    console.log('사용자 정보 로드 시도...');
    loadUserInfo()
        .then(userData => {
            console.log('사용자 정보 로드 성공:', userData);
            try {
                // UI 컴포넌트 업데이트
                updateUserInterface(userData);
                // 로그아웃 이벤트 리스너 등록
                setupLogoutButton();
                // 추가 UI 구성 요소 초기화
                initUiComponents();
                console.log('홈 페이지 UI 초기화 완료');
            } catch (error) {
                console.error('UI 초기화 중 오류:', error);
                showError('페이지 초기화 중 오류가 발생했습니다.');
            }
        })
        .catch(error => {
            console.error('사용자 정보 로드 실패:', error);
            
            // 오류 메시지 표시 및 처리
            if (error.message === '토큰이 만료되었습니다') {
                showError('세션이 만료되었습니다. 다시 로그인해주세요.');
                console.warn('세션 만료됨. 로그인 페이지로 리디렉션 예정');
            } else {
                showError('사용자 정보를 불러오는데 실패했습니다. 다시 로그인해주세요.');
                console.warn('인증 오류. 로그인 페이지로 리디렉션 예정');
            }
            
            // 오류 상세 정보 기록
            console.error('홈 페이지 초기화 실패 상세:', JSON.stringify(error, null, 2));
            
            // 로컬 스토리지 정리 (토큰 문제 시)
            try {
                localStorage.removeItem('access_token');
                console.log('로컬 스토리지에서 토큰 제거됨');
            } catch (e) {
                console.error('로컬 스토리지 정리 중 오류:', e);
            }
            
            // 3초 후 로그인 페이지로 이동
            setTimeout(() => {
                console.log('로그인 페이지로 리디렉션...');
                window.location.href = '/';
            }, 3000);
        });
}

/**
 * 로그아웃 버튼 설정
 */
function setupLogoutButton() {
    // 두 가지 ID를 모두 확인 (버튼 ID가 다를 수 있음)
    const logoutBtn = document.getElementById('logout-btn') || document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
        console.log('로그아웃 버튼 이벤트 설정 완료');
    } else {
        console.warn('로그아웃 버튼을 찾을 수 없습니다.');
    }
}

/**
 * 사용자 정보 UI 업데이트
 * @param {Object} userData - 사용자 데이터
 */
function updateUserInterface(userData) {
    // 사용자 정보 표시
    const userInfo = document.getElementById('userInfo');
    if (userInfo) {
        userInfo.textContent = `${userData.sub || userData.id} (${userData.role})`;
    }
    
    // 관리자용 UI 표시 (관리자인 경우)
    if (userData.role === 'admin') {
        const adminSection = document.getElementById('adminSection');
        if (adminSection) {
            adminSection.classList.remove('hidden');
        }
    }
    
    // 토큰 만료 정보 표시 (디버깅용)
    const tokenExp = localStorage.getItem('token_expiry');
    if (tokenExp) {
        const expDate = new Date(parseInt(tokenExp));
        const now = new Date();
        const diff = expDate - now;
        
        // 남은 시간 계산 (밀리초 -> 분)
        const minsLeft = Math.floor(diff / (1000 * 60));
        
        console.log(
            `토큰 정보 - 만료: ${expDate.toLocaleString()}, ` +
            `남은 시간: ${minsLeft}분`
        );
    }
}

/**
 * 이벤트 리스너 설정
 */
function setupEventListeners() {
    // 로그아웃 버튼
    setupLogoutButton();
    
    // 기타 이벤트 리스너 등록
    // ...
    
    console.log('이벤트 리스너 설정 완료');
}

/**
 * WebSocket 초기화
 */
function initializeWebSocket() {
    // WebSocket 초기화 로직
    // ...
    
    console.log('WebSocket 초기화 완료');
}

/**
 * 메시지 입력창 포커스
 */
function focusMessageInput() {
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.focus();
    }
}

/**
 * 추가 UI 구성 요소 초기화
 */
function initUiComponents() {
    // 여기에 추가 컴포넌트 초기화 코드 추가
    // 예: 웹소켓 초기화, 메시지 입력창 설정 등
    console.log('추가 UI 구성 요소 초기화 완료');
    
    // 메뉴 이벤트 설정
    setupMenuEvents();
    
    // 크롤링 상태 업데이트 시작
    startCrawlingStatusUpdates();
}

/**
 * 메뉴 이벤트 설정
 */
function setupMenuEvents() {
    const menuItems = document.querySelectorAll('.nav-link');
    if (menuItems.length > 0) {
        menuItems.forEach(item => {
            item.addEventListener('click', (e) => {
                // 활성 메뉴 표시 업데이트
                menuItems.forEach(m => m.classList.remove('active'));
                e.target.classList.add('active');
                
                // 해당 섹션으로 이동 또는 표시
                const targetId = e.target.getAttribute('data-target');
                if (targetId) {
                    showSection(targetId);
                }
            });
        });
    }
}

/**
 * 섹션 표시 제어
 */
function showSection(sectionId) {
    // 모든 섹션 숨기기
    const sections = document.querySelectorAll('.content-section');
    sections.forEach(section => {
        section.style.display = 'none';
    });
    
    // 지정된 섹션만 표시
    const targetSection = document.getElementById(sectionId);
    if (targetSection) {
        targetSection.style.display = 'block';
    }
}

/**
 * 크롤링 상태 업데이트 시작
 */
function startCrawlingStatusUpdates() {
    // 10초마다 크롤링 상태 확인
    const statusCheckInterval = setInterval(() => {
        updateCrawlingStatus();
    }, 10000);
    
    // 페이지 이탈 시 인터벌 정리
    window.addEventListener('beforeunload', () => {
        clearInterval(statusCheckInterval);
    });
    
    // 초기 상태 확인
    updateCrawlingStatus();
}

/**
 * 크롤링 상태 업데이트
 */
async function updateCrawlingStatus() {
    try {
        const token = localStorage.getItem('access_token');
        if (!token) {
            console.warn('인증 토큰이 없습니다. 상태 업데이트를 건너뜁니다.');
            return;
        }
        
        // 실제 API 엔드포인트 확인 필요 (status 또는 crawling/status)
        const response = await fetch('/api/status', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const statusData = await response.json();
            updateStatusDisplay(statusData);
        } else if (response.status === 401) {
            console.warn('인증 만료. 상태 업데이트를 중단합니다.');
            // 토큰 갱신 시도는 loadUserInfo 함수에서 처리됨
        } else {
            console.warn(`크롤링 상태 업데이트 실패. 상태 코드: ${response.status}`);
        }
    } catch (error) {
        console.warn('크롤링 상태 업데이트 실패:', error);
    }
}

/**
 * 상태 표시 업데이트
 */
function updateStatusDisplay(statusData) {
    const statusElement = document.getElementById('crawling-status');
    if (!statusElement) return;
    
    // 상태 데이터 구조 확인 필요 (data.is_running 또는 다른 필드)
    const isRunning = statusData.is_running || 
                       (statusData.data && statusData.data.is_running);
    
    if (isRunning) {
        statusElement.textContent = '크롤링 진행 중...';
        statusElement.className = 'text-primary';
    } else {
        statusElement.textContent = '크롤링 대기 중';
        statusElement.className = 'text-secondary';
    }
    
    // 진행률 표시 업데이트 (있다면)
    const progressElement = document.getElementById('crawling-progress');
    const progressData = statusData.progress || 
                          (statusData.data && statusData.data.progress);
    
    if (progressElement && progressData !== undefined) {
        progressElement.value = progressData;
        progressElement.textContent = `${progressData}%`;
    }
    
    // 결과 수 표시 (있다면)
    const resultCountElement = document.getElementById('result-count');
    const totalItems = statusData.total_items || 0;
    
    if (resultCountElement && totalItems !== undefined) {
        resultCountElement.textContent = totalItems;
    }
}

/**
 * 사용자 정보 로드 함수
 * @returns {Promise<Object>} 사용자 정보 객체
 */
export async function loadUserInfo() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        console.error('토큰이 없습니다. 로그인 필요');
        throw new Error('토큰이 없습니다');
    }
    
    try {
        console.log('사용자 정보 요청 시작...');
        
        // 토큰 만료 여부 확인 (클라이언트 측)
        const tokenData = parseJwt(token);
        if (tokenData) {
            const currentTime = Math.floor(Date.now() / 1000);
            
            if (tokenData.exp && tokenData.exp < currentTime) {
                console.warn(`토큰이 만료되었습니다. 만료시간: ${new Date(tokenData.exp * 1000)}, 현재시간: ${new Date()}`);
                // 토큰 갱신 시도
                console.log('토큰 갱신 시도...');
                const refreshResult = await refreshToken(token);
                
                if (!refreshResult.success) {
                    // 갱신 실패 시 로그아웃
                    handleTokenExpiration('인증이 만료되었습니다. 다시 로그인해주세요.');
                    throw new Error('토큰이 만료되었습니다');
                }
                
                // 갱신 성공 시 로컬 스토리지 업데이트
                const newToken = refreshResult.access_token;
                localStorage.setItem('access_token', newToken);
                
                // 새 토큰에서 정보 추출
                const newTokenData = parseJwt(newToken);
                localStorage.setItem('token_expiry', newTokenData.exp * 1000);
                console.log(`토큰 갱신 성공. 새 만료시간: ${new Date(newTokenData.exp * 1000).toLocaleString()}`);
                
                // 새 토큰으로 계속 진행
                return await fetchUserInfo(newToken);
            }
            
            const remaining = tokenData.exp - currentTime;
            console.log(`토큰 유효 시간 남음: ${Math.floor(remaining / 60)}분 ${remaining % 60}초`);
            
            // 만료 10분 전에 경고 및 자동 갱신
            if (remaining < 600 && remaining > 0) {
                console.warn(`토큰이 곧 만료됩니다. 남은 시간: ${Math.floor(remaining / 60)}분 ${remaining % 60}초`);
                
                // 백그라운드로 토큰 갱신
                refreshToken(token).then(result => {
                    if (result.success) {
                        console.log('토큰 사전 갱신 성공');
                        localStorage.setItem('access_token', result.access_token);
                        const newTokenData = parseJwt(result.access_token);
                        localStorage.setItem('token_expiry', newTokenData.exp * 1000);
                    } else {
                        console.warn('토큰 사전 갱신 실패:', result.error);
                    }
                }).catch(err => {
                    console.error('토큰 사전 갱신 오류:', err);
                });
            }
        }
        
        // 현재 토큰으로 사용자 정보 요청
        return await fetchUserInfo(token);
        
    } catch (error) {
        console.error('사용자 정보 로드 오류:', error);
        throw error;
    }
}

/**
 * 실제 사용자 정보 요청 함수 (코드 중복 방지)
 */
async function fetchUserInfo(token) {
    const response = await fetch('/api/me', {
        method: 'GET',
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });
    
    console.log('API 응답 코드:', response.status);
    
    if (!response.ok) {
        let errorDetail;
        
        try {
            // 표준화된 오류 응답 파싱 시도
            const errorJson = await response.json();
            errorDetail = errorJson.message || errorJson.detail || '알 수 없는 오류';
            const errorCode = errorJson.code || (errorJson.detail && errorJson.detail.code);
            console.error(`사용자 정보 로드 실패. 코드: ${errorCode}, 메시지: ${errorDetail}`);
            
            // 토큰 만료 오류 처리
            if (errorCode === 'auth_002' || errorCode === 'expired_token' || 
                (response.headers.get('X-Error-Code') === 'TOKEN_EXPIRED')) {
                console.warn('토큰 만료 감지됨, 자동 로그아웃 진행');
                handleTokenExpiration('인증이 만료되었습니다. 다시 로그인해주세요.');
            }
        } catch (parseError) {
            // JSON 파싱 실패 시 텍스트로 처리
            errorDetail = await response.text().catch(() => '응답 텍스트 가져오기 실패');
            console.error(`사용자 정보 로드 실패 (텍스트): ${errorDetail}`);
        }
        
        // 401 오류면 토큰이 만료되었거나 잘못된 경우
        if (response.status === 401) {
            console.warn('인증 오류, 자동 로그아웃 진행');
            handleTokenExpiration('인증이 만료되었습니다. 다시 로그인해주세요.');
        }
        
        throw new Error(`사용자 정보를 가져올 수 없습니다: ${errorDetail}`);
    }
    
    const userData = await response.json();
    console.log('사용자 정보 로드 완료:', userData);
    
    // 사용자 정보 저장
    localStorage.setItem('user_info', JSON.stringify(userData));
    localStorage.setItem('user_id', userData.id || userData.sub);
    localStorage.setItem('user_role', userData.role);
    
    return userData;
} 
