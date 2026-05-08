"""配置管理 — 支持 TOML 文件 + 环境变量 + 构造函数参数三层覆盖"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional


@dataclass
class ModelConfig:
    type: Literal["vllm", "openai", "ollama"] = "vllm"
    name: str = "Qwen/Qwen2.5-VL-3B-Instruct"
    api_base: str = "http://localhost:8000/v1"
    api_key: str = ""


@dataclass
class BrowserConfig:
    headless: bool = True
    viewport_width: int = 1280
    viewport_height: int = 720
    homepage: str = "https://www.baidu.com"
    screenshot_delay: float = 1.0
    screenshot_quality: int = 70


@dataclass
class AgentConfig:
    max_steps: int = 30
    action_timeout: float = 30.0
    task_timeout: float = 300.0


@dataclass
class Config:
    model: ModelConfig = field(default_factory=ModelConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)

    @classmethod
    def from_dict(cls, d: dict) -> "Config":
        cfg = cls()
        if "model" in d:
            cfg.model = ModelConfig(**{k: v for k, v in d["model"].items() if k in ModelConfig.__dataclass_fields__})
        if "browser" in d:
            cfg.browser = BrowserConfig(**{k: v for k, v in d["browser"].items() if k in BrowserConfig.__dataclass_fields__})
        if "agent" in d:
            cfg.agent = AgentConfig(**{k: v for k, v in d["agent"].items() if k in AgentConfig.__dataclass_fields__})
        return cfg

    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量加载覆盖。"""
        cfg = cls()
        if os.getenv("BROWSER_AGENT_MODEL_TYPE"):
            cfg.model.type = os.environ["BROWSER_AGENT_MODEL_TYPE"]  # type: ignore
        if os.getenv("BROWSER_AGENT_MODEL"):
            cfg.model.name = os.environ["BROWSER_AGENT_MODEL"]
        if os.getenv("BROWSER_AGENT_API_BASE"):
            cfg.model.api_base = os.environ["BROWSER_AGENT_API_BASE"]
        if os.getenv("BROWSER_AGENT_API_KEY"):
            cfg.model.api_key = os.environ["BROWSER_AGENT_API_KEY"]
        if os.getenv("BROWSER_AGENT_HEADLESS"):
            cfg.browser.headless = os.environ["BROWSER_AGENT_HEADLESS"].lower() == "true"
        return cfg
