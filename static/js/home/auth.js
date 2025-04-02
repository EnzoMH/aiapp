/**
 * auth.js - 인증 모듈
 * 로그인, 로그아웃, 사용자 정보 처리 관련 함수
 */

/**
 * 로그인 처리 함수
 * @param {Event} event - 이벤트 객체
 */
export async function handleLogin(event) {
    event.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    // 입력 확인
    if (!username || !password) {
        showError('아이디와 비밀번호를 모두 입력해주세요.');
        return;
    }
    
    try {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);
        
        // API 호출
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
        
        // 홈 페이지로 리디렉션
        window.location.href = '/home';
        
    } catch (error) {
        showError('서버 연결에 문제가 있습니다. 잠시 후 다시 시도해주세요.');
        console.error('Login error:', error);
    }
}

/**
 * 로그아웃 처리 함수
 */
export function handleLogout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_info');
    localStorage.removeItem('user_id');
    localStorage.removeItem('user_role');
    window.location.href = '/';
}

/**
 * 사용자 정보 로드 함수
 * @returns {Promise<Object>} 사용자 정보 객체
 */
export async function loadUserInfo() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        throw new Error('토큰이 없습니다');
    }
    
    try {
        const response = await fetch('/api/me', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            throw new Error('사용자 정보를 가져올 수 없습니다');
        }
        
        const userData = await response.json();
        console.log('사용자 정보 로드 완료:', userData);
        
        // 사용자 정보 저장
        localStorage.setItem('user_info', JSON.stringify(userData));
        
        return userData;
    } catch (error) {
        console.error('사용자 정보 로드 오류:', error);
        throw error;
    }
}

/**
 * JWT 토큰 파싱 함수
 * @param {string} token - JWT 토큰
 * @returns {Object|null} 파싱된 토큰 정보
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
 * @param {string} message - 표시할 메시지
 */
function showError(message) {
    const errorMessageElement = document.getElementById('errorMessage');
    if (errorMessageElement) {
        errorMessageElement.textContent = message;
        errorMessageElement.classList.remove('hidden');
    }
} 
