/**
 * login.js - 로그인 페이지 기능
 * 로그인 기능 및 관련 유틸리티 함수
 */

// 페이지 로드 시 실행
document.addEventListener('DOMContentLoaded', function() {
    // 이미 로그인된 경우 홈으로 리디렉션
    const token = localStorage.getItem('access_token');
    if (token) {
        window.location.href = '/home';
        return;
    }
    
    // 로그인 폼 이벤트 리스너 등록
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
});

/**
 * 로그인 처리 함수
 * @param {Event} event - 폼 제출 이벤트
 */
async function handleLogin(event) {
    event.preventDefault();
    
    // 입력 값 가져오기
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    // 입력 검증
    if (!username || !password) {
        showError('아이디와 비밀번호를 모두 입력해주세요.');
        return;
    }
    
    try {
        // 폼 데이터 생성
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);
        
        // 로그인 API 호출
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: formData
        });
        
        // 응답 처리
        const data = await response.json();
        
        if (!response.ok) {
            showError(data.detail || '로그인에 실패했습니다.');
            return;
        }
        
        // 로그인 성공 처리
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
        
        // 홈 페이지로 리디렉션
        window.location.href = '/home';
        
    } catch (error) {
        showError('서버 연결에 문제가 있습니다. 잠시 후 다시 시도해주세요.');
        console.error('로그인 오류:', error);
    }
}

/**
 * JWT 토큰 파싱 함수
 * @param {string} token - JWT 토큰
 * @returns {Object} 토큰에서 추출한 페이로드 (사용자 정보)
 */
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
        return null;
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