"""模型客户端抽象基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModelResponse:
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    finish_reason: str = "stop"


class BaseModelClient(ABC):
    """所有模型后端的统一接口。"""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ModelResponse:
        """发送聊天请求，返回模型响应。"""
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        """流式聊天，逐块 yield 文本内容。"""
        ...
        yield  # pragma: no cover

    @classmethod
    def create(cls, model_type: str, **kwargs) -> "BaseModelClient":
        """工厂方法：根据类型创建客户端。"""
        if model_type == "vllm":
            from browser_agent.models.vllm import VLLMClient
            return VLLMClient(**kwargs)
        elif model_type == "openai":
            from browser_agent.models.openai import OpenAIClient
            return OpenAIClient(**kwargs)
        elif model_type == "ollama":
            from browser_agent.models.ollama import OllamaClient
            return OllamaClient(**kwargs)
        else:
            raise ValueError(f"不支持的模型类型: {model_type}，可选: vllm, openai, ollama")
