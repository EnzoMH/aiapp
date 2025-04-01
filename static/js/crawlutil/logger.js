/**
 * Logger Utility
 * Logging utility for debug logging and error tracking
 */

class Logger {
    constructor(prefix = '', enabled = true) {
        this.prefix = prefix;
        this.enabled = enabled;
        this.logHistory = [];
        this.maxHistoryLength = 100;
        this.logLevel = 'debug'; // debug, info, warn, error
        
        // Browser console color settings
        this.styles = {
            debug: 'color: #8a8a8a',
            info: 'color: #0086b3',
            warn: 'color: #ff9800; font-weight: bold',
            error: 'color: #ff0000; font-weight: bold',
            success: 'color: #4caf50; font-weight: bold',
            highlight: 'background-color: #ffff00; color: #000000',
            network: 'color: #9c27b0; font-weight: bold',
            request: 'color: #3f51b5; font-style: italic',
            response: 'color: #009688; font-style: italic'
        };
        
        // 브라우저 콘솔에 초기화 메시지 출력
        this.highlight(`Logger initialized: ${prefix || 'Default'}`);
        
        // 브라우저 환경 정보 로깅
        this._logBrowserInfo();
    }

    /**
     * 브라우저 환경 정보 로깅
     * @private
     */
    _logBrowserInfo() {
        try {
            const browserInfo = {
                userAgent: navigator.userAgent,
                language: navigator.language,
                platform: navigator.platform,
                cookieEnabled: navigator.cookieEnabled,
                windowSize: `${window.innerWidth}x${window.innerHeight}`,
                url: window.location.href
            };
            
            this.debug('Browser environment:', browserInfo);
        } catch (error) {
            this.warn('Failed to log browser info:', error);
        }
    }

    /**
     * Set log level
     * @param {string} level - Log level (debug, info, warn, error)
     */
    setLogLevel(level) {
        this.logLevel = level;
        this.info(`Log level set to: ${level}`);
    }

    /**
     * Enable/disable logging
     * @param {boolean} enabled - Whether logging is enabled
     */
    setEnabled(enabled) {
        this.enabled = enabled;
        this.info(`Logging ${enabled ? 'enabled' : 'disabled'}`);
    }

    /**
     * Format log message
     * @param {string} level - Log level
     * @param {string} message - Log message
     * @returns {string} Formatted log message
     */
    formatMessage(level, message) {
        const timestamp = new Date().toISOString();
        return `[${timestamp}] [${level.toUpperCase()}]${this.prefix ? ' [' + this.prefix + ']' : ''} ${message}`;
    }

    /**
     * Add message to log history
     * @param {string} level - Log level
     * @param {string} formattedMessage - Formatted message
     */
    addToHistory(level, formattedMessage) {
        this.logHistory.push({
            level,
            message: formattedMessage,
            timestamp: new Date()
        });
        
        // Maintain maximum length
        if (this.logHistory.length > this.maxHistoryLength) {
            this.logHistory.shift();
        }
    }

    /**
     * Output debug log
     * @param {string} message - Log message
     * @param  {...any} args - Additional arguments
     */
    debug(message, ...args) {
        if (!this.enabled || this.shouldSkipLogLevel('debug')) return;
        
        const formattedMessage = this.formatMessage('debug', message);
        this.addToHistory('debug', formattedMessage);
        
        if (args.length > 0) {
            console.debug(`%c${formattedMessage}`, this.styles.debug, ...args);
        } else {
            console.debug(`%c${formattedMessage}`, this.styles.debug);
        }
    }

    /**
     * Output info log
     * @param {string} message - Log message
     * @param  {...any} args - Additional arguments
     */
    info(message, ...args) {
        if (!this.enabled || this.shouldSkipLogLevel('info')) return;
        
        const formattedMessage = this.formatMessage('info', message);
        this.addToHistory('info', formattedMessage);
        
        if (args.length > 0) {
            console.info(`%c${formattedMessage}`, this.styles.info, ...args);
        } else {
            console.info(`%c${formattedMessage}`, this.styles.info);
        }
    }

    /**
     * Output warning log
     * @param {string} message - Log message
     * @param  {...any} args - Additional arguments
     */
    warn(message, ...args) {
        if (!this.enabled || this.shouldSkipLogLevel('warn')) return;
        
        const formattedMessage = this.formatMessage('warn', message);
        this.addToHistory('warn', formattedMessage);
        
        if (args.length > 0) {
            console.warn(`%c${formattedMessage}`, this.styles.warn, ...args);
        } else {
            console.warn(`%c${formattedMessage}`, this.styles.warn);
        }
    }

