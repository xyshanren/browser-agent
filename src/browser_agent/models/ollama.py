"""Ollama 本地客户端 — 支持多模态 + 工具调用"""

import json
from typing import Optional

import httpx

from browser_agent.models.base import BaseModelClient, ModelResponse


class OllamaClient(BaseModelClient):
    """Ollama 本地推理客户端。

    支持:
    - 纯文本聊天
    - 多模态（截图 + 文本）
    - 工具调用（Function Calling）
    - 流式输出
    """

    def __init__(self, model: str = "qwen3-vl:2b",
                 api_base: str = "http://localhost:11434",
                 api_key: str = ""):
        self.model = model
        self.api_base = api_base.rstrip("/")

    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        """将 OpenAI 格式消息转换为 Ollama 格式。

        Ollama 消息格式：
        - 纯文本: {"role": "user", "content": "hello"}
        - 多模态: {"role": "user", "content": "描述图片", "images": ["base64..."]}
        - 工具结果: {"role": "tool", "content": "结果"}
        """
        result = []
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "user")

            # 处理多模态消息（含图片）
            if isinstance(content, list):
                texts = []
                images = []
                for part in content:
                    if part.get("type") == "text":
                        texts.append(part["text"])
                    elif part.get("type") == "image_url":
                        img_url = part["image_url"]["url"]
                        if img_url.startswith("data:image"):
                            _, b64 = img_url.split(",", 1)
                            images.append(b64)
                entry = {"role": role, "content": "\n".join(texts)}
                if images:
                    entry["images"] = images
                result.append(entry)
            else:
                result.append({"role": role, "content": str(content)})
        return result

    async def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ModelResponse:
        ollama_messages = self._convert_messages(messages)

        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), trust_env=False) as client:
            resp = await client.post(f"{self.api_base}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        message = data.get("message", {})
        content = message.get("content", "") or ""
        tool_calls_raw = message.get("tool_calls", [])

        # 解析 Ollama 工具调用格式 → 标准 OpenAI 格式
        tool_calls = []
        for tc in tool_calls_raw:
            func = tc.get("function", {})
            arguments = func.get("arguments", {})
            # Ollama 可能返回 dict 或 str，统一转为 JSON 字符串
            if isinstance(arguments, dict):
                arguments_str = json.dumps(arguments, ensure_ascii=False)
            else:
                arguments_str = str(arguments)
            tool_calls.append({
                "id": tc.get("id", f"call_{id(tc)}"),
                "type": "function",
                "function": {
                    "name": func.get("name", ""),
                    "arguments": arguments_str,
                },
            })

        return ModelResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop",
        )

    async def chat_stream(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        ollama_messages = self._convert_messages(messages)

        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), trust_env=False) as client:
            async with client.stream("POST", f"{self.api_base}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line:
                        import json
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if data.get("done"):
                            break
