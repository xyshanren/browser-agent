"""browser-agent 测试"""

from browser_agent.utils import MessageHistory, MessageLabel, MessageRole


def test_message_history():
    """测试消息历史管理。"""
    history = MessageHistory()

    # 添加系统消息
    history.add_text(MessageRole.SYSTEM, "You are a helpful assistant.", MessageLabel.SYSTEM)
    assert len(history) == 1

    # 添加用户消息
    history.add_text(MessageRole.USER, "Hello!", MessageLabel.TASK)
    assert len(history) == 2

    # 添加带图片的消息
    history.add_image(MessageRole.USER, "screenshot", "base64_fake_data", MessageLabel.SCREENSHOT)
    assert len(history) == 3

    # 构建 OpenAI 格式
    msgs = history.build_openai_messages(keep_max_screenshots=1)
    assert len(msgs) == 3
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert msgs[2]["role"] == "user"  # 图片消息也是 user role

    # 测试工具消息
    history.add_tool_result("执行成功", "call_123")
    assert len(history) == 4

    # 测试 assistant 工具调用消息
    history.add_tool_calls("I'll click the button", [{"function": {"name": "click", "arguments": '{"mark_id": 0}'}}],
                           MessageLabel.AGENT_RESPONSE)
    assert len(history) == 5

    # 测试截图保留数量限制
    history2 = MessageHistory()
    history2.add_text(MessageRole.SYSTEM, "sys", MessageLabel.SYSTEM)
    history2.add_image(MessageRole.USER, "s1", "img1", MessageLabel.SCREENSHOT)
    history2.add_image(MessageRole.USER, "s2", "img2", MessageLabel.SCREENSHOT)
    history2.add_image(MessageRole.USER, "s3", "img3", MessageLabel.SCREENSHOT)

    msgs2 = history2.build_openai_messages(keep_max_screenshots=1)
    # system + 1 screenshot (仅保留最新的)
    image_count = sum(1 for m in msgs2 if isinstance(m["content"], list) and any(p["type"] == "image_url" for p in m["content"]))
    assert image_count == 1, f"Expected 1 screenshot, got {image_count}"


def test_system_prompt_access():
    """测试系统提示词提取。"""
    history = MessageHistory()
    assert history.get_system_prompt() is None

    history.add_text(MessageRole.SYSTEM, "You are a browser agent.", MessageLabel.SYSTEM)
    assert history.get_system_prompt() == "You are a browser agent."
