"""Tests for team coordination tools."""

from __future__ import annotations

import pytest

from kimi_cli.harness.coordinator.team import AgentRole, TeamCoordinator
from kimi_cli.tools.team import (
    AddTeamMember,
    BroadcastMessage,
    CreateTeam,
    DispatchTask,
    ListTeams,
)


@pytest.fixture
def runtime_with_team_coordinator(runtime):
    runtime.team_coordinator = TeamCoordinator(runtime)
    return runtime


@pytest.mark.asyncio
async def test_create_team(runtime_with_team_coordinator):
    tool = CreateTeam(runtime_with_team_coordinator)
    result = await tool(
        tool.params(
            name="test-team",
            members=[
                {"agent_id": "a1", "agent_type": "coder", "role": "leader"},
                {"agent_id": "a2", "agent_type": "explore", "role": "worker"},
            ],
        )
    )
    assert not result.is_error
    assert "Created team 'test-team' with 2 member(s)" in result.output

    team = runtime_with_team_coordinator.team_coordinator.get_team("test-team")
    assert team is not None
    assert len(team.members) == 2
    assert team.members[0].role == AgentRole.LEADER


@pytest.mark.asyncio
async def test_create_team_invalid_role_fallback(runtime_with_team_coordinator):
    tool = CreateTeam(runtime_with_team_coordinator)
    result = await tool(
        tool.params(
            name="team-bad-role",
            members=[
                {"agent_id": "a1", "agent_type": "coder", "role": "unknown"},
            ],
        )
    )
    assert not result.is_error
    team = runtime_with_team_coordinator.team_coordinator.get_team("team-bad-role")
    assert team.members[0].role == AgentRole.WORKER


@pytest.mark.asyncio
async def test_add_team_member(runtime_with_team_coordinator):
    coord = runtime_with_team_coordinator.team_coordinator
    coord.create_team("dev-team")

    tool = AddTeamMember(runtime_with_team_coordinator)
    result = await tool(
        tool.params(
            team_name="dev-team",
            agent_id="w1",
            agent_type="coder",
            role="worker",
        )
    )
    assert not result.is_error
    assert "Added coder (w1) to team 'dev-team'" in result.output

    team = coord.get_team("dev-team")
    assert len(team.members) == 1


@pytest.mark.asyncio
async def test_add_team_member_missing_team(runtime_with_team_coordinator):
    tool = AddTeamMember(runtime_with_team_coordinator)
    result = await tool(
        tool.params(
            team_name="missing",
            agent_id="w1",
            agent_type="coder",
        )
    )
    assert result.is_error
    assert "not found" in result.message


@pytest.mark.asyncio
async def test_list_teams_empty(runtime_with_team_coordinator):
    tool = ListTeams(runtime_with_team_coordinator)
    result = await tool(tool.params())
    assert not result.is_error
    assert "No teams found" in result.output


@pytest.mark.asyncio
async def test_list_teams_with_entries(runtime_with_team_coordinator):
    coord = runtime_with_team_coordinator.team_coordinator
    team = coord.create_team("ops-team")
    team.add_member(
        __import__(
            "kimi_cli.harness.coordinator.team", fromlist=["TeamMember"]
        ).TeamMember(agent_id="x1", agent_type="plan", role=AgentRole.LEADER)
    )

    tool = ListTeams(runtime_with_team_coordinator)
    result = await tool(tool.params())
    assert not result.is_error
    assert "ops-team" in result.output
    assert "x1" in result.output


@pytest.mark.asyncio
async def test_dispatch_task_missing_team(runtime_with_team_coordinator):
    tool = DispatchTask(runtime_with_team_coordinator)
    result = await tool(
        tool.params(team_name="missing", task="do something", strategy="leader")
    )
    assert not result.is_error
    assert "No results returned" in result.output


@pytest.mark.asyncio
async def test_dispatch_task_invalid_strategy(runtime_with_team_coordinator):
    tool = DispatchTask(runtime_with_team_coordinator)
    result = await tool(
        tool.params(team_name="any", task="do something", strategy="invalid")
    )
    assert result.is_error
    assert "Invalid strategy" in result.message


@pytest.mark.asyncio
async def test_broadcast_message(runtime_with_team_coordinator):
    coord = runtime_with_team_coordinator.team_coordinator
    coord.create_team("msg-team")
    coord.get_team("msg-team").add_member(
        __import__(
            "kimi_cli.harness.coordinator.team", fromlist=["TeamMember"]
        ).TeamMember(agent_id="m1", agent_type="coder", role=AgentRole.WORKER)
    )

    tool = BroadcastMessage(runtime_with_team_coordinator)
    result = await tool(
        tool.params(team_name="msg-team", message="Hello team!")
    )
    assert not result.is_error
    assert "Broadcasted message to team 'msg-team'" in result.output


@pytest.mark.asyncio
async def test_broadcast_message_missing_team(runtime_with_team_coordinator):
    tool = BroadcastMessage(runtime_with_team_coordinator)
    result = await tool(
        tool.params(team_name="missing", message="Hello!")
    )
    assert result.is_error
    assert "not found" in result.message


def test_team_tools_require_coordinator(runtime):
    """When coordinator is None, tools should return an error."""
    runtime.team_coordinator = None
    for ToolCls in (CreateTeam, AddTeamMember, ListTeams, DispatchTask, BroadcastMessage):
        tool = ToolCls(runtime)
        assert "unavailable" in tool.description or tool.description != ""
