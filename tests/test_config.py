"""配置模块测试"""

from browser_agent.config import Config, ModelConfig, BrowserConfig


def test_default_config():
    """测试默认配置。"""
    cfg = Config()
    assert cfg.model.type == "vllm"
    assert cfg.model.name == "Qwen/Qwen2.5-VL-3B-Instruct"
    assert cfg.browser.headless is True
    assert cfg.agent.max_steps == 30


def test_config_from_dict():
    """测试从字典加载配置。"""
    d = {
        "model": {"type": "openai", "name": "gpt-4o", "api_key": "sk-xxx"},
        "browser": {"headless": False, "viewport_width": 1920},
        "agent": {"max_steps": 50},
    }
    cfg = Config.from_dict(d)
    assert cfg.model.type == "openai"
    assert cfg.model.name == "gpt-4o"
    assert cfg.model.api_key == "sk-xxx"
    assert cfg.browser.headless is False
    assert cfg.browser.viewport_width == 1920
    assert cfg.agent.max_steps == 50


def test_config_partial_dict():
    """测试部分覆盖。"""
    d = {"model": {"type": "ollama"}}
    cfg = Config.from_dict(d)
    assert cfg.model.type == "ollama"
    # 未指定的字段保持默认
    assert cfg.model.name == "Qwen/Qwen2.5-VL-3B-Instruct"
    assert cfg.browser.headless is True
