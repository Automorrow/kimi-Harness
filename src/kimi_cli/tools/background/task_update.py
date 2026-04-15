"""Tool for updating background task metadata."""

from __future__ import annotations

from typing import override

from kosong.tooling import CallableTool2, ToolError, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.background import format_task
from kimi_cli.soul.agent import Runtime
from kimi_cli.tools.display import BackgroundTaskDisplayBlock


class TaskUpdateParams(BaseModel):
    task_id: str = Field(description="The background task ID to update.")
    description: str | None = Field(
        default=None,
        description="Updated task description.",
    )
    progress: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Progress percentage (0-100).",
    )
    status_note: str | None = Field(
        default=None,
        description="Short human-readable task note.",
    )


class TaskUpdate(CallableTool2[TaskUpdateParams]):
    name: str = "TaskUpdate"
    description: str = "Update a task description, progress, or status note."
    params: type[TaskUpdateParams] = TaskUpdateParams

    def __init__(self, runtime: Runtime):
        super().__init__()
        self._runtime = runtime

    @override
    async def __call__(self, params: TaskUpdateParams) -> ToolReturnValue:
        if self._runtime.role != "root":
            return ToolError(
                message="Background tasks can only be managed by the root agent.",
                brief="Background task unavailable",
            )

        try:
            view = self._runtime.background_tasks.update_task(
                params.task_id,
                description=params.description,
                progress=params.progress,
                status_note=params.status_note,
            )
        except Exception as exc:
            return ToolError(
                message=f"Failed to update task: {exc}",
                brief="Update failed",
            )

        return ToolReturnValue(
            is_error=False,
            output=format_task(view, include_command=True),
            message=f"Updated task {view.spec.id}.",
            display=[
                BackgroundTaskDisplayBlock(
                    task_id=view.spec.id,
                    kind=view.spec.kind,
                    status=view.runtime.status,
                    description=view.spec.description,
                )
            ],
        )
