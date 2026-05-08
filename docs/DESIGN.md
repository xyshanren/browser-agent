# Browser-Agent 设计文档

> **版本**: 1.0
> **更新**: 2026-05-08
> **许可证**: MIT

---

## 1. 项目定位

**Browser-Agent** 是一个轻量级、可扩展的 Python 框架，让 AI 模型（VLM）能像人一样操作浏览器，完成网页自动化任务。

核心设计理念：
- **工具框架，不是模型** — 不微调模型，通过精心设计的提示词 + 工具定义发挥 VLM 能力
- **多后端** — 支持 vLLM（本地推理）、OpenAI API（云端）、Ollama（本地轻量）等多种推理后端
- **可扩展环境** — 当前聚焦浏览器，架构上预留桌面 GUI 环境接口（未来对接 Mano-P 等专用模型）
- **pip 安装即用** — 零配置，`pip install browser-agent` → `import` 即可使用

---

## 2. 架构总览

```
┌─────────────────────────────────────────────────────┐
│                    BrowserAgent                      │
│  ┌─────────────────────────────────────────────────┐│
│  │              Observe → Think → Act 循环          ││
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ││
│  │  │ Observe  │→ │  Think   │→ │    Act       │  ││
│  │  │ (截图+POI)│  │ (VLM推理) │  │ (执行工具)   │  ││
│  │  └──────────┘  └──────────┘  └──────────────┘  ││
│  └─────────────────────────────────────────────────┘│
│                          │                           │
│  ┌─────────────────────────────────────────────────┐│
│  │               Pluggable Layers                   ││
│  │                                                  ││
│  │  Environment Layer     Model Layer               ││
│  │  ┌──────────────┐    ┌──────────────────────┐   ││
│  │  │ ● WebBrowser │    │ ● VLLMClient         │   ││
│  │  │ ● DesktopGUI │←──→│ ● OpenAIClient       │   ││
│  │  │   (future)   │    │ ● OllamaClient       │   ││
│  │  │ ● GameUI     │    │ ● ManoPClient(future)│   ││
│  │  │   (future)   │    └──────────────────────┘   ││
│  │  └──────────────┘                                ││
│  └─────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

### 2.1 核心循环（Observe → Think → Act）

每一步循环：

```
1. OBSERVE
   ├── Playwright 截取当前页面截图
   ├── inject POI 检测 JS → 获取所有交互元素列表
   ├── 在截图上标注 Bounding Box 编号
   └── 打包：截图(base64) + POI文本列表 → 发往模型

2. THINK
   ├── VLM 接收多模态输入
   ├── 分析截图，理解页面状态
   ├── 推理下一步最佳操作
   ├── 输出 <observation> 观察结果 </observation>
   ├── 输出 <thinking> 推理过程 </thinking>
   └── 输出 <tool_call> 工具调用 </tool_call>

3. ACT
   ├── 解析 tool_call 中的函数名和参数
   ├── Playwright 执行对应操作（click/type/scroll...）
   ├── 获取执行结果和新的页面状态
   └── 回到 OBSERVE 或 结束任务
```

### 2.2 上下文窗口管理

VLM 的视觉 Token 开销巨大（每张截图 ~1000-3000 tokens），因此：

- **历史中只保留最新的 1 张截图**
- 保留所有文本对话历史（确保模型不丢失上下文）
- 系统提示词包含所有可用的工具定义

```
消息历史结构：
system: [系统提示词 + 工具定义]
user:   "Task: 搜索今天天气"
user:   [截图1 + POI文本]     ← 最新截图
assistant: <observation>...</observation>
           <thinking>...</thinking>
           <tool_call>...</tool_call>
user:   [工具执行结果]
user:   [截图2 + POI文本]     ← 丢弃截图1，保留截图2
assistant: ...
```

---

## 3. 模块设计

### 3.1 `browser_agent.agent` — 主入口

```python
class BrowserAgent:
    """浏览器自动化 Agent 主类。"""
    
    def __init__(self, model_type="vllm", model="Qwen/Qwen2.5-VL-3B-Instruct",
                 api_base=None, api_key=None, headless=True, max_steps=30):
        ...
    
    def run(self, task: str) -> AgentResult:
        """同步执行任务，阻塞直到完成或超时。"""
    
    def run_stream(self, task: str) -> Iterator[Step]:
        """流式执行，每一步 yield 当前状态（截图+思考+行动）。"""
    
    async def run_async(self, task: str) -> AgentResult:
        """异步执行，适合集成到 asyncio 框架中。"""
