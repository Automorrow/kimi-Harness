"""Harness Team Tools - multi-agent team coordination."""

from __future__ import annotations

from pathlib import Path
from typing import Any, override

from kosong.tooling import CallableTool2, ToolError, ToolOk, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.tools.utils import load_desc


# ---------------------------------------------------------------------------
# CreateTeam
# ---------------------------------------------------------------------------

class CreateTeamParams(BaseModel):
    name: str = Field(description="The name of the team to create.")


class CreateTeam(CallableTool2[CreateTeamParams]):
    name: str = "CreateTeam"
    description: str = load_desc(Path(__file__).parent / "create.md", {})
    params: type[CreateTeamParams] = CreateTeamParams

    @override
    async def __call__(self, params: CreateTeamParams) -> ToolReturnValue:
        from kimi_cli.harness._state import get_harness_runtime

        runtime = get_harness_runtime()
        if runtime is None or runtime.team_coordinator is None:
            return ToolError(
                message="Team coordinator not initialized. Use 'harness' magic word first.",
                brief="Team coordinator not initialized",
            )

        try:
            team = runtime.team_coordinator.create_team(name=params.name)
            return ToolOk(
                output=(
                    f"Team '{team.name}' created.\n"
                    f"Use AddTeamMember to add agents to this team."
                ),
                message="Team created",
            )
        except ValueError as e:
            return ToolError(message=str(e), brief="Team exists")
        except Exception as e:
            return ToolError(
                message=f"Failed to create team: {e}",
                brief="Create failed",
            )


# ---------------------------------------------------------------------------
# AddTeamMember
# ---------------------------------------------------------------------------

class AddTeamMemberParams(BaseModel):
    team_name: str = Field(description="The name of the team to add the member to.")
    agent_type: str = Field(
        description=(
            "The subagent type for this member "
            "(e.g. 'explore', 'code', 'test')."
        ),
    )
    role: str = Field(
        default="worker",
        description=(
            "The role of the member in the team. "
            "One of: 'leader', 'worker', 'reviewer', 'explorer'."
        ),
    )


class AddTeamMember(CallableTool2[AddTeamMemberParams]):
    name: str = "AddTeamMember"
    description: str = load_desc(Path(__file__).parent / "add_member.md", {})
    params: type[AddTeamMemberParams] = AddTeamMemberParams

    @override
    async def __call__(self, params: AddTeamMemberParams) -> ToolReturnValue:
        from kimi_cli.harness._state import get_harness_runtime
        from kimi_cli.harness.coordinator.team import AgentRole, TeamMember

        runtime = get_harness_runtime()
        if runtime is None or runtime.team_coordinator is None:
            return ToolError(
                message="Team coordinator not initialized. Use 'harness' magic word first.",
                brief="Team coordinator not initialized",
            )

        try:
            role = AgentRole(params.role.lower())
        except ValueError:
            return ToolError(
                message=(
                    f"Invalid role '{params.role}'. "
                    f"Must be one of: leader, worker, reviewer, explorer."
                ),
                brief="Invalid role",
            )

        member = TeamMember(
            agent_id=f"{params.agent_type}-{id(params)}",
            agent_type=params.agent_type,
            role=role,
        )

        added = runtime.team_coordinator.add_member(
            team_name=params.team_name,
            member=member,
        )
        if not added:
            return ToolError(
                message=f"Team '{params.team_name}' not found.",
                brief="Team not found",
            )

        return ToolOk(
            output=(
                f"Member '{member.agent_id}' (role={role.value}) "
                f"added to team '{params.team_name}'."
            ),
            message="Member added",
        )


# ---------------------------------------------------------------------------
# DispatchTask
# ---------------------------------------------------------------------------

class DispatchTaskParams(BaseModel):
    team_name: str = Field(description="The name of the team to dispatch the task to.")
    task: str = Field(description="The task description to dispatch.")
    strategy: str = Field(
        default="leader",
        description=(
            "Dispatch strategy. One of: 'leader' (send to leader only), "
            "'broadcast' (send to all members), "
            "'round_robin' (send to next available worker)."
        ),
    )


class DispatchTask(CallableTool2[DispatchTaskParams]):
    name: str = "DispatchTask"
    description: str = load_desc(Path(__file__).parent / "dispatch.md", {})
    params: type[DispatchTaskParams] = DispatchTaskParams

    @override
    async def __call__(self, params: DispatchTaskParams) -> ToolReturnValue:
        from kimi_cli.harness._state import get_harness_runtime

        runtime = get_harness_runtime()
        if runtime is None or runtime.team_coordinator is None:
            return ToolError(
                message="Team coordinator not initialized. Use 'harness' magic word first.",
                brief="Team coordinator not initialized",
            )

        valid_strategies = ("leader", "broadcast", "round_robin")
        if params.strategy not in valid_strategies:
            return ToolError(
                message=f"Invalid strategy '{params.strategy}'. Must be one of: {', '.join(valid_strategies)}.",
                brief="Invalid strategy",
            )

        results = runtime.team_coordinator.dispatch(
            team_name=params.team_name,
            task=params.task,
            strategy=params.strategy,  # type: ignore[arg-type]
        )

        if not results:
            return ToolError(
                message=f"No team '{params.team_name}' found or no eligible members.",
                brief="Dispatch failed",
            )

        lines = [f"Dispatched task to {len(results)} member(s):\n"]
        for r in results:
            lines.append(f"- [{r.agent_id}] {r.output}")

        return ToolOk(
            output="\n".join(lines),
            message=f"Dispatched to {len(results)} member(s)",
        )


