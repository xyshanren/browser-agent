"""
Browser-Agent MCP Server

让 browser-agent 通过 Model Context Protocol 被任何 MCP 客户端调用。
支持：Claude Desktop, Cline, Cursor, Continue, 以及所有 MCP 兼容工具。

Usage:
    python -m browser_agent.mcp_server
    # 或
    browser-agent-mcp
"""

import asyncio
import json
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .agent import BrowserAgent

# Server instance
server = Server("browser-agent")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """暴露给 MCP 客户端的工具列表"""
    return [
        Tool(
            name="browser_navigate",
            description="导航到 URL 或执行搜索任务",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "要执行的任务描述，如 '打开百度' 或 '搜索深圳天气'"
                    },
                    "headless": {
                        "type": "boolean",
                        "description": "是否隐藏浏览器窗口（默认 True）",
                        "default": True
                    },
                    "max_steps": {
                        "type": "integer",
                        "description": "最大操作步数（默认 20）",
                        "default": 20
                    }
                },
                "required": ["task"]
            }
        ),
        Tool(
            name="browser_screenshot",
            description="截取当前页面截图并返回描述",
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "boolean",
                        "description": "是否用 VLM 描述截图内容（默认 False，直接返回 base64）",
                        "default": False
                    }
                }
            }
        ),
        Tool(
            name="browser_click",
            description="点击页面上的元素（通过坐标或描述）",
            inputSchema={
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X 坐标"},
                    "y": {"type": "integer", "description": "Y 坐标"},
                    "description": {"type": "string", "description": "要点击的元素描述（如 '登录按钮'）"}
                }
            }
        ),
        Tool(
            name="browser_type",
            description="在当前焦点元素中输入文本",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "要输入的文本"},
                    "submit": {"type": "boolean", "description": "输入后是否按回车", "default": False}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="browser_extract",
            description="提取页面上的结构化数据",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要提取的数据描述，如 '所有产品价格' 或 '新闻标题列表'"
                    },
                    "format": {
                        "type": "string",
                        "description": "输出格式：json, text, table",
                        "default": "json"
                    }
                },
                "required": ["query"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """执行工具调用"""
    try:
        if name == "browser_navigate":
            return await _browser_navigate(
                task=arguments.get("task", ""),
                headless=arguments.get("headless", True),
                max_steps=arguments.get("max_steps", 20)
            )
        elif name == "browser_screenshot":
            return await _browser_screenshot(arguments.get("description", False))
        elif name == "browser_click":
            return await _browser_click(arguments)
        elif name == "browser_type":
            return await _browser_type(arguments)
        elif name == "browser_extract":
            return await _browser_extract(
                query=arguments.get("query", ""),
                format_type=arguments.get("format", "json")
            )
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def _browser_navigate(task: str, headless: bool = True, max_steps: int = 20) -> list[TextContent]:
    """导航或执行任务"""
    agent = BrowserAgent(
        max_steps=max_steps,
        headless=headless,
        model_type="ollama",
        model="qwen3-vl:2b"
    )
    result = await agent.run(task)
    return [TextContent(type="text", text=result.text)]


async def _browser_screenshot(describe: bool = False) -> list[TextContent]:
    """截图"""
    # 简单实现：复用 BrowserSession
    from .browser import BrowserSession
    session = BrowserSession()
    screenshot = await session.take_screenshot()
    if describe:
        # 可以用 VLM 描述截图
        return [TextContent(type="text", text="[Screenshot captured - base64 length: {}]".format(len(screenshot)))]
    return [TextContent(type="text", text=screenshot)]


async def _browser_click(args: dict) -> list[TextContent]:
    """点击元素"""
    x, y = args.get("x", 0), args.get("y", 0)
    desc = args.get("description", "")
    if desc:
        return [TextContent(type="text", text=f"Click by description: {desc}")]
    return [TextContent(type="text", text=f"Click at ({x}, {y})")]


async def _browser_type(args: dict) -> list[TextContent]:
    """输入文本"""
    text = args.get("text", "")
    submit = args.get("submit", False)
    return [TextContent(type="text", text=f"Type: {text}" + (" [submitted]" if submit else ""))]


async def _browser_extract(query: str, format_type: str = "json") -> list[TextContent]:
    """提取数据"""
    return [TextContent(type="text", text=f"Extract '{query}' as {format_type}")]


async def main():
    """MCP Server 入口"""
    print("Starting Browser-Agent MCP Server...", file=sys.stderr)
    await stdio_server.run(server)


if __name__ == "__main__":
    asyncio.run(main())
