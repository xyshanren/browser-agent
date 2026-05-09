# Browser-Agent 设计文档

> **版本**: 2.0（架构重构版）
> **更新**: 2026-05-08
> **许可证**: MIT

---

## 1. 项目定位

**Browser-Agent** 是一个轻量级、可扩展的 **GUI 自动化编排器**。

核心不在于浏览器自动化，而在于让 AI 模型通过**纯视觉理解**来操作任何图形界面。执行器可插拔，从 Playwright 浏览器控制到 Mano-P 桌面 GUI 控制，上层编排层无感知。

### 三层架构

```
Hermes Agent (高层规划)
    │   "做这件事"
    ▼
browser-agent (编排器/监督器)
    │   "怎么做 + 监督执行"
    ├── Observe: 截图 → VLM 理解
    ├── Think:   规划下一步
    ├── Act:     驱动执行器操作
    └── Verify:  执行前后截图对比
    │
    ├── PlaywrightExecutor (浏览器)
    │   └── 通过 CDP/DOM 定位元素
    │
    └── ManoPExecutor (桌面 GUI — 未来)
        └── 纯视觉定位坐标（不依赖任何协议）
```

### 核心设计理念

- **纯视觉优先** — 最终目标是像人一样「看屏幕、理解、操作」，不依赖底层协议
- **执行器可插拔** — Playwright（Web 场景）和 Mano-P（桌面场景）可切换
- **模型可插拔** — Ollama/vLLM/API 三后端
- **编排+监督** — 不仅仅是执行，还要验证结果、自动纠错

---

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                 BrowserAgent（编排器）                    │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Observe → Think → Act 循环           │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │   │
│  │  │ Observe  │→ │  Think   │→ │    Act       │  │   │
│  │  │ (截图+POI)│  │ (VLM推理) │  │ (executor)  │  │   │
│  │  └──────────┘  └──────────┘  └──────┬───────┘  │   │
│  └──────────────────────────────────────────────────┘   │
│                          │                               │
│  ┌──────────────────────────────────────────────────┐   │
│  │              可插拔层                               │   │
│  │                                                    │   │
│  │  Model Layer          Executor Layer                │   │
│  │  ┌──────────────┐    ┌──────────────────────┐    │   │
│  │  │ OllamaClient │    │ PlaywrightExecutor   │    │   │
│  │  │ VLLMClient   │    │  (浏览器 - 已实现)   │    │   │
│  │  │ OpenAIClient │    ├──────────────────────┤    │   │
│  │  │ ManoPClient  │    │ ManoPExecutor        │    │   │
│  │  │   (未来)     │    │  (桌面GUI - 未来)    │    │   │
│  │  └──────────────┘    └──────────────────────┘    │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
         │                          ▲
         │  pip install              │ Hermes Agent Skill
         │  import 使用              │ 轻量包装
         ▼                          │
    ┌──────────┐           ┌──────────────────┐
    │ Python   │           │ Hermes Agent     │
    │ 应用/脚本 │           │ Skill 包装       │
    └──────────┘           └──────────────────┘
```

---

## 3. 执行器接口（BaseExecutor）

所有执行器通过统一抽象接口与编排器交互：

```python
class BaseExecutor(ABC):
    async def start(self)                              # 初始化（打开浏览器/连接服务）
    async def stop(self)                               # 释放资源
    async def observe(self) -> Observation              # 截图 + 环境信息
    async def act(self, action_name, args) -> ActionResult  # 执行动作
    @property
    def tools(self) -> list[dict]                      # 可用工具 Schema
    @property
    def info_for_model(self) -> str                    # 环境描述（注入系统提示词）
