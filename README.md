# Browser-Agent

<div align="center">

**GUI 自动化编排器 — 让 AI 通过纯视觉理解操作任何界面**

[![PyPI](https://img.shields.io/pypi/v/gui-agent-vlm?color=blue)](https://pypi.org/project/gui-agent-vlm/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](pyproject.toml)
[![Playwright](https://img.shields.io/badge/Playwright-1.50+-green.svg)](pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-ready-purple.svg)](SKILL.md)

</div>

---

## 快速开始

```bash
pip install gui-agent-vlm
playwright install chromium
```

### 使用

```python
from browser_agent import BrowserAgent

# 自动检测可用模型（Mano-P > Ollama > vLLM > LM Studio）
agent = BrowserAgent()
result = agent.run("搜索今天深圳的天气并告诉我结果")
print(result.text)
```

或通过 CLI：
```bash
browser-agent "搜索今天深圳的天气"
```

### 指定模型

```bash
browser-agent --model-type ollama --model qwen3-vl:2b "搜索深圳天气"
browser-agent --model-type openai --model gpt-4o --api-key sk-xxx "搜索深圳天气"
browser-agent --model-type manop "搜索深圳天气"  # Mano-P 云端
```

## 架构

```
Agent (高层规划)
  │  "帮我查天气、整理文件、发邮件"
  ▼
browser-agent (编排器 + ModelRouter 自动选模型)
  │  Observe → Think → Act → Verify
  │
  ├── PlaywrightExecutor (浏览器)
  │   └── 通过 VLM 截图理解 + 操作
  │
  └── ManoPExecutor (桌面 GUI)
      └── 纯视觉定位（Mano-P 云端 API）
```

- **执行器可插拔** — Playwright（Web）/ Mano-P（桌面 GUI）
- **模型自动检测** — Mano-P → Ollama → vLLM → LM Studio 自动回退
- **三种调用方式** — CLI / Python API / MCP Server

## 跨平台支持

browser-agent 是纯 Python 项目，依赖全部跨平台，支持 **Linux、Windows、macOS**。

### 平台兼容性矩阵

| 场景 | Linux 原生 | WSL2 | Windows 原生 | macOS |
|------|-----------|------|-------------|-------|
| Playwright headless | ✅ | ✅ | ✅ | ✅ |
| Playwright headed | ✅ Xvfb/X11 | ✅ WSLg(Win11)/Xvfb(Win10) | ✅ | ✅ |
| Ollama 本地 VLM | ✅ | ✅ | ✅ | ✅ |
| vLLM GPU | ✅ 最优 | ⚠️ GPU 穿透复杂 | ⚠️ CUDA | ⚠️ Metal |
| LM Studio | ❌ | ❌ | ✅ | ✅ |
| Mano-P 桌面 GUI | ❌ | ❌ | ❌ | ✅ MLX |

### WSL2 中使用（Hermes Agent 典型场景）

Hermes Agent 运行在 WSL2 中时，browser-agent 可直接装在 WSL2 内使用：

```bash
# WSL2 中安装
pip install gui-agent-vlm playwright
playwright install chromium
playwright install-deps chromium   # 安装 Linux 系统依赖

# 使用（headless 模式，无需显示环境）
browser-agent "搜索今天深圳的天气"
```

**headless 模式完全不需要显示环境**，Playwright 在 WSL2 中运行无任何障碍。

如需查看浏览器窗口（调试用）：
- **Windows 11**: WSLg 自动支持，`--no-headless` 即可
- **Windows 10**: 需安装 X 服务器（如 VcXsrv），设置 `DISPLAY=:0`

### 跨平台调用（WSL2 Hermes → Windows browser-agent）

如果需要在 WSL2 中调用 Windows 原生桌面上的浏览器或 Mano-P：

```bash
# 方案 1: 全部在 WSL2 内完成（推荐）
# browser-agent 在 WSL2 中启动自己的 Chromium 进程，无需操作 Windows 浏览器
browser-agent "搜索深圳天气"

# 方案 2: 通过 MCP 桥接 Windows
# Windows 上启动 MCP Server
# PowerShell: browser-agent-mcp
# WSL2 中的 Hermes 通过 host.docker.internal:PORT 连接
```

> **关键理解**: Playwright 启动的是自己管理的 Chromium 实例，不是操作"系统上已经打开的浏览器"。因此 WSL2 里的 browser-agent 无需与 Windows 端的浏览器交互——它自己在 WSL2 中启动 Chromium 即可。

## 模型选择

browser-agent 内置 ModelRouter，自动检测可用 VLM：

| 优先级 | 模型源 | 如何启用 |
|--------|--------|----------|
| P0 | 用户显式指定 | `--model-type` / `--model` 参数 |
| P1 | Ollama | 运行 `ollama serve` + 拉取 VLM 模型 |
| P2 | vLLM | `vllm serve Qwen/Qwen2.5-VL-* --port 8000` |
| P3 | LM Studio | 启动并加载 VLM 模型 |
| P4 | Agent 注入 | 设置 `BROWSER_AGENT_FALLBACK_*` 环境变量 |

Mano-P 云端 API 也已集成，代码就绪，但需要明略科技提供的 API key（`MANOP_API_KEY`），目前暂未开放注册。有 key 后可作为显式指定使用：`--model-type manop`。

任何 AI Agent 可以通过环境变量将自己的模型注入 browser-agent：

```bash
export BROWSER_AGENT_FALLBACK_MODEL_TYPE=openai
export BROWSER_AGENT_FALLBACK_MODEL=gpt-4o
export BROWSER_AGENT_FALLBACK_API_KEY=sk-xxx
```

## MCP Server

browser-agent 内置 MCP Server，可被任何 MCP 兼容客户端调用：

```json
{
  "mcpServers": {
    "browser-agent": {
      "command": "python",
      "args": ["-m", "browser_agent.mcp_server"]
    }
  }
}
```

支持工具：`browser_navigate` / `browser_screenshot` / `browser_click` / `browser_type` / `browser_extract`

## 作为 Agent Skill 使用

参阅 [SKILL.md](SKILL.md) — 支持 CLI、Python API、MCP Server 三种集成方式。

## Mano-P 集成

Mano-P 是明略科技开源的 GUI-VLA 模型，代码已集成，但暂未默认启用。

| 场景 | 方案 | 状态 |
|:----|:------|:----:|
| Web 浏览器 | PlaywrightExecutor + 本地 VLM | ✅ 生产可用 |
| 桌面软件/3D/专业工具 | ManoPExecutor + Mano-P Cloud API | ⚠️ 代码就绪，需 `MANOP_API_KEY`（暂未开放注册） |
| Mano-P 本地推理 | 直接在本地运行模型 | ⏳ 仅 macOS Apple Silicon，等待 NVIDIA CUDA 开源 |

> 注意：Mano-P 不在自动检测队列中。持有了 `MANOP_API_KEY` 后通过 `--model-type manop` 显式指定即可使用。

## 测试

```bash
pytest tests/ -v
```

## 许可证

MIT
