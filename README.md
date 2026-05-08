# Browser-Agent

<div align="center">

**GUI 自动化编排器 — 让 AI 通过纯视觉理解操作任何界面**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](pyproject.toml)
[![Playwright](https://img.shields.io/badge/Playwright-1.50+-green.svg)](pyproject.toml)
[![Ollama](https://img.shields.io/badge/Ollama-qwen3--vl:2b-orange.svg)](https://ollama.com)

</div>

---

## 快速开始

```bash
pip install browser-agent
playwright install chromium
ollama pull qwen3-vl:2b  # 下载 VLM 模型（~2GB）
```

### 使用

```python
from browser_agent import BrowserAgent

agent = BrowserAgent()  # 默认: Playwright + Ollama qwen3-vl:2b
result = agent.run("搜索今天深圳的天气并告诉我结果")
print(result.text)  # → "深圳今天28℃，多云，降水概率90%"
```

或通过 CLI：
```bash
browser-agent "搜索今天深圳的天气"
browser-agent --stream --no-headless "帮我查看 GitHub 趋势"
```

## 架构（v2.0）

```
Hermes Agent (高层规划)
    │  "帮我查天气、整理文件、发邮件"
    ▼
browser-agent (编排器 + 监督器)
    │  Observe → Think → Act → Verify
    │
    ├── PlaywrightExecutor (浏览器)    ← 当前已实现
    │   └── 通过 DOM + CDP 定位元素
    │
    └── ManoPExecutor (桌面GUI/未来)
        └── 纯视觉定位（不依赖任何协议）
```

- **执行器可插拔** — Playwright（Web） / Mano-P（桌面 GUI）
- **模型可插拔** — Ollama / vLLM / OpenAI 一键切换
- **三层架构** — Hermes Agent(规划) → browser-agent(编排) → executor(执行)

## 模型后端

| 后端 | 命令 | 说明 |
|------|------|------|
| **Ollama** (默认) | `ollama pull qwen3-vl:2b` | 本地运行，~2GB，完全离线 |
| **vLLM** | `vllm serve Qwen/Qwen2.5-VL-3B-Instruct --port 8000` | 性能更强 |
| **OpenAI** | 设置 `api_key` | 云端，最省资源 |

## 设计文档

详见 [docs/DESIGN.md](docs/DESIGN.md)

## 集成 Hermes Agent

browser-agent 可作为 Hermes Agent 的 Skill 使用：

```bash
# 安装 SKILL 后，在 Hermes 中直接调用
browser-agent "搜索今天深圳的天气"
```

Skill 文件位于 Hermes Agent 的 `optional-skills/productivity/browser-agent/SKILL.md`。

## 测试

```bash
# 单元测试
pytest tests/ -v

# 模拟端到端
python examples/e2e_test.py

# 真实 VLM 端到端（需 Ollama + qwen3-vl:2b）
python examples/ollama_e2e.py "你的任务描述"
```

## 许可证

MIT
