"""端到端测试：真实 Qwen3-VL 模型（Ollama）

使用本地部署的 qwen3-vl:2b 模型，完整跑通
Observe→Think→Act 循环。
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from browser_agent import BrowserAgent
from browser_agent.utils.logger import logger


async def main():
    task = sys.argv[1] if len(sys.argv) > 1 else "打开百度，搜索'深圳天气'，告诉我今天的温度和湿度"

    agent = BrowserAgent(
        model_type="ollama",
        model="qwen3-vl:2b",
        api_base="http://localhost:11434",
        headless=False,  # 显示浏览器方便观察
        max_steps=15,
        task_timeout=300,
        action_timeout=120,  # qwen3-vl:2b 推理较慢，给足超时
        homepage="https://www.baidu.com",
    )

    print(f"\n{'='*60}")
    print(f"🤖 任务: {task}")
    print(f"📦 模型: qwen3-vl:2b (Ollama 本地)")
    print(f"{'='*60}\n")

    try:
        result = await agent.run_async(task)
    except Exception as e:
        print(f"\n❌ 任务出错: {e}")
        import traceback
        traceback.print_exc()
        return

    print(f"\n{'='*60}")
    if result.success:
        print(f"✨ 任务完成! 共 {len(result.steps)} 步")
        print(f"   最终结果: {result.text[:500]}")
    else:
        print(f"⚠️  任务未完成 (共 {len(result.steps)} 步)")
        if result.steps:
            last = result.steps[-1]
            print(f"   最后一步: {last.action_name}({last.action_args})")
            print(f"   结果: {last.action_result[:200]}")
    print(f"{'='*60}\n")

    # 打印完整步骤
    print("详细步骤记录：")
    for s in result.steps:
        print(f"\n  Step {s.number}:")
        if s.observation:
            print(f"    Obs: {s.observation[:100]}...")
        if s.thinking:
            print(f"    Think: {s.thinking[:150]}")
        if s.action_name:
            print(f"    Act: {s.action_name}({s.action_args})")
        if s.action_result:
            print(f"    Result: {s.action_result[:200]}")


if __name__ == "__main__":
    asyncio.run(main())
