"""监督纠错端到端测试 — Agent 循环 + 截图验证

使用 Mock 模型和 Mock 执行器验证监督纠错功能：
- 启用手动监督时，动作会进行截图比对验证
- 无变化时自动重试
"""

import base64
from typing import Optional

import pytest
from browser_agent.agent import BrowserAgent
from browser_agent.executors import BaseExecutor, Observation, ActionResult
from browser_agent.models.base import BaseModelClient, ModelResponse
from browser_agent.supervisor import Supervisor


class MockModelClient(BaseModelClient):
    """模拟模型客户端。"""
    def __init__(self, responses: list[ModelResponse]):
        self.responses = responses
        self.call_count = 0

    async def chat(self, messages, tools=None, temperature=0.7, max_tokens=4096):
        resp = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return resp

    async def chat_stream(self, messages, tools=None, temperature=0.7, max_tokens=4096):
        yield "mock stream"


class MockExecutor(BaseExecutor):
    """模拟执行器 — 返回预设的截图和动作结果。"""

    def __init__(self, screenshot_bytes: Optional[bytes] = None):
        self._screenshot_bytes = screenshot_bytes or self._make_test_image()
        self._current_url = "https://example.com"
        self._action_count = 0
        self._call_screenshot_count = 0

    @staticmethod
    def _make_test_image() -> bytes:
        from PIL import Image
        import io
        img = Image.new("RGB", (100, 100), (128, 128, 128))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()

    async def start(self): pass
    async def stop(self): pass

    def _bytes_to_b64(self, data: bytes) -> str:
        return base64.b64encode(data).decode()

    async def observe(self) -> Observation:
        return Observation(
            screenshot_base64=self._bytes_to_b64(self._screenshot_bytes),
            element_text="mock elements",
            url=self._current_url,
        )

    async def screenshot(self) -> bytes:
        self._call_screenshot_count += 1
        return self._screenshot_bytes

    async def act(self, action_name: str, arguments: dict) -> ActionResult:
        self._action_count += 1
        return ActionResult(text="action completed", success=True)

    @property
    def tools(self) -> list[dict]:
        return [{"type": "function", "function": {"name": "click", "parameters": {"type": "object", "properties": {"x": {"type": "integer"}}}}}]

    @property
    def info_for_model(self) -> str:
        return "You are testing."


class TestSupervisedAgent:
    """Agent 循环 + 监督纠错测试。"""

    @pytest.mark.asyncio
    async def test_supervision_no_retry_on_success(self):
        """监督启用 + 截图一致 → 默认不重试（阈值设置合理）。"""
        agent = BrowserAgent(
            max_steps=3,
            supervision_threshold=0.05,  # 启用监督
        )
        # 替换为 mock
        agent.executor = MockExecutor()
        agent.model = MockModelClient([
            ModelResponse(
                content="<observation>page</observation><thinking>click</thinking>",
                tool_calls=[{"id": "c1", "type": "function", "function": {"name": "click", "arguments": '{"x": 100}'}}],
            ),
            ModelResponse(
                content="<observation>done</observation><thinking>finished</thinking>",
                tool_calls=[{"id": "c2", "type": "function", "function": {"name": "finish", "arguments": '{"answer": "done"}'}}],
            ),
        ])

        result = await agent.run_async("test")
        assert len(result.steps) > 0
        assert result.success

    @pytest.mark.asyncio
    async def test_supervision_custom_threshold(self):
        """自定义监督阈值配置。"""
        agent = BrowserAgent(
            max_steps=3,
            supervision_threshold=0.20,
        )
        assert agent._supervisor_enabled is True
        assert agent._supervisor is not None
        assert agent._supervisor.threshold == 0.20

    def test_supervisor_disabled_by_default(self):
        """默认不启用监督（threshold=0）。"""
        agent = BrowserAgent(max_steps=3)
        assert agent._supervisor_enabled is False
        assert agent._supervisor is None

    @pytest.mark.asyncio
    async def test_supervision_verification_in_steps(self):
        """监督启用后，Step 中包含 verification 信息。"""
        executor = MockExecutor()
        agent = BrowserAgent(max_steps=3, supervision_threshold=0.05)
        agent.executor = executor
        agent.model = MockModelClient([
            ModelResponse(
                content="<observation>page</observation><thinking>click</thinking>",
                tool_calls=[{"id": "c1", "type": "function", "function": {"name": "click", "arguments": '{"x": 100}'}}],
            ),
            ModelResponse(
                content="<observation>done</observation><thinking>finished</thinking>",
                tool_calls=[{"id": "c2", "type": "function", "function": {"name": "finish", "arguments": '{"answer": "ok"}'}}],
            ),
        ])

        result = await agent.run_async("test")
        assert result.success
        # 验证 action step 包含 verification 信息
        has_verification = False
        for step in result.steps:
            if step.verification is not None:
                assert isinstance(step.verification.score, float)
                assert isinstance(step.verification.changed, bool)
                has_verification = True
                break
        assert has_verification, "监督启用的 agent 执行后 Step 应包含 verification"
