"""Harness 多 Agent 协调器 - 团队管理与任务分发.

在 kimi-cli 现有 LaborMarket + SubagentStore 基础上，
增加团队级协调能力，支持多 Agent 协作完成任务。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


class AgentRole(str, Enum):
    """Agent 在团队中的角色。"""

    LEADER = "leader"
    WORKER = "worker"
    REVIEWER = "reviewer"
    EXPLORER = "explorer"


@dataclass
class TeamMember:
    """团队成员定义。

    Attributes:
        agent_id: Agent 实例 ID。
        agent_type: Agent 类型（如 general-purpose、explore）。
        role: 在团队中的角色。
        capabilities: 能力描述列表。
    """

    agent_id: str
    agent_type: str
    role: AgentRole = AgentRole.WORKER
    capabilities: list[str] = field(default_factory=list)


@dataclass
class Team:
    """Agent 团队。

    Attributes:
        name: 团队名称。
        members: 团队成员列表。
        created_at: 创建时间。
    """

    name: str
    members: list[TeamMember] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def add_member(self, member: TeamMember) -> None:
        """添加团队成员。"""
        self.members.append(member)

    def get_leader(self) -> TeamMember | None:
        """获取团队领导者。"""
        for m in self.members:
            if m.role == AgentRole.LEADER:
                return m
        return None

    def get_workers(self) -> list[TeamMember]:
        """获取所有工作者。"""
        return [m for m in self.members if m.role == AgentRole.WORKER]


@dataclass
class TaskResult:
    """Agent 任务执行结果。

    Attributes:
        agent_id: 执行任务的 Agent ID。
        task_id: 任务 ID。
        output: 任务输出。
        is_error: 是否出错。
        duration_ms: 执行耗时（毫秒）。
    """

    agent_id: str
    task_id: str
    output: str
    is_error: bool = False
    duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# TeamCoordinator
# ---------------------------------------------------------------------------


class TeamCoordinator:
    """多 Agent 团队协调器.

    管理 Agent 团队的创建、任务分发和结果收集。
    与 kimi-cli 现有的 LaborMarket（类型注册）和
    SubagentStore（实例管理）互补，增加团队级抽象。

    Usage::

        coordinator = TeamCoordinator()
        team = coordinator.create_team("refactor-team", members=[...])
        results = await coordinator.dispatch(team, "重构认证模块")
    """

    def __init__(self) -> None:
        self._teams: dict[str, Team] = {}
        self._round_robin_indices: dict[str, int] = {}

    def create_team(
        self,
        name: str,
        members: list[TeamMember] | None = None,
    ) -> Team:
        """创建一个 Agent 团队。

        Args:
            name: 团队名称。
            members: 初始成员列表。

        Returns:
            创建的 Team 实例。
        """
        team = Team(name=name, members=members or [])
        self._teams[name] = team
        logger.info("Team created: {name} with {count} members", name=name, count=len(team.members))
        return team

    def get_team(self, name: str) -> Team | None:
        """获取团队。"""
        return self._teams.get(name)

    def list_teams(self) -> list[Team]:
        """列出所有团队。"""
        return list(self._teams.values())

    def remove_team(self, name: str) -> bool:
        """移除团队。"""
        return self._teams.pop(name, None) is not None

    async def dispatch(
        self,
        team_name: str,
        task: str,
        *,
        strategy: Literal["leader", "broadcast", "round_robin"] = "leader",
    ) -> list[TaskResult]:
        """向团队分发任务。

        Args:
            team_name: 团队名称。
            task: 任务描述。
            strategy: 分发策略。
                - ``leader``: 仅发送给团队领导者。
                - ``broadcast``: 发送给所有成员。
                - ``round_robin``: 轮流发送给工作者。

        Returns:
            所有 Agent 的执行结果列表。
        """
        team = self._teams.get(team_name)
        if team is None:
            logger.error("Team not found: {name}", name=team_name)
            return []

        targets = self._select_targets(team, strategy)
        if not targets:
            logger.warning("No targets selected for task dispatch")
            return []

        results: list[TaskResult] = []
        task_id = str(uuid.uuid4())[:8]

        async def _execute_single(member: TeamMember) -> TaskResult:
            t0 = time.monotonic()
            try:
                # 实际执行需要与 Runtime 集成
                # 这里提供框架，具体执行逻辑由 Runtime 注入
                output = f"[Task {task_id}] Dispatched to {member.agent_type} ({member.agent_id}): {task}"
                return TaskResult(
                    agent_id=member.agent_id,
                    task_id=task_id,
                    output=output,
                    is_error=False,
                    duration_ms=(time.monotonic() - t0) * 1000,
                )
            except Exception as e:
                return TaskResult(
                    agent_id=member.agent_id,
                    task_id=task_id,
                    output=str(e),
                    is_error=True,
                    duration_ms=(time.monotonic() - t0) * 1000,
                )

        # broadcast 策略并行执行，其他策略串行
        if strategy == "broadcast" and len(targets) > 1:
            results = list(await asyncio.gather(*[_execute_single(m) for m in targets]))
        else:
            for member in targets:
                results.append(await _execute_single(member))

        return results

    async def broadcast(
        self,
        team_name: str,
        message: str,
    ) -> None:
        """向团队所有成员广播消息。

        Args:
            team_name: 团队名称。
            message: 广播消息。
        """
        team = self._teams.get(team_name)
        if team is None:
            logger.error("Team not found: {name}", name=team_name)
            return

        for member in team.members:
            logger.info(
                "Broadcast to {agent_type} ({agent_id}): {message}",
                agent_type=member.agent_type,
                agent_id=member.agent_id,
                message=message[:100],
            )

    def _select_targets(
        self,
        team: Team,
        strategy: Literal["leader", "broadcast", "round_robin"],
    ) -> list[TeamMember]:
        """根据策略选择任务目标。"""
        workers = team.get_workers() or team.members
        match strategy:
            case "leader":
                leader = team.get_leader()
                return [leader] if leader else team.members[:1]
            case "broadcast":
                return team.members
            case "round_robin":
                if not workers:
                    return team.members
                idx = self._round_robin_indices.get(team.name, 0)
                member = workers[idx % len(workers)]
                self._round_robin_indices[team.name] = idx + 1
                return [member]
            case _:
                return team.members
