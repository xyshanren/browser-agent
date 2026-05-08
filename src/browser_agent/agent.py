"""BrowserAgent — 浏览器自动化 Agent 主类"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import AsyncIterator, Iterator, Optional

from browser_agent.browser import BrowserSession
from browser_agent.config import Config
from browser_agent.models.base import BaseModelClient
from browser_agent.tools.browser_tools import BROWSER_TOOLS, execute_tool, parse_tool_call
from browser_agent.utils import MessageHistory, MessageLabel, MessageRole
from browser_agent.utils.logger import logger

# ── 系统提示词 ──

SYSTEM_PROMPT = """You are Browser-Agent, an AI assistant that can perform actions in a web browser.
You were developed based on the Proxy-Lite architecture.

You see the screen as a screenshot with interactive elements highlighted and numbered.
You also see the available actions (tools) you can use.

For each step, you MUST respond with:
1. <observation>Briefly describe what you see on the screen.</observation>
2. <thinking>Explain your reasoning about what to do next to complete the task.</thinking>
3. A tool call to perform the next action.

Rules:
- You can click numbered elements, type text, scroll, navigate to URLs, and go back.
- Use the "finish" tool when the task is completed.
- Be precise with element IDs.
- If an action fails, try a different approach."""


# ── 数据模型 ──


@dataclass
class Step:
    """Agent 单步执行结果。"""
    number: int
    observation: str = ""
    thinking: str = ""
    action_name: str = ""
    action_args: dict = field(default_factory=dict)
    action_result: str = ""
    screenshot_base64: Optional[str] = None
    finished: bool = False


@dataclass
class AgentResult:
    """Agent 最终执行结果。"""
    text: str = ""
    steps: list[Step] = field(default_factory=list)
    success: bool = False


# ── Agent 主类 ──


class BrowserAgent:
    """浏览器自动化 Agent。

    使用 VLM 模型驱动浏览器操作，实现自动化网页任务。

    用法：
        agent = BrowserAgent()
        result = await agent.run_async("搜索今天深圳的天气")
        print(result.text)
    """

    def __init__(
        self,
        model_type: str = "vllm",
        model: str = "Qwen/Qwen2.5-VL-3B-Instruct",
        api_base: Optional[str] = None,
        api_key: str = "",
        headless: bool = True,
        max_steps: int = 30,
        task_timeout: float = 300.0,
        action_timeout: float = 30.0,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        homepage: str = "https://www.baidu.com",
    ):
        self.max_steps = max_steps
        self.task_timeout = task_timeout
        self.action_timeout = action_timeout
        self.homepage = homepage

        # 创建浏览器会话
        self.browser = BrowserSession(
            headless=headless,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )

        # 创建模型客户端（惰性初始化，避免认证错误阻碍构造）
        self._model_type = model_type
        self._model_name = model
        self._api_base = api_base
        self._api_key = api_key
        self._model: Optional[BaseModelClient] = None

        # 消息历史
        self.history = MessageHistory()

        # 保存步骤记录
        self._steps: list[Step] = []

    def __del__(self):
        """确保浏览器资源被释放。"""
        if hasattr(self, 'browser') and self.browser:
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self.browser.stop())
                loop.close()
            except Exception:
                pass

    @property
    def model(self) -> BaseModelClient:
        """懒加载模型客户端。"""
        if self._model is None:
            kwargs = {"model": self._model_name, "api_key": self._api_key}
            if self._api_base:
                kwargs["api_base"] = self._api_base
            self._model = BaseModelClient.create(self._model_type, **kwargs)
        return self._model

    @model.setter
    def model(self, value: BaseModelClient):
        """允许外部替换模型客户端（如注入 mock）。"""
        self._model = value

    def run(self, task: str) -> AgentResult:
        """同步执行任务。"""
        return asyncio.run(self.run_async(task))

    async def run_async(self, task: str) -> AgentResult:
        """异步执行任务。"""
        self._steps = []
        async for _ in self._run_stream(task):
            pass
        return AgentResult(
            text=self._steps[-1].action_result if self._steps else "",
            steps=self._steps,
            success=any(s.finished for s in self._steps),
        )

    def run_stream(self, task: str) -> Iterator[Step]:
        """流式执行，yield 每一步状态。

        注意：如果在 asyncio 事件循环中调用此方法，请改用 run_async。"""
        try:
            loop = asyncio.get_running_loop()
            raise RuntimeError(
                "run_stream() 不能在已有事件循环中调用。"
                "请在异步环境中使用 await agent.run_async(task)。"
            )
        except RuntimeError:
            loop = asyncio.new_event_loop()
        
        async_gen = self._run_stream(task)

        try:
            while True:
                step = loop.run_until_complete(async_gen.__anext__())
                yield step
        except StopAsyncIteration:
            pass
        finally:
            loop.close()

    async def _run_stream(self, task: str) -> AsyncIterator[Step]:
        """异步流式执行核心逻辑。"""
        # 初始化消息历史
        self.history = MessageHistory()
        self.history.add_text(MessageRole.SYSTEM, SYSTEM_PROMPT, MessageLabel.SYSTEM)
        self.history.add_text(MessageRole.USER, f"Task: {task}", MessageLabel.TASK)

        # 启动浏览器
        await self.browser.start()
        await self.browser.goto(self.homepage)

        try:
            for step_num in range(self.max_steps):
                # ── OBSERVE ──
                screenshot_b64 = await self.browser.screenshot_base64()
                poi_text = self.browser.poi_text

                observation_text = f"URL: {self.browser.current_url}\n{poi_text}" if poi_text else f"URL: {self.browser.current_url}"
                self.history.add_image(MessageRole.USER, observation_text, screenshot_b64, MessageLabel.SCREENSHOT)

                # ── THINK: 调用模型（带重试） ──
                messages = self.history.build_openai_messages(keep_max_screenshots=1)

                response = None
                for attempt in range(3):
                    try:
                        response = await asyncio.wait_for(
                            self.model.chat(messages, tools=BROWSER_TOOLS),
                            timeout=self.action_timeout,
                        )
                        break
                    except asyncio.TimeoutError:
                        logger.warning(f"⏱️ 模型响应超时 (>{self.action_timeout}s) 尝试 {attempt + 1}/3")
                        if attempt < 2:
                            await asyncio.wait_for(
                                self.model.chat([{"role": "user", "content": "请继续。"}], tools=BROWSER_TOOLS),
                                timeout=self.action_timeout,
                            )
                            continue
                    except Exception as e:
                        logger.error(f"❌ 模型调用失败: {e}")
                        step = Step(number=step_num, observation="error", action_name="", action_result=f"模型调用失败: {e}")
                        self._steps.append(step)
                        yield step
                        break
                
                if response is None:
                    step = Step(number=step_num, observation="timeout", action_name="", action_result="模型连续超时，终止任务")
                    self._steps.append(step)
                    yield step
                    break

                # 解析响应
                content = response.content
                tool_calls = response.tool_calls

                # 提取 observation 和 thinking
                obs_match = re.search(r"<observation>(.*?)</observation>", content, re.DOTALL)
                think_match = re.search(r"<thinking>(.*?)</thinking>", content, re.DOTALL)
                observation_text = obs_match.group(1).strip() if obs_match else ""
                thinking_text = think_match.group(1).strip() if think_match else content

                logger.info(f"🧠 Step {step_num}: {thinking_text[:200]}")

                # 记录 assistant 消息
                self.history.add_tool_calls(content, tool_calls, MessageLabel.AGENT_RESPONSE)

                # ── ACT: 执行工具调用 ──
                if not tool_calls:
                    logger.warning("⚠️ 模型未返回工具调用")
                    step = Step(
                        number=step_num,
                        observation=observation_text,
                        thinking=thinking_text,
                        action_name="",
                        action_result="模型未返回工具调用",
                        screenshot_base64=screenshot_b64,
                    )
                    self._steps.append(step)
                    yield step
                    continue

                finished = False
                # 模型可能一次返回多个工具调用，使用子步骤编号
                action_index = 0
                for tc in tool_calls:
                    tool_name, tool_call_id, arguments = parse_tool_call(tc)
                    sub_step = f"{step_num}.{action_index}"
                    action_index += 1

                    # 检查是否完成
                    if tool_name == "finish":
                        answer = arguments.get("answer", "")
                        self.history.add_tool_result(answer, tool_call_id)
                        step = Step(
                            number=step_num,
                            observation=observation_text,
                            thinking=thinking_text,
                            action_name=tool_name,
                            action_args=arguments,
                            action_result=answer,
                            screenshot_base64=screenshot_b64,
                            finished=True,
                        )
                        self._steps.append(step)
                        yield step
                        finished = True
                        break

                    # 执行浏览器操作
                    logger.info(f"🛠️  [{sub_step}] {tool_name}({arguments})")
                    try:
                        result = await asyncio.wait_for(
                            execute_tool(self.browser, tool_name, arguments),
                            timeout=10.0,
                        )
                    except Exception as e:
                        result = f"执行失败: {e}"
                        logger.warning(f"⚠️ {result}")

                    self.history.add_tool_result(result, tool_call_id)

                    step = Step(
                        number=step_num,
                        observation=observation_text,
                        thinking=thinking_text,
                        action_name=tool_name,
                        action_args=arguments,
                        action_result=result,
                        screenshot_base64=screenshot_b64,
                    )
                    self._steps.append(step)
                    yield step

                if finished:
                    return

        finally:
            await self.browser.stop()
