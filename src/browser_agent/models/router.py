"""模型自动选择器 (ModelRouter)

自动检测可用模型源并按优先级选择最合适的 VLM。

检测优先级:
    P0: 显式指定参数 (model_type/model 非 None) → 跳过检测
    P1: Mano-P 云端 API (MANOP_API_KEY 已配置) → 专用 GUI 模型
    P2: 本地 VLM (Ollama → vLLM → LM Studio) → 隐私优先
    P3: Agent 模型注入 (BROWSER_AGENT_FALLBACK_* 环境变量) → 降级托底

使用方法:
    selection = await ModelRouter.detect()
    agent = BrowserAgent(
        model_type=selection.model_type,
        model=selection.model,
        api_base=selection.api_base,
        api_key=selection.api_key,
        executor_type=selection.executor_type,
    )
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Optional

from browser_agent.utils.logger import logger


@dataclass
class ModelSelection:
    """模型选择结果 — 包含初始化 BrowserAgent 所需的全部参数。"""
    model_type: str = "ollama"
    model: str = "qwen3-vl:2b"
    api_base: Optional[str] = None
    api_key: str = ""
    executor_type: str = "playwright"
    source: str = "default"       # 来源标记: explicit / manop / ollama / vllm / lmstudio / fallback
    auto_detected: bool = False   # 是否经过自动检测


# --- 环境变量常量 ---
ENV_MANOP_API_KEY = "MANOP_API_KEY"
ENV_MANOP_API_BASE = "MANOP_API_BASE"

ENV_FALLBACK_MODEL_TYPE = "BROWSER_AGENT_FALLBACK_MODEL_TYPE"
ENV_FALLBACK_MODEL = "BROWSER_AGENT_FALLBACK_MODEL"
ENV_FALLBACK_API_BASE = "BROWSER_AGENT_FALLBACK_API_BASE"
ENV_FALLBACK_API_KEY = "BROWSER_AGENT_FALLBACK_API_KEY"


class ModelRouter:
    """模型自动选择器。"""

    # 检测超时（秒）
    HTTP_TIMEOUT = 2.0

    @classmethod
    async def detect(
        cls,
        model_type: Optional[str] = None,
        model: Optional[str] = None,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> ModelSelection:
        """按优先级自动检测可用模型。

        如果 model_type 已指定 (非 None)，跳过检测直接返回。
        """
        # P0: 显式指定 → 直接使用
        if model_type is not None:
            selected = ModelSelection(
                model_type=model_type,
                model=model or "qwen3-vl:2b",
                api_base=api_base,
                api_key=api_key or "",
                executor_type="playwright",
                source="explicit",
                auto_detected=False,
            )
            logger.info(f"model router: explicit config → {model_type}/{selected.model}")
            return selected

        # P1: Mano-P 云端 API
        manop_key = api_key or os.getenv(ENV_MANOP_API_KEY, "")
        if manop_key:
            logger.info("model router: Mano-P cloud API available ✓")
            return ModelSelection(
                model_type="manop",
                model="Mano-P-1.0-4B",
                api_base=api_base or os.getenv(ENV_MANOP_API_BASE, "https://mano.mininglamp.com"),
                api_key=manop_key,
                executor_type="mano_p",
                source="manop",
                auto_detected=True,
            )

        # P2: 本地 VLM 自动检测
        local = await cls._detect_local_vlm()
        if local:
            logger.info(f"model router: local VLM detected → {local.source}/{local.model}")
            return local

        # P3: Agent 模型注入 (fallback)
        fallback = cls._get_fallback_config()
        if fallback:
            logger.info(f"model router: agent fallback → {fallback.source}/{fallback.model}")
            return fallback

        # 全无 → 返回默认配置（Ollama + qwen3-vl:2b）
        logger.warning("model router: no model detected, using default ollama/qwen3-vl:2b")
        return ModelSelection(
            source="default",
            auto_detected=True,
        )

    @classmethod
    async def _detect_local_vlm(cls) -> Optional[ModelSelection]:
        """按顺序检测本地 VLM 服务。"""
        checks = [
            (cls._check_ollama, "ollama"),
            (cls._check_vllm, "vllm"),
            (cls._check_lmstudio, "lmstudio"),
        ]
        for check_fn, source in checks:
            result = await check_fn()
            if result:
                return result
        return None

    @classmethod
    async def _check_ollama(cls) -> Optional[ModelSelection]:
        """检测 Ollama 是否运行且包含 VLM 模型。"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=cls.HTTP_TIMEOUT) as client:
                resp = await client.get("http://localhost:11434/api/tags")
                if resp.status_code != 200:
                    return None

                models = resp.json().get("models", [])
                # 查找视觉模型（通常包含 "vl"、"vision"、"llava" 等关键词）
                vlm_keywords = ["vl", "vision", "llava", "cogvlm", "minicpm-v"]
                candidates = []
                for m in models:
                    name = m.get("name", "")
                    if any(kw in name.lower() for kw in vlm_keywords):
                        candidates.append(name)

                if candidates:
                    # 优先选择最新的模型
                    candidates.sort(reverse=True)
                    selected = candidates[0]
                    logger.info(f"  ollama: found VLM models → {candidates}")
                    return ModelSelection(
                        model_type="ollama",
                        model=selected,
                        api_base="http://localhost:11434",
                        executor_type="playwright",
                        source="ollama",
                        auto_detected=True,
                    )
                # 有 Ollama 但无 VLM 模型 → 提示用户
                logger.info(f"  ollama: running but no VLM model found (detected: {[m.get('name','') for m in models]})")
                return None
        except Exception as e:
            logger.debug(f"  ollama check failed: {e}")
            return None

    @classmethod
    async def _check_vllm(cls) -> Optional[ModelSelection]:
        """检测 vLLM 是否运行且支持视觉。"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=cls.HTTP_TIMEOUT) as client:
                resp = await client.get("http://localhost:8000/v1/models")
                if resp.status_code != 200:
                    return None

                models = resp.json().get("data", [])
                for item in models:
                    model_id = item.get("id", "")
                    # vLLM VLM 模型通常包含 "VL" 或 "vision"
                    if "vl" in model_id.lower() or "vision" in model_id.lower():
                        logger.info(f"  vllm: found VLM model → {model_id}")
                        return ModelSelection(
                            model_type="vllm",
                            model=model_id,
                            api_base="http://localhost:8000/v1",
                            executor_type="playwright",
                            source="vllm",
                            auto_detected=True,
                        )

                logger.info(f"  vllm: running but no VLM model found (detected: {[m.get('id','') for m in models]})")
                return None
        except Exception as e:
            logger.debug(f"  vllm check failed: {e}")
            return None

    @classmethod
    async def _check_lmstudio(cls) -> Optional[ModelSelection]:
        """检测 LM Studio 是否运行且加载了模型。"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=cls.HTTP_TIMEOUT) as client:
                resp = await client.get("http://localhost:1234/v1/models")
                if resp.status_code != 200:
                    return None

                models = resp.json().get("data", [])
                if not models:
                    return None

                # LM Studio API 与 OpenAI 兼容
                model_id = models[0].get("id", "")
                logger.info(f"  lmstudio: found model → {model_id}")
                return ModelSelection(
                    model_type="openai",
                    model=model_id,
                    api_base="http://localhost:1234/v1",
                    api_key="lm-studio",
                    executor_type="playwright",
                    source="lmstudio",
                    auto_detected=True,
                )
        except Exception as e:
            logger.debug(f"  lmstudio check failed: {e}")
            return None

    @classmethod
    def _get_fallback_config(cls) -> Optional[ModelSelection]:
        """读取 Agent 注入的降级模型配置 (环境变量)。"""
        model_type = os.getenv(ENV_FALLBACK_MODEL_TYPE)
        model = os.getenv(ENV_FALLBACK_MODEL)
        if not model_type or not model:
            return None

        logger.info(f"  fallback: agent injected → {model_type}/{model}")
        return ModelSelection(
            model_type=model_type,
            model=model,
            api_base=os.getenv(ENV_FALLBACK_API_BASE),
            api_key=os.getenv(ENV_FALLBACK_API_KEY, ""),
            executor_type="playwright",
            source="fallback",
            auto_detected=True,
        )
