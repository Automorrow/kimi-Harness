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
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from kimi_cli.soul.agent import Runtime

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

    def __init__(self, runtime: Runtime | None = None) -> None:
        self._runtime = runtime
        self._teams: dict[str, Team] = {}
        self._round_robin_indices: dict[str, int] = {}

    def set_runtime(self, runtime: Runtime) -> None:
        """设置 Runtime 引用（由 Runtime.__post_init__ 回填）。"""
        self._runtime = runtime

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
        logger.info("Team created: %s with %s members", name, len(team.members))
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
            logger.error("Team not found: %s", team_name)
            return []

        if self._runtime is None:
            logger.error("Cannot dispatch: TeamCoordinator has no Runtime reference")
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
                from kosong.tooling import ToolError, ToolOk

                from kimi_cli.subagents.runner import (
                    ForegroundRunRequest,
                    ForegroundSubagentRunner,
                )

                runner = ForegroundSubagentRunner(self._runtime)  # type: ignore[arg-type]
                req = ForegroundRunRequest(
                    description=f"[Team:{team.name}] {task[:80]}",
                    prompt=task,
                    requested_type=member.agent_type,
                    model=None,
                    resume=None,
                )
                result = await runner.run(req)

                if isinstance(result, ToolOk):
                    output = result.output if isinstance(result.output, str) else str(result.output)
                    return TaskResult(
                        agent_id=member.agent_id,
                        task_id=task_id,
                        output=output,
                        is_error=False,
                        duration_ms=(time.monotonic() - t0) * 1000,
                    )
                else:
                    return TaskResult(
                        agent_id=member.agent_id,
                        task_id=task_id,
                        output=result.message if isinstance(result, ToolError) else str(result),
                        is_error=True,
                        duration_ms=(time.monotonic() - t0) * 1000,
                    )
            except Exception as e:
                logger.error(
                    "Task {task_id} failed on {agent}: {error}",
                    task_id=task_id,
                    agent=member.agent_type,
                    error=e,
                )
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
            logger.error("Team not found: %s", team_name)
            return

        for member in team.members:
            logger.info(
                "Broadcast to %s (%s): %s",
                member.agent_type,
                member.agent_id,
                message[:100],
            )

    async def orchestrate(
        self,
        team_name: str,
        task: str,
        *,
        phases: list[OrchestrationPhase] | None = None,
    ) -> list[TaskResult]:
        """Execute a multi-phase orchestration on a team.

        Each phase runs sequentially, with the results of previous phases
        injected into the next phase's prompt template.

        Args:
            team_name: Team name.
            task: Overall task description.
            phases: Custom phases. If None, uses the default four-phase
                pipeline (research → plan → implement → review).

        Returns:
            All task results from all phases.
        """
        team = self._teams.get(team_name)
        if team is None:
            logger.error("Team not found: %s", team_name)
            return []

        if self._runtime is None:
            logger.error("Cannot orchestrate: TeamCoordinator has no Runtime reference")
            return []

        phases = phases or _DEFAULT_PHASES
        all_results: list[TaskResult] = []
        previous_results_text = ""

        for phase in phases:
            logger.info(
                "Orchestration phase '%s' starting for team '%s'",
                phase.name,
                team_name,
            )

            # Build prompt from template
            prompt = phase.prompt_template.format(
                task=task,
                previous_results=previous_results_text if previous_results_text else "(none)",
            )

            # Select targets: filter by role if agent_filter is set
            if phase.agent_filter:
                filtered = [
                    m for m in team.members
                    if m.role.value == phase.agent_filter
                    or m.agent_type == phase.agent_filter
                ]
                if not filtered:
                    logger.warning(
                        "No members match filter '%s' in phase '%s', using all members",
                        phase.agent_filter,
                        phase.name,
                    )
                    filtered = team.members
                targets = filtered
            else:
                targets = team.members

            if not targets:
                logger.warning("No targets for phase '%s'", phase.name)
                continue

            # Execute using dispatch logic
            task_id = str(uuid.uuid4())[:8]
            phase_results: list[TaskResult] = []

            async def _execute_phase(member: TeamMember, p: str = prompt) -> TaskResult:
                t0 = time.monotonic()
                try:
                    from kosong.tooling import ToolError, ToolOk
                    from kimi_cli.subagents.runner import (
                        ForegroundRunRequest,
                        ForegroundSubagentRunner,
                    )

                    runner = ForegroundSubagentRunner(self._runtime)
                    req = ForegroundRunRequest(
                        description=f"[Orchestration:{team_name}:{phase.name}] {task[:60]}",
                        prompt=p,
                        requested_type=member.agent_type,
                        model=None,
                        resume=None,
                    )
                    result = await runner.run(req)

                    if isinstance(result, ToolOk):
                        output = result.output if isinstance(result.output, str) else str(result.output)
                        return TaskResult(
                            agent_id=member.agent_id,
                            task_id=task_id,
                            output=output,
                            is_error=False,
                            duration_ms=(time.monotonic() - t0) * 1000,
                        )
                    else:
                        return TaskResult(
                            agent_id=member.agent_id,
                            task_id=task_id,
                            output=result.message if isinstance(result, ToolError) else str(result),
                            is_error=True,
                            duration_ms=(time.monotonic() - t0) * 1000,
                        )
                except Exception as e:
                    logger.error(
                        "Phase '%s' failed on %s: %s",
                        phase.name,
                        member.agent_type,
                        e,
                    )
                    return TaskResult(
                        agent_id=member.agent_id,
                        task_id=task_id,
                        output=str(e),
                        is_error=True,
                        duration_ms=(time.monotonic() - t0) * 1000,
                    )

            # Parallel execution for broadcast, serial for others
            if phase.strategy == "broadcast" and len(targets) > 1:
                phase_results = list(
                    await asyncio.gather(*[_execute_phase(m) for m in targets])
                )
            else:
                for member in targets:
                    phase_results.append(await _execute_phase(member))

            all_results.extend(phase_results)

            # Format results for next phase
            parts = [f"=== Phase: {phase.name} ==="]
            for r in phase_results:
                status = "ERROR" if r.is_error else "OK"
                parts.append(f"[{status}] {r.agent_id}:\n{r.output}")
            previous_results_text = "\n\n".join(parts)

            logger.info(
                "Orchestration phase '%s' completed with %d results",
                phase.name,
                len(phase_results),
            )

        return all_results

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


