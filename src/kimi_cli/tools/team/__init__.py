"""Team coordination tools for multi-agent collaboration."""

from __future__ import annotations

from typing import override

from kosong.tooling import CallableTool2, ToolError, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.harness.coordinator.team import AgentRole, TeamMember
from kimi_cli.soul.agent import Runtime


class CreateTeamParams(BaseModel):
    name: str = Field(description="Team name (unique identifier).")
    members: list[dict[str, str]] = Field(
        default_factory=list,
        description=(
            "Initial team members. Each member is a dict with "
            "'agent_id', 'agent_type', and optional 'role' (leader/worker/reviewer/explorer). "
            "Example: [{'agent_id': 'coder-1', 'agent_type': 'coder', 'role': 'worker'}]"
        ),
    )


class AddTeamMemberParams(BaseModel):
    team_name: str = Field(description="Name of the team.")
    agent_id: str = Field(description="Agent instance ID.")
    agent_type: str = Field(description="Agent type (e.g., coder, explore, plan).")
    role: str = Field(default="worker", description="Role: leader, worker, reviewer, explorer.")


class DispatchTaskParams(BaseModel):
    team_name: str = Field(description="Name of the team.")
    task: str = Field(description="Task description / prompt to send to the team.")
    strategy: str = Field(
        default="leader",
        description="Dispatch strategy: 'leader' (send to leader), 'broadcast' (send to all), 'round_robin' (rotate among workers).",
    )


class BroadcastMessageParams(BaseModel):
    team_name: str = Field(description="Name of the team.")
    message: str = Field(description="Message to broadcast to all team members.")


class ListTeamsParams(BaseModel):
    pass


class CreateTeam(CallableTool2[CreateTeamParams]):
    name: str = "CreateTeam"
    description: str = "Create a multi-agent team for collaborative tasks."
    params: type[CreateTeamParams] = CreateTeamParams

    def __init__(self, runtime: Runtime):
        super().__init__()
        self._runtime = runtime

    @override
    async def __call__(self, params: CreateTeamParams) -> ToolReturnValue:
        coordinator = self._runtime.team_coordinator
        if coordinator is None:
            return ToolError(
                message="Team coordination is not available.",
                brief="Team coordinator unavailable",
            )

        members: list[TeamMember] = []
        for m in params.members:
            role_str = m.get("role", "worker")
            try:
                role = AgentRole(role_str)
            except ValueError:
                role = AgentRole.WORKER
            members.append(
                TeamMember(
                    agent_id=m["agent_id"],
                    agent_type=m["agent_type"],
                    role=role,
                )
            )

        team = coordinator.create_team(params.name, members=members)
        return ToolReturnValue(
            is_error=False,
            output=f"Created team '{team.name}' with {len(team.members)} member(s).",
            message=f"Created team '{team.name}' with {len(team.members)} member(s).",
            display=[],
        )


class AddTeamMember(CallableTool2[AddTeamMemberParams]):
    name: str = "AddTeamMember"
    description: str = "Add a member to an existing team."
    params: type[AddTeamMemberParams] = AddTeamMemberParams

    def __init__(self, runtime: Runtime):
        super().__init__()
        self._runtime = runtime

    @override
    async def __call__(self, params: AddTeamMemberParams) -> ToolReturnValue:
        coordinator = self._runtime.team_coordinator
        if coordinator is None:
            return ToolError(
                message="Team coordination is not available.",
                brief="Team coordinator unavailable",
            )

        team = coordinator.get_team(params.team_name)
        if team is None:
            return ToolError(
                message=f"Team '{params.team_name}' not found.",
                brief="Team not found",
            )

        try:
            role = AgentRole(params.role)
        except ValueError:
            role = AgentRole.WORKER

        team.add_member(
            TeamMember(
                agent_id=params.agent_id,
                agent_type=params.agent_type,
                role=role,
            )
        )
        return ToolReturnValue(
            is_error=False,
            output=f"Added {params.agent_type} ({params.agent_id}) to team '{params.team_name}'.",
            message=f"Added {params.agent_type} ({params.agent_id}) to team '{params.team_name}'.",
            display=[],
        )


