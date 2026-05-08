---
name: browser-agent
description: 浏览器/桌面 GUI 自动化工具。通过纯视觉理解操作界面，支持搜索、填表、数据抓取等任务。基于 qwen3-vl VLM 模型本地运行。支持 CLI / Python API / MCP Server 三种调用方式。
version: 1.1.0
author: xyshanren
license: MIT
metadata:
  hermes:
    tags: [Browser-Automation, GUI-VLA, Web-Scraping, Vision-Language-Model, Ollama, Local-AI, MCP]
    related_skills: [cli, web-development]
    homepage: https://github.com/convergence-ai/proxy-lite
  mcp:
    server_name: browser-agent
    tools: [browser_navigate, browser_screenshot, browser_click, browser_type, browser_extract]
prerequisites:
  commands: [python3, pip3, ollama]
  env_vars: []
  run_once:
    - command: pip3 install browser-agent playwright
      description: 安装 browser-agent 及其依赖
    - command: python3 -m playwright install chromium
      description: 安装 Playwright 浏览器引擎
    - command: ollama pull qwen3-vl:2b
      description: 下载 VLM 模型（约 2GB）
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
用户输入任务 → 截图观察页面 → VLM 理解内容 → 规划操作步骤 → 执行操作 → 返回结果
```

模型运行在本地（Ollama + qwen3-vl:2b），所有数据不出设备。

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

```terminal
# 本地 vLLM
browser-agent --model-type vllm --model "Qwen/Qwen2.5-VL-3B-Instruct" --api-base "http://localhost:8000/v1" "..."

# OpenAI API
browser-agent --model-type openai --model gpt-4o --api-key "sk-xxx" "..."
```

### Python 集成（推荐用于复杂任务）

```python
from browser_agent import BrowserAgent

agent = BrowserAgent(headless=True, max_steps=20)
result = agent.run("打开百度，搜索今天深圳的天气，告诉我温度和湿度")
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

1. **首次使用需要安装模型**: `ollama pull qwen3-vl:2b`（约 2GB）
2. **确保 Ollama 正在运行**: `ollama serve`
3. **headless 模式（默认）**: 浏览器在后台运行，不显示窗口
4. **耗时任务**: 模型推理需要时间，耐心等待（每步约 5-15 秒）
5. **反爬检测**: 部分网站可能拦截自动化操作，可尝试 `--no-headless` 降低被检测概率
6. **模型选择**: qwen3-vl:2b 是轻量模型，任务复杂时可换用 4B 或通过 API 使用更强的模型

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

### 方案 A: pip 安装（推荐）

```bash
pip install browser-agent
# 其他 Agent 直接 import 使用
```

### 方案 B: 软链接到 Hermes Agent

```bash
# 在 hermes-agent-cn 项目中
ln -s /path/to/browser-agent/SKILL.md \
  optional-skills/productivity/browser-agent/SKILL.md
```

### 方案 C: MCP Server（跨框架通用）

任何支持 MCP 的 Agent 框架都能通过 MCP Server 调用 browser-agent。
