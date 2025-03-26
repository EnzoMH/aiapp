export class FileHandler {
    constructor() {
        this.uploadedFiles = new Map();
        this.allowedTypes = ['.pdf', '.hwp', '.hwpx', '.doc', '.docx'];
        this.maxFileSize = 10 * 1024 * 1024; // 10MB
    }

    getUploadedFiles() {
        return this.uploadedFiles;
    }

    clearFiles() {
        this.uploadedFiles.clear();
    }

    // 파일 유효성 검사
    validateFile(file) {
        const extension = '.' + file.name.split('.').pop().toLowerCase();
        
        if (!this.allowedTypes.includes(extension)) {
            return {
                valid: false,
                error: '지원하지 않는 파일 형식입니다'
            };
        }
        
        if (file.size > this.maxFileSize) {
            return {
                valid: false,
                error: '파일 크기는 10MB를 초과할 수 없습니다'
            };
        }
        
        return { valid: true };
    }

    // 파일 업로드 처리
    async uploadFile(file, progressCallback) {
        try {
            // 유효성 검사
            const validation = this.validateFile(file);
            if (!validation.valid) {
                throw new Error(validation.error);
            }
            
            // 프로그레스 업데이트 - 시작
            if (progressCallback) progressCallback(file.name, 10);
            
            const formData = new FormData();
            formData.append('file', file);
            
            // 프로그레스 업데이트 - 진행 중
            if (progressCallback) progressCallback(file.name, 30);
            
            const response = await fetch('/mainupload', {
                method: 'POST',
                body: formData
            });
            
            // 프로그레스 업데이트 - 진행 중
            if (progressCallback) progressCallback(file.name, 70);
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '업로드 실패');
            }
            
            const result = await response.json();
            
            // 프로그레스 업데이트 - 완료
            if (progressCallback) progressCallback(file.name, 100);
            
            // 업로드된 파일 목록에 추가
            this.uploadedFiles.set(file.name, result);
            
            return {
                success: true,
                data: result
            };
        } catch (error) {
            console.error('File upload error:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    // 파일 삭제
    removeFile(filename) {
        if (this.uploadedFiles.has(filename)) {
            this.uploadedFiles.delete(filename);
            return true;
        }
        return false;
    }

    // 파일 정보 가져오기
    getFileInfo(filename) {
        return this.uploadedFiles.get(filename) || null;
    }

    // 파일 확장자에 따른 아이콘 클래스 가져오기 (fontawesome)
    getFileIconClass(filename) {
        const extension = filename.split('.').pop().toLowerCase();
        
        switch (extension) {
            case 'pdf':
                return 'fa-file-pdf';
            case 'doc':
            case 'docx':
                return 'fa-file-word';
            case 'hwp':
            case 'hwpx':
                return 'fa-file-alt';
            default:
                return 'fa-file';
        }
    }

    // 드래그 & 드롭 이벤트 설정
    setupDragAndDrop(dropZone, onFileUpload) {
        if (!dropZone) return;
        
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('drag-over');
        });
        
        dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('drag-over');
        });
        
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('drag-over');
            
            const files = Array.from(e.dataTransfer.files);
            if (onFileUpload && typeof onFileUpload === 'function') {
                files.forEach(file => {
                    const validation = this.validateFile(file);
                    if (validation.valid) {
                        onFileUpload(file);
                    }
                });
            }
        });
    }
} 