// utils.js - 공통 유틸리티 함수

// 토스트 알림 표시
export function showToast(type, message) {
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

// 메시지 마크다운 렌더링
export function renderMarkdown(content) {
    if (typeof marked !== 'undefined') {
        try {
            // XSS 방지를 위한 설정
            marked.setOptions({
                sanitize: true,
                breaks: true
            });
            return marked.parse(content);
        } catch (error) {
            console.error('마크다운 렌더링 오류:', error);
            return content;
        }
    }
    return content;
}

// 코드 하이라이팅
export function highlightCode() {
    if (typeof Prism !== 'undefined') {
        Prism.highlightAll();
    }
}

// 첫 글자 대문자로 변환
export function capitalizeFirstLetter(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
}

// 객체를 URL 쿼리 문자열로 변환
export function toQueryString(obj) {
    return Object.keys(obj)
        .filter(key => obj[key] !== undefined && obj[key] !== null)
        .map(key => `${encodeURIComponent(key)}=${encodeURIComponent(obj[key])}`)
        .join('&');
}

// 에러 응답에서 메시지 추출
export async function extractErrorMessage(response) {
    try {
        const data = await response.json();
        return data.detail || data.message || '알 수 없는 오류가 발생했습니다';
    } catch (e) {
        return response.statusText || '서버 오류가 발생했습니다';
    }
}

// 깊은 객체 복사
export function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
}

// 날짜 포맷팅
export function formatDate(date, format = 'YYYY-MM-DD') {
    const d = new Date(date);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    const seconds = String(d.getSeconds()).padStart(2, '0');
    
    return format
        .replace('YYYY', year)
        .replace('MM', month)
        .replace('DD', day)
        .replace('HH', hours)
        .replace('mm', minutes)
        .replace('ss', seconds);
}

// 디바운스 함수
export function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 쓰로틀 함수
export function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func(...args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
} 