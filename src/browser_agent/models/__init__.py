"""模型客户端 — 多后端抽象"""

from browser_agent.models.base import BaseModelClient, ModelResponse
from browser_agent.models.vllm import VLLMClient
from browser_agent.models.openai import OpenAIClient
from browser_agent.models.ollama import OllamaClient
from browser_agent.models.mano_p import ManoPClient

__all__ = ["BaseModelClient", "ModelResponse", "VLLMClient", "OpenAIClient", "OllamaClient", "ManoPClient"]
