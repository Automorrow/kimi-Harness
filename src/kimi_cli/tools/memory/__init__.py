"""Harness Memory tools for AI agent.

Provides SaveMemory and SearchMemory tools that allow the agent
to persist and retrieve cross-session memories.
"""

from __future__ import annotations

from pathlib import Path
from typing import override

from kosong.tooling import CallableTool2, ToolError, ToolOk, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.soul.agent import Runtime
from kimi_cli.tools.utils import load_desc
from kimi_cli.utils.logging import logger


class SaveMemoryParams(BaseModel):
    title: str = Field(
        description="A short title for the memory entry (e.g. 'Project uses pnpm not npm')."
    )
    content: str = Field(
        description="The memory content to persist. Be specific and concise."
    )


class SaveMemory(CallableTool2[SaveMemoryParams]):
    name: str = "SaveMemory"
    params: type[SaveMemoryParams] = SaveMemoryParams

    def __init__(self, runtime: Runtime) -> None:
        description = load_desc(Path(__file__).parent / "save.md")
        super().__init__(description=description)
        self._runtime = runtime

    @override
    async def __call__(self, params: SaveMemoryParams) -> ToolReturnValue:
        mm = self._runtime.memory_manager
        if mm is None:
            return ToolError(
                message="Memory is not enabled. Include 'harness' in your message to enable it.",
                brief="Memory not enabled",
            )
        try:
            entry = mm.add_entry(title=params.title, content=params.content)
            return ToolOk(
                output=f"Memory saved: {entry.name}",
                message=f"Memory entry '{entry.name}' saved successfully.",
            )
        except Exception as exc:
            logger.warning("Failed to save memory: {error}", error=exc)
            return ToolError(
                message=f"Failed to save memory: {exc}",
                brief="Save failed",
            )


class SearchMemoryParams(BaseModel):
    query: str = Field(
        description="Search query to filter memory entries. Matches against titles and content."
    )


class SearchMemory(CallableTool2[SearchMemoryParams]):
    name: str = "SearchMemory"
    params: type[SearchMemoryParams] = SearchMemoryParams

    def __init__(self, runtime: Runtime) -> None:
        description = load_desc(Path(__file__).parent / "search.md")
        super().__init__(description=description)
        self._runtime = runtime

    @override
    async def __call__(self, params: SearchMemoryParams) -> ToolReturnValue:
        mm = self._runtime.memory_manager
        if mm is None:
            return ToolError(
                message="Memory is not enabled. Include 'harness' in your message to enable it.",
                brief="Memory not enabled",
            )
        try:
            entries = mm.list_entries()
            if not entries:
                return ToolOk(
                    output="No memories found.",
                    message="No memory entries exist yet.",
                )
            query_lower = params.query.lower()
            matched = [
                e for e in entries
                if query_lower in e.title.lower() or query_lower in e.content.lower()
            ]
            if not matched:
                return ToolOk(
                    output=f"No memories matching '{params.query}'.",
                    message=f"No entries matched '{params.query}'. Showing all {len(entries)} entries.",
                )
            lines = [f"Found {len(matched)} matching memories:"]
            for e in matched:
                lines.append(f"- **{e.title}**: {e.content[:200]}")
            return ToolOk(
                output="\n".join(lines),
                message=f"Found {len(matched)} matching memory entries.",
            )
        except Exception as exc:
            logger.warning("Failed to search memory: {error}", error=exc)
            return ToolError(
                message=f"Failed to search memory: {exc}",
                brief="Search failed",
            )
