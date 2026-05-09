"""端到端测试扩展 — 多步骤编排 + 复杂交互

使用 Mock 模拟多步骤、多站点、表单填写等复杂场景。
全模拟运行，无需真实浏览器或 VLM 模型。
"""

import asyncio
from browser_agent import BrowserAgent
from browser_agent.models.base import BaseModelClient, ModelResponse
from browser_agent.executors import BaseExecutor, Observation, ActionResult
from browser_agent.utils.logger import logger


class MockModelClient(BaseModelClient):
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
    def __init__(self):
        self._url = "https://www.baidu.com"
        self._page_text = "搜索输入框 新闻 地图"
        self._actions = []

    async def start(self): pass
    async def stop(self): pass

    async def observe(self) -> Observation:
        import base64
        return Observation(
            screenshot_base64=base64.b64encode(b"fake_image_data").decode(),
            element_text=self._page_text,
            url=self._url,
        )

    async def act(self, action_name: str, arguments: dict) -> ActionResult:
        self._actions.append((action_name, arguments))
        if action_name == "navigate":
            self._url = arguments.get("url", self._url)
            self._page_text = "页面已加载 内容区域 链接1 链接2"
            return ActionResult(text=f"导航到 {self._url}", success=True)
        elif action_name == "type_text":
            return ActionResult(text=f"已输入: {arguments.get('text', '')}", success=True)
        elif action_name == "click":
            # 模拟点击后页面变化
            self._page_text = "搜索结果 标题1 标题2 标题3"
            return ActionResult(text=f"点击了 {arguments.get('mark_id', '?')}", success=True)
        elif action_name == "scroll":
            self._page_text = "页面底部 页脚 版权信息"
            return ActionResult(text="已滚动", success=True)
        elif action_name == "extract_text":
            return ActionResult(text="温度: 28°C, 湿度: 65%, 风力: 3级", success=True)
        return ActionResult(text="done", success=True)

    @property
    def tools(self) -> list[dict]:
        return [
            {"type": "function", "function": {"name": "navigate", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}}}},
            {"type": "function", "function": {"name": "type_text", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "mark_id": {"type": "integer"}, "submit": {"type": "boolean"}}}}},
            {"type": "function", "function": {"name": "click", "parameters": {"type": "object", "properties": {"mark_id": {"type": "integer"}}}}},
            {"type": "function", "function": {"name": "extract_text", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}}},
            {"type": "function", "function": {"name": "finish", "parameters": {"type": "object", "properties": {"answer": {"type": "string"}}}}},
        ]

    @property
    def info_for_model(self) -> str:
        return "You are a browser agent."


async def test_multi_step_workflow():
    """测试多步骤编排：导航 → 搜索 → 提取 → 完成。"""
    logger.info("🧪 E2E: Multi-step workflow (navigate → search → extract → finish)")

    agent = BrowserAgent(max_steps=10)
    agent.executor = MockExecutor()
    agent.model = MockModelClient([
        # 步骤 1: 导航到百度
        ModelResponse(
            content="<observation>看到百度首页</observation><thinking>先导航到百度</thinking>",
            tool_calls=[{"id": "c1", "type": "function", "function": {"name": "navigate", "arguments": '{"url": "https://www.baidu.com"}'}}],
        ),
        # 步骤 2: 输入搜索
        ModelResponse(
            content="<observation>百度首页已加载</observation><thinking>输入搜索关键词</thinking>",
            tool_calls=[{"id": "c2", "type": "function", "function": {"name": "type_text", "arguments": '{"text": "深圳天气", "mark_id": 0, "submit": true}'}}],
        ),
        # 步骤 3: 提取结果
        ModelResponse(
            content="<observation>搜索结果页</observation><thinking>提取天气信息</thinking>",
            tool_calls=[{"id": "c3", "type": "function", "function": {"name": "extract_text", "arguments": '{"query": "温度"}'}}],
        ),
        # 步骤 4: 完成
        ModelResponse(
            content="<observation>数据已提取</observation><thinking>任务完成</thinking>",
            tool_calls=[{"id": "c4", "type": "function", "function": {"name": "finish", "arguments": '{"answer": "深圳今天28°C"}'}}],
        ),
    ])

    result = await agent.run_async("查深圳天气")
    assert result.success
    assert len(result.steps) >= 4
    logger.info(f"  ✅ Steps: {len(result.steps)}, Result: {result.text[:100]}")


async def test_error_recovery():
    """测试错误恢复：模型返回非法调用后自动恢复。"""
    logger.info("🧪 E2E: Error recovery (invalid tool call → recover → finish)")

    agent = BrowserAgent(max_steps=10)
    agent.executor = MockExecutor()
    agent.model = MockModelClient([
        # 非法调用（不存在的工具）
        ModelResponse(
            content="<observation>page</observation><thinking>未知操作</thinking>",
            tool_calls=[{"id": "c1", "type": "function", "function": {"name": "non_existent_tool", "arguments": '{}'}}],
        ),
        # 恢复 → 导航
        ModelResponse(
            content="<observation>尝试恢复</observation><thinking>使用标准工具</thinking>",
            tool_calls=[{"id": "c2", "type": "function", "function": {"name": "navigate", "arguments": '{"url": "https://example.com"}'}}],
        ),
        # 完成
        ModelResponse(
            content="<observation>已导航</observation><thinking>完成</thinking>",
            tool_calls=[{"id": "c3", "type": "function", "function": {"name": "finish", "arguments": '{"answer": "已恢复并完成任务"}'}}],
        ),
    ])

    result = await agent.run_async("测试错误恢复")
    assert result.success
    logger.info(f"  ✅ Steps: {len(result.steps)}, Result: {result.text[:100]}")


async def test_form_filling():
    """测试表单填写流程。"""
    logger.info("🧪 E2E: Form filling workflow")

    agent = BrowserAgent(max_steps=10)
    agent.executor = MockExecutor()
    agent.model = MockModelClient([
        # 输入文本
        ModelResponse(
            content="<observation>表单页</observation><thinking>填写用户名</thinking>",
            tool_calls=[{"id": "c1", "type": "function", "function": {"name": "type_text", "arguments": '{"text": "test_user", "mark_id": 0}'}}],
        ),
        # 点击提交
        ModelResponse(
            content="<observation>已输入</observation><thinking>点击提交</thinking>",
            tool_calls=[{"id": "c2", "type": "function", "function": {"name": "click", "arguments": '{"mark_id": 1}'}}],
        ),
        # 完成
        ModelResponse(
            content="<observation>提交成功</observation><thinking>完成</thinking>",
            tool_calls=[{"id": "c3", "type": "function", "function": {"name": "finish", "arguments": '{"answer": "表单已提交"}'}}],
        ),
    ])

    result = await agent.run_async("填写登录表单")
    assert result.success
    assert len(result.steps) == 3
    logger.info(f"  ✅ Steps: {len(result.steps)}, Result: {result.text}")


async def main():
    logger.info("=" * 60)
    logger.info("🚀 Browser-Agent E2E Test Suite Extended")
    logger.info("=" * 60)

    await test_multi_step_workflow()
    await test_error_recovery()
    await test_form_filling()

    logger.info("=" * 60)
    logger.info("✅ All extended E2E tests passed!")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
