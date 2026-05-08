"""Mano-P 执行器 — 纯视觉桌面 GUI 自动化

Mano-P 通过纯视觉理解操作任何桌面 GUI：
- 不依赖 DOM / CDP / Accessibility Tree
- 通过归一化坐标定位元素
- 可操作浏览器、桌面软件、专业工具、游戏界面
- 截图由执行器发送，模型"看"到的是和用户一样的画面

参考: https://github.com/Mininglamp-AI/Mano-P
"""

from __future__ import annotations

import base64
import io
import platform
from typing import Optional

from browser_agent.executors import BaseExecutor, Observation, ActionResult
from browser_agent.models.mano_p import ManoPClient
from browser_agent.utils.logger import logger


# Mano-P 支持的动作类型（用于工具 Schema）
MANOP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "computer",
            "description": "执行桌面 GUI 操作（点击、输入、快捷键、滚动等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "left_click", "right_click", "double_click",
                            "mouse_move", "left_click_drag",
                            "type", "key",
                            "scroll", "wait", "screenshot",
                            "done", "fail",
                        ],
                        "description": "要执行的操作类型",
                    },
                    "coordinate": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "归一化坐标 [x, y]，范围 0-1",
                    },
                    "text": {
                        "type": "string",
                        "description": "要输入的文本（仅 type 操作）",
                    },
                    "modifiers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "修饰键，如 ['ctrl']",
                    },
                    "mains": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "主键，如 ['c']",
                    },
                    "scroll_direction": {
                        "type": "string",
                        "enum": ["up", "down", "left", "right"],
                        "description": "滚动方向（仅 scroll 操作）",
                    },
                },
                "required": ["action"],
            },
        },
    },
]


