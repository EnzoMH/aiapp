// fileManager.js - 파일 처리 관련 기능

import { showToast } from './utils.js';

// 파일 유효성 검사
function validateFile(file) {
    const allowedTypes = ['.pdf', '.hwp', '.hwpx', '.doc', '.docx'];
    const extension = '.' + file.name.split('.').pop().toLowerCase();
    
    if (!allowedTypes.includes(extension)) {
        return {
            valid: false,
            message: '지원하지 않는 파일 형식입니다'
        };
    }
    
    if (file.size > 10 * 1024 * 1024) { // 10MB
        return {
            valid: false,
            message: '파일 크기는 10MB를 초과할 수 없습니다'
        };
    }
    
    return {
        valid: true
    };
}

// 파일 업로드 처리
async function uploadFile(file, onSuccess, onError, onProgress) {
    try {
        // 파일 유효성 검사
        const validation = validateFile(file);
        if (!validation.valid) {
            if (typeof onError === 'function') {
                onError(validation.message);
            }
            return null;
        }
        
        if (typeof onProgress === 'function') {
            onProgress(file.name, 10); // 시작 진행률
        }
        
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch('/mainupload', {
            method: 'POST',
            body: formData
        });
        
        if (typeof onProgress === 'function') {
            onProgress(file.name, 90); // 업로드 완료 진행률
        }
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '업로드 실패');
        }
        
        const result = await response.json();
        
        if (typeof onProgress === 'function') {
            onProgress(file.name, 100); // 처리 완료 진행률
        }
        
        // 성공 콜백 호출
        if (typeof onSuccess === 'function') {
            onSuccess(file.name, result);
        }
        
        return result;
    } catch (error) {
        console.error('File upload error:', error);
        
        // 오류 콜백 호출
        if (typeof onError === 'function') {
            onError(error.message);
        }
        
        return null;
    }
}

// 파일 선택 처리
function handleFileSelection(event, onFileUpload, onError) {
    const files = Array.from(event.target.files);
    if (!files.length) return;
    
    const uploadPromises = files.map(file => {
        return uploadFile(
            file,
            (filename, result) => {
                if (typeof onFileUpload === 'function') {
                    onFileUpload(filename, result);
                }
            },
            (errorMessage) => {
                if (typeof onError === 'function') {
                    onError(errorMessage);
                }
            }
        );
    });
    
    // 모든 업로드 완료 후 파일 입력 초기화
    Promise.all(uploadPromises).finally(() => {
        event.target.value = '';
    });
}

// 모듈 내보내기
export {
    validateFile,
    uploadFile,
    handleFileSelection
}; 