# ---------------------------------------------------------------------------
# OrchestrateTask
# ---------------------------------------------------------------------------

class OrchestrateTaskParams(BaseModel):
    team_name: str = Field(description="The name of the team to orchestrate the task with.")
    task: str = Field(description="The task description to orchestrate across phases.")


class OrchestrateTask(CallableTool2[OrchestrateTaskParams]):
    name: str = "OrchestrateTask"
    description: str = load_desc(Path(__file__).parent / "orchestrate.md", {})
    params: type[OrchestrateTaskParams] = OrchestrateTaskParams

    @override
    async def __call__(self, params: OrchestrateTaskParams) -> ToolReturnValue:
        from kimi_cli.harness._state import get_harness_runtime

        runtime = get_harness_runtime()
        if runtime is None or runtime.team_coordinator is None:
            return ToolError(
                message="Team coordinator not initialized. Use 'harness' magic word first.",
                brief="Team coordinator not initialized",
            )

        results = runtime.team_coordinator.orchestrate(
            team_name=params.team_name,
            task=params.task,
        )

        if not results:
            return ToolError(
                message=f"No team '{params.team_name}' found or no eligible members.",
                brief="Orchestration failed",
            )

        lines = [f"Orchestrated task across {len(results)} phase(s):\n"]
        for r in results:
            lines.append(f"- [{r.agent_id}] {r.output}")

        return ToolOk(
            output="\n".join(lines),
            message=f"Orchestrated {len(results)} phase(s)",
        )


# ---------------------------------------------------------------------------
# BroadcastMessage
# ---------------------------------------------------------------------------

class BroadcastMessageParams(BaseModel):
    team_name: str = Field(description="The name of the team to broadcast to.")
    message: str = Field(description="The message to broadcast to all team members.")


class BroadcastMessage(CallableTool2[BroadcastMessageParams]):
    name: str = "BroadcastMessage"
    description: str = load_desc(Path(__file__).parent / "broadcast.md", {})
    params: type[BroadcastMessageParams] = BroadcastMessageParams

    @override
    async def __call__(self, params: BroadcastMessageParams) -> ToolReturnValue:
        from kimi_cli.harness._state import get_harness_runtime

        runtime = get_harness_runtime()
        if runtime is None or runtime.team_coordinator is None:
            return ToolError(
                message="Team coordinator not initialized. Use 'harness' magic word first.",
                brief="Team coordinator not initialized",
            )

        team = runtime.team_coordinator.get_team(params.team_name)
        if team is None:
            return ToolError(
                message=f"Team '{params.team_name}' not found.",
                brief="Team not found",
            )

        if not team.members:
            return ToolError(
                message=f"Team '{params.team_name}' has no members.",
                brief="No members",
            )

        results = runtime.team_coordinator.dispatch(
            team_name=params.team_name,
            task=params.message,
            strategy="broadcast",
        )

        lines = [f"Broadcast to {len(results)} member(s):\n"]
        for r in results:
            lines.append(f"- [{r.agent_id}] {r.output}")

        return ToolOk(
            output="\n".join(lines),
            message=f"Broadcast to {len(results)} member(s)",
        )


# ---------------------------------------------------------------------------
# ListTeams
# ---------------------------------------------------------------------------

class ListTeamsParams(BaseModel):
    pass


class ListTeams(CallableTool2[ListTeamsParams]):
    name: str = "ListTeams"
    description: str = load_desc(Path(__file__).parent / "list.md", {})
    params: type[ListTeamsParams] = ListTeamsParams

    @override
    async def __call__(self, params: ListTeamsParams) -> ToolReturnValue:
        from kimi_cli.harness._state import get_harness_runtime

        runtime = get_harness_runtime()
        if runtime is None or runtime.team_coordinator is None:
            return ToolError(
                message="Team coordinator not initialized. Use 'harness' magic word first.",
                brief="Team coordinator not initialized",
            )

        teams = runtime.team_coordinator.list_teams()
        if not teams:
            return ToolOk(
                output="No teams have been created yet.",
                message="No teams",
            )

        lines: list[str] = []
        for team in teams:
            members_info = ", ".join(
                f"{m.agent_type}({m.role.value})" for m in team.members
            ) or "no members"
            lines.append(
                f"- **{team.name}** (created: {team.created_at}) — {members_info}"
            )

        return ToolOk(
            output="\n".join(lines),
            message=f"{len(teams)} team(s)",
        )
