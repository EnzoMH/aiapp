/**
 * login.js - 로그인 페이지 기능
 * 로그인 기능 및 관련 유틸리티 함수
 */

// 페이지 로드 시 실행
document.addEventListener('DOMContentLoaded', function() {
    // 로그인 폼 이벤트 리스너 등록
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
    
    // 페이지 리로드 방지 로직
    const lastLoginAttempt = sessionStorage.getItem('last_login_attempt');
    const now = Date.now();
    
    if (lastLoginAttempt && (now - parseInt(lastLoginAttempt)) < 1000) {
        console.warn('너무 빠른 로그인 시도 감지');
        
        // 로그인 폼 비활성화 (5초 후 재활성화)
        const submitBtn = loginForm.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
            
            setTimeout(() => {
                submitBtn.disabled = false;
            }, 5000);
            
            showError('너무 빠른 요청이 감지되었습니다. 잠시 후 다시 시도해주세요.');
        }
    }
});

/**
 * 로그인 처리 함수
 * @param {Event} event - 폼 제출 이벤트
 */
async function handleLogin(event) {
    event.preventDefault();
    
    // 현재 시간 기록
    sessionStorage.setItem('last_login_attempt', Date.now().toString());
    
    // 입력 값 가져오기
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    // 폼 요소 가져오기
    const submitBtn = event.target.querySelector('button[type="submit"]');
    
    // 입력 검증
    if (!username || !password) {
        showError('아이디와 비밀번호를 모두 입력해주세요.');
        return;
    }
    
    try {
        // 로딩 상태 표시
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="animate-pulse">로그인 중...</span>';
        }
        
        // 기존 로컬 스토리지 정보 삭제
        localStorage.removeItem('user_id');
        localStorage.removeItem('user_role');
        localStorage.removeItem('user_info');
        
        // 폼 데이터 생성
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);
        
        // 로그인 API 호출
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache'
            },
            body: formData,
            credentials: 'include' // 세션 쿠키를 전송하고 받기 위해 필요
        });
        
        // 응답 처리
        const data = await response.json();
        
        if (!response.ok) {
            showError(data.detail || '로그인에 실패했습니다.');
            
            // 로딩 상태 복원
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = '로그인';
            }
            return;
        }
        
        // 로그인 성공 처리
        if (data.session_valid) {
            console.log('로그인 성공:', {
                user_id: data.user_id,
                role: data.role
            });
            
            // 사용자 정보 로컬 저장소에 저장 (세션 식별용)
            localStorage.setItem('user_id', data.user_id);
            localStorage.setItem('user_role', data.role);
            
            // 리프레시 카운터 초기화
            sessionStorage.removeItem('login_visit_count');
            sessionStorage.removeItem('last_login_visit');
            
            // 세션이 제대로 설정되었는지 확인
            console.log('세션 쿠키 확인:', document.cookie);
            
            // 리디렉션 전 메시지 표시 및 지연
            showLoginSuccess('로그인 성공! 홈 페이지로 이동합니다...');
            
            // 홈 페이지로 리디렉션 전 약간의 지연을 추가하여 세션 처리 완료 보장
            setTimeout(() => {
                // 새 페이지로 이동하는 대신 페이지 내용을 대체하도록 함
                window.location.replace('/home');
            }, 1500);
        } else {
            showError('세션 생성에 실패했습니다.');
            
            // 로딩 상태 복원
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = '로그인';
            }
        }
    } catch (error) {
        showError('서버 연결에 문제가 있습니다. 잠시 후 다시 시도해주세요.');
        console.error('로그인 오류:', error);
        
        // 로딩 상태 복원
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = '로그인';
        }
    }
}

/**
 * 오류 메시지 표시 함수
 * @param {string} message - 표시할 오류 메시지
 */
function showError(message) {
    const errorMessageElement = document.getElementById('errorMessage');
    if (errorMessageElement) {
        errorMessageElement.textContent = message;
        errorMessageElement.classList.remove('hidden');
    }
}

/**
 * 로그인 성공 메시지 표시 함수
 * @param {string} message - 표시할 메시지
 */
function showLoginSuccess(message) {
    // 성공 메시지를 표시할 요소 가져오기 또는 생성
    let successMessage = document.getElementById('successMessage');
    
    if (!successMessage) {
        successMessage = document.createElement('div');
        successMessage.id = 'successMessage';
        successMessage.className = 'text-green-600 text-sm bg-green-50 p-2 rounded mt-2 text-center';
        
        // errorContainer에 추가
        const errorContainer = document.getElementById('errorContainer');
        if (errorContainer) {
            errorContainer.appendChild(successMessage);
        }
    }
    
    // 메시지 설정 및 표시
    successMessage.textContent = message;
    successMessage.classList.remove('hidden');
} 