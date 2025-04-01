/**
 * DOM 헬퍼 유틸리티
 * DOM 요소 조작 및 이벤트 처리를 위한 헬퍼 함수들
 */

/**
 * DOM 요소 가져오기 (안전하게)
 * @param {string} id - 요소의 ID
 * @param {boolean} required - 필수 여부
 * @returns {HTMLElement|null} - 찾은 요소 또는 null
 */
function getElement(id, required = false) {
    const element = document.getElementById(id);
    
    if (!element && required) {
        console.error(`필수 DOM 요소를 찾을 수 없음: ${id}`);
    }
    
    return element;
}

/**
 * 여러 DOM 요소 가져오기
 * @param {string[]} ids - 요소 ID 배열
 * @returns {Object} - ID를 키로 하는 요소 객체
 */
function getElements(ids) {
    const elements = {};
    const missing = [];
    
    ids.forEach(id => {
        const element = document.getElementById(id);
        elements[id] = element;
        
        if (!element) {
            missing.push(id);
        }
    });
    
    if (missing.length > 0) {
        console.warn(`DOM 요소를 찾을 수 없음: ${missing.join(', ')}`);
    }
    
    return elements;
}

/**
 * 상태 메시지 추가
 * @param {string} containerId - 컨테이너 ID
 * @param {string} message - 메시지 내용
 * @param {string} type - 메시지 타입 (info, success, warning, danger)
 */
function appendStatusMessage(containerId, message, type = 'info') {
    const container = document.getElementById(containerId);
    if (!container) {
        console.error(`상태 메시지 컨테이너를 찾을 수 없음: ${containerId}`);
        return;
    }
    
    appendMessage(container, message, type);
}

/**
 * 상태 메시지 추가 (컨테이너 요소 직접 전달)
 * @param {HTMLElement} container - 컨테이너 요소
 * @param {string} message - 메시지 내용
 * @param {string} type - 메시지 타입 (info, success, warning, danger)
 */
function appendMessage(container, message, type = 'info') {
    if (!container) {
        console.error('상태 메시지 컨테이너가 null 또는 undefined입니다');
        return;
    }
    
    const messageItem = document.createElement('div');
    messageItem.className = `alert alert-${type} py-1 mb-2`;
    messageItem.textContent = message;
    
    // 타임스탬프 추가
    const timestamp = document.createElement('small');
    timestamp.className = 'float-end text-muted';
    timestamp.textContent = new Date().toLocaleTimeString();
    messageItem.appendChild(timestamp);
    
    // 첫 메시지인 경우 초기 텍스트 제거
    if (container.querySelector('.text-center.text-muted')) {
        container.innerHTML = '';
    }
    
    container.appendChild(messageItem);
    container.scrollTop = container.scrollHeight;
}

/**
 * 버튼 상태 변경
 * @param {string} buttonId - 버튼 ID
 * @param {boolean} disabled - 비활성화 여부
 */
function setButtonState(buttonId, disabled) {
    const button = document.getElementById(buttonId);
    if (button) {
        button.disabled = disabled;
    }
}

/**
 * 프로그레스 바 업데이트
 * @param {string} barId - 프로그레스 바 ID
 * @param {string} percentId - 퍼센트 표시 요소 ID
 * @param {string} statusId - 상태 표시 요소 ID
 * @param {number} percent - 퍼센트 값 (0-100)
 * @param {string} statusText - 상태 텍스트
 */
function updateProgressBar(barId, percentId, statusId, percent, statusText) {
    const bar = document.getElementById(barId);
    const percentElement = document.getElementById(percentId);
    const statusElement = document.getElementById(statusId);
    
    if (bar) {
        bar.style.width = `${percent}%`;
    }
    
    if (percentElement) {
        percentElement.textContent = `${percent}%`;
    }
    
    if (statusElement && statusText) {
        statusElement.textContent = statusText;
    }
}

/**
 * 테이블 생성 및 데이터 채우기
 * @param {string} containerId - 컨테이너 ID
 * @param {Array} data - 표시할 데이터 배열
 * @param {Array} columns - 컬럼 정의 ([{key, label, renderer}])
 */
function renderTable(containerId, data, columns) {
    const container = document.getElementById(containerId);
    if (!container) {
        console.error(`테이블 컨테이너를 찾을 수 없음: ${containerId}`);
        return;
    }
    
    container.innerHTML = '';
    
    if (!data || data.length === 0) {
        container.innerHTML = '<div class="text-center text-muted"><p>데이터가 없습니다.</p></div>';
        return;
    }
    
    const table = document.createElement('table');
    table.className = 'table table-hover table-sm';
    
    // 테이블 헤더
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    
    columns.forEach(column => {
        const th = document.createElement('th');
        th.textContent = column.label;
        th.scope = 'col';
        headerRow.appendChild(th);
    });
    
    thead.appendChild(headerRow);
    table.appendChild(thead);
    
    // 테이블 바디
    const tbody = document.createElement('tbody');
    
    data.forEach(item => {
        const row = document.createElement('tr');
        
        columns.forEach(column => {
            const cell = document.createElement('td');
            
            if (column.renderer) {
                // 렌더러 함수가 있으면 사용
                cell.innerHTML = column.renderer(item);
            } else {
                // 기본 렌더링 (키를 통해 값 접근)
                const value = item[column.key] || '';
                cell.textContent = value;
            }
            
            row.appendChild(cell);
        });
        
        tbody.appendChild(row);
    });
    
    table.appendChild(tbody);
    container.appendChild(table);
}

// DomUtils 객체를 생성하여 모든 함수를 메서드로 노출
const DomUtils = {
    getElement,
    getElements,
    appendStatusMessage,
    appendMessage,
    setButtonState,
    updateProgressBar,
    renderTable
};

// 개별 함수와 DomUtils 객체를 내보냄
export { 
    getElement, 
    getElements, 
    appendStatusMessage, 
    appendMessage, 
    setButtonState, 
    updateProgressBar, 
    renderTable,
    DomUtils as default 
}; 