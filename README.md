# Kimi Harness

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-green.svg)](https://www.python.org/)

> 基于 [MoonshotAI/kimi-cli](https://github.com/MoonshotAI/kimi-cli) 的白盒化 Agent 基础设施改造，架构参考 [HKUDS/OpenHarness](https://github.com/HKUDS/OpenHarness)。

---

## 太长不看？一句话开始

**在任意 LLM Agent（Claude Code、AmpCode、Cursor 等）中粘贴以下内容即可安装：**

```
请帮我安装 kimi-harness，按照这个指南操作：
https://raw.githubusercontent.com/Automorrow/kimi-Harness/main/README.md
```

**或者自己动手，3 分钟搞定：**

```sh
git clone https://github.com/Automorrow/kimi-Harness.git
cd kimi-Harness
uv sync --all-extras --all-packages
uv run kh
```

---

## 🪄 魔法词：`harness`（规划中）

> ⚠️ 此功能尚在开发中，暂不可用。

不想看文档？在你的提示词中加入 `harness`（或 `hns`）。

Kimi Harness 会自动启用全部能力——跨会话记忆、多级权限、沙箱隔离、多 Agent 协调、标准化事件流。Agent 自己会搞清楚该怎么做。

**示例：**

```
harness 帮我重构这个项目的认证模块，注意安全边界
```

```
hns 审查这个 PR，给出改进建议
```

---

## 这是什么？

Kimi Harness 将 kimi-cli 的核心组件抽象为可独立审查、替换、组合的标准接口，实现**白盒化** Agent 架构。

> **Harness = Tools + Knowledge + Observation + Action + Permissions**

### 和原版 kimi-cli 有什么不同？

| 维度 | kimi-cli | Kimi Harness |
|------|----------|-------------|
| CLI 命令 | `kimi` | `kimi-harness` / `kh` |
| 数据目录 | `~/.kimi/` | `~/.kimi-harness/` |
| 记忆系统 | ❌ 无 | ✅ 跨会话持久化记忆 |
| 权限系统 | 审批门面 | 多级规则（路径/命令/敏感保护） |
| 工具抽象 | kosong 内部 | BaseTool 标准接口 + ToolRegistry |
| 事件系统 | WireMessage（私有） | HarnessStreamEvent（标准化 JSON） |
| 多 Agent | 子 Agent | 子 Agent + **团队协调** |
| 沙箱 | ❌ 无 | ✅ 3 种模式（无/命令级/Docker） |
| 技能兼容 | kimi/claude/codex | kimi/claude/codex/**openharness** |

**两者可安全共存**，数据目录、配置、插件完全隔离。

---

## 安装

### 前置要求

| 依赖 | 说明 |
|------|------|
| **Python** | 3.12+ |
| **uv** | [安装指南](https://docs.astral.sh/uv/getting-started/installation/) |

### 方式一：源码安装（推荐）

```sh
# 1. 克隆
git clone https://github.com/Automorrow/kimi-Harness.git
cd kimi-Harness

# 2. 安装依赖（含 kosong、kaos 等 workspace 子包）
uv sync --all-extras --all-packages

# 3. 验证
uv run kh --version
```

### 方式二：安装到系统

```sh
cd kimi-Harness
uv pip install -e .
kimi-harness --version
```

### 方式三：构建独立二进制

```sh
make build-bin    # 单文件可执行
# 或
make build-bin-onedir  # 目录形式
```

---

## 快速上手

### 基本使用

```sh
# 启动交互式 Agent
kh

# 使用全名
kimi-harness

# 指定模型
kh --model kimi-k2

# 非交互模式（管道）
echo "解释这段代码" | kh --print

# 指定工作目录
kh --cwd /path/to/project
```

### 配置 API Key

```sh
# 方式一：环境变量
export KIMI_API_KEY="your-api-key"
kh

# 方式二：登录（OAuth）
kh
> /login

# 方式三：使用其他 Provider
export OPENAI_API_KEY="sk-xxx"
kh --provider openai --model gpt-4o

# 方式四：使用 Gemini
export GOOGLE_API_KEY="xxx"
kh --provider gemini --model gemini-2.5-pro
```

### Shell 模式

Kimi Harness 不仅是编码 Agent，也是一个 Shell。按 `Ctrl-X` 切换到 Shell 命令模式，直接运行终端命令：

```
> 你好，帮我看看这个项目
（Agent 模式，AI 回复）

$ ls -la              ← 按 Ctrl-X 切换
（Shell 模式，直接执行命令）

> 继续分析            ← 再按 Ctrl-X 切回
（Agent 模式）
```

### 使用技能（Skills）

```sh
# 列出可用技能
kh
> /skills

# 使用特定技能
> /skill:commit          # 智能 Git 提交
> /skill:review          # 代码审查
> /skill:debug           # 调试助手
> /skill:plan            # 架构规划
> /skill:pdf             # PDF 处理
> /skill:xlsx            # Excel 处理
```

### MCP 工具集成

```sh
# 添加 HTTP 服务器
kh mcp add --transport http context7 https://mcp.context7.com/mcp

# 添加 stdio 服务器
kh mcp add --transport stdio chrome-devtools -- npx chrome-devtools-mcp@latest

# 添加带 OAuth 的服务器
kh mcp add --transport http --auth oauth linear https://mcp.linear.app/mcp

# 列出已添加的服务器
kh mcp list

# 移除服务器
kh mcp remove chrome-devtools
```

也可以通过配置文件批量添加：

```json
// mcp.json
{
  "mcpServers": {
    "context7": {
      "url": "https://mcp.context7.com/mcp",
      "headers": { "CONTEXT7_API_KEY": "YOUR_KEY" }
    },
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@latest"]
    }
  }
}
```

```sh
kh --mcp-config-file mcp.json
```

### IDE 集成（ACP 协议）

Kimi Harness 支持 [Agent Client Protocol](https://github.com/agentclientprotocol/agent-client-protocol)，可接入任意兼容 IDE。

**Zed / JetBrains 配置：**

```json
{
  "agent_servers": {
    "Kimi Harness": {
      "type": "custom",
      "command": "kimi-harness",
      "args": ["acp"],
      "env": {}
    }
  }
}
```

**VS Code 扩展：** 安装 [Kimi Code VS Code Extension](https://marketplace.visualstudio.com/items?itemName=moonshot-ai.kimi-code)，将命令改为 `kimi-harness`。

### Web UI

```sh
# 启动 Web 服务（默认端口 5495）
kh web

# 局域网访问
kh web --network

# 公网访问（谨慎使用）
kh web --network --public

# 指定端口
kh web --port 8080
```

服务器无桌面环境时，通过 SSH 端口转发访问：

```sh
ssh -L 5495:127.0.0.1:5495 user@server
# 本地浏览器打开 http://127.0.0.1:5495
```

### Zsh 集成

```sh
# 安装插件
git clone https://github.com/MoonshotAI/zsh-kimi-cli.git \
  ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/kimi-cli

# 添加到 .zshrc
plugins=(... kimi-cli)
```

重启 Zsh 后按 `Ctrl-X` 切换 Agent 模式。

---

## Harness 核心能力

### 🧠 跨会话记忆

Agent 可以记住之前对话中的关键信息，下次启动时自动加载。

```
> 记住：我们选择了 PostgreSQL 作为主数据库
（记忆已保存到 ~/.kimi-harness/memory/）

# 下次启动时...
> 我们之前选了什么数据库？
（Agent 自动检索记忆：PostgreSQL）
```

记忆存储位置：
- 项目级：`.kimi-harness/memory/MEMORY.md`
- 用户级：`~/.kimi-harness/memory/MEMORY.md`

### 🔒 多级权限

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `default` | 写操作需确认 | 日常开发 |
| `full_auto` | 全部自动放行 | 沙箱/Docker 环境 |
| `plan` | 阻止所有写操作 | 大规模重构规划 |
| `dont_ask` | 自动批准写操作 | 自动化流水线 |
| `accept_edits` | 自动批准文件编辑 | 代码审查 |

内置敏感路径保护（SSH 密钥、AWS/GCP/Azure 凭证等），**始终生效，不可关闭**。

### 📡 标准化事件流

```sh
# 以 JSON 事件流模式运行，便于程序化监控
kh --output-format stream-json
```

输出示例：
```json
{"type": "tool_execution_started", "tool_name": "bash", "timestamp": "..."}
{"type": "tool_execution_completed", "tool_name": "bash", "output": "...", "is_error": false}
{"type": "permission", "tool_name": "write_file", "decision": "allowed"}
```

### 🏗️ 多 Agent 团队

```yaml
# agents/review-team.yaml
extend: default
name: review-team
permission_mode: accept_edits
skills: [review, commit]
```

### 🐳 沙箱执行

> ⚠️ Docker 模式需要服务器安装 Docker。命令级沙箱（`isolation: worktree`）无需额外依赖。

```yaml
# 在 Agent Spec 中声明隔离模式
isolation: none        # 直接执行
isolation: worktree    # Git worktree 隔离
isolation: remote      # 远程执行
```

---

## 自定义 Agent

创建 `.kimi-harness/agents/my-agent.yaml`：

```yaml
extend: default
name: my-agent
model: kimi-k2
system_prompt_path: prompts/my-agent.md

# --- Harness 扩展字段 ---
permission_mode: default
max_turns: 50
memory: project                   # none | project | global
isolation: none
skills: [commit, review, debug]
hooks:
  pre_tool_use:
    - plugin: audit-logger
background: false
color: blue
```

使用：

```sh
kh --agent my-agent
```

---

## 配置文件

主配置：`~/.kimi-harness/config.toml`

```toml
[default]
model = "kimi-k2"
provider = "kimi"

[permissions]
mode = "default"  # default | full_auto | plan | dont_ask | accept_edits
```

项目级配置：`.kimi-harness/config.toml`（优先级更高）

---

## 项目结构

```
kimi-Harness/
├── src/kimi_cli/
│   ├── harness/                    # ★ Harness 新增模块
│   │   ├── tools/base.py           #   BaseTool + ToolRegistry + KosongToolAdapter
│   │   ├── memory/manager.py       #   MemoryManager 跨会话记忆
│   │   ├── permissions/checker.py  #   PermissionChecker 多级权限
│   │   ├── events/stream.py        #   HarnessStreamEvent 统一事件
│   │   ├── coordinator/team.py     #   TeamCoordinator 团队协调
│   │   └── sandbox/executor.py     #   SandboxExecutor 沙箱执行
│   ├── soul/                       # Agent 核心运行时
│   ├── tools/                      # 内置工具
│   ├── skill/                      # 技能系统（兼容 OpenHarness）
│   ├── subagents/                  # 子 Agent 系统
│   ├── wire/                       # 通信层
│   └── agentspec.py                # Agent 规范（含 Harness 扩展字段）
├── packages/                       # kosong + kaos
├── web/                            # Web UI
└── tests/                          # 测试套件
```

---

## 开发

```sh
git clone https://github.com/Automorrow/kimi-Harness.git
cd kimi-Harness

make prepare       # 准备开发环境
uv run kh          # 运行
make format        # 格式化代码
make check         # lint + 类型检查
make test          # 运行测试
make build-web     # 构建 Web UI（需要 Node.js）
make build-bin     # 构建独立二进制
```

---

## 常见问题

<details>
<summary>和原版 kimi-cli 可以同时安装吗？</summary>

可以。两者数据目录（`~/.kimi` vs `~/.kimi-harness`）、配置、插件、会话完全隔离。
</details>

<details>
<summary>支持哪些 LLM Provider？</summary>

Kimi（MoonshotAI）、OpenAI、Anthropic Claude、Google Gemini、Vertex AI、Ollama 等，通过 `--provider` 切换。
</details>

<details>
<summary>如何使用 OpenHarness 的技能？</summary>

将 `.md` 技能文件放入 `~/.openharness/skills/` 或项目的 `.openharness/skills/` 目录，Kimi Harness 会自动发现。
</details>

<details>
<summary>Web 端口冲突怎么办？</summary>

默认端口 `5495`（kimi-cli 用 `5494`）。如果仍冲突，会自动寻找可用端口。也可用 `kh web --port 8080` 指定。
</details>

---

## 致谢

- [MoonshotAI/kimi-cli](https://github.com/MoonshotAI/kimi-cli) — 上游项目，Apache 2.0
- [HKUDS/OpenHarness](https://github.com/HKUDS/OpenHarness) — 架构参考，MIT

## 许可证

[Apache License 2.0](LICENSE) — Copyright 2026 Automorrow
