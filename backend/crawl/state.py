class CrawlingState:
    """
    크롤링 상태 관리 클래스
    """
    
    def __init__(self):
        self.is_running = False
        self.keywords = []
        self.date_range = None
        self.start_time = None
        self.completed_at = None
        self.processed_keywords = 0
        self.current_progress = 0
        self.results = []
        self.connections = []
        self.agent_connections = []
        self.current_crawler = None
        self.detail_status = {}
        self.user_search_keywords = []  # 사용자 검색 키워드 저장
        
    def reset_results(self):
        """
        결과 초기화
        """
        self.results = []
        self.processed_keywords = 0
        self.current_progress = 0
        self.detail_status = {}
        
    def set_running(self, is_running: bool):
        """
        실행 상태 설정
        """
        self.is_running = is_running
        
    def set_keywords(self, keywords: list):
        """
        키워드 설정
        """
        self.keywords = keywords
        
    def set_date_range(self, date_range: tuple):
        """
        날짜 범위 설정
        """
        self.date_range = date_range
        
    def set_start_time(self, start_time):
        """
        시작 시간 설정
        """
        self.start_time = start_time
        
    def set_completed_at(self, completed_at):
        """
        완료 시간 설정
        """
        self.completed_at = completed_at
        
    def increment_processed_keywords(self):
        """
        처리된 키워드 수 증가
        """
        self.processed_keywords += 1
        
    def update_progress(self, progress: float):
        """
        진행률 업데이트
        """
        self.current_progress = progress
        
    def add_result(self, result: dict):
        """
        결과 추가
        """
        self.results.append(result)
        
    def add_results(self, results: list):
        """
        여러 결과 한번에 추가
        """
        self.results.extend(results)
        
    def set_current_crawler(self, crawler):
        """
        현재 크롤러 설정
        """
        self.current_crawler = crawler
        
    def add_websocket_connection(self, connection):
        """
        WebSocket 연결 추가
        """
        if connection not in self.connections:
            self.connections.append(connection)
            
    def remove_websocket_connection(self, connection):
        """
        WebSocket 연결 제거
        """
        if connection in self.connections:
            self.connections.remove(connection)
            
    def add_agent_websocket_connection(self, connection):
        """
        에이전트 WebSocket 연결 추가
        """
        if connection not in self.agent_connections:
            self.agent_connections.append(connection)
            
    def remove_agent_websocket_connection(self, connection):
        """
        에이전트 WebSocket 연결 제거
        """
        if connection in self.agent_connections:
            self.agent_connections.remove(connection)
            
    def update_detail_status(self, bid_id: str, status: dict):
        """
        상세 정보 추출 상태 업데이트
        """
        self.detail_status[bid_id] = status
        
    def set_user_search_keywords(self, keywords: list):
        """
        사용자 검색 키워드 설정
        """
        self.user_search_keywords = keywords 