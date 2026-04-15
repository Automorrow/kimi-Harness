"""Tool for sending messages to running agents."""

from __future__ import annotations

from kosong.tooling import CallableTool2, ToolError, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.soul.agent import Runtime
from kimi_cli.subagents.mailbox import create_user_message, write_to_mailbox


class SendMessageParams(BaseModel):
    """Arguments for sending a follow-up message to an agent."""

    to: str = Field(
        description="Target agent ID. Supports 'agent_id' or 'agent_id@team_name' format."
    )
    message: str = Field(description="Message to send to the agent")


class SendMessage(CallableTool2[SendMessageParams]):
    """Send a follow-up message to a running agent."""

    name: str = "SendMessage"
    description: str = "Send a follow-up message to a running agent."
    params: type[SendMessageParams] = SendMessageParams

    def __init__(self, runtime: Runtime):
        super().__init__()
        self._runtime = runtime

    async def __call__(self, params: SendMessageParams) -> ToolReturnValue:
        if self._runtime.role != "root":
            return ToolError(
                message="Only the root agent can send messages to other agents.",
                brief="SendMessage unavailable",
            )

        # Parse target agent_id (supports agent_id or agent_id@team_name)
        target = params.to.split("@")[0].strip()
        if not target:
            return ToolError(
                message="Invalid target agent ID.",
                brief="Invalid target",
            )

        # Validate that the target agent exists in the subagent store
        store = self._runtime.subagent_store
        if store is not None and not store.meta_path(target).exists():
            return ToolError(
                message=f"No agent found with ID: {target}",
                brief="Agent not found",
            )

        try:
            msg = create_user_message(
                sender="root",
                recipient=target,
                content=params.message,
            )
            await write_to_mailbox(target, msg)
        except Exception as exc:
            return ToolError(
                message=f"Failed to send message: {exc}",
                brief="Send failed",
            )

        return ToolReturnValue(
            is_error=False,
            output=f"Sent message to agent {target}.",
            message=f"Sent message to agent {target}.",
            display=[],
        )