    /**
     * Output error log
     * @param {string} message - Log message
     * @param  {...any} args - Additional arguments
     */
    error(message, ...args) {
        if (!this.enabled || this.shouldSkipLogLevel('error')) return;
        
        const formattedMessage = this.formatMessage('error', message);
        this.addToHistory('error', formattedMessage);
        
        if (args.length > 0) {
            console.error(`%c${formattedMessage}`, this.styles.error, ...args);
        } else {
            console.error(`%c${formattedMessage}`, this.styles.error);
        }
    }

    /**
     * Output success log
     * @param {string} message - Log message
     * @param  {...any} args - Additional arguments
     */
    success(message, ...args) {
        if (!this.enabled || this.shouldSkipLogLevel('info')) return;
        
        const formattedMessage = this.formatMessage('success', message);
        this.addToHistory('success', formattedMessage);
        
        if (args.length > 0) {
            console.log(`%c${formattedMessage}`, this.styles.success, ...args);
        } else {
            console.log(`%c${formattedMessage}`, this.styles.success);
        }
    }

    /**
     * Output highlighted log
     * @param {string} message - Log message
     * @param  {...any} args - Additional arguments
     */
    highlight(message, ...args) {
        if (!this.enabled) return;
        
        const formattedMessage = this.formatMessage('highlight', message);
        this.addToHistory('highlight', formattedMessage);
        
        if (args.length > 0) {
            console.log(`%c${formattedMessage}`, this.styles.highlight, ...args);
        } else {
            console.log(`%c${formattedMessage}`, this.styles.highlight);
        }
    }
    
    /**
     * Log network request
     * @param {string} method - HTTP method
     * @param {string} url - Request URL
     * @param {Object} data - Request data
     */
    logRequest(method, url, data) {
        if (!this.enabled || this.shouldSkipLogLevel('info')) return;
        
        const formattedMessage = this.formatMessage('network', `REQUEST: ${method} ${url}`);
        this.addToHistory('network', formattedMessage);
        
        console.groupCollapsed(`%c${formattedMessage}`, this.styles.request);
        if (data) {
            console.log('Request data:', data);
        }
        console.trace('Request trace:');
        console.groupEnd();
    }
    
    /**
     * Log network response
     * @param {string} method - HTTP method
     * @param {string} url - Request URL
     * @param {number} status - Response status
     * @param {Object} data - Response data
     * @param {number} timeMs - Response time in milliseconds
     */
    logResponse(method, url, status, data, timeMs) {
        if (!this.enabled || this.shouldSkipLogLevel('info')) return;
        
        const isSuccess = status >= 200 && status < 300;
        const style = isSuccess ? this.styles.response : this.styles.error;
        
        const formattedMessage = this.formatMessage('network', `RESPONSE: ${method} ${url} (${status}) - ${timeMs}ms`);
        this.addToHistory('network', formattedMessage);
        
        console.groupCollapsed(`%c${formattedMessage}`, style);
        if (data) {
            console.log('Response data:', data);
        }
        console.groupEnd();
    }

    /**
     * Determine whether to skip logging based on log level
     * @param {string} level - Log level
     * @returns {boolean} Whether to skip
     */
    shouldSkipLogLevel(level) {
        const levels = ['debug', 'info', 'warn', 'error'];
        const currentLevelIndex = levels.indexOf(this.logLevel);
        const messageLevelIndex = levels.indexOf(level);
        
        return messageLevelIndex < currentLevelIndex;
    }

    /**
     * Export log history
     * @returns {Array} Log history
     */
    getLogHistory() {
        return [...this.logHistory];
    }

    /**
     * Clear log history
     */
    clearLogHistory() {
        this.logHistory = [];
        this.debug('Log history cleared');
    }

    /**
     * Download log history
     * @param {string} filename - File name
     */
    downloadLogHistory(filename = 'log_history.json') {
        const blob = new Blob([JSON.stringify(this.logHistory, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        
        a.href = url;
        a.download = filename;
        a.click();
        
        setTimeout(() => URL.revokeObjectURL(url), 100);
        this.info(`Log history downloaded as ${filename}`);
    }
}

// Create default logger instance
const logger = new Logger('Crawl');

// Global logger helper object
const Debug = {
    log: (...args) => logger.debug(...args),
    debug: (...args) => logger.debug(...args),
    info: (...args) => logger.info(...args),
    warn: (...args) => logger.warn(...args),
    error: (...args) => logger.error(...args),
    success: (...args) => logger.success(...args),
    highlight: (...args) => logger.highlight(...args),
    logRequest: (...args) => logger.logRequest(...args),
    logResponse: (...args) => logger.logResponse(...args),
    getLogger: () => logger
};

export { Logger, Debug }; 