```

### 3.2 `browser_agent.browser` — 浏览器控制

```python
class BrowserSession:
    """Playwright 浏览器会话封装。"""
    
    async def goto(self, url: str)
    async def click(self, mark_id: int)
    async def type_text(self, mark_id: int, text: str, submit: bool = False)
    async def scroll(self, direction: str, mark_id: int = -1)
    async def screenshot(self) -> tuple[bytes, bytes]
        # 返回: (原始截图, 标注截图)
    async def get_page_text(self) -> str
        # 返回当前页面所有可交互元素的文本描述
    async def go_back(self)
    async def reload(self)
    async def wait(self, seconds: float = 3.0)
```

### 3.3 `browser_agent.models` — 模型后端

所有模型后端实现同一接口：

```python
class BaseModelClient(ABC):
    """模型客户端抽象基类。"""
    
    @abstractmethod
    async def chat(self, messages: list, tools: list = None) -> ModelResponse:
        """发送聊天请求，返回模型响应。"""
    
    @abstractmethod
    async def chat_stream(self, messages: list, tools: list = None) -> AsyncIterator[str]:
        """流式聊天。"""
```

已实现的客户端：

| 客户端 | 后端 | 启动命令 | 适用场景 |
|--------|------|---------|---------|
| `VLLMClient` | 本地 vLLM | `vllm serve Qwen/Qwen2.5-VL-3B-Instruct --port 8000` | 本地推理，完全离线 |
| `OpenAIClient` | OpenAI API | 无需启动 | 云 API，最省资源 |
| `OllamaClient` | Ollama 本地 | `ollama run qwen2.5-vl:3b` | 本地轻量推理 |

### 3.4 `browser_agent.tools` — 工具集

```python
# 浏览器工具
def goto(url: str) -> str
def click(mark_id: int) -> str
def type_text(entries: list[dict], submit: bool) -> str
def scroll(direction: str, mark_id: int) -> str
def go_back() -> str
def reload() -> str
def wait() -> str

# 任务完成工具
def finish(answer: str) -> str  # 标记任务完成并返回结果
```

### 3.5 `browser_agent.vision` — 视觉模块

```python
# find_pois.js — 注入到页面的 JavaScript
#   检测所有可交互元素，返回：{element_descriptions, element_centroids}

# annotator.py — 截图标注
def annotate_bounding_boxes(image: bytes, pois: list) -> bytes
    # 在截图上绘制编号的 bounding box
```

---

## 4. 配置系统

配置文件（`~/.browser-agent/config.toml` 或同级 `.env`）：

```toml
[model]
type = "vllm"              # vllm | openai | ollama
name = "Qwen/Qwen2.5-VL-3B-Instruct"
api_base = "http://localhost:8000/v1"
api_key = ""

[browser]
headless = true
viewport_width = 1280
viewport_height = 720
homepage = "https://www.google.com"
screenshot_delay = 1.0
screenshot_quality = 70

[agent]
max_steps = 30
action_timeout = 30
task_timeout = 300
```

---

## 5. API 设计（面向最终用户）

### 5.1 在代码中直接调用

```python
from browser_agent import BrowserAgent

# 最简单用法
agent = BrowserAgent()
result = agent.run("搜索深圳明天的天气并告诉我结果")
print(result.text)

# 流式查看每一步
for step in agent.run_stream("在 GitHub 搜索 proxy-lite"):
    print(f"\n=== Step {step.number} ===")
    print(f"🔍 Observation: {step.observation}")
    print(f"🧠 Thinking: {step.thinking}")
    print(f"🛠️  Action: {step.action_name}({step.action_args})")
    if step.screenshot:
        # 自动保存或展示截图
        step.screenshot.save(f"step_{step.number}.png")

# 异步集成到其他 Agent
async def my_agent():
    agent = BrowserAgent(model_type="openai", model="gpt-4o")
    result = await agent.run_async("帮我登录邮箱检查新邮件")
```

### 5.2 CLI 命令行

```bash
# 直接运行任务
browser-agent "搜索今天深圳的天气"
browser-agent --headless false "帮我登录 GitHub"

# 指定模型
browser-agent --model openai --api-key sk-xxx "..."

# 流式输出
browser-agent --stream "..."
```

### 5.3 作为 MCP Tool 在你的 Hermes Agent 中使用

```yaml
# skill/browser-agent.yaml
name: browser-agent
description: 浏览器自动操作工具，可打开网页、搜索、填写表单等
tools:
  - browser_automate(task: str) -> str
