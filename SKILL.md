---
name: browser-agent
description: 浏览器/桌面 GUI 自动化工具。通过纯视觉理解操作界面，支持搜索、填表、数据抓取等任务。支持自动检测本地 VLM / Mano-P 云端 API / Agent 模型注入三种模型源。
version: 1.2.0
author: xyshanren
license: MIT
metadata:
  hermes:
    tags: [Browser-Automation, GUI-VLA, Web-Scraping, Vision-Language-Model, MCP]
    related_skills: [cli, web-development]
    homepage: https://github.com/xyshanren/browser-agent
  mcp:
    server_name: browser-agent
    tools: [browser_navigate, browser_screenshot, browser_click, browser_type, browser_extract]
prerequisites:
  commands: [python3, pip3]
  env_vars: []
  run_once:
    - command: pip3 install browser-agent playwright
      description: 安装 browser-agent 及其依赖
    - command: python3 -m playwright install chromium
      description: 安装 Playwright 浏览器引擎
    - command: pip3 install "browser-agent[mcp]"
      description: 安装 MCP 支持（可选）
required_environment_variables: []
---

# Browser-Agent: GUI 自动化工具

通过 AI 视觉理解自动操作浏览器/桌面界面。支持：
- 🌐 网页搜索、数据抓取、表单填写
- 📊 提取结构化数据（表格、列表、价格）
- 🔄 多步骤任务编排（先查天气、再搜索、最后汇总）
- 🖥️ 浏览器操作（点击、输入、滚动、导航）

## 工作原理

```
用户输入任务 → ModelRouter 自动选模型 → 截图观察页面 → VLM 理解内容 → 规划操作 → 执行操作 → 返回结果
```

模型选择（无需手动配置，自动检测）：

| 优先级 | 模型源 | 检测方式 |
|--------|--------|----------|
| P0 | 显式指定 | `--model-type` / `--model` 参数 |
| P1 | Mano-P 云端 API | 自动检测 `MANOP_API_KEY` 环境变量 |
| P2 | 本地 VLM (Ollama / vLLM / LM Studio) | 自动 ping localhost 端口 |
| P3 | Agent 模型注入 | `BROWSER_AGENT_FALLBACK_*` 环境变量 |

## 使用方法

### 基础任务

```terminal
browser-agent "搜索今天深圳的天气"
```

### 显示浏览器窗口（调试用）

```terminal
browser-agent --no-headless "帮我登录 GitHub 检查通知"
```

### 流式查看每一步

```terminal
browser-agent --stream "搜索 Python 3.13 新特性并总结"
```

### 使用不同模型

不指定模型时，ModelRouter 自动检测可用模型：

```terminal
# 自动检测：Mano-P > Ollama > vLLM > LM Studio > Agent 注入
browser-agent "搜索今天深圳的天气"
```

也支持手动指定：

```terminal
# 本地 vLLM
browser-agent --model-type vllm --model "Qwen/Qwen2.5-VL-3B-Instruct" --api-base "http://localhost:8000/v1" "..."

# OpenAI API
browser-agent --model-type openai --model gpt-4o --api-key "sk-xxx" "..."

# Mano-P 云端（GUI专用）
browser-agent --model-type manop "..."
```

### Python 集成

```python
from browser_agent import BrowserAgent

# 自动检测模型
agent = BrowserAgent()
result = agent.run("打开百度，搜索今天深圳的天气，告诉我温度和湿度")

# 显式指定模型
agent = BrowserAgent(model_type="ollama", model="qwen3-vl:2b")
result = agent.run("搜索深圳天气")
print(result.text)
```

## 多步骤编排

对于复杂任务，Hermes Agent 可以分步调用 browser-agent：

```terminal
# 步骤 1: 收集信息
browser-agent "打开百度，搜索深圳今天天气，提取温度和风力"

# 步骤 2: 对比分析（基于步骤 1 的结果继续）
browser-agent "打开百度，搜索广州今天天气，和深圳对比"

# 或使用 Python 一次性编排
python -c "
from browser_agent import BrowserAgent
a = BrowserAgent()
r1 = a.run('搜索深圳天气')
print('深圳:', r1.text)
r2 = a.run('搜索广州天气')
print('广州:', r2.text)
print('综合:', r1.text, r2.text)
"
```

