"""Kimi Harness - 跨会话记忆与多 Agent 团队协调"""

from kimi_cli.harness.magic_word import detect_magic_word, MagicWordResult
from kimi_cli.harness.memory.manager import MemoryManager
from kimi_cli.harness.coordinator.team import TeamCoordinator

__all__ = [
    "MemoryManager",
    "TeamCoordinator",
    "detect_magic_word",
    "MagicWordResult",
]
