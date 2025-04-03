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
        localStorage.setItem('token_expiry', tokenPayload.exp * 1000); // 밀리초 단위로 저장
        
        console.log('로그인 성공:', {
            token: data.access_token.substring(0, 10) + '...',
            user_id: tokenPayload.sub,
            role: tokenPayload.role,
            expires: new Date(tokenPayload.exp * 1000).toLocaleString()
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
    clearUserData();
    window.location.href = '/';
}

/**
 * 토큰 만료시 자동 로그아웃 및 알림
 * @param {string} message - 표시할 메시지
 */
function handleTokenExpiration(message = '세션이 만료되었습니다. 다시 로그인해주세요.') {
    clearUserData();
    
    // 만료 메시지 표시 (alert 또는 DOM 요소에)
    if (document.getElementById('error-message-container')) {
        const errorContainer = document.getElementById('error-message-container');
        errorContainer.textContent = message;
        errorContainer.style.display = 'block';
    } else {
        alert(message);
    }
    
    // 3초 후 로그인 페이지로 리디렉션
    setTimeout(() => {
        window.location.href = '/';
    }, 3000);
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
        const errorText = await response.text().catch(() => '응답 텍스트 가져오기 실패');
        console.error(`사용자 정보 로드 실패. 상태 코드: ${response.status}, 응답:`, errorText);
        
        // 401 오류면 토큰이 만료되었거나 잘못된 경우
        if (response.status === 401) {
            console.warn('인증 오류, 자동 로그아웃 진행');
            handleTokenExpiration('인증이 만료되었습니다. 다시 로그인해주세요.');
        }
        
        throw new Error('사용자 정보를 가져올 수 없습니다');
    }
    
    const userData = await response.json();
    console.log('사용자 정보 로드 완료:', userData);
    
    // 사용자 정보 저장
    localStorage.setItem('user_info', JSON.stringify(userData));
    localStorage.setItem('user_id', userData.id || userData.sub);
    localStorage.setItem('user_role', userData.role);
    
    return userData;
}

/**
 * 토큰 갱신 함수
 * @param {string} oldToken - 기존 토큰
 * @returns {Promise<Object>} 갱신 결과 객체
 */
async function refreshToken(oldToken) {
    try {
        console.log('토큰 갱신 API 호출...', oldToken ? oldToken.substring(0, 15) + '...' : '토큰 없음');
        
        if (!oldToken) {
            console.error('갱신할 토큰이 없습니다');
            return {
                success: false,
                error: '갱신할 토큰이 없습니다',
                status: 'no_token'
            };
        }
        
        // 토큰 만료 여부 확인
        const tokenData = parseJwt(oldToken);
        if (!tokenData || !tokenData.sub) {
            console.error('토큰을 파싱할 수 없거나 유효하지 않은 토큰입니다');
            return {
                success: false,
                error: '유효하지 않은 토큰',
                status: 'invalid_token'
            };
        }
        
        console.log(`토큰 갱신 시도: 사용자 ID = ${tokenData.sub}, 만료시간 = ${new Date(tokenData.exp * 1000).toLocaleString()}`);
        
        // API 호출
        const response = await fetch('/api/refresh', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${oldToken}`
            }
        });
        
        // 응답 코드 및 상태 로깅
        console.log(`토큰 갱신 응답 코드: ${response.status}, ${response.statusText}`);
        
        // 실패 처리
        if (!response.ok) {
            let errorData;
            try {
                errorData = await response.json();
                console.error(`토큰 갱신 실패. 상태 코드: ${response.status}, 응답:`, errorData);
            } catch (parseError) {
                errorData = await response.text().catch(() => '응답 텍스트 가져오기 실패');
                console.error(`토큰 갱신 실패. 상태 코드: ${response.status}, 파싱 오류:`, parseError);
            }
            
            return {
                success: false,
                error: errorData?.message || '토큰 갱신 실패',
                code: errorData?.code || 'unknown',
                status: response.status
            };
        }
        
        // 응답 처리
        const data = await response.json();
        if (!data.access_token) {
            console.error('응답에 액세스 토큰이 없습니다', data);
            return {
                success: false,
                error: '응답에 액세스 토큰이 없습니다',
                data: data
            };
        }
        
        // 새 토큰 유효성 확인
        const newTokenData = parseJwt(data.access_token);
        if (!newTokenData || !newTokenData.exp) {
            console.error('새 토큰이 유효하지 않습니다', newTokenData);
            return {
                success: false,
                error: '새 토큰이 유효하지 않습니다'
            };
        }
        
        const expiry = new Date(newTokenData.exp * 1000);
        console.log(`토큰 갱신 성공: 만료시간 = ${expiry.toLocaleString()}, 사용자 = ${newTokenData.sub}`);
        
        return {
            success: true,
            access_token: data.access_token,
            token_type: data.token_type,
            expiry: expiry
        };
    } catch (error) {
        console.error('토큰 갱신 중 오류 발생:', error);
        return {
            success: false,
            error: error.message || '토큰 갱신 중 오류 발생'
        };
    }
}

/**
 * 로컬 스토리지에서 사용자 데이터 제거
 */
function clearUserData() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_info');
    localStorage.removeItem('user_id');
    localStorage.removeItem('user_role');
    localStorage.removeItem('token_expiry');
}

/**
 * JWT 토큰 디코딩 함수
 * @param {string} token - JWT 토큰
 * @returns {Object|null} 디코딩된 토큰 데이터 또는 null
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

/**
 * 토큰 상태 정기적으로 확인
 * 페이지 로드 시 실행할 수 있음
 */
export function startTokenMonitoring() {
    // 5분마다 토큰 상태 확인
    const tokenCheckInterval = setInterval(() => {
        const token = localStorage.getItem('access_token');
        if (!token) {
            clearInterval(tokenCheckInterval);
            return;
        }
        
        const tokenData = parseJwt(token);
        if (tokenData) {
            const currentTime = Math.floor(Date.now() / 1000);
            
            if (tokenData.exp && tokenData.exp < currentTime) {
                clearInterval(tokenCheckInterval);
                handleTokenExpiration();
            } else if (tokenData.exp && (tokenData.exp - currentTime) < 600) {
                // 만료 10분 전에 자동 갱신
                refreshToken(token).then(result => {
                    if (result.success) {
                        console.log('토큰 모니터링: 자동 갱신 성공');
                        localStorage.setItem('access_token', result.access_token);
                        const newTokenData = parseJwt(result.access_token);
                        localStorage.setItem('token_expiry', newTokenData.exp * 1000);
                    }
                }).catch(error => {
                    console.error('토큰 모니터링: 자동 갱신 실패', error);
                });
            }
        }
    }, 300000); // 5분마다
    
    // 페이지 이탈 시 인터벌 정리
    window.addEventListener('beforeunload', () => {
        clearInterval(tokenCheckInterval);
    });
} 
