# Kimi Harness

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-green.svg)](https://www.python.org/)

> 基于 [MoonshotAI/kimi-cli](https://github.com/MoonshotAI/kimi-cli) 的白盒化 Agent 基础设施改造，架构参考 [HKUDS/OpenHarness](https://github.com/HKUDS/OpenHarness)。

## 简介

Kimi Harness 将 kimi-cli 的核心组件抽象为可独立审查、替换、组合的标准接口，实现**白盒化** Agent 架构。公式：

> **Harness = Tools + Knowledge + Observation + Action + Permissions**

与原始 kimi-cli 相比，Kimi Harness 新增了：

- **BaseTool 标准接口** — 统一工具抽象 + KosongToolAdapter 适配器
- **ToolRegistry** — 独立的工具注册表，与执行/Hook/MCP 解耦
- **MemoryManager** — 跨会话持久化记忆系统
- **PermissionChecker** — 多级权限检查（路径规则、命令拒绝、敏感路径保护）
- **HarnessStreamEvent** — 9 种统一流式事件 + WireToStreamAdapter
- **TeamCoordinator** — 多 Agent 团队协调器
- **SandboxExecutor** — 沙箱执行环境（无隔离/命令级/Docker）
- **OpenHarness 生态兼容** — 技能路径兼容 `~/.openharness/skills/`

## 与上游 kimi-cli 的区别

| 维度 | kimi-cli | Kimi Harness |
|------|----------|-------------|
| 包名 | `kimi-cli` | `kimi-harness` |
| CLI 命令 | `kimi` / `kimi-cli` | `kimi-harness` / `kh` |
| 数据目录 | `~/.kimi/` | `~/.kimi-harness/` |
| 记忆系统 | 无 | MemoryManager（跨会话持久化） |
| 权限系统 | Approval（审批门面） | PermissionChecker（多级规则） |
| 工具抽象 | kosong Tool | BaseTool + ToolRegistry |
| 事件系统 | WireMessage | HarnessStreamEvent（标准化） |
| 多 Agent | LaborMarket | LaborMarket + TeamCoordinator |
| 沙箱 | 无 | SandboxExecutor（3 种模式） |
| 技能兼容 | kimi/claude/codex | kimi/claude/codex/**openharness** |

两者可安全地同时安装在同一系统上，数据目录、配置、插件完全隔离。

## 安装

```sh
# 从源码安装
git clone https://github.com/Automorrow/kimi-Harness.git
cd kimi-Harness
pip install -e .
```

安装后可通过 `kimi-harness` 或 `kh` 命令启动。

## 使用

```sh
# 启动交互式 Agent
kimi-harness

# 使用简短命令
kh

# 指定模型
kimi-harness --model kimi-k2

# 以 stream-json 模式运行（可观测性输出）
kh --output-format stream-json
```

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
│   ├── soul/                       # Agent 核心运行时（继承自 kimi-cli）
│   ├── tools/                      # 内置工具（继承自 kimi-cli）
│   ├── skill/                      # 技能系统（扩展了 OpenHarness 路径）
│   ├── subagents/                  # 子 Agent 系统（继承自 kimi-cli）
│   ├── wire/                       # 通信层（继承自 kimi-cli）
│   └── agentspec.py                # Agent 规范（扩展了 Harness 字段）
├── packages/                       # kosong + kaos（继承自 kimi-cli）
├── web/                            # Web UI（继承自 kimi-cli）
└── tests/                          # 测试套件（继承自 kimi-cli）
```

## Harness 扩展的 AgentSpec 字段

在原有 kimi-cli AgentSpec 基础上，新增以下声明式字段：

```yaml
# agents/my-agent.yaml
extend: default
name: my-agent
model: kimi-k2

# --- Harness 扩展字段 ---
permission_mode: default          # default | full_auto | plan | dont_ask | accept_edits
max_turns: 50                     # 最大 agentic 轮次
memory: project                   # none | project | global
isolation: none                   # none | worktree | remote
skills: [commit, review, debug]   # 预加载技能列表
hooks:                            # 会话级钩子
  pre_tool_use:
    - plugin: audit-logger
background: false                 # 是否后台运行
color: blue                       # UI 颜色
```

## 开发

```sh
git clone https://github.com/Automorrow/kimi-Harness.git
cd kimi-Harness

make prepare      # 准备开发环境
uv run kimi-harness  # 运行
make format       # 格式化代码
make check        # lint + 类型检查
make test         # 运行测试
```

## 致谢

- [MoonshotAI/kimi-cli](https://github.com/MoonshotAI/kimi-cli) — 上游项目，Apache 2.0 许可证
- [HKUDS/OpenHarness](https://github.com/HKUDS/OpenHarness) — 架构参考，MIT 许可证

## 许可证

[Apache License 2.0](LICENSE) — Copyright 2026 Automorrow
