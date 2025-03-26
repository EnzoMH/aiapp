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
            const formData = new FormData();
            formData.append('username', username);
            formData.append('password', password);
            
            const response = await fetch('/api/login', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                const error = await response.json();
                return {
                    success: false,
                    error: error.detail || '로그인에 실패했습니다.'
                };
            }
            
            const data = await response.json();
            return {
                success: true,
                access_token: data.access_token
            };
        } catch (error) {
            console.error('Login error:', error);
            return {
                success: false,
                error: '서버 연결에 문제가 있습니다.'
            };
        }
    }

    static logout() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_id');
        localStorage.removeItem('user_role');
        window.location.href = '/';
    }

    static getUserInfo() {
        const token = localStorage.getItem('access_token');
        if (!token) return null;
        
        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            return {
                id: payload.sub,
                role: payload.role
            };
        } catch (error) {
            console.error('Error parsing token:', error);
            return null;
        }
    }

    static isAdmin() {
        const userInfo = this.getUserInfo();
        return userInfo && userInfo.role === 'admin';
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

    // 사용자 권한 확인
    hasRole(role) {
        return this.userRole === role;
    }

    // 토큰 갱신 함수 (필요한 경우 구현)
    async refreshToken() {
        // 토큰 갱신 로직 (API가 있을 경우)
    }
} 