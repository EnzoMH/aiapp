/**
 * index.js - 홈 페이지 초기화 모듈
 * 홈 페이지 UI 초기화 및 이벤트 처리
 */

import { loadUserInfo, handleLogout } from './auth.js';

// 웹소켓 매니저
let chatWs = null;

/**
 * 홈 페이지 UI 초기화
 */
export async function initHomeUI() {
    console.log('홈 페이지 UI 초기화 시작');
    
    // 로그인 상태 확인
    const token = localStorage.getItem('access_token');
    if (!token) {
        console.warn('로그인 토큰이 없습니다. 로그인 페이지로 이동합니다.');
        window.location.href = '/';
        return;
    }

    try {
        // 사용자 정보 로드
        const userData = await loadUserInfo();
        
        // 사용자 정보 표시
        updateUserInfo(userData);
        
        // 이벤트 리스너 설정
        setupEventListeners();
        
        // 웹소켓 초기화
        initializeWebSocket();
        
        // 메시지 입력창 포커스
        focusMessageInput();
        
        console.log('홈 페이지 UI 초기화 완료');
    } catch (error) {
        console.error('홈 페이지 초기화 실패:', error);
        alert('페이지 초기화에 실패했습니다. 다시 로그인해주세요.');
        
        // 로그인 페이지로
        setTimeout(() => {
            window.location.href = '/';
        }, 1000);
    }
}

/**
 * 사용자 정보 UI 업데이트
 * @param {Object} userData - 사용자 데이터
 */
function updateUserInfo(userData) {
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
}

/**
 * 이벤트 리스너 설정
 */
function setupEventListeners() {
    // 로그아웃 버튼
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }
    
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
