"""Playwright 执行器 — 基于 Playwright 的 Web 浏览器控制"""

from __future__ import annotations

from browser_agent.browser import BrowserSession
from browser_agent.executors import BaseExecutor, Observation, ActionResult
from browser_agent.tools.browser_tools import BROWSER_TOOLS, execute_tool
from browser_agent.utils.logger import logger


class PlaywrightExecutor(BaseExecutor):
    """Playwright 执行器。

    通过 Playwright 控制 Chromium 浏览器，适用于 Web 场景。
    使用 DOM 注入 + POI 检测来定位交互元素。
    """

    def __init__(
        self,
        headless: bool = True,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        screenshot_delay: float = 1.0,
        screenshot_quality: int = 70,
        homepage: str = "https://www.baidu.com",
    ):
        self.headless = headless
        self.homepage = homepage
        self.screenshot_delay = screenshot_delay
        self.screenshot_quality = screenshot_quality

        self.browser = BrowserSession(
            headless=headless,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            screenshot_delay=screenshot_delay,
            screenshot_quality=screenshot_quality,
        )

    async def start(self):
        await self.browser.start()
        await self.browser.goto(self.homepage)
        logger.info(f"🌐 Playwright browser started at {self.homepage}")

    async def stop(self):
        await self.browser.stop()

    async def observe(self) -> Observation:
        screenshot_b64 = await self.browser.screenshot_base64()
        poi_text = self.browser.poi_text
        url = self.browser.current_url

        element_text = f"URL: {url}\n{poi_text}" if poi_text else f"URL: {url}"
        return Observation(
            screenshot_base64=screenshot_b64,
            element_text=element_text,
            url=url,
        )

    async def act(self, action_name: str, arguments: dict) -> ActionResult:
        """执行浏览器操作。"""
        try:
            result_text = await execute_tool(self.browser, action_name, arguments)
        except Exception as e:
            result_text = f"执行失败: {e}"
            logger.warning(f"⚠️ {result_text}")

        return ActionResult(text=result_text, success="失败" not in result_text)

    @property
    def tools(self) -> list[dict]:
        return BROWSER_TOOLS

    @property
    def info_for_model(self) -> str:
        return (
            "You are operating a web browser. "
            "You see screenshots with elements highlighted by numbered markers. "
            "You can click on elements by their mark_id, type text into form fields, "
            "navigate to URLs, scroll the page, and go back. "
            "Use the numbered markers in the screenshot to locate interactive elements.\n\n"
            "IMPORTANT: If you encounter a CAPTCHA, verification page, or any challenge "
            "that requires human interaction (slider puzzle, image selection, checkbox), "
            "use the 'wait_for_user' tool with a clear message describing what the user needs to do. "
            "The user will complete it manually and the execution will continue."
        )