```

---

## 6. 项目结构

```
browser-agent/
├── pyproject.toml          # 项目配置 (hatchling build)
├── README.md
├── LICENSE                 # MIT
├── docs/
│   └── DESIGN.md           # 本设计文档
├── src/
│   └── browser_agent/
│       ├── __init__.py     # 导出 BrowserAgent
│       ├── agent.py        # BrowserAgent 主类 + 循环引擎
│       ├── browser.py      # BrowserSession (Playwright 封装)
│       ├── config.py       # 配置加载 (TOML + 环境变量)
│       ├── models/
│       │   ├── __init__.py
│       │   ├── base.py     # BaseModelClient 抽象接口
│       │   ├── vllm.py     # VLLMClient (OpenAI 兼容格式)
│       │   ├── openai.py   # OpenAIClient
│       │   └── ollama.py   # OllamaClient
│       ├── tools/
│       │   ├── __init__.py # 工具注册 + schema 生成
│       │   └── browser_tools.py  # 浏览器工具函数定义
│       ├── vision/
│       │   ├── __init__.py
│       │   ├── find_pois.js      # POI 检测 JS（移植自 proxy-lite）
│       │   └── annotator.py      # Bounding Box 标注
│       └── utils/
│           ├── __init__.py
│           ├── history.py        # 消息历史管理
│           └── logger.py         # 日志
├── tests/
│   ├── __init__.py
│   ├── test_agent.py
│   ├── test_browser.py
│   └── test_tools.py
└── examples/
    ├── basic_usage.py
    └── stream_demo.py
```

---

## 7. 未来扩展：Mano-P GUI-VLA 集成

> 本项目架构天然适配 Mano-P 的核心能力，未来可无缝扩展。

### 7.1 Mano-P 简介

Mano-P 1.0 是明略科技开源的 **GUI-VLA（视觉-语言-动作）** 模型，专为桌面 GUI 自动化设计：

| 特性 | Mano-P 1.0-4B |
|------|:------------:|
| 参数量 | 4B |
| 许可证 | **Apache 2.0** ✅ |
| OSWorld 排名 | **#1** (58.2% 专用模型) |
| 输入 | 纯视觉（截图） |
| 动作空间 | click / type / hotkey / scroll / drag / mouse move |
| 支持平台 | macOS (稳定)、Windows/Linux (Beta) |
| 推理模式 | 本地（Apple Silicon）/ 云端 API |

### 7.2 集成方案

```
BrowserAgent 当前 (v1)
└── Environment: WebBrowser (Playwright)
    └── Actions: click/type/scroll/goto/wait/back/reload

BrowserAgent 未来 (v2)
├── Environment: WebBrowser (Playwright)
│   └── Actions: click/type/scroll/goto/wait/back/reload
└── Environment: DesktopGUI (Mano-P / PyAutoGUI)
    ├── Actions: click/type/hotkey/scroll/drag/mouse_move
    ├── OS: macOS / Windows / Linux
    └── 应用: 桌面软件、3D 工具、游戏界面、专业应用
```

### 7.3 关键设计点

1. **统一 Action 接口**：WebBrowser 和 DesktopGUI 的 Action 可以统一为：
   ```python
   class Action:
       type: Literal["click", "type", "scroll", "keypress", ...]
       params: dict  # 坐标、文本、键值等
   ```

2. **环境抽象层**：将 `BrowserSession` 重构为 `BaseEnvironment`：
   ```python
   class BaseEnvironment(ABC):
       async def observe() -> Observation  # 截图 + POI
       async def act(action: Action) -> Observation  # 执行动作
       @property
       def tools() -> list[ToolDef]  # 可用工具定义
   ```

3. **模型选择策略**：根据 Environment 类型自动选择最优模型：
   - Web 任务 → Qwen2.5-VL / GPT-4o
   - 桌面 GUI → Mano-P 1.0-4B
   - 混合任务 → 组合使用

---

## 8. 质量目标

| 维度 | 目标 |
|------|------|
| **安装** | `pip install browser-agent` 零报错 |
| **导入** | `from browser_agent import BrowserAgent` ≤ 2 秒 |
| **测试覆盖** | 核心模块 ≥ 80% |
| **代码质量** | Ruff lint 零告警 |
| **文档** | README + DESIGN + 两个示例脚本 |
| **兼容性** | Python 3.11+ / Windows 主 + macOS/Linux（实验性） |

---

## 9. 与 Proxy-Lite 的设计对比

| 维度 | Proxy-Lite | Browser-Agent |
|------|:----------:|:-------------:|
| 模型绑定 | 硬编码 proxy-lite-3b | 多后端可切换 |
| 环境扩展 | 仅 WebBrowser | 预留 DesktopGUI 接口 |
| 安装方式 | uv + 源码编译 | pip 安装 |
| 工程化 | ❌ 无测试/CI | pytest + GitHub CI |
| 许可证 | CC BY-NC 4.0 | MIT |
| 代码精简度 | ~1500 行框架代码 | ~600 行核心（预估） |
| 用户 API | Runner/Config 模式 | `BrowserAgent().run()` 模式 |
| Mano-P 集成 | ❌ 无考虑 | ✅ 架构预留 |
