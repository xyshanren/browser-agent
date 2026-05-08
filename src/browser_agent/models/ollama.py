"""Ollama 本地客户端"""

from typing import Optional

import httpx

from browser_agent.models.base import BaseModelClient, ModelResponse


class OllamaClient(BaseModelClient):
    """Ollama 本地推理客户端。"""

    def __init__(self, model: str = "qwen2.5-vl:3b",
                 api_base: str = "http://localhost:11434",
                 api_key: str = ""):
        self.model = model
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key

    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        """将 OpenAI 格式消息转换为 Ollama 格式。"""
        result = []
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "user")

            # 处理多模态消息（含图片）
            if isinstance(content, list):
                # Ollama 格式：images 字段
                texts = []
                images = []
                for part in content:
                    if part.get("type") == "text":
                        texts.append(part["text"])
                    elif part.get("type") == "image_url":
                        img_url = part["image_url"]["url"]
                        if img_url.startswith("data:image"):
                            # 提取 base64 数据
                            _, b64 = img_url.split(",", 1)
                            images.append(b64)
                result.append({
                    "role": role,
                    "content": "\n".join(texts),
                    "images": images if images else None,
                })
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

        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.api_base}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = data.get("message", {}).get("content", "")

        # Ollama 目前不支持原生 tool calling，返回纯文本
        return ModelResponse(content=content)

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

        async with httpx.AsyncClient() as client:
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
