"""浏览器工具函数定义 — 供 VLM 调用的工具集"""

import json
import re
from typing import Any

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
            "description": "等待指定秒数，适用于页面正在加载或需要等待动画完成。不要等待超过 3 秒，如果页面没变化换个策略。",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {"type": "number", "description": "等待秒数（1-10）", "default": 3},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wait_for_user",
            "description": "【遇到验证码/人机验证时使用】暂停执行并弹出提示，等待用户手动完成验证后按回车继续。适用于百度验证、滑块验证、图形验证等自动化无法处理的场景。",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "给用户的提示信息，说明需要做什么（如'请完成滑块验证'）",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": "按下键盘上的特定键，支持组合键。例如 Enter, Escape, Tab, Control+a, Alt+F4",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "要按下的键名，如 Enter, Escape, Tab, Control+a, Alt+F4"},
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hover",
            "description": "将鼠标悬停在指定编号的元素上，不点击",
            "parameters": {
                "type": "object",
                "properties": {
                    "mark_id": {"type": "integer", "description": "要悬停的元素的 Mark ID"},
                },
                "required": ["mark_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_text",
            "description": "提取指定编号元素的文本内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "mark_id": {"type": "integer", "description": "要提取文本的元素的 Mark ID"},
                },
                "required": ["mark_id"],
            },
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
    # ── 多标签页工具 ──
    {
        "type": "function",
        "function": {
            "name": "open_tab",
            "description": "打开一个新的浏览器标签页并导航到指定 URL。切换到新标签页。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要打开的 URL"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "switch_tab",
            "description": "切换到指定编号的标签页。使用 list_tabs 查看所有标签页及其编号。",
            "parameters": {
                "type": "object",
                "properties": {
                    "tab_id": {"type": "integer", "description": "目标标签页编号"},
                },
                "required": ["tab_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_tab",
            "description": "关闭指定编号的标签页（不能关闭最后一个）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "tab_id": {"type": "integer", "description": "要关闭的标签页编号"},
                },
                "required": ["tab_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tabs",
            "description": "列出所有打开的标签页及其编号、URL、标题。切换标签页后使用此工具确认当前所在标签页。",
            "parameters": {"type": "object", "properties": {}},
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


async def tool_wait(browser: BrowserSession, seconds: float = 3.0) -> str:
    """执行等待操作。"""
    await browser.wait(seconds)
    return f"已等待 {seconds} 秒"


async def tool_wait_for_user(browser: BrowserSession, message: str = "") -> str:
    """暂停执行，等待用户手动操作（如完成验证码）。

    适用于验证码、人机验证等自动化无法处理的场景。
    用户完成手动操作后在终端按回车继续。
    """
    import sys
    msg = message or "遇到验证码，请手动完成验证"
    print(f"\n⏸️  {msg}")
    print("   请在浏览器中手动操作，完成后按 Enter 继续...", flush=True)
    sys.stdin.readline()  # 等待用户按回车
    return f"用户已手动完成操作: {msg}"


async def tool_press_key(browser: BrowserSession, key: str) -> str:
    """按键盘键。"""
    page = browser.current_page
    if not page:
        return "错误: 没有打开的页面"
    
    # 解析组合键: "Control+a" → [("Control", "a")]
    parts = key.split("+")
    if len(parts) > 1:
        modifier = parts[0]
        character = "+".join(parts[1:])
        await page.keyboard.press(f"{modifier}+{character}")
    else:
        await page.keyboard.press(key)
    return f"已按键: {key}"


async def tool_hover(browser: BrowserSession, mark_id: int) -> str:
    """悬停到指定元素。"""
    page = browser.current_page
    if not page or mark_id < 0 or mark_id >= len(browser.poi_centroids):
        return f"错误: 无效的 mark_id {mark_id}"
    centroid = browser.poi_centroids[mark_id]
    await page.mouse.move(centroid["x"], centroid["y"])
    return f"已悬停到元素 [{mark_id}]"


async def tool_extract_text(browser: BrowserSession, mark_id: int) -> str:
    """提取元素文本。"""
    page = browser.current_page
    if not page or mark_id < 0 or mark_id >= len(browser.poi_elements):
        return f"错误: 无效的 mark_id {mark_id}"
    elem = browser.poi_elements[mark_id]
    text = elem.get("text", "") or ""
    return f"元素 [{mark_id}] 文本: {text[:500]}"


async def tool_finish(browser: BrowserSession, answer: str) -> str:
    """任务完成，返回结果。"""
    return answer


# ── 多标签页工具函数 ──


async def tool_open_tab(browser: BrowserSession, url: str) -> str:
    """打开新标签页并导航到 URL。"""
    tab_id = await browser.open_tab(url)
    return f"已打开新标签页 [{tab_id}]: {url}"


async def tool_switch_tab(browser: BrowserSession, tab_id: int) -> str:
    """切换到指定标签页。"""
    success = await browser.switch_tab(tab_id)
    if not success:
        return f"错误: 标签页 [{tab_id}] 不存在。当前标签页: {list(browser._tabs.keys())}"
    return f"已切换到标签页 [{tab_id}]: {browser.current_url}"


async def tool_close_tab(browser: BrowserSession, tab_id: int) -> str:
    """关闭指定标签页。"""
    success = await browser.close_tab(tab_id)
    if not success:
        return f"错误: 无法关闭标签页 [{tab_id}]（不存在或只剩最后一个）"
    return f"已关闭标签页 [{tab_id}]"


async def tool_list_tabs(browser: BrowserSession) -> str:
    """列出所有标签页。"""
    infos = browser.list_tabs_info()
    if not infos:
        return "没有打开的标签页"
    lines = ["打开的标签页:"]
    for info in infos:
        marker = " ← 当前" if info["current"] else ""
        lines.append(f"  [{info['id']}] {info['title'][:60]} — {info['url'][:80]}{marker}")
    return "\n".join(lines)


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
        "wait_for_user": tool_wait_for_user,
        "press_key": tool_press_key,
        "hover": tool_hover,
        "extract_text": tool_extract_text,
        "finish": tool_finish,
        "open_tab": tool_open_tab,
        "switch_tab": tool_switch_tab,
        "close_tab": tool_close_tab,
        "list_tabs": tool_list_tabs,
    }

    func = tool_map.get(tool_name)
    if not func:
        return (f"未知操作: '{tool_name}'。"
                f"可用操作: {', '.join(tool_map.keys())}。请重新观察页面后选择正确的操作。")

    return await func(browser, **arguments)


# ── 工具调用解析 ──


def parse_tool_call(tool_call: dict) -> tuple[str, str, dict]:
    """解析模型的 tool_call 响应，返回 (tool_name, tool_call_id, arguments)。

    包含 autoFixer 多层 JSON 容错：
    1. 标准 tool_call.function.arguments 解析
    2. 模型把 action 名当 function name 返回（非标准格式）
    3. JSON 嵌套在 content 字段中
    4. 双层 JSON 字符串
    5. 基本类型参数补齐（如 click_element_by_index: 2 → {index: 2}）
    6. 兜底默认值
    """
    from browser_agent.utils.logger import logger

    func = tool_call.get("function", {})
    tool_name = func.get("name", "")
    arguments_raw = func.get("arguments", "{}")

    # 检查 tool_call 本身的顶层结构（某些模型返回格式异常）
    if not tool_name and "name" in tool_call:
        tool_name = tool_call.get("name", "")

    # ── autoFixer 多层 JSON 解析 ──
    arguments = _fix_json_arguments(arguments_raw, tool_name, logger)

    tool_call_id = tool_call.get("id", "call_1")

    return tool_name, tool_call_id, arguments


def _fix_json_arguments(raw: Any, tool_name: str = "", logger=None) -> dict:
    """修复 LLM/VLM 返回的各种 JSON 格式异常。

    处理策略（按优先级）：
    1. 已是 dict → 直接返回
    2. 标准 JSON.parse
    3. 从文本中提取 JSON 对象
    4. 修复嵌套引用/转义问题
    5. 基本类型补齐为对象
    6. 兜底返回空 dict
    """
    # Level 0: 已经是字典
    if isinstance(raw, dict):
        return raw

    if not isinstance(raw, str):
        return {}

    trimmed = raw.strip()

    # Level 1: 标准 JSON 解析（只接受 object/dict 类型）
    try:
        parsed = json.loads(trimmed)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Level 2: 从文本中提取第一个 JSON 对象
    json_match = re.search(r'\{[\s\S]*\}', trimmed)
    if json_match:
        try:
            parsed = json.loads(json_match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # Level 3: 修复嵌套引号和转义问题
    # 有些模型返回 "\"key\": \"value\"" 形式的双 JSON 字符串
    try:
        unescaped = trimmed.encode('utf-8').decode('unicode_escape')
        parsed = json.loads(unescaped)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass

    # Level 4: 尝试 unicode_escape 后再提取 JSON
    try:
        unescaped = trimmed.encode('utf-8').decode('unicode_escape')
        json_match = re.search(r'\{[\s\S]*\}', unescaped)
        if json_match:
            parsed = json.loads(json_match.group(0))
            if isinstance(parsed, dict):
                return parsed
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass

    # Level 5: 基本类型→对象补齐（如 "2" → {"mark_id": 2}）
    # 对于只有一个 required 字段的工具，基本类型自动补齐
    if tool_name:
        param_keys = _get_tool_param_keys(tool_name)
        if len(param_keys) == 1:
            key = param_keys[0]
            try:
                return {key: json.loads(trimmed)}
            except (json.JSONDecodeError, TypeError):
                # 字符串值直接保留
                if isinstance(trimmed, str) and trimmed:
                    return {key: trimmed}
        elif len(param_keys) > 1:
            # 多个参数但只有一个值——尝试作为第一个 required 参数
            try:
                val = json.loads(trimmed)
                return {param_keys[0]: val}
            except (json.JSONDecodeError, TypeError):
                pass

    # Level 6: 兜底
    if logger:
        logger.warning(f"⚠️ autoFixer: 无法解析参数 (tool={tool_name}), raw={trimmed[:200]}")
    return {}


def _get_tool_param_keys(tool_name: str) -> list[str]:
    """获取指定工具的 required 参数列表（用于 autoFixer 补齐）。"""
    for t in BROWSER_TOOLS:
        if t["function"]["name"] == tool_name:
            return t["function"]["parameters"].get("required", [])
    return []
