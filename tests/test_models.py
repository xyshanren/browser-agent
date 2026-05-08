"""模型客户端测试"""

import pytest

from browser_agent.models.base import ModelResponse, BaseModelClient


def test_model_response():
    """测试 ModelResponse 数据结构。"""
    resp = ModelResponse(content="Hello", tool_calls=[{"name": "test"}], finish_reason="stop")
    assert resp.content == "Hello"
    assert len(resp.tool_calls) == 1
    assert resp.finish_reason == "stop"

    resp2 = ModelResponse()
    assert resp2.content == ""
    assert resp2.tool_calls == []
    assert resp2.finish_reason == "stop"


def test_model_factory_unknown():
    """测试未知模型类型。"""
    with pytest.raises(ValueError, match="不支持的模型类型"):
        BaseModelClient.create("unknown_model")


@pytest.mark.asyncio
async def test_vllm_client_initialization():
    """测试 VLLMClient 初始化。"""
    from browser_agent.models.vllm import VLLMClient
    client = VLLMClient(model="test-model", api_base="http://localhost:9999/v1", api_key="sk-test")
    assert client.model == "test-model"
    assert client.api_base == "http://localhost:9999/v1"


@pytest.mark.asyncio
async def test_openai_client_initialization():
    """测试 OpenAIClient 初始化。"""
    from browser_agent.models.openai import OpenAIClient
    client = OpenAIClient(model="gpt-4o", api_key="sk-test")
    assert client.model == "gpt-4o"


@pytest.mark.asyncio
async def test_ollama_client_initialization():
    """测试 OllamaClient 初始化。"""
    from browser_agent.models.ollama import OllamaClient
    client = OllamaClient(model="qwen2.5-vl:3b", api_base="http://localhost:11434")
    assert client.model == "qwen2.5-vl:3b"
    assert client.api_base == "http://localhost:11434"
