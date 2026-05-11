"""端到端测试：验证 v0.1.1 新功能（DOM Dehydration + 结构化反射）

使用硅基流动 Qwen/Qwen3-VL-8B-Thinking 云端 API。
测试步骤：
1. 导航到百度首页
2. 搜索"深圳天气"
3. 提取结果中的温度信息

验证点：
- DOM Dehydration 文本是否正常输出
- 模型是否能按结构化反射格式响应
- 多步任务链是否完整走通
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from browser_agent import BrowserAgent
from browser_agent.utils.logger import logger


async def main():
    task = "打开百度，搜索'深圳天气'，告诉我今天的温度和湿度"

    agent = BrowserAgent(
        model_type="openai",
        model="Qwen/Qwen3-VL-8B-Thinking",
        api_base="https://api.siliconflow.cn/v1",
        api_key="sk-neyrigdktloquxosvunnevywowxxbdkvexwoquczyxdorqft",
        headless=False,  # 显示浏览器方便观察
        max_steps=20,
        task_timeout=300,
        action_timeout=120,
        homepage="https://www.baidu.com",
    )

    print(f"\n{'='*60}")
    print(f"🤖 任务: {task}")
    print(f"📦 模型: Qwen/Qwen3-VL-8B-Thinking (硅基流动)")
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

    # 打印详细步骤（含新字段）
    print("详细步骤记录：")
    for s in result.steps:
        print(f"\n  Step {s.number}:")
        if s.observation:
            print(f"    Obs: {s.observation[:100]}...")
        if s.thinking:
            print(f"    Think: {s.thinking[:150]}")
        if s.evaluation:
            print(f"    ✅  Eval: {s.evaluation[:150]}")
        if s.next_goal:
            print(f"    🎯  Next: {s.next_goal[:150]}")
        if s.action_name:
            print(f"    Act: {s.action_name}({s.action_args})")
        if s.action_result:
            print(f"    Result: {s.action_result[:200]}")


if __name__ == "__main__":
    asyncio.run(main())
