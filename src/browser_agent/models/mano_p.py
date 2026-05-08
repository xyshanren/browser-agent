"""Mano-P 云端 API 客户端

Mano-P 1.0 是明略科技开源的 GUI-VLA（视觉-语言-动作）模型。
支持通过纯视觉理解操作桌面 GUI（不限于浏览器）。

本客户端通过 Mano-P 云端 API（mano.mininglamp.com）或自行部署的端点，
实现纯视觉桌面 GUI 自动化。

参考: https://github.com/Mininglamp-AI/Mano-P
"""

import json
import uuid
from typing import Any, Optional

import httpx

from browser_agent.models.base import BaseModelClient, ModelResponse


class ManoPClient(BaseModelClient):
    """Mano-P 云端 API 客户端。

    Mano-P 使用会话（session）模式：
    1. 创建会话 → 获得 session_id
    2. 发送截图 + 任务描述 → 服务器返回 actions
    3. 执行 actions → 发送结果 → 继续循环
    4. 结束后关闭会话

    Actions 格式:
    {
        "name": "computer",
        "input": {
            "action": "left_click",        # 动作类型
            "coordinate": [0.5, 0.3],      # 归一化坐标 (0-1)
            "text": "hello",               # 输入文本
            "modifiers": ["ctrl"],
            "mains": ["c"],
            "scroll_direction": "down",
        }
    }
    """

    def __init__(
        self,
        model: str = "Mano-P-1.0-4B",
        api_base: str = "https://mano.mininglamp.com",
        api_key: str = "",
    ):
        self.model = model
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.session_id: Optional[str] = None
        self.device_id: Optional[str] = None

    async def create_session(self, task: str, platform: str = "Windows") -> str:
        """创建一个新的自动化会话。

        Returns:
            session_id: 会话 ID
        """
        if not self.device_id:
            self.device_id = f"browser-agent-{uuid.uuid4().hex[:8]}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.api_base}/v1/devices/{self.device_id}/start",
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

    async def step(self, tool_results: list[dict]) -> dict:
        """执行一步推理，返回模型预测的动作。

        Args:
            tool_results: 上一步动作执行结果列表

        Returns:
            {
                "reasoning": "...",        # 模型的推理过程
                "actions": [...],          # 要执行的动作列表
                "status": "RUNNING/DONE",  # 任务状态
                "action_desc": "...",      # 动作描述
            }
        """
        if not self.session_id:
            raise RuntimeError("请先调用 create_session()")

        payload = {
            "request_id": str(uuid.uuid4()),
            "tool_results": tool_results,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.api_base}/v1/sessions/{self.session_id}/step",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def close_session(self, skip_eval: bool = False, close_reason: Optional[str] = None):
        """关闭会话。"""
        if not self.session_id:
            return
        params = f"skip_eval={str(skip_eval).lower()}"
        if close_reason:
            params += f"&close_reason={close_reason}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{self.api_base}/v1/sessions/{self.session_id}/close?{params}",
                json={},
            )

    async def chat(self, messages, tools=None, temperature=0.7, max_tokens=4096):
        """基类接口实现 — Mano-P 不使用标准 chat 接口。
        使用 create_session() + step() + close_session() 替代。
        """
        raise NotImplementedError(
            "Mano-P 使用会话模式。请使用:\n"
            "  client = ManoPClient()\n"
            "  await client.create_session(task)\n"
            "  data = await client.step(tool_results)\n"
            "  actions = data['actions']"
        )

    async def chat_stream(self, messages, tools=None, temperature=0.7, max_tokens=4096):
        raise NotImplementedError("Mano-P 不支持流式响应")
