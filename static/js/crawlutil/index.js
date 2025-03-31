/**
 * Crawl 유틸리티 모듈들을 하나로 모은 인덱스 파일
 * 이 파일을 통해 다른 모듈에서 필요한 기능들을 쉽게 가져올 수 있습니다.
 */

// 로거 모듈 내보내기
export { Logger, Debug } from './logger.js';

// WebSocket 관리자 내보내기
export { default as WebSocketManager } from './websocket.js';

// DOM 헬퍼 모듈 내보내기
export * from './dom-helper.js';

// API 서비스 모듈 내보내기
export * from './api-service.js';

/**
 * 모든 유틸리티 기능을 하나의 객체로 묶어서 내보냅니다.
 * 이를 통해 import { CrawlUtils } from './crawlutil' 형태로 사용할 수 있습니다.
 */
import { Logger, Debug } from './logger.js';
import WebSocketManager from './websocket.js';
import * as DomHelper from './dom-helper.js';
import * as ApiService from './api-service.js';

const CrawlUtils = {
    Logger,
    Debug,
    WebSocketManager,
    Dom: DomHelper,
    Api: ApiService
};

export default CrawlUtils; 