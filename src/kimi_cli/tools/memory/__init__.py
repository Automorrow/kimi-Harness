"""Harness Memory Tools - SaveMemory and SearchMemory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, override

from kosong.tooling import CallableTool2, ToolError, ToolOk, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.tools.utils import load_desc


class SaveMemoryParams(BaseModel):
    title: str = Field(description="A short descriptive title for this memory.")
    content: str = Field(description="The content to remember.")
    user_level: bool = Field(
        default=False,
        description="If true, save to user-level memory (persists across projects).",
    )


class SearchMemoryParams(BaseModel):
    query: str = Field(description="Search query to find relevant memories.")
    user_level: bool = Field(
        default=False,
        description="If true, search user-level memories.",
    )


class SaveMemory(CallableTool2[SaveMemoryParams]):
    name: str = "SaveMemory"
    description: str = load_desc(Path(__file__).parent / "save.md", {})
    params: type[SaveMemoryParams] = SaveMemoryParams

    @override
    async def __call__(self, params: SaveMemoryParams) -> ToolReturnValue:
        from kimi_cli.harness._state import get_harness_runtime

        runtime = get_harness_runtime()
        if runtime is None or runtime.memory_manager is None:
            return ToolError(
                message="Memory not initialized. Use 'harness' magic word first.",
                brief="Memory not initialized",
            )

        try:
            entry_path = runtime.memory_manager.add_entry(
                title=params.title,
                content=params.content,
                user_level=params.user_level,
            )
            return ToolOk(
                output=f"Memory saved: {params.title}\nPath: {entry_path}",
                message="Memory saved",
            )
        except Exception as e:
            return ToolError(
                message=f"Failed to save memory: {e}",
                brief="Save failed",
            )


class SearchMemory(CallableTool2[SearchMemoryParams]):
    name: str = "SearchMemory"
    description: str = load_desc(Path(__file__).parent / "search.md", {})
    params: type[SearchMemoryParams] = SearchMemoryParams

    @override
    async def __call__(self, params: SearchMemoryParams) -> ToolReturnValue:
        from kimi_cli.harness._state import get_harness_runtime

        runtime = get_harness_runtime()
        if runtime is None or runtime.memory_manager is None:
            return ToolError(
                message="Memory not initialized. Use 'harness' magic word first.",
                brief="Memory not initialized",
            )

        try:
            results = runtime.memory_manager.search_entries(
                query=params.query,
                user_level=params.user_level,
            )
            if not results:
                return ToolOk(
                    output=f"No memories found matching '{params.query}'.",
                    message="No results",
                )

            lines: list[str] = []
            for entry in results:
                lines.append(f"## {entry['title']} ({entry.get('created', 'unknown')})")
                lines.append(entry.get("content", ""))
                lines.append("")

            output = "\n".join(lines)
            if len(output) > 50_000:
                output = output[:50_000] + "\n... (truncated)"

            return ToolOk(
                output=output,
                message=f"Found {len(results)} memor{('y' if len(results) == 1 else 'ies')}",
            )
        except Exception as e:
            return ToolError(
                message=f"Failed to search memory: {e}",
                brief="Search failed",
            )