```

### 3.1 PlaywrightExecutor（已实现）

- **定位方式**: JS 注入 POI 检测 + Bounding Box 标注
- **工具集**: click/type_text/scroll/goto/back/reload/wait/press_key/hover/extract_text
- **依赖**: Chromium + CDP 协议
- **适用**: Web 浏览器场景

### 3.2 ManoPExecutor（未来）

- **定位方式**: 纯视觉坐标（模型直接输出 `click(x, y)`）
- **工具集**: click_coord/type_at/scroll/press_key/hotkey/wait
- **依赖**: 无（只看截图）
- **适用**: 桌面软件、专业工具、游戏界面

---

## 4. 系统提示词注入

编排器自动根据执行器类型生成系统提示词：

```python
SYSTEM_PROMPT = """You are Browser-Agent, an AI assistant that can perform actions on a computer screen.

{info_for_model}       ← 由 executor.info_for_model 动态注入

For each step, you MUST respond with:
1. <observation>...</observation>
2. <thinking>...</thinking>
3. A tool call to perform the next action."""
```

Playwright 模式下提示词包含编号元素信息；Mano-P 模式下提示词包含屏幕坐标信息。

---

## 5. 项目结构

```
browser-agent/
├── pyproject.toml
├── README.md
├── LICENSE
├── docs/DESIGN.md
├── src/browser_agent/
│   ├── __init__.py           # 导出 BrowserAgent
│   ├── agent.py              # BrowserAgent 编排器主类
│   ├── cli.py                # CLI 入口
│   ├── config.py             # 配置管理
│   ├── executors/            # ← 可插拔执行器
│   │   ├── __init__.py       #   BaseExecutor 抽象 + 工厂
│   │   ├── playwright.py     #   Playwright 浏览器执行器
│   │   └── mano_p.py         #   Mano-P 桌面 GUI 执行器（实验性）
│   ├── browser.py            # BrowserSession（Playwright 底层封装）
│   ├── models/               # 模型客户端
│   │   ├── base.py           #   抽象 + 工厂
│   │   ├── ollama.py         #   Ollama 客户端
│   │   ├── vllm.py           #   vLLM 客户端
│   │   ├── openai.py         #   OpenAI 兼容 API
│   │   └── mano_p.py         #   Mano-P 会话式 API 客户端
│   ├── tools/                # 工具定义（11 个工具）
│   ├── vision/               # POI 检测 JS
│   └── utils/                # 工具函数
├── tests/                    # 14 个单元测试
└── examples/                 # 使用示例
```

---

## 6. 用法示例

### 默认（Playwright 执行器 + Ollama 模型）

```python
from browser_agent import BrowserAgent

agent = BrowserAgent()  # 默认: executor="playwright", model="ollama/qwen3-vl:2b"
result = agent.run("搜索今天深圳的天气")
print(result.text)  # → "深圳今天28℃，多云"
```

### 指定执行器和模型

```python
# Playwright 浏览器模式
agent = BrowserAgent(
    executor_type="playwright",
    model_type="ollama",
    model="qwen3-vl:2b",
    headless=False,
)

# 未来: Mano-P 桌面 GUI 模式
agent = BrowserAgent(
    executor_type="mano_p",
    model_type="mano_p",
    model="Mano-P-1.0-4B",
)
```

---

## 7. 集成 Hermes Agent

Hermes Agent 通过 Skill 调用 browser-agent：

```yaml
# browser-agent.skill
name: browser-agent
description: GUI 自动化操作（浏览器/桌面软件）
command: |
  from browser_agent import BrowserAgent
  agent = BrowserAgent(model_type="ollama", model="qwen3-vl:2b")
  result = agent.run("{{task}}")
  return result.text
```

Hermes 负责高层规划，browser-agent 负责 GUI 执行和监督——**互不依赖，松耦合**。

---

## 8. 质量目标

| 维度 | 当前状态 |
|------|---------|
| 单元测试 | 15 个 ✅ |
| 模拟 E2E 测试 | 2 个 ✅ |
| 真实 VLM E2E 测试 | qwen3-vl:2b 通过 ✅ |
| 可插拔执行器 | Playwright 执行器 ✅ / ManoPExecutor ✅ |
| 多模型后端 | Ollama/vLLM/OpenAI/ManoPClient ✅ |

---

## 9. Mano-P 集成状态

### Cloud API 验证

| 端点 | 状态 | 说明 |
|------|:----:|------|
| `POST /v1/sessions` | ✅ 可用 | 创建会话，返回 session_id |
| `POST /v1/sessions/{id}/step` | ✅ 可用 | 发送截图/动作结果，返回推理+actions |
| `POST /v1/sessions/{id}/close` | ✅ 可用 | 关闭会话 |

> ⚠️ Cloud API 需要 `MANOP_API_KEY`（明略科技提供），目前暂未开放注册。未设置 key 时 ModelRouter 不会尝试连接。有 key 后通过 `--model-type manop` 显式启用。

API 响应示例（OpenAPI 3.1.0 验证通过）：
```json
{
  "reasoning": "我来帮您打开百度搜索深圳天气！",
  "actions": [{"name": "open_url", "input": {"url": "https://..."}}],
  "status": "RUNNING"
}
```

### 本地推理限制

| 平台 | 支持状态 | 原因 |
|:----|:--------:|:-----|
| macOS Apple Silicon (M4+) | ✅ 完整支持 | MLX + Cider SDK |
| Windows + NVIDIA GPU | ❌ 不支持 | Mano-P 仅支持 Apple MLX |
| Linux + NVIDIA GPU | ❌ 不支持 | 同上 |
| 算力棒 (USB 4.0) | ✅ 支持 | 任意 Mac 即插即用 |

### 适配策略

当前状态：**代码已就绪 + 云端 API 已验证，等待 NVIDIA/CUDA 生态开源。**

```
Mano-P 云端 API (mano.mininglamp.com)
    ↓ HTTP
