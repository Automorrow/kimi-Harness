"""Tool for maintaining a project TODO markdown file."""

from __future__ import annotations

from pathlib import Path
from typing import override

from kosong.tooling import CallableTool2, ToolError, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.soul.agent import Runtime


class TodoWriteParams(BaseModel):
    """Arguments for TODO writes."""

    item: str = Field(description="TODO item text")
    checked: bool = Field(default=False, description="Whether the item is checked/done")
    path: str = Field(default="TODO.md", description="Path to the TODO markdown file")


class TodoWrite(CallableTool2[TodoWriteParams]):
    """Add or update an item in a TODO markdown file."""

    name: str = "TodoWrite"
    description: str = (
        "Add a new TODO item or mark an existing one as done in a markdown checklist file."
    )
    params: type[TodoWriteParams] = TodoWriteParams

    def __init__(self, runtime: Runtime):
        super().__init__()
        self._runtime = runtime

    @override
    async def __call__(self, params: TodoWriteParams) -> ToolReturnValue:
        target_path = Path(params.path)
        if not target_path.is_absolute():
            target_path = Path(self._runtime.session.work_dir) / params.path

        existing = target_path.read_text(encoding="utf-8") if target_path.exists() else "# TODO\n"

        unchecked_line = f"- [ ] {params.item}"
        checked_line = f"- [x] {params.item}"
        target_line = checked_line if params.checked else unchecked_line

        if unchecked_line in existing and params.checked:
            updated = existing.replace(unchecked_line, checked_line, 1)
        elif target_line in existing:
            return ToolReturnValue(
                is_error=False,
                output=f"No change needed in {target_path}",
                message=f"No change needed in {target_path}",
                display=[],
            )
        else:
            updated = existing.rstrip() + f"\n{target_line}\n"

        try:
            target_path.write_text(updated, encoding="utf-8")
        except Exception as exc:
            return ToolError(
                message=f"Failed to write {target_path}: {exc}",
                brief="Write failed",
            )

        return ToolReturnValue(
            is_error=False,
            output=f"Updated {target_path}",
            message=f"Updated {target_path}",
            display=[],
        )
