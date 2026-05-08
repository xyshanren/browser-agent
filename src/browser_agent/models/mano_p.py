"""Mano-P 云端 API 客户端

Mano-P 1.0 是明略科技开源的 GUI-VLA（视觉-语言-动作）模型。
支持通过纯视觉理解操作桌面 GUI（不限于浏览器）。

API 端点（已通过 OpenAPI 验证）:
- POST /v1/sessions                    — 创建会话
- POST /v1/sessions/{id}/step          — 执行一步推理
- POST /v1/sessions/{id}/close         — 关闭会话
- POST /v1/devices/{id}/stop           — 停止设备会话

参考: https://github.com/Mininglamp-AI/Mano-P
"""

import uuid
from typing import Optional

import httpx

from browser_agent.models.base import BaseModelClient, ModelResponse


class ManoPClient(BaseModelClient):
    """Mano-P 云端 API 客户端。

    Mano-P 使用会话（session）模式：
    1. create_session(task) → 获得 session_id
    2. step(screenshot_b64, tool_results) → 服务器返回 actions
    3. 执行 actions → 继续 step() 循环
    4. 完成后 close_session()
    """

    def __init__(
        self,
        model: str = "Mano-P-1.0-4B",
        api_base: str = "https://mano.mininglamp.com",
        api_key: str = "",
    ):
        self.model = model
        self.api_base = api_base.rstrip("/")
        self.session_id: Optional[str] = None
        self.device_id: Optional[str] = None

    async def create_session(self, task: str, platform: str = "Windows") -> str:
        """创建自动化会话。

        POST /v1/sessions
        Request: {task, device_id, platform}
        Response: {session_id, reused}
        """
        if not self.device_id:
            self.device_id = f"browser-agent-{uuid.uuid4().hex[:8]}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.api_base}/v1/sessions",
                json={
                    "task": task,
                    "device_id": self.device_id,
                    "platform": platform,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        self.session_id = data.get("session_id")
        if not self.session_id:
            raise RuntimeError(f"创建 Mano-P 会话失败: {data}")
        return self.session_id

    async def step(self, screenshot_b64: str = "", tool_results: Optional[list[dict]] = None) -> dict:
        """执行一步推理。

        POST /v1/sessions/{session_id}/step
        Request: {request_id, screenshot_b64?, tool_results}
        Response: {reasoning, actions, status}
        """
        if not self.session_id:
            raise RuntimeError("请先调用 create_session()")

        payload: dict = {
            "request_id": str(uuid.uuid4()),
            "tool_results": tool_results or [],
        }
        if screenshot_b64:
            payload["screenshot_b64"] = screenshot_b64

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.api_base}/v1/sessions/{self.session_id}/step",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def close_session(self, skip_eval: bool = False):
        """关闭会话。"""
        if not self.session_id:
            return
        params = f"skip_eval={str(skip_eval).lower()}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{self.api_base}/v1/sessions/{self.session_id}/close?{params}",
                json={},
            )

    async def chat(self, messages, tools=None, temperature=0.7, max_tokens=4096):
        raise NotImplementedError(
            "Mano-P 使用会话模式。请使用:\n"
            "  client.create_session(task)\n"
            "  data = await client.step(screenshot_b64, tool_results)\n"
        )

    async def chat_stream(self, messages, tools=None, temperature=0.7, max_tokens=4096):
        raise NotImplementedError("Mano-P 不支持流式响应")
