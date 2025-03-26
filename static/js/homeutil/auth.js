export class AuthManager {
    constructor() {
        this.token = localStorage.getItem('access_token');
        this.userId = localStorage.getItem('user_id');
        this.userRole = localStorage.getItem('user_role');
    }

    isLoggedIn() {
        return !!this.token;
    }

    getUserInfo() {
        return {
            id: this.userId,
            role: this.userRole
        };
    }

    static async login(username, password) {
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
                throw new Error(data.detail || '로그인에 실패했습니다.');
            }
            
            // 로그인 성공
            localStorage.setItem('access_token', data.access_token);
            
            // JWT 토큰에서 사용자 정보 추출
            const tokenPayload = AuthManager.parseJwt(data.access_token);
            localStorage.setItem('user_id', tokenPayload.sub);
            localStorage.setItem('user_role', tokenPayload.role);
            
            return {
                success: true,
                token: data.access_token,
                user_id: tokenPayload.sub,
                role: tokenPayload.role
            };
        } catch (error) {
            console.error('Login error:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    static logout() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_id');
        localStorage.removeItem('user_role');
        window.location.href = '/';
    }

    // JWT 토큰 디코딩 함수
    static parseJwt(token) {
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

    async loadUserInfo() {
        if (!this.token) {
            console.warn('토큰이 없습니다');
            return false;
        }
        
        try {
            const response = await fetch('/api/me', {
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });
            
            if (!response.ok) {
                console.warn('토큰이 유효하지 않습니다');
                AuthManager.logout();
                return false;
            }
            
            const userData = await response.json();
            return userData;
        } catch (error) {
            console.error('사용자 정보 로드 오류:', error);
            return false;
        }
    }

    // 관리자 권한 확인
    isAdmin() {
        return this.userRole === 'admin';
    }

    // 사용자 권한 확인
    hasRole(role) {
        return this.userRole === role;
    }

    // 토큰 갱신 함수 (필요한 경우 구현)
    async refreshToken() {
        // 토큰 갱신 로직 (API가 있을 경우)
    }
} 