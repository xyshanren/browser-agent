"""消息历史管理 — 上下文窗口控制"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class MessageLabel(str, Enum):
    SYSTEM = "system"
    TASK = "task"
    SCREENSHOT = "screenshot"
    AGENT_RESPONSE = "agent_response"
    TOOL_RESULT = "tool_result"


@dataclass
class Message:
    role: MessageRole
    content: str
    label: Optional[MessageLabel] = None
    image_base64: Optional[str] = None
    tool_calls: list[dict] = field(default_factory=list)
    tool_call_id: Optional[str] = None


@dataclass
class MessageHistory:
    messages: list[Message] = field(default_factory=list)

    def add(self, msg: Message):
        self.messages.append(msg)

    def add_text(self, role: MessageRole, content: str, label: Optional[MessageLabel] = None):
        self.messages.append(Message(role=role, content=content, label=label))

    def add_image(self, role: MessageRole, content: str, image_base64: str, label: Optional[MessageLabel] = None):
        self.messages.append(Message(role=role, content=content, label=label, image_base64=image_base64))

    def add_tool_calls(self, content: str, tool_calls: list[dict], label: Optional[MessageLabel] = None):
        self.messages.append(Message(role=MessageRole.ASSISTANT, content=content, label=label, tool_calls=tool_calls))

    def add_tool_result(self, content: str, tool_call_id: str):
        self.messages.append(Message(role=MessageRole.TOOL, content=content, label=MessageLabel.TOOL_RESULT, tool_call_id=tool_call_id))

    def get_system_prompt(self) -> Optional[str]:
        for msg in self.messages:
            if msg.role == MessageRole.SYSTEM:
                return msg.content
        return None

    def build_openai_messages(self, keep_max_screenshots: int = 1) -> list[dict]:
        """构建 OpenAI 格式的消息列表，控制截图保留数量以节省 token。"""
        result = []
        screenshot_count = 0

        # 从后往前遍历，只保留最近的 keep_max_screenshots 张截图
        reversed_msgs = list(reversed(self.messages))
        filtered = []
        for msg in reversed_msgs:
            if msg.label == MessageLabel.SCREENSHOT and msg.image_base64:
                if screenshot_count < keep_max_screenshots:
                    screenshot_count += 1
                    filtered.append(msg)
                # else: 丢弃旧的截图
            else:
                filtered.append(msg)

        for msg in reversed(filtered):
            if msg.role == MessageRole.TOOL:
                result.append({
                    "role": "tool",
                    "content": msg.content,
                    "tool_call_id": msg.tool_call_id,
                })
            elif msg.tool_calls:
                result.append({
                    "role": "assistant",
                    "content": msg.content or None,
                    "tool_calls": [
                        {
                            "id": tc.get("id", "call_1"),
                            "type": "function",
                            "function": {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]},
                        }
                        for tc in msg.tool_calls
                    ],
                })
            elif msg.image_base64:
                result.append({
                    "role": msg.role.value,
                    "content": [
                        {"type": "text", "text": msg.content},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{msg.image_base64}"}},
                    ],
                })
            else:
                result.append({
                    "role": msg.role.value,
                    "content": msg.content,
                })

        return result

    def __len__(self) -> int:
        return len(self.messages)
