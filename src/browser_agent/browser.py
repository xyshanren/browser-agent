"""浏览器会话 — Playwright 封装 + POI 检测"""

from __future__ import annotations

import asyncio
import base64
import re
from pathlib import Path
from typing import Optional

from playwright.async_api import Browser as PlaywrightBrowser
from playwright.async_api import BrowserContext, Page, async_playwright

from browser_agent.utils.logger import logger

# playwright-stealth 作为可选依赖，支持 v1.x 和 v2.x
# 导入失败时静默降级（不影响核心功能）
_stealth_available = False
try:
    try:
        # playwright-stealth v2.x (preferred for Python 3.12+)
        from playwright_stealth import Stealth

        async def stealth_page(page, **kwargs):
            stealth = Stealth(**kwargs)
            await stealth.apply_stealth_async(page)
        _stealth_available = True
    except ImportError:
        # playwright-stealth v1.x (legacy)
        from playwright_stealth import StealthConfig, stealth_async as _stealth_async

        async def stealth_page(page, **kwargs):
            await _stealth_async(page, StealthConfig(**kwargs))
        _stealth_available = True
except Exception:
    # playwright-stealth 依赖冲突或未安装，静默降级
    async def stealth_page(page, **kwargs):
        pass
    logger.info("playwright-stealth 未安装或依赖冲突，已降级（不影响核心功能）")

# POI 检测 JavaScript — 从 proxy-lite 移植并精简
FIND_POIS_JS = (Path(__file__).parent / "vision" / "find_pois.js").read_text(encoding="utf-8")


class TabState:
    """单个标签页的状态快照。"""
    __slots__ = ("page", "poi_elements", "poi_centroids", "poi_dehydrated_dom")

    def __init__(self, page: Page):
        self.page = page
        self.poi_elements: list[dict] = []
        self.poi_centroids: list[dict] = []
        self.poi_dehydrated_dom: str = ""


