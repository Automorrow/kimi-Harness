"""Kimi Harness - 白盒化 Agent 基础设施层.

将 kimi-cli 的核心组件抽象为可独立审查、替换、组合的标准接口，
实现对齐 OpenHarness 的白盒化架构。

主要组件:
- MemoryManager: 跨会话记忆持久化（memory/manager.py）
- TeamCoordinator: 多 Agent 团队协调（coordinator/team.py）

这些组件通过 Runtime 扩展字段注入，由魔法词检测触发激活。
"""

from __future__ import annotations

__all__ = [
    "MemoryManager",
    "TeamCoordinator",
    "MagicWordResult",
    "detect_magic_word",
]


def __getattr__(name: str):
    """延迟导入，避免循环依赖导致的 segfault。"""
    _LAZY_MAP = {
        "MemoryManager": "kimi_cli.harness.memory.manager",
        "TeamCoordinator": "kimi_cli.harness.coordinator.team",
        "MagicWordResult": "kimi_cli.harness.magic_word",
        "detect_magic_word": "kimi_cli.harness.magic_word",
    }
    if name in _LAZY_MAP:
        import importlib

        module = importlib.import_module(_LAZY_MAP[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