## 注意事项

1. **模型自动选择**: 不指定模型时，ModelRouter 按 P1→P2→P3 优先级自动检测。可用 `--model-type` 显式覆盖。
2. **本地 VLM**: 如使用本地模型，需先安装并运行 Ollama / vLLM / LM Studio。Ollama: `ollama pull qwen3-vl:2b && ollama serve`
3. **Mano-P 云端**: 设置 `MANOP_API_KEY` 环境变量即可启用，无需本地 GPU。
4. **Agent 模型注入**: 调用方可设置 `BROWSER_AGENT_FALLBACK_*` 环境变量传递备选模型，仅 VLM 模型有效。
5. **headless 模式（默认）**: 浏览器在后台运行，不显示窗口。
6. **耗时任务**: 模型推理需要时间，每步约 5-15 秒。
7. **反爬检测**: 部分网站可能拦截自动化操作，可尝试 `--no-headless` 降低被检测概率。

### 跨平台说明

browser-agent 是纯 Python 项目，**Android 和 iOS 除外**，主流平台均可运行：

| 平台 | Playwright headless | Playwright headed | Ollama | 备注 |
|------|-------------------|-------------------|--------|------|
| Linux 原生 | ✅ | ✅ 需 Xvfb/X11 | ✅ | 服务器部署首选 |
| WSL2 | ✅ | ✅ WSLg(Win11)/Xvfb(Win10) | ✅ | Hermes Agent 典型场景 |
| Windows 原生 | ✅ | ✅ | ✅ | 桌面自动化首选 |
| macOS | ✅ | ✅ | ✅ | 开发调试友好 |

**WSL2 关键说明**：Playwright 在 WSL2 中 headless 模式运行无需任何额外配置。Hermes Agent 与 browser-agent 都装在 WSL2 内即可正常使用。Mano-P（桌面 GUI 自动化）目前仅支持 macOS Apple Silicon，Windows/Linux 暂不支持，等待其第三阶段开源。详见 [跨平台支持](README.md#跨平台支持)。

---

## MCP Server 模式

browser-agent 内置 MCP Server，可以被**任何 MCP 兼容客户端**调用：

### Claude Desktop 配置

```json
// Windows: %APPDATA%\Claude\claude_desktop_config.json
// macOS: ~/.config/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "browser-agent": {
      "command": "python",
      "args": ["-m", "browser_agent.mcp_server"]
    }
  }
}
```

### Cline / Cursor / Continue 配置

在对应的 MCP settings 中添加：

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

### MCP 工具列表

| 工具 | 说明 | 参数 |
|------|------|------|
| `browser_navigate` | 执行浏览器任务 | `task` (必填), `headless`, `max_steps` |
| `browser_screenshot` | 截图当前页面 | `describe` (是否描述内容) |
| `browser_click` | 点击元素 | `x`, `y` 或 `description` |
| `browser_type` | 输入文本 | `text` (必填), `submit` |
| `browser_extract` | 提取结构化数据 | `query` (必填), `format` |

### 使用示例

```
用户: 帮我搜索一下 GitHub 上的热门 AI 项目
     ↓ MCP 调用 browser_navigate
     ↓ Agent 执行任务并返回结果
```

---

## 多 Agent 共享

browser-agent 作为独立 Python 包，支持被多个 Agent 框架共享：

### 方式 A: pip 安装（推荐）

```bash
pip install browser-agent
# 直接 import 使用
```

### 方式 B: MCP Server（跨框架通用）

任何支持 MCP 的 Agent 框架都能通过 MCP Server 调用 browser-agent。

### 方式 C: Agent 模型注入

调用方可设置环境变量让 browser-agent 使用 Agent 自身的模型（需为 VLM）：

```bash
export BROWSER_AGENT_FALLBACK_MODEL_TYPE=openai
export BROWSER_AGENT_FALLBACK_MODEL=gpt-4o
export BROWSER_AGENT_FALLBACK_API_KEY=sk-xxx
```