class BrowserSession:
    """Playwright 浏览器会话封装。

    负责：
    - 启动/关闭浏览器
    - 页面导航和交互（click/type/scroll）
    - 标签页管理（创建/切换/关闭/列出）
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
        cookie_file: Optional[str] = None,
    ):
        self.headless = headless
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.screenshot_delay = screenshot_delay
        self.screenshot_quality = screenshot_quality
        self.cookie_file = cookie_file or str(Path.home() / ".browser-agent" / "cookies.json")

        self._playwright = None
        self._browser: Optional[PlaywrightBrowser] = None
        self._context: Optional[BrowserContext] = None

        # 多标签页管理
        self._tabs: dict[int, TabState] = {}     # tab_id → TabState
        self._current_tab_idx: int = 0            # 当前活跃标签页 ID
        self._next_tab_id: int = 0                # 自增 ID 分配器

    # ── POI 属性代理（指向当前 tab）───────────────

    @property
    def poi_elements(self) -> list[dict]:
        t = self._tabs.get(self._current_tab_idx)
        return t.poi_elements if t else []

    @poi_elements.setter
    def poi_elements(self, value: list[dict]):
        t = self._tabs.get(self._current_tab_idx)
        if t:
            t.poi_elements = value

    @property
    def poi_centroids(self) -> list[dict]:
        t = self._tabs.get(self._current_tab_idx)
        return t.poi_centroids if t else []

    @poi_centroids.setter
    def poi_centroids(self, value: list[dict]):
        t = self._tabs.get(self._current_tab_idx)
        if t:
            t.poi_centroids = value

    @property
    def poi_dehydrated_dom(self) -> str:
        t = self._tabs.get(self._current_tab_idx)
        return t.poi_dehydrated_dom if t else ""

    @poi_dehydrated_dom.setter
    def poi_dehydrated_dom(self, value: str):
        t = self._tabs.get(self._current_tab_idx)
        if t:
            t.poi_dehydrated_dom = value

    # ── 生命周期 ──────────────────────────────────

    async def start(self):
        """启动浏览器并创建初始标签页。"""
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

        # 创建初始标签页
        page = await self._context.new_page()
        page.set_default_timeout(60_000)
        await stealth_page(page, navigator_user_agent=False)
        await page.add_init_script(FIND_POIS_JS)

        self._tabs = {0: TabState(page)}
        self._current_tab_idx = 0
        self._next_tab_id = 1

        # 加载持久化 Cookie
        await self._load_cookies()

        logger.info(f"🌐 Browser started (headless={self.headless})")

    async def stop(self):
        """关闭浏览器，并保存 Cookie。"""
        # 保存持久化 Cookie
        await self._save_cookies()

        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("🌐 Browser stopped")

    @property
    def current_page(self) -> Optional[Page]:
        t = self._tabs.get(self._current_tab_idx)
        return t.page if t else None

    @property
    def current_url(self) -> str:
        page = self.current_page
        return page.url if page else ""

    # ── 页面属性 ──────────────────────────────────

    @property
    def tab_count(self) -> int:
        return len(self._tabs)

    @property
    def current_tab_id(self) -> int:
        return self._current_tab_idx

    def tab_ids(self) -> list[int]:
        return sorted(self._tabs.keys())

    def tab_info(self, tab_id: int) -> Optional[dict]:
        t = self._tabs.get(tab_id)
        if not t:
            return None
        try:
            url = t.page.url
            title = t.page.title
        except Exception:
            url = ""
            title = ""
        return {"id": tab_id, "url": url, "title": title, "current": tab_id == self._current_tab_idx}

    def list_tabs_info(self) -> list[dict]:
        return [self.tab_info(tid) for tid in self.tab_ids() if self.tab_info(tid)]

    async def open_tab(self, url: str = "") -> int:
        """创建新标签页，返回 tab_id。"""
        page = await self._context.new_page()
        page.set_default_timeout(60_000)
        await stealth_page(page, navigator_user_agent=False)
        await page.add_init_script(FIND_POIS_JS)

        tab_id = self._next_tab_id
        self._next_tab_id += 1
        self._tabs[tab_id] = TabState(page)

        if url:
            await page.goto(url, wait_until="domcontentloaded")

        logger.info(f"📑 打开标签页 [{tab_id}]: {url or '(空白)'}")
        return tab_id

    async def close_tab(self, tab_id: int) -> bool:
        """关闭指定标签页。不允许关闭最后一个。"""
        if tab_id not in self._tabs:
            return False
        if len(self._tabs) <= 1:
            logger.warning("⚠️ 不能关闭最后一个标签页")
            return False

        t = self._tabs.pop(tab_id)
        try:
            await t.page.close()
        except Exception:
            pass

        # 如果关闭的是当前 tab，切换到第一个可用 tab
        if self._current_tab_idx == tab_id:
            self._current_tab_idx = next(iter(sorted(self._tabs.keys())))

        logger.info(f"📑 关闭标签页 [{tab_id}]")
        return True

    async def switch_tab(self, tab_id: int) -> bool:
        """切换到指定标签页。"""
        if tab_id not in self._tabs:
            return False
        self._current_tab_idx = tab_id
        logger.info(f"📑 切换到标签页 [{tab_id}]: {self.current_url}")
        return True

    # ── POI 检测 ──────────────────────────────────

    async def update_poi(self):
        """执行 POI 检测，更新交互元素列表。

        每次截图前重新注入 JS 并检测，防止页面导航后 JS 上下文丢失。
        """
        page = self.current_page
        if not page:
            return

        try:
            await page.wait_for_load_state(timeout=30000)
        except Exception:
            pass

        try:
            # 重新注入 POI 检测 JS（页面导航后会丢失 init_script）
            await page.evaluate(FIND_POIS_JS)
            result = await page.evaluate("findPOIsConvergence()")
        except Exception as e:
            logger.warning(f"POI detection failed: {e}")
            self.poi_elements = []
            self.poi_centroids = []
            return

        if result:
            self.poi_elements = result.get("element_descriptions", [])
            self.poi_centroids = result.get("element_centroids", [])
            self.poi_dehydrated_dom = result.get("dehydrated_dom", "")

    @property
    def poi_text(self) -> str:
        """当前页面所有交互元素的双通道描述：DOM Dehydration + 详细属性。"""
        # 首先生成 DOM Dehydration 文本
        parts = []
        if self.poi_dehydrated_dom:
            parts.append("<dehydrated_dom>\n" + self.poi_dehydrated_dom + "\n</dehydrated_dom>\n")

        # 然后附上详细属性列表（供高级操作参考）
        attr_lines = []
        for i, elem in enumerate(self.poi_elements):
            tag = elem.get("tag", "unknown").lower()
            text = elem.get("text", "") or ""
            attrs = []
            for k in ("value", "placeholder", "aria_label", "name", "role", "type", "title", "scrollable", "required", "disabled"):
                v = elem.get(k)
                if v is not None and v is not False:
                    attrs.append(f'{k}="{v}"')
            attr_str = " " + " ".join(attrs) if attrs else ""
            text_display = text[:200].replace("\n", "⏎")
            attr_lines.append(f"- [{i}] <{tag}{attr_str}> {text_display}")
        if attr_lines:
            parts.append("<element_details>\n" + "\n".join(attr_lines) + "\n</element_details>")

        return "\n".join(parts)

    # ── Cookie 持久化 ──────────────────────────────

    async def _save_cookies(self):
        """保存当前 Cookie 到文件。"""
        if not self._context:
            return
        try:
            cookies = await self._context.cookies()
            if not cookies:
                return
            cookie_path = Path(self.cookie_file)
            cookie_path.parent.mkdir(parents=True, exist_ok=True)
            import json
            cookie_path.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info(f"🍪 已保存 {len(cookies)} 个 Cookie → {cookie_path}")
        except Exception as e:
            logger.warning(f"⚠️ Cookie 保存失败: {e}")

    async def _load_cookies(self):
        """从文件加载 Cookie。"""
        cookie_path = Path(self.cookie_file)
        if not cookie_path.exists():
            return
        try:
            import json
            cookies = json.loads(cookie_path.read_text(encoding="utf-8"))
            if self._context and cookies:
                await self._context.add_cookies(cookies)
                logger.info(f"🍪 已加载 {len(cookies)} 个 Cookie ← {cookie_path}")
        except Exception as e:
            logger.warning(f"⚠️ Cookie 加载失败: {e}")

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
        # 导航后清除旧 POI，下次截图时会重新检测
        self.poi_elements = []
        self.poi_centroids = []
        self.poi_dehydrated_dom = ""

    async def click(self, mark_id: int):
        """点击指定编号的交互元素。

        如果 mark_id 超出范围（页面已变化），自动触发 POI 刷新并提示模型重新观察。
        """
        page = self.current_page
        if not page:
            raise ValueError(f"Invalid mark_id: {mark_id} — 页面已关闭")

        if mark_id < 0 or mark_id >= len(self.poi_centroids):
            # 尝试刷新 POI
            await self.update_poi()
            if mark_id < 0 or mark_id >= len(self.poi_centroids):
                raise ValueError(
                    f"Invalid mark_id: {mark_id} (共 {len(self.poi_centroids)} 个元素) "
                    f"— 页面内容已变化，请重新观察获取最新的 Mark ID"
                )

        centroid = self.poi_centroids[mark_id]
        x, y = centroid["x"], centroid["y"]
        await page.mouse.click(x, y)

    async def type_text(self, mark_id: int, text: str, submit: bool = False):
        """在指定元素中输入文本。"""
        page = self.current_page
        if not page:
            raise ValueError(f"Invalid mark_id: {mark_id} — 页面已关闭")

        if mark_id < 0 or mark_id >= len(self.poi_centroids):
            # 尝试刷新 POI
            await self.update_poi()
            if mark_id < 0 or mark_id >= len(self.poi_centroids):
                raise ValueError(
                    f"Invalid mark_id: {mark_id} (共 {len(self.poi_centroids)} 个元素) "
                    f"— 页面内容已变化，请重新观察获取最新的 Mark ID"
                )

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
