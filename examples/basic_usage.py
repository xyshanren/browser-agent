"""基础使用示例"""

import asyncio

from browser_agent import BrowserAgent


def basic_demo():
    """最简单的使用方式：同步调用"""
    agent = BrowserAgent(
        model_type="openai",
        model="gpt-4o",
        api_key="your-api-key-here",
        headless=True,
    )

    result = agent.run("Search for 'browser automation' on Google and tell me the top result.")
    print(f"Result: {result.text}")


def stream_demo():
    """流式查看每一步执行过程"""
    agent = BrowserAgent(
        model_type="vllm",
        model="Qwen/Qwen2.5-VL-3B-Instruct",
        api_base="http://localhost:8000/v1",
        headless=False,  # 显示浏览器窗口
        max_steps=20,
    )

    for step in agent.run_stream("打开百度，搜索'深圳天气'，告诉我今天的温度"):
        print(f"\n=== Step {step.number} ===")
        print(f"🔍 观察: {step.observation[:100]}")
        print(f"🧠 思考: {step.thinking[:200]}")
        print(f"🛠️  行动: {step.action_name}({step.action_args})")
        print(f"✅ 结果: {step.action_result[:200]}")


async def async_demo():
    """异步方式，适合集成到 Agent 框架中"""
    agent = BrowserAgent(
        model_type="ollama",
        model="qwen2.5-vl:3b",
        headless=True,
    )

    result = await agent.run_async("Visit github.com and tell me what's trending today.")
    print(f"Result: {result.text}")


if __name__ == "__main__":
    # 运行前请配置 api_key 或启动本地 vLLM 服务器
    print("请先配置模型后端后再运行示例")
    print("vLLM: vllm serve Qwen/Qwen2.5-VL-3B-Instruct --port 8000")
    print("OpenAI: 设置 api_key")
    print("Ollama: ollama run qwen2.5-vl:3b")
