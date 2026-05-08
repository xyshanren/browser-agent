# Browser-Agent

<div align="center">

**轻量级浏览器自动化 Agent 框架 — 让 VLM 像人一样操作浏览器**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](pyproject.toml)
[![Playwright](https://img.shields.io/badge/Playwright-1.50+-green.svg)](pyproject.toml)

</div>

---

## 快速开始

```bash
pip install browser-agent
playwright install chromium
```

### 配置模型后端

**Option 1: 本地 vLLM（推荐）**
```bash
vllm serve Qwen/Qwen2.5-VL-3B-Instruct --port 8000
```

**Option 2: OpenAI API**
```bash
export BROWSER_AGENT_API_KEY=sk-xxx
```

**Option 3: Ollama**
```bash
ollama run qwen2.5-vl:3b
```

### 使用

```python
from browser_agent import BrowserAgent

agent = BrowserAgent()
result = agent.run("搜索今天深圳的天气并告诉我结果")
print(result.text)
```

或通过 CLI：
```bash
browser-agent "搜索今天深圳的天气"
browser-agent --stream "帮我查看 GitHub 趋势"
```

## 架构

```
Observe (截图+POI检测) → Think (VLM 推理) → Act (浏览器操作)
```

- **多模型后端**：vLLM、OpenAI、Ollama 一键切换
- **POI 检测引擎**：自动识别页面上所有可交互元素
- **上下文管理**：智能截图保留策略，最大化 token 利用
- **可扩展架构**：预留桌面 GUI 环境接口

## 未来规划

- [x] 基础浏览器自动化框架
- [ ] 桌面 GUI 操作支持（集成 Mano-P 等 VLA 模型）
- [ ] 多 Tab 支持
- [ ] Cookie/Session 持久化
- [ ] 任务中断恢复

## 许可证

MIT
