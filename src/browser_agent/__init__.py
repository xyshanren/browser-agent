"""browser-agent: 轻量级浏览器自动化 Agent 框架"""

from browser_agent.agent import BrowserAgent

__all__ = ["BrowserAgent", "run_mcp_server"]
__version__ = "0.1.0"


def run_mcp_server():
    """启动 MCP Server（供 CLI 调用）"""
    from browser_agent.mcp_server import main
    import asyncio
    asyncio.run(main())
