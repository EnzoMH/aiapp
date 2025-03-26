// login.js - 로그인 페이지 스크립트
import { AuthManager } from './homeutil/auth.js';
import { UIManager } from './homeutil/ui-manager.js';

document.addEventListener('DOMContentLoaded', function() {
    const uiManager = new UIManager();
    
    // URL 파라미터에서 로그인 정보 확인
    const urlParams = new URLSearchParams(window.location.search);
    const username = urlParams.get('username');
    const password = urlParams.get('password');
    
    if (username && password) {
        handleLogin(username, password);
    }
    
    // 로그인 폼 이벤트 리스너
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            await handleLogin(username, password);
        });
    }
});

async function handleLogin(username, password) {
    try {
        const result = await AuthManager.login(username, password);
        
        if (result.success) {
            // 토큰 저장
            localStorage.setItem('access_token', result.access_token);
            
            // 홈 페이지로 리다이렉션
            window.location.href = '/home';
        } else {
            uiManager.showError(result.error || '로그인에 실패했습니다.');
        }
    } catch (error) {
        console.error('Login error:', error);
        uiManager.showError('서버 연결에 문제가 있습니다. 잠시 후 다시 시도해주세요.');
    }
} 