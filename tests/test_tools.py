"""工具模块测试"""

import json

from browser_agent.tools.browser_tools import BROWSER_TOOLS, parse_tool_call


def test_tool_schemas():
    """验证工具 Schema 定义完整性。"""
    tool_names = {t["function"]["name"] for t in BROWSER_TOOLS}
    expected = {"goto", "click", "type_text", "scroll", "go_back", "reload", "wait", "finish"}
    assert tool_names == expected, f"工具不匹配: {tool_names} vs {expected}"

    # 验证每个工具都有 description 和 parameters
    for t in BROWSER_TOOLS:
        func = t["function"]
        assert "description" in func, f"工具 {func['name']} 缺少 description"
        assert "parameters" in func, f"工具 {func['name']} 缺少 parameters"


def test_parse_tool_call():
    """测试工具调用解析。"""
    # OpenAI 格式（arguments 为 JSON 字符串）
    tool_call = {
        "id": "call_abc",
        "type": "function",
        "function": {
            "name": "click",
            "arguments": '{"mark_id": 5}',
        },
    }
    name, call_id, args = parse_tool_call(tool_call)
    assert name == "click"
    assert call_id == "call_abc"
    assert args == {"mark_id": 5}

    # 当 arguments 已经是 dict 格式
    tool_call2 = {
        "id": "call_def",
        "type": "function",
        "function": {
            "name": "type_text",
            "arguments": {"mark_id": 3, "text": "hello"},
        },
    }
    name2, call_id2, args2 = parse_tool_call(tool_call2)
    assert name2 == "type_text"
    assert args2 == {"mark_id": 3, "text": "hello"}
