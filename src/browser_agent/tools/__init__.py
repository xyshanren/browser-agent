"""工具定义 — 为 VLM 提供可调用的浏览器工具集"""

from browser_agent.tools.browser_tools import (
    BROWSER_TOOLS,
    parse_tool_call,
    tool_goto,
    tool_click,
    tool_type_text,
    tool_scroll,
    tool_go_back,
    tool_reload,
    tool_wait,
    tool_finish,
)

__all__ = [
    "BROWSER_TOOLS",
    "parse_tool_call",
    "tool_goto",
    "tool_click",
    "tool_type_text",
    "tool_scroll",
    "tool_go_back",
    "tool_reload",
    "tool_wait",
    "tool_finish",
]
