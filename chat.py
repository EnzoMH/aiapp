from enum import Enum
from typing import List, Dict, Optional, Any, Union
import json
import time
import asyncio
import os
import logging
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import uuid

# AI 모델 라이브러리 임포트
from anthropic import AsyncAnthropic
import google.generativeai as genai
from google.genai import types
from llama_cpp import Llama
from transformers import AutoTokenizer

from dotenv import load_dotenv

from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Any, Union, Literal
from dataclasses import dataclass
import json
import time
import uuid

from pydantic import BaseModel, Field

from dbcon import SessionLocal, Session, Message as DBMessage, Session as DBSession


load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MessageModel(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: float = Field(default_factory=time.time)
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

class SessionModel(BaseModel):
    session_id: str
    user_id: str
    model: str
    messages: List[MessageModel] = []
    created_at: float = Field(default_factory=time.time)
    last_updated: float = Field(default_factory=time.time)
    system_prompt: str = "당신은 도움이 되는 AI 어시스턴트입니다. 사용자의 질문에 대해 정확하고 친절하게 답변하세요."

class MemoryModel(BaseModel):
    content: str
    timestamp: float = Field(default_factory=time.time)
    importance: float = 1.0
    status: str = "active"
    keywords: List[str] = []









            