# ---------------------------------------------------------------------------
# Multi-phase orchestration
# ---------------------------------------------------------------------------


@dataclass
class OrchestrationPhase:
    """A single phase in a multi-phase orchestration.

    Attributes:
        name: Phase name (e.g. "research", "plan", "implement", "review").
        prompt_template: Prompt template with ``{task}`` and ``{previous_results}`` placeholders.
        strategy: Dispatch strategy (leader/broadcast/round_robin).
        agent_filter: If set, only dispatch to members with this role.
    """

    name: str
    prompt_template: str
    strategy: str = "leader"
    agent_filter: str | None = None


# Default orchestration phases (research → plan → implement → review)
_DEFAULT_PHASES: list[OrchestrationPhase] = [
    OrchestrationPhase(
        name="research",
        prompt_template=(
            "Research the following task thoroughly. "
            "Find all relevant files, understand the codebase structure, "
            "and identify what needs to change.\n\n"
            "Task: {task}"
        ),
        strategy="broadcast",
        agent_filter="explore",
    ),
    OrchestrationPhase(
        name="plan",
        prompt_template=(
            "Based on the research findings below, create a detailed "
            "implementation plan for the task.\n\n"
            "Task: {task}\n\n"
            "Research findings:\n{previous_results}"
        ),
        strategy="leader",
    ),
    OrchestrationPhase(
        name="implement",
        prompt_template=(
            "Implement the following task based on the plan below. "
            "Write code, make changes, and run tests to verify.\n\n"
            "Task: {task}\n\n"
            "Plan:\n{previous_results}"
        ),
        strategy="broadcast",
        agent_filter="coder",
    ),
    OrchestrationPhase(
        name="review",
        prompt_template=(
            "Review the implementation below for correctness, "
            "edge cases, and potential issues. Output PASS or FAIL.\n\n"
            "Task: {task}\n\n"
            "Implementation:\n{previous_results}"
        ),
        strategy="leader",
        agent_filter="reviewer",
    ),
]
