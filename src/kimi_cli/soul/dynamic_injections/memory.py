"""Memory dynamic injection provider.

When Harness Memory is enabled (via magic word), injects the memory
context into the LLM step as a dynamic system reminder.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from kosong.message import Message

from kimi_cli.soul.dynamic_injection import DynamicInjection, DynamicInjectionProvider

if TYPE_CHECKING:
    from kimi_cli.soul.kimisoul import KimiSoul


class MemoryInjectionProvider(DynamicInjectionProvider):
    """Inject memory context when Harness MemoryManager is active."""

    async def get_injections(
        self,
        history: Sequence[Message],
        soul: KimiSoul,
    ) -> list[DynamicInjection]:
        runtime = soul._runtime
        if runtime.memory_manager is None:
            return []
        try:
            prompt = runtime.memory_manager.load_memory_prompt()
        except Exception:
            return []
        if not prompt:
            return []
        return [DynamicInjection(type="memory", content=prompt)]
