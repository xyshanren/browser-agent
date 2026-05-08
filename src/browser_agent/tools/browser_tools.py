"""浏览器工具函数定义 — 供 VLM 调用的工具集"""

import json
from typing import Any, Callable

from browser_agent.browser import BrowserSession

# ── 工具 Schema 定义（OpenAI Tool Calling 格式） ──

BROWSER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "goto",
            "description": "导航到指定的 URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要访问的网页地址，必须是完整的 URL"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "点击页面上指定编号的交互元素",
            "parameters": {
                "type": "object",
                "properties": {
                    "mark_id": {"type": "integer", "description": "要点击的元素的 Mark ID（编号）"},
                },
                "required": ["mark_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "在指定元素中输入文本，可选择输入完成后提交（按 Enter）",
            "parameters": {
                "type": "object",
                "properties": {
                    "mark_id": {"type": "integer", "description": "要输入文本的元素的 Mark ID"},
                    "text": {"type": "string", "description": "要输入的文本内容"},
                    "submit": {"type": "boolean", "description": "输入完成后是否按 Enter 提交"},
                },
                "required": ["mark_id", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "滚动页面或指定元素",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down", "left", "right"],
                        "description": "滚动方向",
                    },
                    "mark_id": {
                        "type": "integer",
                        "description": "要滚动的元素 Mark ID，-1 表示滚动整个页面",
                    },
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "go_back",
            "description": "后退到上一页",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reload",
            "description": "刷新当前页面",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wait",
            "description": "等待 3 秒，适用于页面正在加载或需要等待的情况",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "任务已完成，返回最终结果。在完成用户要求的任务后使用此工具提供回答。",
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string", "description": "给用户的最终回答"},
                },
                "required": ["answer"],
            },
        },
    },
]

# ── 工具名称到浏览器方法映射 ──

_TOOL_BROWSER_MAP: dict[str, str] = {
    "goto": "goto",
    "click": "click",
    "type_text": "type_text",
    "scroll": "scroll",
    "go_back": "go_back",
    "reload": "reload",
    "wait": "wait",
}


# ── 工具执行函数 ──


async def tool_goto(browser: BrowserSession, url: str) -> str:
    """执行导航操作。"""
    await browser.goto(url)
    return f"已导航到: {url}"


async def tool_click(browser: BrowserSession, mark_id: int) -> str:
    """执行点击操作。"""
    await browser.click(mark_id)
    element_info = browser.poi_elements[mark_id] if mark_id < len(browser.poi_elements) else {}
    tag = element_info.get("tag", "unknown")
    text = element_info.get("text", "") or ""
    return f"已点击元素 [{mark_id}] <{tag}> {text[:50]}"


async def tool_type_text(browser: BrowserSession, mark_id: int, text: str, submit: bool = False) -> str:
    """执行输入操作。"""
    await browser.type_text(mark_id, text, submit=submit)
    return f"已在元素 [{mark_id}] 输入: \"{text}\"" + (" 并按 Enter 提交" if submit else "")


async def tool_scroll(browser: BrowserSession, direction: str, mark_id: int = -1) -> str:
    """执行滚动操作。"""
    await browser.scroll(direction, mark_id)
    return f"已向 {direction} 滚动"


async def tool_go_back(browser: BrowserSession) -> str:
    """执行后退操作。"""
    await browser.go_back()
    return "已后退到上一页"


async def tool_reload(browser: BrowserSession) -> str:
    """执行刷新操作。"""
    await browser.reload()
    return "页面已刷新"


async def tool_wait(browser: BrowserSession) -> str:
    """执行等待操作。"""
    await browser.wait()
    return "已等待 3 秒"


async def tool_finish(browser: BrowserSession, answer: str) -> str:
    """任务完成，返回结果。"""
    return answer


# ── 工具调度 ──


async def execute_tool(browser: BrowserSession, tool_name: str, arguments: dict) -> str:
    """根据工具名称执行对应的浏览器操作。"""
    tool_map = {
        "goto": tool_goto,
        "click": tool_click,
        "type_text": tool_type_text,
        "scroll": tool_scroll,
        "go_back": tool_go_back,
        "reload": tool_reload,
        "wait": tool_wait,
        "finish": tool_finish,
    }

    func = tool_map.get(tool_name)
    if not func:
        return f"错误: 未知工具 '{tool_name}'"

    return await func(browser, **arguments)


# ── 工具调用解析 ──


def parse_tool_call(tool_call: dict) -> tuple[str, str, dict]:
    """解析模型的 tool_call 响应，返回 (tool_name, tool_call_id, arguments)。"""
    func = tool_call.get("function", {})
    tool_name = func.get("name", "")
    arguments_raw = func.get("arguments", "{}")
    if isinstance(arguments_raw, str):
        arguments = json.loads(arguments_raw)
    else:
        arguments = arguments_raw
    tool_call_id = tool_call.get("id", "call_1")
    return tool_name, tool_call_id, arguments
