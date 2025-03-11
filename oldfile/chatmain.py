import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import logging
import json
import asyncio
from typing import List
from langchain_community.chat_models import ChatOllama
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from huggingface_hub import InferenceClient
from llama_cpp import Llama
from transformers import AutoTokenizer

from dotenv import load_dotenv
from anthropic import AsyncAnthropic
import google.generativeai as genai
  

# 환경변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# 정적 파일 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Streaming 콜백 핸들러
class StreamingCallback(StreamingStdOutCallbackHandler):
    def __init__(self, websocket):
        super().__init__()
        self.websocket = websocket
        self.buffer = ""
        
    def on_llm_start(self, *args, **kwargs):
        print("AI가 대화를 시작합니다.")
        
    def on_llm_end(self, *args, **kwargs):
        print("AI가 대화를 종료합니다.")

    async def on_llm_new_token(self, token: str, **kwargs):
        print(f"New token: {token}")
        self.buffer += token
        # 토큰을 즉시 전송하도록 수정
        chunk_message = {
            "type": "assistant",
            "content": token,
            "streaming": True
        }
        try:
            await self.websocket.send_text(json.dumps(chunk_message))
        except Exception as e:
            print(f"Error sending message: {str(e)}")

# # Ollama 모델 초기화
# try:
#     llm = ChatOllama(
#         model="EEVE-Korean-10.8B:latest",
#         callback_manager=CallbackManager([StreamingStdOutCallbackHandler()]),
#         temperature=0.8,
#         max_tokens=1000
#     )
#     logger.info("Ollama 모델 초기화 성공")
# except Exception as e:
#     logger.error(f"Ollama 모델 초기화 실패: {str(e)}")
#     raise