class ManoPExecutor(BaseExecutor):
    """Mano-P 执行器。

    通过 Mano-P 的纯视觉能力操作任何桌面 GUI。
    使用系统级输入模拟（pynput），不依赖浏览器技术。

    注意：当前需要 Mano-P 云端 API 服务（mano.mininglamp.com），
    或自行部署的 Mano-P 推理端点。
    """

    def __init__(
        self,
        api_base: str = "https://mano.mininglamp.com",
        api_key: str = "",
        model: str = "Mano-P-1.0-4B",
        screenshot_quality: int = 70,
    ):
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        self.screenshot_quality = screenshot_quality

        self.client: Optional[ManoPClient] = None
        self._task: str = ""

        # 输入模拟（延迟初始化，避免无头环境报错）
        self._mouse = None
        self._keyboard = None

    def _init_input(self):
        """延迟初始化输入控制器。"""
        if self._mouse is None:
            try:
                from pynput import mouse, keyboard
                self._mouse = mouse.Controller()
                self._keyboard = keyboard.Controller()
            except ImportError:
                logger.warning("pynput 未安装，桌面操作不可用。pip install pynput")
                raise

    async def start(self):
        self._init_input()
        logger.info("🖥️  Mano-P executor ready")

    async def stop(self):
        if self.client and self.client.session_id:
            await self.client.close_session()
            logger.info("🖥️  Mano-P session closed")

    async def _take_screenshot(self) -> bytes:
        """截取当前屏幕。"""
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                raw = sct.grab(monitor)
                from PIL import Image
                img = Image.frombytes("RGB", raw.size, raw.rgb)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=self.screenshot_quality)
                return buf.getvalue()
        except ImportError:
            raise RuntimeError("需要 mss 库: pip install mss Pillow")

    async def observe(self) -> Observation:
        screenshot = await self._take_screenshot()
        b64 = base64.b64encode(screenshot).decode("utf-8")

        # Mano-P 模式下无 POI 文本，只有截图
        return Observation(
            screenshot_base64=b64,
            element_text="",  # 纯视觉模式，无元素标注
            url="",
        )

    async def act(self, action_name: str, arguments: dict) -> ActionResult:
        """执行 Mano-P 格式的动作。

        Action 格式:
        {
            "name": "computer",
            "input": {
                "action": "left_click",
                "coordinate": [0.5, 0.3],
                "text": "hello",
                ...
            }
        }
        """
        if action_name != "computer" and action_name != "finish":
            return ActionResult(text=f"未知动作: {action_name}", success=False)

        if action_name == "finish":
            return ActionResult(text="任务完成", success=True)

        action = arguments.get("action", "")
        self._init_input()

        try:
            if action in ("left_click", "right_click", "double_click", "middle_click", "triple_click"):
                coord = arguments.get("coordinate")
                if coord:
                    x, y = self._screen_coord(coord)
                    self._mouse.position = (x, y)
                self._do_click(action)
                return ActionResult(text=f"{action} at {coord or 'current position'}")

            elif action == "mouse_move":
                coord = arguments.get("coordinate")
                if coord:
                    x, y = self._screen_coord(coord)
                    self._mouse.position = (x, y)
                return ActionResult(text=f"mouse_move to {coord}")

            elif action == "left_click_drag":
                coord = arguments.get("coordinate")
                if coord:
                    x, y = self._screen_coord(coord)
                    self._mouse.position = (x, y)
                return ActionResult(text=f"drag_to {coord}")

            elif action == "type":
                text = arguments.get("text", "")
                self._type_text(text)
                return ActionResult(text=f"type: {text}")

            elif action == "key":
                self._do_hotkey(arguments)
                return ActionResult(text="hotkey executed")

            elif action == "scroll":
                direction = arguments.get("scroll_direction", "down")
                self._do_scroll(direction, arguments.get("coordinate"))
                return ActionResult(text=f"scroll {direction}")

            elif action == "wait":
                import time
                time.sleep(0.5)
                return ActionResult(text="wait ok")

            elif action == "screenshot":
                return ActionResult(text="screenshot taken")

            elif action in ("done", "finish_task"):
                return ActionResult(text="task completed", success=True)

            else:
                return ActionResult(text=f"未知 action: {action}", success=False)

        except Exception as e:
            return ActionResult(text=f"执行失败: {e}", success=False)

    def _screen_coord(self, coord: list) -> tuple:
        """将归一化坐标 (0-1) 转换为屏幕像素坐标。"""
        import mss
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            x = int(monitor["left"] + coord[0] * monitor["width"])
            y = int(monitor["top"] + coord[1] * monitor["height"])
        return x, y

    def _do_click(self, action: str):
        from pynput.mouse import Button
        btn_map = {
            "left_click": Button.left,
            "right_click": Button.right,
            "double_click": Button.left,
            "middle_click": Button.middle,
            "triple_click": Button.left,
        }
        btn = btn_map.get(action, Button.left)
        count = 2 if action == "double_click" else (3 if action == "triple_click" else 1)
        self._mouse.click(btn, count)

    def _type_text(self, text: str):
        """通过剪贴板粘贴文本（避免输入法冲突）。"""
        import subprocess, os
        system = platform.system()
        if system == "Windows":
            subprocess.run(["clip"], input=text.encode("utf-16le"), check=True)
        elif system == "Darwin":
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        else:
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), check=True)

        from pynput.keyboard import Key
        paste_key = Key.cmd if system == "Darwin" else Key.ctrl
        self._keyboard.press(paste_key)
        self._keyboard.press("v")
        self._keyboard.release("v")
        self._keyboard.release(paste_key)

    def _do_hotkey(self, args: dict):
        from pynput.keyboard import Key
        mods = args.get("modifiers", [])
        mains = args.get("mains", [])
        for m in mods:
            self._keyboard.press(getattr(Key, m, m))
        for k in mains:
            key_obj = getattr(Key, k, k)
            self._keyboard.press(key_obj)
            self._keyboard.release(key_obj)
        for m in reversed(mods):
            self._keyboard.release(getattr(Key, m, m))

    def _do_scroll(self, direction: str, coord: Optional[list]):
        if coord:
            x, y = self._screen_coord(coord)
            self._mouse.position = (x, y)
        dy = 10 if direction == "up" else (-10 if direction == "down" else 0)
        dx = 10 if direction == "right" else (-10 if direction == "left" else 0)
        self._mouse.scroll(dx, dy)

    @property
    def tools(self) -> list[dict]:
        return MANOP_TOOLS

    @property
    def info_for_model(self) -> str:
        return (
            "You are operating a desktop GUI through pure visual understanding. "
            "You see the entire screen as a screenshot. "
            "There are no numbered elements — you must identify UI elements by their visual appearance. "
            "Use normalized coordinates [0-1, 0-1] to specify where to click or move. "
            "For example, [0.5, 0.5] is the center of the screen. "
            "You can click, type text, use keyboard shortcuts, scroll, and more."
        )
