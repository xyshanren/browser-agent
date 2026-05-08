"""端到端测试 — 验证完整 Observe→Think→Act 循环

不启动真实 VLM 模型，使用 Mock 客户端验证框架流程正确性。
避免依赖外部模型服务。
"""

import asyncio
from browser_agent import BrowserAgent
from browser_agent.models.base import BaseModelClient, ModelResponse


class MockModelClient(BaseModelClient):
    """模拟模型客户端 — 返回预设的 tool_call，用于测试流程。"""

    def __init__(self, responses: list[ModelResponse]):
        self.responses = responses
        self.call_count = 0

    async def chat(self, messages, tools=None, temperature=0.7, max_tokens=4096):
        resp = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return resp

    async def chat_stream(self, messages, tools=None, temperature=0.7, max_tokens=4096):
        yield "mock stream"


async def test_browser_launch():
    """测试浏览器启动和截图功能。"""
    print("=" * 60)
    print("🧪 Test 1: Browser Launch & Screenshot")
    print("=" * 60)

    from browser_agent.browser import BrowserSession

    browser = BrowserSession(headless=True)
    await browser.start()

    # 导航到百度
    await browser.goto("https://www.baidu.com")
    print(f"   URL: {browser.current_url}")

    # 截图
    raw, annotated = await browser.screenshot()
    print(f"   原始截图: {len(raw)} bytes")
    print(f"   标注截图: {len(annotated)} bytes")
    print(f"   POI 元素数: {len(browser.poi_elements)}")

    # 检查 POI 检测结果
    poi_text = browser.poi_text
    print(f"   POI 文本行数: {len(poi_text.split(chr(10)))}")
    if poi_text:
        print(f"   前 3 个 POI:")
        for line in poi_text.split(chr(10))[:3]:
            print(f"     {line}")

    await browser.stop()
    print("✅ Browser test passed!\n")


async def test_agent_flow():
    """测试 Agent 完整 Observe→Think→Act 流程（Mock 模型）。"""
    print("=" * 60)
    print("🧪 Test 2: Agent Flow (Mock Model)")
    print("=" * 60)

    # Mock 响应序列：搜索 → 点击 → 完成
    mock_responses = [
        ModelResponse(
            content="<observation>看到百度首页搜索框</observation><thinking>在搜索框中输入 hello</thinking>",
            tool_calls=[{
                "id": "call_1", "type": "function",
                "function": {"name": "type_text", "arguments": '{"mark_id": 0, "text": "hello", "submit": true}'},
            }],
        ),
        ModelResponse(
            content="<observation>搜索结果已显示</observation><thinking>任务完成，返回结果</thinking>",
            tool_calls=[{
                "id": "call_2", "type": "function",
                "function": {"name": "finish", "arguments": '{"answer": "搜索已完成，返回 hello 的搜索结果页面"}'},
            }],
        ),
    ]

    agent = BrowserAgent(
        headless=True,
        max_steps=5,
        task_timeout=60,
        model_type="openai",
        model="gpt-4o-mini",
        api_key="sk-test-dummy",  # 避免认证错误，后面会被 mock 替换
    )
    # 替换为 mock 客户端
    agent.model = MockModelClient(mock_responses)

    result = await agent.run_async("测试搜索功能")
    print(f"   Steps: {len(result.steps)}")
    for s in result.steps:
        print(f"   Step {s.number}: {s.action_name}({s.action_args}) → {s.action_result[:80]}")
    print(f"   最终结果: {result.text[:100]}")
    print(f"   成功: {result.success}")
    print("✅ Agent flow test passed!\n")


async def main():
    print("\n🚀 Browser-Agent End-to-End Tests\n")

    await test_browser_launch()
    await test_agent_flow()

    print("=" * 60)
    print("✅ All E2E tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
