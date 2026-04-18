"""记忆动态注入提供者 - 将记忆上下文注入到 LLM 步骤中"""

from __future__ import annotations

from kimi_cli.soul.dynamic_injection import DynamicInjection, DynamicInjectionProvider
from kimi_cli.soul.message import Message


class MemoryInjectionProvider(DynamicInjectionProvider):
    """当 Harness Memory 启用时，自动将记忆上下文注入到 LLM 步骤中"""

    async def get_injections(
        self, history: list[Message], soul: Any
    ) -> list[DynamicInjection]:
        runtime = soul.agent.runtime
        if runtime is None or runtime.memory_manager is None:
            return []

        memory_manager = runtime.memory_manager
        memory_prompt = memory_manager.load_memory_prompt()

        if not memory_prompt:
            return []

        return [
            DynamicInjection(
                role="user",
                content=f"<memory-context>\n{memory_prompt}\n</memory-context>",
            )
        ]
