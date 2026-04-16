"""Unit tests for kimi_cli.harness.coordinator.team - TeamCoordinator, Team, TeamMember."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kimi_cli.harness.coordinator.team import (
    AgentRole,
    Team,
    TeamCoordinator,
    TeamMember,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_member(
    agent_id: str = "agent-1",
    agent_type: str = "general-purpose",
    role: AgentRole = AgentRole.WORKER,
) -> TeamMember:
    return TeamMember(
        agent_id=agent_id,
        agent_type=agent_type,
        role=role,
        capabilities=["coding"],
    )


def _make_coordinator(runtime=None) -> TeamCoordinator:
    return TeamCoordinator(runtime=runtime)


# ---------------------------------------------------------------------------
# TestTeamCRUD
# ---------------------------------------------------------------------------


class TestTeamCRUD:

    def test_create_team(self) -> None:
        """创建团队后可以通过 get 获取。"""
        coord = _make_coordinator()
        team = coord.create_team("dev-team", members=[_make_member("a1")])
        assert team.name == "dev-team"
        assert len(team.members) == 1
        assert coord.get_team("dev-team") is team

    def test_create_duplicate_team_overwrites(self) -> None:
        """创建同名团队会覆盖旧团队。"""
        coord = _make_coordinator()
        team_a = coord.create_team("alpha", members=[_make_member("a1")])
        team_b = coord.create_team("alpha", members=[_make_member("b1"), _make_member("b2")])
        assert coord.get_team("alpha") is team_b
        assert len(coord.get_team("alpha").members) == 2

    def test_get_nonexistent_team_returns_none(self) -> None:
        """获取不存在的团队返回 None。"""
        coord = _make_coordinator()
        assert coord.get_team("ghost") is None

    def test_list_teams(self) -> None:
        """list_teams 返回所有已创建的团队。"""
        coord = _make_coordinator()
        coord.create_team("team-a")
        coord.create_team("team-b")
        coord.create_team("team-c")
        teams = coord.list_teams()
        names = {t.name for t in teams}
        assert names == {"team-a", "team-b", "team-c"}

    def test_list_teams_empty(self) -> None:
        """无团队时 list_teams 返回空列表。"""
        coord = _make_coordinator()
        assert coord.list_teams() == []

    def test_remove_team(self) -> None:
        """删除存在的团队返回 True。"""
        coord = _make_coordinator()
        coord.create_team("to-remove")
        assert coord.remove_team("to-remove") is True
        assert coord.get_team("to-remove") is None

    def test_remove_nonexistent_team(self) -> None:
        """删除不存在的团队返回 False。"""
        coord = _make_coordinator()
        assert coord.remove_team("nonexistent") is False


# ---------------------------------------------------------------------------
# TestTeamMembers
# ---------------------------------------------------------------------------


class TestTeamMembers:

    def test_add_member(self) -> None:
        """添加成员到团队。"""
        team = Team(name="test")
        m = _make_member("a1")
        team.add_member(m)
        assert len(team.members) == 1
        assert team.members[0].agent_id == "a1"

    def test_add_duplicate_member(self) -> None:
        """添加重复成员不会去重（直接追加）。"""
        team = Team(name="test")
        m = _make_member("a1")
        team.add_member(m)
        team.add_member(m)
        assert len(team.members) == 2

    def test_remove_member(self) -> None:
        """从团队移除成员。"""
        team = Team(name="test")
        m1 = _make_member("a1")
        m2 = _make_member("a2")
        team.add_member(m1)
        team.add_member(m2)
        team.members.remove(m1)
        assert len(team.members) == 1
        assert team.members[0].agent_id == "a2"

    def test_remove_nonexistent_member(self) -> None:
        """移除不存在的成员抛 ValueError。"""
        team = Team(name="test")
        m = _make_member("a1")
        try:
            team.members.remove(m)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_get_leader(self) -> None:
        """获取团队 leader。"""
        team = Team(name="test")
        leader = _make_member("l1", role=AgentRole.LEADER)
        team.add_member(leader)
        team.add_member(_make_member("w1"))
        assert team.get_leader() is leader

    def test_get_leader_none(self) -> None:
        """无 leader 时返回 None。"""
        team = Team(name="test")
        team.add_member(_make_member("w1"))
        assert team.get_leader() is None

    def test_get_workers(self) -> None:
        """获取所有 worker 成员。"""
        team = Team(name="test")
        team.add_member(_make_member("l1", role=AgentRole.LEADER))
        team.add_member(_make_member("w1", role=AgentRole.WORKER))
        team.add_member(_make_member("w2", role=AgentRole.WORKER))
        workers = team.get_workers()
        assert len(workers) == 2
        assert all(w.role == AgentRole.WORKER for w in workers)


# ---------------------------------------------------------------------------
# TestDispatchStrategies
# ---------------------------------------------------------------------------


class TestDispatchStrategies:

    def test_leader_strategy_targets_leader(self) -> None:
        """leader 策略：任务分发给 leader。"""
        coord = _make_coordinator()
        leader = _make_member("l1", role=AgentRole.LEADER)
        coord.create_team("t", members=[leader, _make_member("w1")])

        targets = coord._select_targets(coord.get_team("t"), "leader")
        assert len(targets) == 1
        assert targets[0].agent_id == "l1"
        assert targets[0].role == AgentRole.LEADER

    def test_leader_strategy_no_leader_falls_back(self) -> None:
        """leader 策略无 leader 时回退到第一个成员。"""
        coord = _make_coordinator()
        coord.create_team("t", members=[_make_member("w1"), _make_member("w2")])

        targets = coord._select_targets(coord.get_team("t"), "leader")
        assert len(targets) == 1
        assert targets[0].agent_id == "w1"

    def test_broadcast_strategy_targets_all(self) -> None:
        """broadcast 策略：任务广播给所有成员。"""
        coord = _make_coordinator()
        coord.create_team("t", members=[
            _make_member("a1"),
            _make_member("a2"),
            _make_member("a3"),
        ])

        targets = coord._select_targets(coord.get_team("t"), "broadcast")
        assert len(targets) == 3

    def test_round_robin_strategy_rotates(self) -> None:
        """round_robin 策略：轮流分发。"""
        coord = _make_coordinator()
        coord.create_team("t", members=[
            _make_member("w1", role=AgentRole.WORKER),
            _make_member("w2", role=AgentRole.WORKER),
            _make_member("w3", role=AgentRole.WORKER),
        ])
        team = coord.get_team("t")

        # 第一轮
        t1 = coord._select_targets(team, "round_robin")
        assert t1[0].agent_id == "w1"

        # 第二轮
        t2 = coord._select_targets(team, "round_robin")
        assert t2[0].agent_id == "w2"

        # 第三轮
        t3 = coord._select_targets(team, "round_robin")
        assert t3[0].agent_id == "w3"

        # 第四轮回绕
        t4 = coord._select_targets(team, "round_robin")
        assert t4[0].agent_id == "w1"

    def test_round_robin_no_workers_falls_back(self) -> None:
        """round_robin 策略无 worker 时回退到所有成员。"""
        coord = _make_coordinator()
        coord.create_team("t", members=[_make_member("l1", role=AgentRole.LEADER)])
        team = coord.get_team("t")

        targets = coord._select_targets(team, "round_robin")
        assert len(targets) == 1
        assert targets[0].agent_id == "l1"


# ---------------------------------------------------------------------------
# TestBroadcast
# ---------------------------------------------------------------------------


class TestBroadcast:

    @pytest.mark.asyncio
    async def test_broadcast_to_all_members(self) -> None:
        """broadcast 向所有成员发送消息（验证不崩溃）。"""
        coord = _make_coordinator()
        coord.create_team("t", members=[
            _make_member("a1"),
            _make_member("a2"),
        ])
        # broadcast 只是记录日志，不抛异常即为通过
        await coord.broadcast("t", "Hello everyone")

    @pytest.mark.asyncio
    async def test_broadcast_nonexistent_team(self) -> None:
        """向不存在的团队广播不崩溃。"""
        coord = _make_coordinator()
        await coord.broadcast("ghost", "Hello")  # 不崩溃即通过


# ---------------------------------------------------------------------------
# TestErrorHandling
# ---------------------------------------------------------------------------


class TestErrorHandling:

    @pytest.mark.asyncio
    async def test_dispatch_nonexistent_team(self) -> None:
        """向不存在的团队分发任务返回空列表。"""
        coord = _make_coordinator()
        results = await coord.dispatch("ghost", "do something")
        assert results == []

    @pytest.mark.asyncio
    async def test_dispatch_no_runtime(self) -> None:
        """无 Runtime 时分发返回空列表。"""
        coord = _make_coordinator(runtime=None)
        coord.create_team("t", members=[_make_member("a1")])
        results = await coord.dispatch("t", "do something")
        assert results == []

    @pytest.mark.asyncio
    async def test_dispatch_empty_team(self) -> None:
        """空团队分发不崩溃（无 leader 时回退到空切片）。"""
        coord = _make_coordinator()
        coord.create_team("empty", members=[])
        # 无 runtime 也返回空列表
        results = await coord.dispatch("empty", "do something")
        assert results == []

    @pytest.mark.asyncio
    async def test_dispatch_empty_team_with_runtime(self) -> None:
        """空团队有 Runtime 时分发不崩溃。"""
        mock_runtime = MagicMock()
        coord = _make_coordinator(runtime=mock_runtime)
        coord.create_team("empty", members=[])
        # leader 策略下无 leader 无 members，targets 为空列表
        results = await coord.dispatch("empty", "do something", strategy="leader")
        assert results == []

    def test_remove_nonexistent_team(self) -> None:
        """删除不存在的团队返回 False。"""
        coord = _make_coordinator()
        assert coord.remove_team("no-such-team") is False

    def test_get_nonexistent_team(self) -> None:
        """获取不存在的团队返回 None。"""
        coord = _make_coordinator()
        assert coord.get_team("no-such-team") is None
