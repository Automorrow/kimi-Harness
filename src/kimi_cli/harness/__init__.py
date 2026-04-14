"""Kimi Harness - 白盒化 Agent 基础设施层.

将 kimi-cli 的核心组件抽象为可独立审查、替换、组合的标准接口，
实现对齐 OpenHarness 的白盒化架构。

主要组件:
- PermissionChecker: 多级权限检查（permissions/checker.py）
- MemoryManager: 跨会话记忆持久化（memory/manager.py）
- SandboxExecutor: 沙箱命令执行（sandbox/executor.py）
- TeamCoordinator: 多 Agent 团队协调（coordinator/team.py）
- ToolRegistry: 标准化工具注册（tools/base.py）
- WireToStreamAdapter: 事件流桥接（events/stream.py）

这些组件通过 Runtime 扩展字段注入，可供外部消费者（如 Web UI、
监控面板、IDE 插件）通过 runtime.tool_registry、
runtime.sandbox_executor 等属性访问。
"""

from __future__ import annotations

__all__ = [
    "PermissionChecker",
    "PermissionMode",
    "PermissionSettings",
    "MemoryManager",
    "SandboxExecutor",
    "SandboxMode",
    "TeamCoordinator",
    "ToolRegistry",
    "WireToStreamAdapter",
    "MagicWordResult",
    "detect_magic_word",
]


def __getattr__(name: str):
    """延迟导入，避免循环依赖导致的 segfault。"""
    _LAZY_MAP = {
        "PermissionChecker": "kimi_cli.harness.permissions.checker",
        "PermissionMode": "kimi_cli.harness.permissions.checker",
        "PermissionSettings": "kimi_cli.harness.permissions.checker",
        "MemoryManager": "kimi_cli.harness.memory.manager",
        "SandboxExecutor": "kimi_cli.harness.sandbox.executor",
        "SandboxMode": "kimi_cli.harness.sandbox.executor",
        "TeamCoordinator": "kimi_cli.harness.coordinator.team",
        "ToolRegistry": "kimi_cli.harness.tools.base",
        "WireToStreamAdapter": "kimi_cli.harness.events.stream",
        "MagicWordResult": "kimi_cli.harness.magic_word",
        "detect_magic_word": "kimi_cli.harness.magic_word",
    }
    if name in _LAZY_MAP:
        import importlib

        module = importlib.import_module(_LAZY_MAP[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
