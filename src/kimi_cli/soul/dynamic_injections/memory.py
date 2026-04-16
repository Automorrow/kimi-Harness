"""Memory dynamic injection provider.

When Harness Memory is enabled (via magic word), injects the memory
context into the LLM step as a dynamic system reminder.

Two-phase injection (inspired by OpenHarness):
1. Always inject MEMORY.md index (truncated to 200 lines) as a directory.
2. When the user query changes, search for relevant memories and inject
   their full content (truncated to 8000 chars per entry).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from kosong.message import Message

from kimi_cli.soul.dynamic_injection import DynamicInjection, DynamicInjectionProvider

if TYPE_CHECKING:
    from kimi_cli.soul.kimisoul import KimiSoul

# Limits matching OpenHarness defaults
_INDEX_MAX_LINES = 200
_CONTENT_MAX_CHARS = 8000
_RELEVANT_MAX_RESULTS = 3


class MemoryInjectionProvider(DynamicInjectionProvider):
    """Inject memory context when Harness MemoryManager is active.

    Uses a two-phase strategy:
    - Phase 1: Always inject MEMORY.md index (acts as a table of contents).
    - Phase 2: When the recent user query changes, search for relevant
      memories and inject their full content for deeper context.
    """

    def __init__(self) -> None:
        self._last_query: str = ""

    async def get_injections(
        self,
        history: Sequence[Message],
        soul: KimiSoul,
    ) -> list[DynamicInjection]:
        runtime = soul._runtime
        if runtime.memory_manager is None:
            return []

        injections: list[DynamicInjection] = []

        # Phase 1: Always inject MEMORY.md index (truncated)
        try:
            prompt = runtime.memory_manager.load_memory_prompt()
        except Exception:
            return []
        if prompt:
            lines = prompt.splitlines()
            if len(lines) > _INDEX_MAX_LINES:
                prompt = (
                    "\n".join(lines[:_INDEX_MAX_LINES])
                    + "\n... (truncated, use SearchMemory for details)"
                )
            injections.append(DynamicInjection(type="memory_index", content=prompt))

        # Phase 2: Search for relevant memories based on recent user query
        query = self._extract_recent_query(history)
        if query and query != self._last_query:
            self._last_query = query
            try:
                from kimi_cli.harness.memory.search import find_relevant_memories

                relevant = find_relevant_memories(
                    query,
                    str(runtime.session.work_dir),
                    max_results=_RELEVANT_MAX_RESULTS,
                )
                if relevant:
                    parts = ["## Relevant Memories"]
                    for header in relevant:
                        content = header.path.read_text(encoding="utf-8")
                        if len(content) > _CONTENT_MAX_CHARS:
                            content = content[:_CONTENT_MAX_CHARS] + "\n... (truncated)"
                        parts.append(f"### {header.title}\n{content}")
                    injections.append(
                        DynamicInjection(
                            type="memory_relevant",
                            content="\n\n".join(parts),
                        )
                    )
            except Exception:
                pass

        return injections

    @staticmethod
    def _extract_recent_query(history: Sequence[Message]) -> str:
        """Extract query text from the most recent user messages.

        Scans the last 3 user messages (skipping system-reminder injections)
        and concatenates their text content.
        """
        user_texts: list[str] = []
        for msg in reversed(history):
            if msg.role != "user":
                continue
            text = ""
            for part in msg.content:
                if hasattr(part, "text") and part.text:
                    text += part.text
            # Skip system-reminder injections (they are not real user queries)
            if text and not text.strip().startswith("<system-reminder>"):
                user_texts.append(text)
            if len(user_texts) >= 3:
                break
        return " ".join(user_texts)[:500] if user_texts else ""
