"""CLI 入口 — 命令行调用 browser-agent"""

import argparse
import asyncio

from browser_agent import BrowserAgent
from browser_agent.config import Config
from browser_agent.utils.logger import logger


def main():
    parser = argparse.ArgumentParser(description="Browser-Agent: 浏览器自动化 Agent")
    parser.add_argument("task", type=str, help="要执行的任务描述")
    parser.add_argument("--model-type", type=str, default=None, help="模型类型: vllm / openai / ollama")
    parser.add_argument("--model", type=str, default=None, help="模型名称")
    parser.add_argument("--api-base", type=str, default=None, help="API 地址")
    parser.add_argument("--api-key", type=str, default=None, help="API Key")
    parser.add_argument("--headless", action="store_true", default=None, help="无头模式")
    parser.add_argument("--no-headless", action="store_true", help="显示浏览器窗口")
    parser.add_argument("--max-steps", type=int, default=None, help="最大步数")
    parser.add_argument("--stream", action="store_true", help="流式显示每一步")

    args = parser.parse_args()

    # 配置优先级：CLI 参数 > 环境变量 > 默认值
    cfg = Config.from_env()

    if args.model_type:
        cfg.model.type = args.model_type
    if args.model:
        cfg.model.name = args.model
    if args.api_base:
        cfg.model.api_base = args.api_base
    if args.api_key:
        cfg.model.api_key = args.api_key
    if args.headless:
        cfg.browser.headless = True
    if args.no_headless:
        cfg.browser.headless = False
    if args.max_steps:
        cfg.agent.max_steps = args.max_steps

    agent = BrowserAgent(
        model_type=cfg.model.type,
        model=cfg.model.name,
        api_base=cfg.model.api_base,
        api_key=cfg.model.api_key,
        headless=cfg.browser.headless,
        max_steps=cfg.agent.max_steps,
    )

    logger.info(f"🤖 开始执行: {args.task}")

    if args.stream:
        for step in agent.run_stream(args.task):
            print(f"\n=== Step {step.number} ===")
            if step.observation:
                print(f"🔍 观察: {step.observation[:100]}..." if len(step.observation) > 100 else f"🔍 观察: {step.observation}")
            if step.thinking:
                print(f"🧠 思考: {step.thinking[:200]}..." if len(step.thinking) > 200 else f"🧠 思考: {step.thinking}")
            if step.action_name:
                print(f"🛠️  行动: {step.action_name}({step.action_args})")
            if step.action_result:
                print(f"✅ 结果: {step.action_result[:200]}" if len(step.action_result) > 200 else f"✅ 结果: {step.action_result}")
            if step.finished:
                print(f"\n✨ 任务完成! 结果: {step.action_result}")
    else:
        result = agent.run(args.task)
        if result.success:
            print(f"\n✨ 任务完成!")
            print(f"   结果: {result.text}")
        else:
            print(f"\n⚠️ 任务未完成 (共 {len(result.steps)} 步)")
            if result.steps:
                last = result.steps[-1]
                print(f"   最后一步: {last.action_name}({last.action_args}) = {last.action_result[:200]}")
