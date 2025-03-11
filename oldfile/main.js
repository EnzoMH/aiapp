document.addEventListener("DOMContentLoaded", function () {
    // DOM 요소 초기화 (기존 코드 유지)
    const searchForm = document.getElementById("searchForm");
    const defaultKeywords = document.getElementById("defaultKeywords");
    const keywordTags = document.getElementById("keywordTags");
    const loading = document.getElementById("loading");
    const results = document.getElementById("results");
    const resultsBody = document.getElementById("resultsBody");
    const resultCount = document.getElementById("resultCount").querySelector("span");
  
    // WebSocket 관리 클래스 업데이트
    class WebSocketManager {
      constructor() {
        this.reconnectAttempts = 0;
        this.MAX_RECONNECT_ATTEMPTS = 5;
        this.isConnected = false;
        this.connect();
      }
  
      // 웹소켓 연결
      connect() {
        this.ws = new WebSocket(`ws://${window.location.host}/ws`);
        this.setupEventHandlers();
      }
  
      // 이벤트 핸들러 설정
      setupEventHandlers() {
        this.ws.onopen = () => {
          console.log("WebSocket 연결 성공");
          this.isConnected = true;
          this.reconnectAttempts = 0;
          this.updateConnectionStatus(true);
        };
  
        this.ws.onmessage = (event) => {
          const data = JSON.parse(event.data);
          this.handleMessage(data);
        };
  
        this.ws.onclose = () => {
          console.log("WebSocket 연결 종료");
          this.isConnected = false;
          this.updateConnectionStatus(false);
          this.attemptReconnect();
        };
  
        this.ws.onerror = (error) => {
          console.error("WebSocket 오류:", error);
          this.updateConnectionStatus(false);
        };
      }
  
      // 연결 상태 업데이트
      updateConnectionStatus(connected) {
        const wsStatus = document.getElementById("wsStatus");
        const wsIndicator = document.getElementById("wsIndicator");
        
        if (connected) {
          wsStatus.classList.remove("hidden");
          wsIndicator.classList.remove("bg-red-500");
          wsIndicator.classList.add("bg-green-500");
        } else {
          wsStatus.classList.remove("hidden");
          wsIndicator.classList.remove("bg-green-500");
          wsIndicator.classList.add("bg-red-500");
        }
      }
  
      // 메시지 처리
      handleMessage(data) {
        console.log("WebSocket message:", data);
        switch (data.type) {
          case "status":
            this.updateStatus(data);
            this.addLogMessage(data.message);
            break;
          case "error":
            this.showError(data.message);
            this.addLogMessage(`오류: ${data.message}`, "error");
            break;
          case "progress":
            this.updateProgress(data);
            break;
          case "crawling_status":
            CrawlingManager.updateStatus(data);
            break;
          default:
            console.log("Unknown message type:", data.type);
        }
      }
  
      // 로그 메시지 추가
      addLogMessage(message, type = "info") {
        const logMessages = document.getElementById("logMessages");
        const logEntry = document.createElement("div");
        const timestamp = new Date().toLocaleTimeString();
        
        logEntry.className = `text-sm ${
          type === "error" ? "text-red-600" : "text-gray-600"
        }`;
        logEntry.textContent = `[${timestamp}] ${message}`;
        
        logMessages.appendChild(logEntry);
        logMessages.scrollTop = logMessages.scrollHeight;
        
        // 로그 컨테이너 표시
        document.getElementById("logContainer").classList.remove("hidden");
      }
  
      // 상태 메시지 표시
      updateStatus(data) {  
        // 상태 메시지를 화면에 표시
        const statusElement = document.getElementById("status");
        if (statusElement) {
          const statusDiv = statusElement.querySelector("div");
          statusDiv.textContent = data.message;
          statusElement.classList.remove("hidden");
  
          setTimeout(() => {
            statusElement.classList.add("hidden");
          }, 5000);
        }
      }
  
      // 에러 메시지 표시
      showError(message) {
        // 에러 메시지를 화면에 표시
        const errorElement = document.getElementById("error");
        if (errorElement) {
          errorElement.classList.remove("hidden");
          errorElement.querySelector("span").textContent = message;
  
          // 5초 후 에러 메시지 자동 제거
          setTimeout(() => errorElement.classList.add("hidden"), 5000);
        }
      }
  
      // 진행 상태 업데이트
      updateProgress(data) {
        // 진행 상황을 화면에 표시
        const progressElement = document.getElementById("progress");
        if (progressElement) {
          // 진행 상태 표시 (예: 크롤링 진행 상황)
          if (data.current && data.total) {
            const percentage = (data.current / data.total) * 100;
            progressElement.innerHTML = `
              <div class="w-full bg-gray-200 rounded-full h-2.5 dark:bg-gray-700">
                <div class="bg-blue-600 h-2.5 rounded-full" style="width: ${percentage}%"></div>
              </div>
              <div class="text-sm text-gray-600 mt-1">
                ${data.message || "처리 중..."} (${data.current}/${data.total})
              </div>
            `;
            progressElement.classList.remove("hidden");
          } else {
            progressElement.classList.add("hidden");
          }
        }
      }
  
      // 크롤링 상세 상태 업데이트
      handleCrawlingStatus(data) {
        if (data.current_keyword) {
          document.getElementById("currentKeyword").textContent = 
            `현재 키워드: ${data.current_keyword}`;
        }
        if (data.processed_count) {
          document.getElementById("processedCount").textContent = 
            `처리된 항목: ${data.processed_count}건`;
        }
      }
  
      // 재연결 로직 강화
      async attemptReconnect() {
        if (this.reconnectAttempts < this.MAX_RECONNECT_ATTEMPTS) {
          this.reconnectAttempts++;
          console.log(`재연결 시도 ${this.reconnectAttempts}/${this.MAX_RECONNECT_ATTEMPTS}`);
          await new Promise(resolve => setTimeout(resolve, 3000)); // 3초 대기
          this.connect();
        }
      }
      // 재연결 로직 강화
      async checkConnection() {
        if (!this.isConnected && this.reconnectAttempts < this.MAX_RECONNECT_ATTEMPTS) {
          console.log(`재연결 시도 ${this.reconnectAttempts + 1}/${this.MAX_RECONNECT_ATTEMPTS}`);
          await this.connect();
        }
      }
    }
    
  
    // 크롤링 관리 클래스 추가
    class CrawlingManager {
      static #instance = null;
      static getInstance() {
        if (!CrawlingManager.#instance) {
          CrawlingManager.#instance = new CrawlingManager();
        }
        return CrawlingManager.#instance;
      }
      constructor() {
        if (CrawlingManager.instance) {
          return CrawlingManager.instance;
        }
        this.isCrawling = false;
        this.setupEventListeners();
        CrawlingManager.instance = this;
      }
  
      // 이벤트 리스너 설정
      setupEventListeners() {
        const startButton = document.getElementById("startCrawling");
        const stopButton = document.getElementById("stopCrawling");
  
        startButton.addEventListener("click", () => this.startCrawling());
        stopButton.addEventListener("click", () => this.stopCrawling());
      }
  
      // 크롤링 시작
      async startCrawling() {
        try {
          const startDate = document.getElementById("startDate").value;
          const endDate = document.getElementById("endDate").value;
  
          if (!startDate || !endDate) {
            throw new Error("날짜를 선택해주세요.");
          }
  
          const response = await fetch("/api/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ startDate, endDate })
          });
  
          if (!response.ok) throw new Error("크롤링 시작 실패");
  
          this.isCrawling = true;
          this.updateCrawlingButtons(true);
          document.getElementById("crawlingDetails").classList.remove("hidden");
          
        } catch (error) {
          console.error("크롤링 시작 오류:", error);
          this.showError(error.message);
        }
      }
  
      // 크롤링 중지
      async stopCrawling() {
        try {
          const response = await fetch("/api/stop", { method: "POST" });
          if (!response.ok) throw new Error("크롤링 중지 실패");
  
          this.isCrawling = false;
          this.updateCrawlingButtons(false);
          
        } catch (error) {
          console.error("크롤링 중지 오류:", error);
          this.showError(error.message);
        }
      }
  
      // 크롤링 버튼 업데이트
      updateCrawlingButtons(isCrawling) {
        const startButton = document.getElementById("startCrawling");
        const stopButton = document.getElementById("stopCrawling");
  
        if (isCrawling) {
          startButton.classList.add("hidden");
          stopButton.classList.remove("hidden");
        } else {
          startButton.classList.remove("hidden");
          stopButton.classList.add("hidden");
        }
      }
  
      // 크롤링 상세 상태 업데이트
      updateDetailedStatus(data) {
        const details = {
          keywordProgress: document.getElementById("keywordProgress"),
          timeRemaining: document.getElementById("timeRemaining"),
          errorCount: document.getElementById("errorCount")
        };
    
        if (details.keywordProgress) {
          details.keywordProgress.textContent = 
            `진행률: ${data.progress}% (${data.current}/${data.total})`;
        }
      }
  
      // 크롤링 상태 업데이트
      static updateStatus(data) {
        const details = document.getElementById("crawlingDetails");
        const currentKeyword = document.getElementById("currentKeyword");
        const processedCount = document.getElementById("processedCount");
        const totalKeywords = document.getElementById("totalKeywords");
        const totalResults = document.getElementById("totalResults");
  
        details.classList.remove("hidden");
        
        currentKeyword.textContent = `현재 키워드: ${data.current_keyword || "-"}`;
        processedCount.textContent = `처리된 키워드: ${data.processed_count || 0}개`;
        totalKeywords.textContent = `전체 키워드: ${data.total_keywords || 0}개`;
        totalResults.textContent = `수집된 결과: ${data.total_results || 0}건`;
      }
  
      showError(message) {
        // 에러 메시지를 화면에 표시
        const errorElement = document.getElementById("error");
        if (errorElement) {
          errorElement.innerHTML = `
            <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
              <strong class="font-bold">오류 발생!</strong>
              <span class="block sm:inline">${message}</span>
            </div>
          `;
          errorElement.classList.remove("hidden");
  
          // 5초 후 에러 메시지 자동 제거
          setTimeout(() => {
            errorElement.classList.add("hidden");
          }, 5000);
        }
      }
    }
    class SearchResultManager {
      static currentResults = [];
      static itemsPerPage = 10;
      static currentPage = 1;
  
      static initializeEventListeners() {
        document.querySelectorAll('.sort-header').forEach(header => {
          header.addEventListener('click', this.handleSort.bind(this));
        });
        
        document.getElementById('filterForm')?.addEventListener('submit', 
          this.handleFilter.bind(this));
      }
      
      // 정렬 수행
      static handleSort(event) {
        const header = event.currentTarget;
        const sortBy = header.dataset.sort;
        const currentOrder = header.dataset.order || 'asc';
        const newOrder = currentOrder === 'asc' ? 'desc' : 'asc';
        header.dataset.order = newOrder;
        
        const sortedResults = this.sortResults(this.currentResults, sortBy, newOrder);
        this.currentResults = sortedResults; // 정렬된 결과 저장
        this.goToPage(this.currentPage); // 현재 페이지 다시 로드
      }
      
      // 필터링 수행
      static handleFilter(event) {
        event.preventDefault();
        const filters = {
          keyword: document.getElementById('filterKeyword').value,
          date: document.getElementById('filterDate').value
        };
        const filteredResults = this.filterResults(this.currentResults, filters);
        this.currentResults = filteredResults; // 필터링된 결과 저장
        this.currentPage = 1; // 필터링 후에는 첫 페이지로
        this.goToPage(1);
      }
  
      // 검색 수행
      static async performSearch(searchData) {
        try {
          const statusElement = document.getElementById("status");
          const progressElement = document.getElementById("progress");
          progressElement?.classList.remove("hidden");
          
          const response = await fetch("/api/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(searchData)
          });
  
          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
          }
  
          const data = await response.json();
          
          if (data.total_results === 0) {
            statusElement?.querySelector("div").textContent = "검색 결과가 없습니다.";
            return {
              count: 0,
              results: [],
              saved_file: null
            };
          }
  
          return {
            count: data.total_results,
            results: data.results.map(result => ({
              basic_info: {
                title: result.basic_info?.title || "",
                bid_number: result.basic_info?.bid_number || "",
                announce_agency: result.basic_info?.announce_agency || "",
                post_date: result.basic_info?.post_date || "",
                process_status: result.basic_info?.process_status || "",
                progress_stage: result.basic_info?.progress_stage || "",
                bid_category: result.basic_info?.bid_category || ""
              },
              detail_info: {
                general_notice: result.detail_info?.general_notice || "",
                bid_progress: result.detail_info?.bid_progress || ""
              }
            })),
            saved_file: data.saved_file
          };
  
        } catch (error) {
          console.error("검색 오류:", error);
          const errorElement = document.getElementById("error");
          if (errorElement) {
            errorElement.classList.remove("hidden");
            errorElement.querySelector("span").textContent = error.message;
            setTimeout(() => errorElement.classList.add("hidden"), 5000);
          }
          throw error;
        } finally {
          document.getElementById("progress")?.classList.add("hidden");
        }
      }
  
      // 특정 페이지의 결과 가져오기
      static getPageResults(pageNumber) {
        const start = (pageNumber - 1) * this.itemsPerPage;
        const end = start + this.itemsPerPage;
        return this.currentResults.slice(start, end);
      }
  
      // 검색 결과 테이블 업데이트
      static updateResultsTable(data) {
        this.currentResults = data.results || [];
        this.currentPage = 1; // 새 검색 결과면 첫 페이지로
        
        const pageResults = this.getPageResults(this.currentPage);
        
        resultsBody.innerHTML = "";
        results.classList.remove("hidden");
        resultCount.textContent = this.currentResults.length || "0";
  
        if (!pageResults || pageResults.length === 0) {
          this.showNoResults();
          return;
        }
  
        pageResults.forEach((item) => {
          const row = this.createResultRow(item);
          resultsBody.appendChild(row);
        });
  
        // 페이지네이션 UI 업데이트
        this.updatePagination(this.currentResults.length, this.currentPage);
  
        // 엑셀 다운로드 버튼 활성화
        if (data.saved_file) {
          this.setupExcelDownload(data.saved_file);
        }
      }
  
      static createResultRow(item) {
        const row = document.createElement("tr");
        row.className = "hover:bg-gray-50";
        const basic_info = item.basic_info || {};
        const detail_info = item.detail_info || {};
      
        const bidUrl = basic_info.bid_number
          ? `https://www.g2b.go.kr:8081/ep/invitation/publish/bidInfoDtl.do?bidno=${basic_info.bid_number}`
          : "#";
      
        row.innerHTML = `
          <td class="px-6 py-4">
            <a href="${bidUrl}" target="_blank" class="text-blue-600 hover:underline">
              ${basic_info.title || ""}
            </a>
          </td>
          <td class="px-6 py-4 whitespace-pre-line">${detail_info.general_notice || ""}</td>
          <td class="px-6 py-4">${basic_info.announce_agency || ""}</td>
          <td class="px-6 py-4">${basic_info.bid_category || ""}</td>
          <td class="px-6 py-4">${basic_info.post_date ? basic_info.post_date.split("\n")[0] : ""}</td>
          <td class="px-6 py-4">${basic_info.progress_stage || ""}</td>
          <td class="px-6 py-4">${basic_info.process_status || ""}</td>
          <td class="px-6 py-4">${detail_info.bid_deadline || ""}</td>
          <td class="px-6 py-4">${detail_info.bid_qualification || ""}</td>
        `;
      
        return row;
      }
      
      static showNoResults() {
        resultsBody.innerHTML = `
          <tr>
            <td colspan="9" class="px-6 py-4 text-center text-gray-500">
              검색 결과가 없습니다.
            </td>
          </tr>
        `;
      }
  
      // 검색 결과 필터링
      static filterResults(results, filters) {
        return results.filter(item => {
          const matchesKeyword = filters.keyword ? 
            item.basic_info.title.includes(filters.keyword) : true;
          const matchesDate = filters.date ? 
            new Date(item.basic_info.post_date) >= new Date(filters.date) : true;
          return matchesKeyword && matchesDate;
        });
      }
    
      // 정렬 기능
      static sortResults(results, sortBy, sortOrder = 'asc') {
        return [...results].sort((a, b) => {
          const valueA = a.basic_info[sortBy];
          const valueB = b.basic_info[sortBy];
          return sortOrder === 'asc' ? 
            valueA.localeCompare(valueB) : 
            valueB.localeCompare(valueA);
        });
      }
  
      // 페이지네이션 UI 업데이트
      static updatePagination(totalResults, currentPage) {
        const totalPages = Math.ceil(totalResults / this.itemsPerPage);
        const paginationElement = document.getElementById("pagination");
        if (!paginationElement) return;
      
        let paginationHTML = `
          <div class="flex items-center justify-between px-4 py-3 bg-white border-t border-gray-200 sm:px-6">
            <div class="flex justify-between flex-1 sm:hidden">
              <button ${currentPage === 1 ? 'disabled' : ''} 
                      class="relative inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 
                      ${currentPage === 1 ? 'opacity-50 cursor-not-allowed' : ''}"
                      onclick="SearchResultManager.goToPage(${currentPage - 1})">
                이전
              </button>
              <button ${currentPage === totalPages ? 'disabled' : ''} 
                      class="relative inline-flex items-center px-4 py-2 ml-3 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50
                      ${currentPage === totalPages ? 'opacity-50 cursor-not-allowed' : ''}"
                      onclick="SearchResultManager.goToPage(${currentPage + 1})">
                다음
              </button>
            </div>
            <div class="hidden sm:flex sm:flex-1 sm:items-center sm:justify-between">
              <div>
                <p class="text-sm text-gray-700">
                  전체 <span class="font-medium">${totalResults}</span> 건 중
                  <span class="font-medium">${(currentPage - 1) * this.itemsPerPage + 1}</span> -
                  <span class="font-medium">${Math.min(currentPage * this.itemsPerPage, totalResults)}</span> 표시
                </p>
              </div>
              <div>
                <nav class="inline-flex -space-x-px rounded-md shadow-sm" aria-label="Pagination">`;
  
        const maxDisplayPages = 5;
        let startPage = Math.max(1, currentPage - Math.floor(maxDisplayPages / 2));
        let endPage = Math.min(totalPages, startPage + maxDisplayPages - 1);
      
        if (startPage > 1) {
          paginationHTML += `
            <button class="px-3 py-2 text-sm font-medium text-gray-500 bg-white border border-gray-300 hover:bg-gray-50"
                    onclick="SearchResultManager.goToPage(1)">
              1
            </button>
            ${startPage > 2 ? '<span class="px-3 py-2 text-gray-500">...</span>' : ''}
          `;
        }
      
        for (let i = startPage; i <= endPage; i++) {
          paginationHTML += `
            <button class="px-3 py-2 text-sm font-medium ${i === currentPage 
              ? 'text-blue-600 border-blue-500 bg-blue-50' 
              : 'text-gray-500 bg-white border-gray-300 hover:bg-gray-50'}"
                    onclick="SearchResultManager.goToPage(${i})">
              ${i}
            </button>
          `;
        }
      
        if (endPage < totalPages) {
          paginationHTML += `
            ${endPage < totalPages - 1 ? '<span class="px-3 py-2 text-gray-500">...</span>' : ''}
            <button class="px-3 py-2 text-sm font-medium text-gray-500 bg-white border border-gray-300 hover:bg-gray-50"
                    onclick="SearchResultManager.goToPage(${totalPages})">
              ${totalPages}
            </button>
          `;
        }
      
        paginationHTML += `
                </nav>
              </div>
            </div>
          </div>
        `;
      
        paginationElement.innerHTML = paginationHTML;
      }
  
      // 페이지 이동
      static goToPage(pageNumber) {
        this.currentPage = pageNumber;
        const pageResults = this.getPageResults(pageNumber);
        
        resultsBody.innerHTML = "";
        pageResults.forEach((item) => {
          const row = this.createResultRow(item);
          resultsBody.appendChild(row);
        });
        
        this.updatePagination(this.currentResults.length, this.currentPage);
      }
  
      // 엑셀 다운로드 버튼 설정
      static setupExcelDownload(filename) {
        const downloadBtn = document.getElementById("downloadExcel");
        if (downloadBtn) {
          downloadBtn.onclick = () =>
            (window.location.href = `/api/download-excel/${filename}`);
          downloadBtn.disabled = false;
          downloadBtn.classList.remove("opacity-50", "cursor-not-allowed");
        }
      }
  }
  
  class KeywordManager {
    constructor() {
        this.keywordInput = document.querySelector(".keyword-input");
        this.addKeywordButton = document.querySelector(".add-keyword");
        this.keywordTags = document.getElementById("keywordTags");
        
        if (!this.keywordInput || !this.addKeywordButton || !this.keywordTags) {
            console.error("Required DOM elements not found");
            return;
        }
        
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        try {
            // 엔터 키 이벤트
            this.keywordInput.addEventListener("keypress", (e) => {
                if (e.key === "Enter") {
                    e.preventDefault();
                    const keyword = this.keywordInput.value.trim();
                    if (keyword) {
                        KeywordManager.addKeyword(keyword);
                        this.keywordInput.value = "";
                    }
                }
            });
  
            // 추가 버튼 클릭 이벤트
            this.addKeywordButton.addEventListener("click", () => {
                const keyword = this.keywordInput.value.trim();
                if (keyword) {
                    KeywordManager.addKeyword(keyword);
                    this.keywordInput.value = "";
                }
            });
  
        } catch (error) {
            console.error("Error setting up keyword event listeners:", error);
        }
    }
  
    static addKeyword(keyword) {
        const keywordTags = document.getElementById("keywordTags");
        if (!keywordTags) return;
  
        if ([...keywordTags.children].some((tag) => tag.dataset.keyword === keyword)) {
            return;
        }
  
        const tag = document.createElement("div");
        tag.className = "inline-flex items-center bg-blue-100 text-blue-800 px-3 py-1 rounded-full";
        tag.dataset.keyword = keyword;
        tag.innerHTML = `
            ${keyword}
            <button type="button" class="ml-2 text-blue-600 hover:text-blue-800 focus:outline-none" 
                    onclick="this.parentElement.remove()">×</button>
        `;
        document.getElementById("keywordTags")?.appendChild(tag);
    }
  
    static initializeDefaultKeywords() {
        const defaultKeywords = document.getElementById("defaultKeywords");
        if (!defaultKeywords) {
          console.error("defaultKeywords element not found");
          return;
        }
  
        const SEARCH_KEYWORDS = [
            "VR",
            "AR",
            "실감",
            "가상현실",
            "증강현실",
            "혼합현실",
            "XR",
            "메타버스",
            "LMS",
            "학습관리시스템",
            "콘텐츠 개발",
            "콘텐츠 제작",
            "교재 개발",
            "교육과정 개발",
            "교육 콘텐츠",
        ];
  
        // 기존 내용 초기화
        defaultKeywords.innerHTML = '';
  
        SEARCH_KEYWORDS.forEach((keyword) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "w-full p-2 text-sm bg-gray-200 rounded hover:bg-gray-300 focus:outline-none";
          button.textContent = keyword;
          button.onclick = () => KeywordManager.addKeyword(keyword);
          defaultKeywords.appendChild(button);
      });
      console.log(`Initialized ${SEARCH_KEYWORDS.length} default keywords`);
    }
  }
  
    // 이벤트 리스너 클래스별로 분리
  class SearchManager {
    constructor() {
      this.searchForm = document.getElementById("searchForm");
      this.setupEventListeners();
    }
  
    setupEventListeners() {
      this.searchForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const keywords = [...keywordTags.children].map((tag) => tag.dataset.keyword);
  
        if (keywords.length === 0) {
          alert("최소 하나의 키워드를 선택해주세요.");
          return;
        }
  
        const searchData = {
          keywords: keywords,
          startDate: document.getElementById("startDate").value,
          endDate: document.getElementById("endDate").value,
        };
  
        loading.classList.remove("hidden");
        results.classList.add("hidden");
  
        try {
          const data = await SearchResultManager.performSearch(searchData);
          SearchResultManager.updateResultsTable(data);
        } catch (error) {
          alert(`검색 중 오류가 발생했습니다: ${error.message}`);
        } finally {
          loading.classList.add("hidden");
        }
      });
    }
  }
  
    // 초기화 함수 업데이트
    function initialize() {
      try {
          console.log("=== 초기화 시작 ===");
          
          // DOM 요소 확인 및 초기화
          console.log("필수 DOM 요소 확인 중...");
          const required_elements = {
              defaultKeywords: document.getElementById("defaultKeywords"),
              startDate: document.getElementById("startDate"),
              endDate: document.getElementById("endDate")
          };
          
          // 필수 요소 존재 확인
          for (const [name, element] of Object.entries(required_elements)) {
              if (!element) {
                  console.error(`${name} 요소를 찾을 수 없음`);
                  throw new Error(`필수 요소 '${name}'를 찾을 수 없습니다`);
              }
              console.log(`${name} 요소 확인 완료`);
          }
          
          console.log("모든 필수 DOM 요소 확인 완료");
          
          // 날짜 설정
          console.log("날짜 설정 중...");
          const today = new Date();
          const oneMonthAgo = new Date(today);
          oneMonthAgo.setMonth(today.getMonth() - 1);
          
          required_elements.startDate.value = oneMonthAgo.toISOString().split("T")[0];
          required_elements.endDate.value = today.toISOString().split("T")[0];
          console.log("날짜 설정 완료:", {
              startDate: required_elements.startDate.value,
              endDate: required_elements.endDate.value
          });
          
          // 매니저 초기화
          console.log("KeywordManager 초기화 중...");
          KeywordManager.initializeDefaultKeywords();
          console.log("KeywordManager 초기화 완료");
          
          console.log("SearchResultManager 초기화 중...");
          SearchResultManager.initializeEventListeners();
          console.log("SearchResultManager 초기화 완료");
          
          // 인스턴스 생성 및 관리
          console.log("매니저 인스턴스 생성 중...");
          const managers = {
              keyword: new KeywordManager(),
              websocket: new WebSocketManager(),
              crawling: CrawlingManager.getInstance(), // 싱글톤 패턴 사용
              search: new SearchManager()
          };
          console.log("매니저 인스턴스 생성 완료");
          
          // 초기화 완료 로그
          console.log("=== 어플리케이션 초기화 완료 ===", {
              defaultKeywordsElement: required_elements.defaultKeywords,
              managers: managers
          });
          
      } catch (error) {
          console.error("=== 초기화 실패 ===");
          console.error("오류 상세 정보:", error);
          console.error("오류 스택:", error.stack);
      }
  }
    // 애플리케이션 시작
    initialize();
  });