"""Mano-P 集成测试"""

import pytest

from browser_agent.executors import BaseExecutor


def test_manop_executor_creation():
    """测试 ManoPExecutor 创建。"""
    executor = BaseExecutor.create("mano_p", api_base="https://example.com")
    assert executor is not None
    assert len(executor.tools) > 0

    # 验证工具定义
    tool_names = {t["function"]["name"] for t in executor.tools}
    assert "computer" in tool_names

    # 验证 action 枚举
    params = executor.tools[0]["function"]["parameters"]
    actions = params["properties"]["action"]["enum"]
    assert "left_click" in actions
    assert "type" in actions
    assert "scroll" in actions
    assert "done" in actions

    # 验证 info_for_model
    info = executor.info_for_model
    assert "desktop GUI" in info
    assert "screenshot" in info


def test_manop_model_client():
    """测试 ManoPClient 初始化。"""
    from browser_agent.models.mano_p import ManoPClient
    client = ManoPClient(api_base="https://mano.mininglamp.com", api_key="test-key")
    assert client.api_base == "https://mano.mininglamp.com"
    assert client.session_id is None


@pytest.mark.asyncio
async def test_manop_executor_tools():
    """测试 ManoPExecutor 工具定义完整性。"""
    executor = BaseExecutor.create("mano_p")
    tools = executor.tools
    assert len(tools) == 1, "Mano-P 应只有 1 个工具定义"

    computer_tool = tools[0]["function"]
    assert computer_tool["name"] == "computer"
    assert "parameters" in computer_tool