ManoPClient ← 已实现，OpenAPI 规格已验证
    ↓
ManoPExecutor ← 已实现，支持 18 种桌面 action
    ↓
browser-agent 编排器 ← 已有 PlaywrightExecutor 生产可用
```

当 Mano-P 第三阶段开源（训练/量化技术）或社区移植到 CUDA 时，可以快速适配：
1. 新增 `ManoPLocalClient`（继承 `BaseModelClient`，标准 chat 接口）
2. ManoPExecutor 保持不变（action 格式已对齐）
3. 用户只需切换 `executor_type="mano_p"` 即可

---

## 10. 跨平台兼容性

### 设计原则

browser-agent 定位为**纯 Python 跨平台工具**，所有核心依赖（playwright、httpx、pillow、pydantic）均为跨平台，不存在 Windows/Linux 专有绑定。

### 各平台支持矩阵

| 功能 | Linux 原生 | WSL2 (Win11) | WSL2 (Win10) | Windows 原生 | macOS |
|------|-----------|-------------|-------------|-------------|-------|
| Playwright headless | ✅ 完全支持 | ✅ 完全支持 | ✅ 完全支持 | ✅ 完全支持 | ✅ 完全支持 |
| Playwright headed | ✅ Xvfb/X11 | ✅ WSLg 内置 | ⚠️ 需 VcXsrv | ✅ 原生窗口 | ✅ 原生窗口 |
| Ollama VLM | ✅ 原生安装 | ✅ 原生安装 | ✅ 原生安装 | ✅ 原生安装 | ✅ 原生安装 |
| vLLM GPU 推理 | ✅ CUDA 最优 | ⚠️ GPU 穿透 | ⚠️ GPU 穿透 | ⚠️ CUDA | ⚠️ Metal |
| LM Studio | ❌ | ❌ | ❌ | ✅ | ✅ |
| Mano-P 桌面 GUI | ❌ | ❌ | ❌ | ❌ | ✅ MLX |

### Hermes Agent + WSL2 典型架构

Hermes Agent 部署在 WSL2 内时：

```
WSL2 (Linux)
├── Hermes Agent          — CLI/Python 入口
├── browser-agent (pip)   — 编排器
│   ├── PlaywrightExecutor
│   └── Chromium (headless)  ← WSL2 内自有进程
└── Ollama / vLLM         — 本地 VLM 推理

Windows (可选桥接)
└── browser-agent MCP Server  ← 用于 Mano-P 桌面 GUI 操作
```

**关键理解**：Playwright 启动的是自己管理的 Chromium 进程，不依赖系统已安装的浏览器。因此 WSL2 内的 browser-agent 完全自给自足，无需跨 WSL2/Windows 边界操作浏览器。

### WSL2 → Windows 跨边界调用

仅在需要 **Mano-P 桌面 GUI 自动化**（操作 Windows 桌面软件）时需要跨边界：

1. Windows 上启动 `browser-agent-mcp`（MCP Server）
2. WSL2 中的 Hermes Agent 通过 `http://host.docker.internal:PORT` 连接
3. 或通过 SSH 隧道转发 MCP 的 stdio 通道

当前 Playwright 浏览器自动化场景完全不需要此桥接。

### 当前可用的执行方案

| 场景 | 推荐方案 | 执行器 | 模型 |
|:----|:--------|:------|:----|
| Web 浏览器 | ✅ 生产可用 | PlaywrightExecutor | qwen3-vl:2b (Ollama) |
| 桌面 GUI | ⚠️ 云端 API 试运行 | ManoPExecutor | mano.mininglamp.com |
| 3D/专业工具 | ⚠️ 同上 | ManoPExecutor | mano.mininglamp.com |

