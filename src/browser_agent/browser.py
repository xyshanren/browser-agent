"""浏览器会话 — Playwright 封装 + POI 检测"""

from __future__ import annotations

import asyncio
import base64
import re
from pathlib import Path
from typing import Optional

from playwright.async_api import Browser as PlaywrightBrowser
from playwright.async_api import BrowserContext, Page, async_playwright
try:
    # playwright-stealth v2.x (preferred for Python 3.12+)
    from playwright_stealth import Stealth

    async def stealth_page(page, **kwargs):
        stealth = Stealth(**kwargs)
        await stealth.apply_stealth_async(page)
except ImportError:
    # playwright-stealth v1.x (legacy)
    from playwright_stealth import StealthConfig, stealth_async as _stealth_async

    async def stealth_page(page, **kwargs):
        await _stealth_async(page, StealthConfig(**kwargs))

from browser_agent.utils.logger import logger

# POI 检测 JavaScript — 从 proxy-lite 移植并精简
FIND_POIS_JS = (Path(__file__).parent / "vision" / "find_pois.js").read_text(encoding="utf-8")


class BrowserSession:
    """Playwright 浏览器会话封装。

    负责：
    - 启动/关闭浏览器
    - 页面导航和交互（click/type/scroll）
    - 截图 + POI（Points of Interest）检测
    - 反爬虫规避（Stealth 模式）
    """

    def __init__(
        self,
        headless: bool = True,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        screenshot_delay: float = 1.0,
        screenshot_quality: int = 70,
    ):
        self.headless = headless
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.screenshot_delay = screenshot_delay
        self.screenshot_quality = screenshot_quality

        self._playwright = None
        self._browser: Optional[PlaywrightBrowser] = None
        self._context: Optional[BrowserContext] = None

        # POI 缓存
        self.poi_elements: list[dict] = []
        self.poi_centroids: list[dict] = []

    # ── 生命周期 ──────────────────────────────────

    async def start(self):
        """启动浏览器。"""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)

        self._context = await self._browser.new_context(
            viewport={"width": self.viewport_width, "height": self.viewport_height},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        self._context.set_default_timeout(60_000)

        page = await self._context.new_page()
        page.set_default_timeout(60_000)

        # 注入 Stealth 脚本（反爬虫）
        await stealth_page(page, navigator_user_agent=False)

        # 注入 POI 检测脚本
        await page.add_init_script(FIND_POIS_JS)

        logger.info(f"🌐 Browser started (headless={self.headless})")

    async def stop(self):
        """关闭浏览器。"""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("🌐 Browser stopped")

    @property
    def current_page(self) -> Optional[Page]:
        if self._context and self._context.pages:
            return self._context.pages[-1]
        return None

    @property
    def current_url(self) -> str:
        page = self.current_page
        return page.url if page else ""

    # ── POI 检测 ──────────────────────────────────

    async def update_poi(self):
        """执行 POI 检测，更新交互元素列表。"""
        page = self.current_page
        if not page:
            return

        try:
            await page.wait_for_load_state(timeout=30000)
        except Exception:
            pass

        try:
            result = await page.evaluate("findPOIsConvergence()")
        except Exception as e:
            logger.warning(f"POI detection failed: {e}")
            self.poi_elements = []
            self.poi_centroids = []
            return

        if result:
            self.poi_elements = result.get("element_descriptions", [])
            self.poi_centroids = result.get("element_centroids", [])

    @property
    def poi_text(self) -> str:
        """当前页面所有交互元素的文本描述。"""
        lines = []
        for i, elem in enumerate(self.poi_elements):
            tag = elem.get("tag", "unknown").lower()
            text = elem.get("text", "") or ""
            attrs = []
            for k in ("value", "placeholder", "aria_label", "name", "role", "title", "scrollable"):
                v = elem.get(k)
                if v is not None and v is not False:
                    attrs.append(f'{k}="{v}"')
            attr_str = " " + " ".join(attrs) if attrs else ""
            text_display = text[:200].replace("\n", "⏎")
            lines.append(f"- [{i}] <{tag}{attr_str}>{text_display}</{tag}>")
        return "\n".join(lines)

    # ── 截图 ──────────────────────────────────────

    async def screenshot(self) -> tuple[bytes, bytes]:
        """截取当前页面，返回 (原始截图, 标注截图)。"""
        page = self.current_page
        if not page:
            raise RuntimeError("No active page")

        if self.screenshot_delay > 0:
            await asyncio.sleep(self.screenshot_delay)

        await self.update_poi()

        raw = await page.screenshot(
            type="jpeg",
            quality=self.screenshot_quality,
            scale="css",
        )

        # 在截图上标注 bounding box
        annotated = annotate_image(raw, self.poi_centroids)

        return raw, annotated

    async def screenshot_base64(self) -> str:
        """截图并返回 base64 编码（带标注）。"""
        _, annotated = await self.screenshot()
        return base64.b64encode(annotated).decode("utf-8")

    # ── 页面操作 ──────────────────────────────────

    async def goto(self, url: str):
        """导航到指定 URL。"""
        page = self.current_page
        if not page:
            raise RuntimeError("No active page")
        await page.goto(url, wait_until="domcontentloaded")

    async def click(self, mark_id: int):
        """点击指定编号的交互元素。"""
        page = self.current_page
        if not page or mark_id < 0 or mark_id >= len(self.poi_centroids):
            raise ValueError(f"Invalid mark_id: {mark_id}")

        centroid = self.poi_centroids[mark_id]
        x, y = centroid["x"], centroid["y"]
        await page.mouse.click(x, y)

    async def type_text(self, mark_id: int, text: str, submit: bool = False):
        """在指定元素中输入文本。"""
        page = self.current_page
        if not page or mark_id < 0 or mark_id >= len(self.poi_centroids):
            raise ValueError(f"Invalid mark_id: {mark_id}")

        # 先清空再输入
        await self.click(mark_id)
        await page.keyboard.press("Control+a")
        await page.keyboard.press("Backspace")
        await page.keyboard.type(text)

        if submit:
            await page.keyboard.press("Enter")

    async def scroll(self, direction: str, mark_id: int = -1):
        """滚动页面。direction: up/down/left/right"""
        page = self.current_page
        if not page:
            return

        scroll_amount = int(self.viewport_height * 0.8 if direction in ("up", "down") else self.viewport_width * 0.8)
        delta_x = 0 if direction in ("up", "down") else (scroll_amount if direction == "right" else -scroll_amount)
        delta_y = 0 if direction in ("left", "right") else (scroll_amount if direction == "down" else -scroll_amount)

        if mark_id >= 0 and mark_id < len(self.poi_centroids):
            centroid = self.poi_centroids[mark_id]
            await page.mouse.move(centroid["x"], centroid["y"])

        await page.mouse.wheel(delta_x, delta_y)

    async def go_back(self):
        """后退到上一页。"""
        page = self.current_page
        if page:
            await page.go_back(wait_until="domcontentloaded")

    async def reload(self):
        """刷新当前页面。"""
        page = self.current_page
        if page:
            await page.reload(wait_until="domcontentloaded")

    async def wait(self, seconds: float = 3.0):
        """等待指定秒数。"""
        await asyncio.sleep(seconds)


# ── 截图标注工具 ─────────────────────────────────


def annotate_image(image_bytes: bytes, centroids: list[dict]) -> bytes:
    """在截图上绘制红色编号的 dot。"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return image_bytes  # 无 PIL 则返回原图

    import io

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)

    for i, pt in enumerate(centroids):
        x, y = pt["x"], pt["y"]
        # 绘制红色圆点
        draw.ellipse([(x - 6, y - 6), (x + 6, y + 6)], fill="red", outline="white", width=2)
        # 绘制编号
        draw.text((x + 8, y - 8), str(i), fill="red", stroke_width=1, stroke_color="white")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()
