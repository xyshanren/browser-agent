"""执行器抽象层 — 定义所有 GUI 执行器的统一接口

browser-agent 支持多种执行器（Executor），每种执行器对应一种 GUI 交互方式：

- PlaywrightExecutor: 基于 Playwright 的 Web 浏览器控制（当前已实现）
- ManoPExecutor: 基于 Mano-P VLA 模型的纯视觉桌面 GUI 控制（未来实现）

所有执行器实现相同的 BaseExecutor 接口，agent 层无需关心具体实现。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Observation:
    """执行器观察到的环境状态。"""
    screenshot_base64: str        # 当前屏幕截图（base64 JPEG）
    element_text: str = ""        # 可交互元素的文本描述（为空时表示纯视觉模式）
    url: str = ""                 # 当前 URL（仅 Web 场景）
    metadata: dict = field(default_factory=dict)


@dataclass
class ActionResult:
    """执行器执行动作后的结果。"""
    text: str                     # 执行结果描述
    screenshot_base64: str = ""   # 执行后的截图
    element_text: str = ""        # 执行后的元素描述
    success: bool = True


class BaseExecutor(ABC):
    """GUI 执行器抽象基类。

    所有执行器（Playwright / Mano-P / ...）必须实现此接口。
    """

    @abstractmethod
    async def start(self):
        """启动执行器（打开浏览器、初始化环境等）。"""
        ...

    @abstractmethod
    async def stop(self):
        """关闭执行器，释放资源。"""
        ...

    @abstractmethod
    async def observe(self) -> Observation:
        """观察当前环境状态，返回截图和可交互元素信息。

        Playwright 模式：注入 JS 检测 POI + 截图标注
        Mano-P 模式：纯截图，无 POI 标注
        """
        ...

    @abstractmethod
    async def act(self, action_name: str, arguments: dict) -> ActionResult:
        """执行一个动作，返回执行结果。

        Args:
            action_name: 动作名称（click / type_text / scroll 等）
            arguments: 动作参数（mark_id / text / 坐标等）
        """
        ...

    @property
    @abstractmethod
    def tools(self) -> list[dict]:
        """返回此执行器支持的工具 Schema（OpenAI Tool Calling 格式）。"""
        ...

    @property
    @abstractmethod
    def info_for_model(self) -> str:
        """返回描述此环境的文本，注入到系统提示词中。

        Playwright: "You are operating a web browser. Elements are numbered..."
        Mano-P:     "You are controlling a desktop interface via screen coordinates..."
        """
        ...

    @classmethod
    def create(cls, executor_type: str, **kwargs) -> "BaseExecutor":
        """工厂方法：根据类型创建执行器实例。"""
        if executor_type == "playwright":
            from browser_agent.executors.playwright import PlaywrightExecutor
            return PlaywrightExecutor(**kwargs)
        elif executor_type == "mano_p":
            raise NotImplementedError("Mano-P 执行器尚未实现")
        else:
            raise ValueError(f"不支持的执行器类型: {executor_type}，可选: playwright, mano_p")