def create_assistant_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", """당신은 아래의 특성을 가진 도움이 되는 AI 조수입니다:
            1. 사용자의 질문에 직접적으로 답변하기
            2. 필요한 경우에만 부가 설명 제공하기
            3. 모호한 경우 구체적인 질문하기"""),
        ("system", "대화 맥락:\n{chat_history}"),
        ("human", "{input}")
    ])

# 프롬프트 템플릿 생성
assistant_prompt = create_assistant_prompt()

# WebSocket 연결 관리
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.conversation_histories: dict = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.conversation_histories[websocket] = []

    def disconnect(self, websocket: WebSocket):
        if websocket in self.conversation_histories:
            del self.conversation_histories[websocket]
        self.active_connections.remove(websocket)

    async def send_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    def get_conversation_history(self, websocket: WebSocket) -> List[dict]:
        return self.conversation_histories.get(websocket, [])

    def add_to_history(self, websocket: WebSocket, message: dict):
        if websocket not in self.conversation_histories:
            self.conversation_histories[websocket] = []
        self.conversation_histories[websocket].append(message)

manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open(os.path.join(static_dir, "home.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

# API 클라이언트 초기화

# 모델 경로 설정
MODEL_PATH = r"C:\Users\qksso\smh\llama-korean\llama-3.2-Korean-Bllossom-3B-gguf-Q4_K_M.gguf"

# API 클라이언트 초기화
try:
    # Claude 설정
    anthropic = AsyncAnthropic(api_key=os.getenv('CLAUDE_API_KEY'))
    
    # Gemini 설정
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    generation_config = {
        'temperature': 0.9,
        'top_p': 1,
        'top_k': 1,
        'max_output_tokens': 3000,
    }
    safety_settings = [
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_NONE",
        },
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "BLOCK_NONE",
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_NONE",
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_NONE",
        },
    ]
    gemini_model = genai.GenerativeModel(
        'gemini-1.5-flash',
        generation_config=generation_config,
        safety_settings=safety_settings
    )

    # Local LLM 설정
    local_model = Llama(
        model_path=MODEL_PATH,
        n_ctx=2048,
        n_threads=8,
        n_batch=512
    )
    tokenizer = AutoTokenizer.from_pretrained('Bllossom/llama-3.2-Korean-Bllossom-3B')
    
    logger.info("AI 모델 초기화 성공")
except Exception as e:
    logger.error(f"AI 모델 초기화 실패: {str(e)}")
    raise


def format_gemini_response(text: str) -> str:
    """Gemini 응답 포맷팅"""
    formatted = text
    
    # 테이블 형식 포함 여부 확인 및 처리
    if '|' in text:
        rows = text.split('\n')
        processed_rows = []
        header_found = False
        
        for row in rows:
            if '|' in row:
                # 헤더 구분선 처리
                if '---' in row:
                    header_found = True
                    continue
                
                # 셀 정제
                cells = [cell.strip() for cell in row.split('|')[1:-1]]
                processed_row = '|' + '|'.join(cells) + '|'
                processed_rows.append(processed_row)
            else:
                processed_rows.append(row)
        
        formatted = '\n'.join(processed_rows)
    
    # * 로 시작하는 리스트 항목 처리
    formatted = '\n'.join(
        line if not line.strip().startswith('*') else line.strip()
        for line in formatted.split('\n')
    )
    
    # 연속된 공백 정규화
    formatted = ' '.join(formatted.split())
    
    return formatted

# AI 응답 생성 함수
async def generate_gemini_response(prompt: str, websocket: WebSocket):
    try:
        response = await gemini_model.generate_content_async(prompt)
        logger.info("Gemini Raw Response:")
        logger.info(response.text)
        
        text = response.text
        # Gemini 특화 포맷팅
        text = format_gemini_response(text)
        
        chunk_message = {
            "type": "assistant",
            "content": text,
            "streaming": True,
            "model": "gemini"  # 모델 정보 추가
        }
        await websocket.send_text(json.dumps(chunk_message))
        
        return text
        
    except Exception as e:
        logger.error(f"Gemini API 오류: {str(e)}")
        raise

async def generate_claude_response(prompt: str, websocket: WebSocket):
    try:
        # 로깅 시작
        logger.info("="*50)
        logger.info("Claude Response Log")
        logger.info("="*50)
        logger.info(f"User Prompt: {prompt}")
        logger.info("-"*50)
        
        stream = await anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
            stream=True
        )
        
        full_response = ""
        async for chunk in stream:
            if chunk.type == "content_block_delta" and chunk.delta:
                # 청크 로깅
                logger.info(f"Chunk: {chunk.delta.text}")
                
                chunk_message = {
                    "type": "assistant",
                    "content": chunk.delta.text,
                    "streaming": True,
                    "model": "claude"  # 모델 정보 추가
                }
                await websocket.send_text(json.dumps(chunk_message))
                full_response += chunk.delta.text
        
        # 최종 응답 로깅
        logger.info("-"*50)
        logger.info(f"Full Response:\n{full_response}")
        logger.info("="*50)
        
        return full_response
    except Exception as e:
        logger.error(f"Claude API 오류: {str(e)}")
        raise

async def generate_local_response(prompt: str, history: List[dict], websocket: WebSocket):
    try:
        messages = []
        for msg in history[-5:]:
            role = "assistant" if msg["type"] == "assistant" else "user"
            messages.append({"role": role, "content": msg["content"]})
        
        messages.append({"role": "user", "content": prompt})
        formatted_prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        # 로깅 시작
        logger.info("="*50)
        logger.info("Local LLM Response Log")
        logger.info("="*50)
        logger.info(f"User Prompt: {prompt}")
        logger.info("-"*50)
        
        full_response = ""
        response_chunks = []
        
        for chunk in local_model(formatted_prompt, max_tokens=512, stream=True):
            if chunk is not None and "choices" in chunk:
                text = chunk["choices"][0]["text"]
                if text:
                    response_chunks.append(text)
                    # 각 청크를 프론트엔드로 전송
                    chunk_message = {
                        "type": "assistant",
                        "content": text,
                        "streaming": True,
                        "model": "meta"  # 모델 정보 추가
                    }
                    await websocket.send_text(json.dumps(chunk_message))
                    full_response += text
        
        # 전체 응답을 프론트엔드로 전송
        final_message = {
            "type": "assistant",
            "content": full_response,
            "streaming": False,
            "model": "meta",
            "isFullResponse": True  # 전체 응답임을 표시
        }
        await websocket.send_text(json.dumps(final_message))
        
        return full_response
    except Exception as e:
        logger.error(f"Local LLM 오류: {str(e)}")
        raise


def format_model_response(response: str, model_type: str) -> str:
    """모델별 응답 포맷팅"""
    if model_type == "gemini":
        # Gemini는 이미 마크다운 형식을 잘 지원하므로 최소한의 처리
        return response
    elif model_type == "claude":
        # Claude의 들여쓰기와 줄바꿈 보완
        response = response.replace('•', '* ')  # 불릿 포인트 통일
        return response
    elif model_type == "meta":
        # Local LLM의 출력 포맷팅
        response = response.replace('***', '**')  # 강조 표시 통일
        return response
    return response
    
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("content", "")
            model_type = message_data.get("model", "meta")  # 기본값은 local model

            user_message_dict = {"type": "user", "content": user_message}
            manager.add_to_history(websocket, user_message_dict)

            try:
                history = manager.get_conversation_history(websocket)
                
                # 모델 선택에 따른 응답 생성
                if model_type == "gemini":
                    ai_response = await generate_gemini_response(user_message, websocket)
                elif model_type == "claude":
                    ai_response = await generate_claude_response(user_message, websocket)
                else:  # meta (local model)
                    ai_response = await generate_local_response(user_message, history, websocket)

                # 완료 메시지 전송
                complete_message = {
                    "type": "assistant",
                    "content": "",
                    "streaming": False
                }
                await websocket.send_text(json.dumps(complete_message))

                # 전체 응답을 히스토리에 추가
                ai_message = {
                    "type": "assistant",
                    "content": ai_response
                }
                manager.add_to_history(websocket, ai_message)

            except Exception as e:
                error_message = {
                    "type": "assistant",
                    "content": f"죄송합니다. 오류가 발생했습니다: {str(e)}"
                }
                await manager.send_message(json.dumps(error_message), websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    #uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    uvicorn.run("main:app", host="0.0.0.0", port=8005, reload=True)