from enum import Enum
from typing import List, Dict, Optional, Any, Union
import os
import logging
import asyncio
import re
import uuid
from fastapi import WebSocket

# 외부 AI 라이브러리 임포트
from anthropic import Anthropic
import google.generativeai as genai
from google.genai import types
from llama_cpp import Llama
from transformers import AutoTokenizer

# 내부 모듈 임포트
from backend.utils.chat.models import ChatMessage, MessageRole


# 로깅 설정
logger = logging.getLogger(__name__)

# AI 모델 타입 정의
class AIModel(str, Enum):
    META = "meta"
    CLAUDE = "claude"
    GEMINI = "gemini"

# AI 모델 관리자
class AIModelManager:
    def __init__(self):
        self.setup_models()
    
    def setup_models(self):
        """AI 모델 초기화"""
        try:
            # Claude 설정
            self.anthropic = Anthropic(api_key=os.getenv('CLAUDE_API_KEY'))
            
            # Gemini 설정
            genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
            self.gemini_config = {
                'temperature': 0.7,  # 약간 낮춰서 더 일관된 응답
                'top_p': 0.95,
                'top_k': 40,
                'max_output_tokens': 4000,  # 출력 토큰 증가
            }
            self.gemini_model = genai.GenerativeModel(
                'gemini-1.5-flash',
                generation_config=self.gemini_config
            )
            
            # Meta(로컬) 모델 설정
            self.local_model = self._initialize_local_model()
            self.tokenizer = AutoTokenizer.from_pretrained('Bllossom/llama-3.2-Korean-Bllossom-3B')
            
            logger.info("AI 모델 초기화 성공")
        except Exception as e:
            logger.error(f"AI 모델 초기화 실패: {e}")
            raise

    def _initialize_local_model(self):
        """로컬 LLM 초기화 (GPU 지원 가능 시 활용)"""
        MODEL_PATH=r"C:\\Users\\MyoengHo Shin\\pjt\\progen\\llama-korean\\llama-3.2-Korean-Bllossom-3B-gguf-Q4_K_M.gguf"
        
        # 모델 경로가 비어있거나 존재하지 않는 경우 처리
        if not MODEL_PATH or not os.path.exists(MODEL_PATH):
            logger.warning(f"모델 경로가 유효하지 않습니다: '{MODEL_PATH}'. Meta 모델을 사용하지 않습니다.")
            return None
        
        try:
            logger.info("GPU 레이어 활성화 시도 중...")
            model = Llama(
                model_path=MODEL_PATH,
                n_ctx=2048,
                n_threads=8,
                n_batch=1024,
                n_gpu_layers=32,
                f16_kv=True,
                offload_kqv=True,
                verbose=True  # 상세 로그 출력
            )
            logger.info("GPU 레이어 활성화 성공!")
            return model
        except Exception as e:
            logger.warning(f"GPU 초기화 실패, CPU로 대체: {e}")
            try:
                logger.info("CPU 모드로 모델 초기화 시도 중...")
                model = Llama(
                    model_path=MODEL_PATH,
                    n_ctx=2048,
                    n_threads=8,
                    n_batch=512,
                    n_gpu_layers=0,
                    verbose=True  # 상세 로그 출력
                )
                logger.info("CPU 모드로 모델 초기화 성공!")
                return model
            except Exception as e:
                logger.error(f"CPU 모델 초기화도 실패: {e}")
                return None

    async def generate_response(self, messages: List[ChatMessage], model: AIModel, websocket: Optional[WebSocket] = None) -> str:
        """개선된 컨텍스트 기반 응답 생성"""
        try:
            # 메시지를 프롬프트로 변환
            prompt = self._format_messages_to_prompt(messages)
            
            # 모델별 응답 생성
            if model == AIModel.GEMINI:
                return await self._generate_gemini_response(prompt, websocket)
            elif model == AIModel.CLAUDE:
                return await self._generate_claude_response(prompt, websocket)
            else:  # META
                return await self._generate_local_response(prompt, websocket)
                
        except Exception as e:
            logger.error(f"{model} 모델 응답 생성 오류: {e}")
            return f"죄송합니다. {model} 모델 응답 생성 중 오류가 발생했습니다."

    def _format_messages_to_prompt(self, messages: List[ChatMessage]) -> str:
        """대화 맥락을 유지하는 프롬프트 구성"""
        formatted_prompt = ""
        
        # 시스템 프롬프트 처리
        system_messages = [msg for msg in messages if msg.role == MessageRole.SYSTEM]
        if system_messages:
            formatted_prompt += f"시스템: {system_messages[0].content}\n\n"
        
        # 대화 컨텍스트 구성 (시스템 메시지 제외)
        chat_messages = [msg for msg in messages if msg.role != MessageRole.SYSTEM]
        
        # 시간순으로 정렬
        chat_messages.sort(key=lambda x: x.timestamp)
        
        # 대화 이력 추가
        for msg in chat_messages:
            role_prefix = "사용자: " if msg.role == MessageRole.USER else "어시스턴트: "
            formatted_prompt += f"{role_prefix}{msg.content}\n\n"
        
        # 최종 응답 유도
        formatted_prompt += "어시스턴트: "
        return formatted_prompt

    async def _generate_gemini_response(self, prompt: str, websocket: Optional[WebSocket] = None) -> str:
        """Gemini 모델용 응답 생성 로직 - 개선된 버전"""
        try:
            # 프롬프트 강화: 더 효과적인 응답을 위한 지시사항 추가
            enhanced_prompt = self._enhance_gemini_prompt(prompt)
            
            # 함수 호출이 필요한지 확인
            if self._needs_function_calling(enhanced_prompt):
                return await self._generate_gemini_response_with_function_calling(enhanced_prompt, websocket)
            
            # 일반 텍스트 응답 생성
            response = await self.gemini_model.generate_content_async(enhanced_prompt)
            formatted_response = self._format_gemini_response(response.text)
            
            if websocket:
                for chunk in self._simulate_streaming(formatted_response):
                    await self._send_chunk(websocket, chunk, "gemini")
                
                await websocket.send_json({
                    "type": "assistant",
                    "isFullResponse": True,
                    "model": "gemini"
                })
            
            return formatted_response
            
        except Exception as e:
            error_msg = f"Gemini 응답 생성 오류: {str(e)}"
            logger.error(error_msg)
            return f"죄송합니다. 응답 생성 중 오류가 발생했습니다."

    def _needs_function_calling(self, prompt: str) -> bool:
        """프롬프트가 함수 호출이 필요한지 판단"""
        # 구조화된 데이터 추출이 필요한 키워드 확인
        extraction_keywords = [
            "추출", "extract", "정보 추출", "데이터 추출", "목록", "list", 
            "요약", "summarize", "분석", "analyze", "정리", "organize",
            "표로 정리", "표 형식", "JSON", "json", "구조화", "structured"
        ]
        
        return any(keyword in prompt for keyword in extraction_keywords)

    async def _generate_gemini_response_with_function_calling(self, prompt: str, websocket: Optional[WebSocket] = None) -> str:
        """함수 호출 기능을 사용한 Gemini 응답 생성"""
        try:
            # 함수 선언 정의
            extract_info = types.FunctionDeclaration(
                name="extract_information",
                description="텍스트에서 중요한 정보를 추출합니다",
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "key_points": {
                            "type": "ARRAY",
                            "items": {
                                "type": "STRING"
                            },
                            "description": "텍스트에서 추출한 주요 포인트 목록"
                        },
                        "entities": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "name": {
                                        "type": "STRING",
                                        "description": "개체의 이름"
                                    },
                                    "type": {
                                        "type": "STRING",
                                        "description": "개체의 유형 (사람, 장소, 조직, 개념 등)"
                                    },
                                    "description": {
                                        "type": "STRING",
                                        "description": "개체에 대한 간략한 설명"
                                    }
                                },
                                "required": ["name", "type"]
                            },
                            "description": "텍스트에서 식별된 주요 개체 목록"
                        },
                        "summary": {
                            "type": "STRING",
                            "description": "텍스트의 간결한 요약"
                        }
                    },
                    "required": ["key_points", "summary"]
                }
            )
            
            # 도구 정의
            extraction_tools = types.Tool(
                function_declarations=[extract_info],
            )
            
            # 함수 호출 응답 생성
            response = await self.gemini_model.generate_content_async(
                prompt,
                generation_config=types.GenerationConfig(
                    temperature=0.2,
                    tools=[extraction_tools]
                )
            )
            
            # 함수 호출 결과 처리
            if hasattr(response.candidates[0].content.parts[0], 'function_call'):
                function_call = response.candidates[0].content.parts[0].function_call
                extracted_data = function_call.args
                
                # 구조화된 데이터를 텍스트로 변환
                formatted_response = self._format_extracted_data(extracted_data)
            else:
                # 함수 호출이 없는 경우 일반 텍스트 응답 사용
                formatted_response = self._format_gemini_response(response.text)
            
            # 웹소켓 응답 처리
            if websocket:
                for chunk in self._simulate_streaming(formatted_response):
                    await self._send_chunk(websocket, chunk, "gemini")
                
                await websocket.send_json({
                    "type": "assistant",
                    "isFullResponse": True,
                    "model": "gemini"
                })
            
            return formatted_response
            
        except Exception as e:
            error_msg = f"Gemini 함수 호출 오류: {str(e)}"
            logger.error(error_msg)
            return f"죄송합니다. 구조화된 정보 추출 중 오류가 발생했습니다."

    def _format_extracted_data(self, data: Dict[str, Any]) -> str:
        """추출된 구조화 데이터를 사용자 친화적인 텍스트로 변환"""
        result = []
        
        # 요약 추가
        if "summary" in data:
            result.append(f"**요약**\n{data['summary']}\n")
        
        # 주요 포인트 추가
        if "key_points" in data and data["key_points"]:
            result.append("**주요 포인트**")
            for i, point in enumerate(data["key_points"], 1):
                result.append(f"{i}. {point}")
            result.append("")
        
        # 개체 정보 추가
        if "entities" in data and data["entities"]:
            result.append("**주요 개체**")
            for entity in data["entities"]:
                entity_type = entity.get("type", "")
                entity_desc = entity.get("description", "")
                
                if entity_desc:
                    result.append(f"* **{entity['name']}** ({entity_type}): {entity_desc}")
                else:
                    result.append(f"* **{entity['name']}** ({entity_type})")
            result.append("")
        
        return "\n".join(result)

    # 추가: 특정 도메인에 대한 함수 호출 정의
    def _get_domain_specific_tools(self, domain: str) -> Optional[types.Tool]:
        """도메인별 특화된 함수 호출 도구 정의"""
        if domain == "programming":
            # 프로그래밍 관련 함수 호출
            code_analysis = types.FunctionDeclaration(
                name="analyze_code",
                description="코드를 분석하고 개선점을 제안합니다",
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "language": {
                            "type": "STRING",
                            "description": "프로그래밍 언어"
                        },
                        "issues": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "description": {
                                        "type": "STRING",
                                        "description": "이슈 설명"
                                    },
                                    "severity": {
                                        "type": "STRING",
                                        "description": "심각도 (high, medium, low)"
                                    },
                                    "suggestion": {
                                        "type": "STRING",
                                        "description": "개선 제안"
                                    }
                                },
                                "required": ["description", "suggestion"]
                            },
                            "description": "코드에서 발견된 이슈 목록"
                        },
                        "best_practices": {
                            "type": "ARRAY",
                            "items": {
                                "type": "STRING"
                            },
                            "description": "코드 개선을 위한 모범 사례 제안"
                        }
                    },
                    "required": ["language", "issues", "best_practices"]
                }
            )
            return types.Tool(function_declarations=[code_analysis])
            
        elif domain == "document":
            # 문서 분석 관련 함수 호출
            document_analysis = types.FunctionDeclaration(
                name="analyze_document",
                description="문서를 분석하고 주요 정보를 추출합니다",
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "document_type": {
                            "type": "STRING",
                            "description": "문서 유형 (계약서, 보고서, 논문 등)"
                        },
                        "sections": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "title": {
                                        "type": "STRING",
                                        "description": "섹션 제목"
                                    },
                                    "content_summary": {
                                        "type": "STRING",
                                        "description": "섹션 내용 요약"
                                    }
                                },
                                "required": ["title", "content_summary"]
                            },
                            "description": "문서의 주요 섹션 목록"
                        },
                        "key_findings": {
                            "type": "ARRAY",
                            "items": {
                                "type": "STRING"
                            },
                            "description": "문서의 주요 발견점"
                        }
                    },
                    "required": ["document_type", "sections", "key_findings"]
                }
            )
            return types.Tool(function_declarations=[document_analysis])
        
        return None

    # 추가: 함수 호출 결과를 처리하는 일반 메서드
    def _process_function_call_result(self, function_call: Any) -> Dict[str, Any]:
        """함수 호출 결과를 처리하여 딕셔너리로 반환"""
        if not function_call or not hasattr(function_call, 'args'):
            return {}
            
        try:
            # 함수 호출 결과를 딕셔너리로 변환
            return function_call.args
        except Exception as e:
            logger.error(f"함수 호출 결과 처리 오류: {str(e)}")
            return {}

    async def _generate_claude_response(self, prompt: str, websocket: Optional[WebSocket] = None) -> str:
        """Claude 모델용 응답 생성 로직 - 동기식 클라이언트 사용"""
        try:
            # 동기식 API 호출
            response = self.anthropic.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # 응답 텍스트 추출
            response_text = response.content[0].text
            
            # 웹소켓으로 응답 전송 (스트리밍 시뮬레이션)
            if websocket:
                for chunk in self._simulate_streaming(response_text):
                    await self._send_chunk(websocket, chunk, "claude")
                
                await websocket.send_json({
                    "type": "assistant",
                    "isFullResponse": True,
                    "model": "claude"
                })
            
            return response_text
        except Exception as e:
            logger.error(f"Claude 응답 생성 오류: {e}")
            return f"죄송합니다. Claude 모델 응답 생성 중 오류가 발생했습니다: {str(e)}"

    async def _generate_local_response(self, prompt: str, websocket: Optional[WebSocket] = None) -> str:
        """로컬(Meta) 모델용 응답 생성 로직"""
        try:
            formatted_prompt = self.tokenizer.apply_chat_template(
                self._convert_to_chat_format(prompt),
                tokenize=False,
                add_generation_prompt=True
            )
            
            response = ""
            for chunk in self.local_model(formatted_prompt, max_tokens=512, stream=True):
                if chunk and "choices" in chunk:
                    text = chunk["choices"][0]["text"]
                    if text:
                        response += text
                        if websocket:
                            await self._send_chunk(websocket, text, "meta")
            
            if websocket:
                await websocket.send_json({
                    "type": "assistant",
                    "isFullResponse": True,
                    "model": "meta"
                })
            
            return response
            
        except Exception as e:
            logger.error(f"로컬 모델 응답 생성 오류: {e}")
            return "죄송합니다. 응답 생성 중 오류가 발생했습니다."
        
    def _convert_to_chat_format(self, prompt: str) -> List[Dict[str, str]]:
        """프롬프트를 채팅 형식으로 변환"""
        messages = []
        current_role = None
        current_content = []
        
        for line in prompt.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('시스템:'):
                if current_role:
                    messages.append({"role": current_role, "content": '\n'.join(current_content)})
                current_role = "system"
                current_content = [line[4:].strip()]
            elif line.startswith('사용자:'):
                if current_role:
                    messages.append({"role": current_role, "content": '\n'.join(current_content)})
                current_role = "user"
                current_content = [line[4:].strip()]
            elif line.startswith('어시스턴트:'):
                if current_role:
                    messages.append({"role": current_role, "content": '\n'.join(current_content)})
                current_role = "assistant"
                current_content = [line[7:].strip()]
            else:
                if current_content:
                    current_content.append(line)
        
        if current_role and current_content:
            messages.append({"role": current_role, "content": '\n'.join(current_content)})
            
        return messages

    def _simulate_streaming(self, text: str, chunk_size: int = 10) -> List[str]:
        """스트리밍 시뮬레이션 (Gemini는 스트리밍을 직접 지원하지 않을 경우)"""
        return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

    async def _send_chunk(self, websocket: WebSocket, text: str, model: str) -> None:
        """웹소켓을 통해 응답 청크 전송"""
        await websocket.send_json({
            "type": "assistant",
            "content": text,
            "streaming": True,
            "model": model
        })

    def _format_gemini_response(self, text: str) -> str:
        """Gemini 응답 포맷팅"""
        # 기본 리스트 형식 정리
        formatted = text.replace('•', '* ')
        
        # 코드 블록 정리
        code_pattern = r'```([a-zA-Z0-9]*)\n(.*?)\n```'
        formatted = re.sub(code_pattern, r'```\1\n\2\n```', formatted, flags=re.DOTALL)
        
        # 불필요한 줄바꿈 정리
        formatted = re.sub(r'\n{3,}', '\n\n', formatted)
        
        return formatted
    
    async def generate_response_with_reasoning(self, messages: List[ChatMessage], model: AIModel, 
                                           websocket: Optional[WebSocket] = None) -> str:
        """추론 기능이 강화된 응답 생성"""
        
        # 시스템 프롬프트 추출 및 강화
        system_prompt = next((msg.content for msg in messages if msg.role == MessageRole.SYSTEM), "")
        reasoning_prompt = system_prompt + "\n\n추가 지시사항: 복잡한 질문에 대답할 때는 다음과 같이 하세요:\n"
        reasoning_prompt += "1. 문제를 작은 부분으로 분해하세요\n"
        reasoning_prompt += "2. 각 부분에 대해 단계적으로 생각하세요\n"
        reasoning_prompt += "3. 중간 결론을 통해 최종 답변을 도출하세요\n"
        
        # 추론 강화 프롬프트로 교체
        for i, msg in enumerate(messages):
            if msg.role == MessageRole.SYSTEM:
                messages[i] = ChatMessage(MessageRole.SYSTEM, reasoning_prompt)
                break
        
        # 일반 응답 생성과 동일한 흐름 사용
        return await self.generate_response(messages, model, websocket)
    
    def _enhance_gemini_prompt(self, original_prompt: str) -> str:
        """Gemini 모델을 위한 프롬프트 강화"""
        # 시스템 지시사항과 사용자 메시지 분리
        system_prompt = ""
        user_messages = []
        
        for line in original_prompt.split("\n"):
            line = line.strip()
            if not line:
                continue
                
            if line.startswith("시스템:"):
                system_prompt += line[4:].strip() + "\n"
            elif line.startswith("사용자:"):
                user_messages.append(line[4:].strip())
        
        # 최종 프롬프트 조합
        enhanced_prompt = original_prompt
        
        # 프롬프트가 너무 짧거나 컨텍스트가 필요한 경우에만 강화
        if len(user_messages) <= 2 or len(original_prompt) < 200:
            enhanced_instruction = """
            이 대화에서 당신은 도움이 되는 AI 어시스턴트입니다. 
            사용자의 질문에 명확하고 정확하게 대답하세요.
            
            답변 작성 지침:
            1. 간결하고 명확하게 정보를 제공하세요.
            2. 한국어로 자연스럽게 대답하세요.
            3. 필요한 경우 예시를 들어 설명하세요.
            4. 정보가 부족한 경우, 확실한 내용만 답변하세요.
            """
            
            # 원본 프롬프트에 강화 지시사항 추가 (시스템 메시지로 추가)
            if "시스템:" in original_prompt:
                # 기존 시스템 메시지 교체
                enhanced_prompt = original_prompt.replace("시스템:", f"시스템: {enhanced_instruction}\n\n")
            else:
                # 시스템 메시지가 없는 경우 추가
                enhanced_prompt = f"시스템: {enhanced_instruction}\n\n" + original_prompt
        
        return enhanced_prompt
