"""Tool for creating background tasks."""

from __future__ import annotations

import uuid
from typing import override

from kosong.tooling import CallableTool2, ToolError, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.background import TaskView, format_task
from kimi_cli.soul.agent import Runtime
from kimi_cli.soul.toolset import get_current_tool_call_or_none
from kimi_cli.tools.display import BackgroundTaskDisplayBlock
from kimi_cli.tools.utils import ToolResultBuilder


class TaskCreateParams(BaseModel):
    type: str = Field(
        default="bash",
        description="Task type: 'bash' or 'agent'.",
    )
    description: str = Field(description="Short task description")
    command: str | None = Field(
        default=None,
        description="Shell command for bash tasks.",
    )
    prompt: str | None = Field(
        default=None,
        description="Prompt for agent tasks.",
    )
    subagent_type: str = Field(
        default="coder",
        description="Built-in agent type for agent tasks. Defaults to 'coder'.",
    )
    model: str | None = Field(
        default=None,
        description="Optional model override for agent tasks.",
    )
    timeout: int | None = Field(
        default=None,
        description="Timeout in seconds. Defaults to system config.",
        ge=30,
        le=3600,
    )


class TaskCreate(CallableTool2[TaskCreateParams]):
    name: str = "TaskCreate"
    description: str = "Create a background shell or agent task."
    params: type[TaskCreateParams] = TaskCreateParams

    def __init__(self, runtime: Runtime):
        super().__init__()
        self._runtime = runtime

    @override
    async def __call__(self, params: TaskCreateParams) -> ToolReturnValue:
        if self._runtime.role != "root":
            return ToolError(
                message="Background tasks can only be created by the root agent.",
                brief="Background task unavailable",
            )

        tool_call = get_current_tool_call_or_none()
        if tool_call is None:
            return ToolResultBuilder().error(
                "TaskCreate requires a tool call context.",
                brief="No tool call context",
            )

        if params.type == "bash":
            if not params.command:
                return ToolError(
                    message="command is required for bash tasks",
                    brief="Missing command",
                )
            env = self._runtime.environment
            try:
                view = self._runtime.background_tasks.create_bash_task(
                    command=params.command,
                    description=params.description.strip(),
                    timeout_s=params.timeout or 60,
                    tool_call_id=tool_call.id,
                    shell_name=env.shell_name,
                    shell_path=str(env.shell_path),
                    cwd=str(self._runtime.session.work_dir),
                )
            except Exception as exc:
                return ToolResultBuilder().error(
                    f"Failed to create bash task: {exc}",
                    brief="Create failed",
                )
        elif params.type == "agent":
            if not params.prompt:
                return ToolError(
                    message="prompt is required for agent tasks",
                    brief="Missing prompt",
                )
            agent_id = uuid.uuid4().hex
            try:
                view = self._runtime.background_tasks.create_agent_task(
                    agent_id=agent_id,
                    subagent_type=params.subagent_type or "coder",
                    prompt=params.prompt,
                    description=params.description.strip(),
                    tool_call_id=tool_call.id,
                    model_override=params.model,
                    timeout_s=params.timeout,
                )
            except Exception as exc:
                return ToolResultBuilder().error(
                    f"Failed to create agent task: {exc}",
                    brief="Create failed",
                )
        else:
            return ToolError(
                message=f"unsupported task type: {params.type}",
                brief="Invalid task type",
            )

        return ToolReturnValue(
            is_error=False,
            output=format_task(view, include_command=True),
            message=f"Created task {view.spec.id} ({view.spec.kind}).",
            display=[
                BackgroundTaskDisplayBlock(
                    task_id=view.spec.id,
                    kind=view.spec.kind,
                    status=view.runtime.status,
                    description=view.spec.description,
                )
            ],
        )
