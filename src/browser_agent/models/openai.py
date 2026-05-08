"""OpenAI API 客户端"""

from typing import Optional

from openai import AsyncOpenAI

from browser_agent.models.base import BaseModelClient, ModelResponse


class OpenAIClient(BaseModelClient):
    """OpenAI / 兼容 API 客户端。"""

    def __init__(self, model: str = "gpt-4o",
                 api_base: Optional[str] = None,
                 api_key: str = ""):
        self.model = model
        kwargs = {"api_key": api_key}
        if api_base:
            kwargs["base_url"] = api_base
        self.client = AsyncOpenAI(**kwargs)

    async def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ModelResponse:
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        response = await self.client.chat.completions.create(**params)
        choice = response.choices[0]
        msg = choice.message

        return ModelResponse(
            content=msg.content or "",
            tool_calls=(
                [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                 for tc in msg.tool_calls]
                if msg.tool_calls else []
            ),
            finish_reason=choice.finish_reason or "stop",
        )

    async def chat_stream(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        stream = await self.client.chat.completions.create(**params)
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content
