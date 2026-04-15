"""Tool for retrieving background task details."""

from __future__ import annotations

from typing import override

from kosong.tooling import CallableTool2, ToolError, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.background import format_task
from kimi_cli.soul.agent import Runtime
from kimi_cli.tools.display import BackgroundTaskDisplayBlock


class TaskGetParams(BaseModel):
    task_id: str = Field(description="The background task ID to retrieve.")


class TaskGet(CallableTool2[TaskGetParams]):
    name: str = "TaskGet"
    description: str = "Get details for a background task."
    params: type[TaskGetParams] = TaskGetParams

    def __init__(self, runtime: Runtime):
        super().__init__()
        self._runtime = runtime

    @override
    async def __call__(self, params: TaskGetParams) -> ToolReturnValue:
        if self._runtime.role != "root":
            return ToolError(
                message="Background tasks can only be managed by the root agent.",
                brief="Background task unavailable",
            )

        view = self._runtime.background_tasks.get_task(params.task_id)
        if view is None:
            return ToolError(
                message=f"Task not found: {params.task_id}",
                brief="Task not found",
            )

        return ToolReturnValue(
            is_error=False,
            output=format_task(view, include_command=True),
            message=f"Retrieved task {view.spec.id}.",
            display=[
                BackgroundTaskDisplayBlock(
                    task_id=view.spec.id,
                    kind=view.spec.kind,
                    status=view.runtime.status,
                    description=view.spec.description,
                )
            ],
        )