class DispatchTask(CallableTool2[DispatchTaskParams]):
    name: str = "DispatchTask"
    description: str = "Dispatch a task to a team of agents."
    params: type[DispatchTaskParams] = DispatchTaskParams

    def __init__(self, runtime: Runtime):
        super().__init__()
        self._runtime = runtime

    @override
    async def __call__(self, params: DispatchTaskParams) -> ToolReturnValue:
        coordinator = self._runtime.team_coordinator
        if coordinator is None:
            return ToolError(
                message="Team coordination is not available.",
                brief="Team coordinator unavailable",
            )

        if params.strategy not in ("leader", "broadcast", "round_robin"):
            return ToolError(
                message=f"Invalid strategy: {params.strategy}",
                brief="Invalid strategy",
            )

        results = await coordinator.dispatch(
            params.team_name,
            params.task,
            strategy=params.strategy,  # type: ignore[arg-type]
        )

        if not results:
            return ToolReturnValue(
                is_error=False,
                output="No results returned (team may be empty or not found).",
                message="No results returned.",
                display=[],
            )

        lines: list[str] = []
        for r in results:
            status = "error" if r.is_error else "ok"
            lines.append(
                f"[{status}] {r.agent_id}: {r.output[:200]}"
            )

        return ToolReturnValue(
            is_error=False,
            output="\n".join(lines),
            message=f"Dispatched task to {len(results)} agent(s).",
            display=[],
        )


class BroadcastMessage(CallableTool2[BroadcastMessageParams]):
    name: str = "BroadcastMessage"
    description: str = "Broadcast a message to all members of a team via their mailbox."
    params: type[BroadcastMessageParams] = BroadcastMessageParams

    def __init__(self, runtime: Runtime):
        super().__init__()
        self._runtime = runtime

    @override
    async def __call__(self, params: BroadcastMessageParams) -> ToolReturnValue:
        coordinator = self._runtime.team_coordinator
        if coordinator is None:
            return ToolError(
                message="Team coordination is not available.",
                brief="Team coordinator unavailable",
            )

        team = coordinator.get_team(params.team_name)
        if team is None:
            return ToolError(
                message=f"Team '{params.team_name}' not found.",
                brief="Team not found",
            )

        await coordinator.broadcast(params.team_name, params.message)
        return ToolReturnValue(
            is_error=False,
            output=f"Broadcasted message to team '{params.team_name}' ({len(team.members)} member(s)).",
            message=f"Broadcasted message to team '{params.team_name}' ({len(team.members)} member(s)).",
            display=[],
        )


class ListTeams(CallableTool2[ListTeamsParams]):
    name: str = "ListTeams"
    description: str = "List all multi-agent teams."
    params: type[ListTeamsParams] = ListTeamsParams

    def __init__(self, runtime: Runtime):
        super().__init__()
        self._runtime = runtime

    @override
    async def __call__(self, params: ListTeamsParams) -> ToolReturnValue:
        coordinator = self._runtime.team_coordinator
        if coordinator is None:
            return ToolError(
                message="Team coordination is not available.",
                brief="Team coordinator unavailable",
            )

        teams = coordinator.list_teams()
        if not teams:
            return ToolReturnValue(
                is_error=False,
                output="No teams found.",
                message="No teams found.",
                display=[],
            )

        lines: list[str] = []
        for t in teams:
            lines.append(f"- {t.name} ({len(t.members)} members)")
            for m in t.members:
                lines.append(f"  - {m.agent_id} ({m.agent_type}, {m.role.value})")

        return ToolReturnValue(
            is_error=False,
            output="\n".join(lines),
            message=f"Found {len(teams)} team(s).",
            display=[],
        )
