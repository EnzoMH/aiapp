// auth.js - 인증 관련 기능

import { showToast } from './utils.js';

// JWT 토큰 디코딩 함수
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
        return { sub: '', role: '' };
    }
}

// 로그인 처리 함수
async function handleLogin(event) {
    event.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorMessage = document.getElementById('errorMessage');
    
    if (!username || !password) {
        showError('아이디와 비밀번호를 모두 입력해주세요.');
        return;
    }
    
    try {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);
        
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
        
        // 대시보드로 리디렉션
        window.location.href = '/home';
        
    } catch (error) {
        showError('서버 연결에 문제가 있습니다. 잠시 후 다시 시도해주세요.');
        console.error('Login error:', error);
    }
}

// 로그아웃 처리
function handleLogout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_id');
    localStorage.removeItem('user_role');
    window.location.href = '/';
}

// 사용자 정보 로드 및 UI 업데이트
async function loadUserInfo() {
    const token = localStorage.getItem('access_token');
    const userRole = localStorage.getItem('user_role');
    const userId = localStorage.getItem('user_id');
    
    console.log('토큰 확인:', token ? token.substring(0, 10) + '...' : 'null');
    console.log('사용자 역할:', userRole);
    console.log('사용자 ID:', userId);
    
    if (!token || !userRole || !userId) {
        console.warn('필요한 사용자 정보가 없습니다. 로그아웃합니다.');
        handleLogout();
        return;
    }
    
    // 사용자 정보 표시
    const userInfo = document.getElementById('userInfo');
    if (userInfo) {
        userInfo.textContent = `${userId} (${userRole})`;
    }
    
    // 관리자 메뉴 표시 설정
    const adminSection = document.getElementById('adminSection');
    if (adminSection && userRole === 'admin') {
        adminSection.classList.remove('hidden');
    }
    
    // 서버에서 현재 사용자 정보 검증
    try {
        console.log('서버에 인증 요청 보내는 중...');
        const response = await fetch('/api/me', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        console.log('서버 응답 상태:', response.status);
        
        if (!response.ok) {
            console.warn('토큰이 유효하지 않습니다. 로그아웃합니다.');
            handleLogout();
        } else {
            const userData = await response.json();
            console.log('사용자 데이터:', userData);
        }
    } catch (error) {
        console.error('Error verifying user:', error);
        showToast('error', '사용자 인증에 실패했습니다');
    }
}

// 관리자 기능 - 사용자 목록 표시 토글
function toggleUsersList() {
    const usersList = document.getElementById('usersList');
    
    if (usersList.classList.contains('hidden')) {
        loadAllUsers();
        usersList.classList.remove('hidden');
    } else {
        usersList.classList.add('hidden');
    }
}

// 관리자 기능 - 모든 사용자 정보 로드
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

// 에러 메시지 표시 (로그인 페이지용)
function showError(message) {
    const errorMessage = document.getElementById('errorMessage');
    if (errorMessage) {
        errorMessage.textContent = message;
        errorMessage.classList.remove('hidden');
    }
}

// 모듈 내보내기
export {
    parseJwt,
    handleLogin,
    handleLogout,
    loadUserInfo,
    toggleUsersList,
    loadAllUsers,
    showError
}; 