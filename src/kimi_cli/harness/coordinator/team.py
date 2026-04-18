"""多 Agent 团队协调器"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from loguru import logger


class AgentRole(str, Enum):
    LEADER = "leader"
    WORKER = "worker"
    REVIEWER = "reviewer"
    EXPLORER = "explorer"


@dataclass
class TeamMember:
    agent_id: str
    agent_type: str
    role: AgentRole = AgentRole.WORKER
    capabilities: list[str] = field(default_factory=list)


@dataclass
class Team:
    name: str
    members: list[TeamMember] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class TaskResult:
    agent_id: str
    task_id: str
    output: str
    is_error: bool = False
    duration_ms: int = 0


@dataclass
class OrchestrationPhase:
    name: str
    role: AgentRole
    prompt_template: str


class TeamCoordinator:
    """多 Agent 团队协调器"""

    def __init__(self, work_dir: Path | str):
        self.work_dir = Path(work_dir)
        self._teams_dir = self.work_dir / ".kimi" / "teams"
        self._teams_dir.mkdir(parents=True, exist_ok=True)
        self._teams: dict[str, Team] = {}
        self._load_teams()

    def _load_teams(self) -> None:
        """从磁盘加载团队"""
        for f in self._teams_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                members = [
                    TeamMember(**m) for m in data.get("members", [])
                ]
                self._teams[data["name"]] = Team(
                    name=data["name"],
                    members=members,
                    created_at=data.get("created_at", ""),
                )
            except Exception as e:
                logger.warning(f"Failed to load team {f}: {e}")

    def _save_team(self, team: Team) -> None:
        """保存团队到磁盘"""
        data = {
            "name": team.name,
            "members": [
                {"agent_id": m.agent_id, "agent_type": m.agent_type,
                 "role": m.role.value, "capabilities": m.capabilities}
                for m in team.members
            ],
            "created_at": team.created_at,
        }
        path = self._teams_dir / f"{team.name}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def create_team(self, name: str) -> Team:
        """创建团队"""
        if name in self._teams:
            raise ValueError(f"Team '{name}' already exists")
        team = Team(name=name)
        self._teams[name] = team
        self._save_team(team)
        logger.info(f"Team created: {name}")
        return team

    def get_team(self, name: str) -> Team | None:
        """获取团队"""
        return self._teams.get(name)

    def list_teams(self) -> list[Team]:
        """列出所有团队"""
        return list(self._teams.values())

    def remove_team(self, name: str) -> bool:
        """删除团队"""
        if name not in self._teams:
            return False
        del self._teams[name]
        path = self._teams_dir / f"{name}.json"
        if path.exists():
            path.unlink()
        logger.info(f"Team removed: {name}")
        return True

    def add_member(self, team_name: str, member: TeamMember) -> bool:
        """向团队添加成员"""
        team = self.get_team(team_name)
        if not team:
            return False
        team.members.append(member)
        self._save_team(team)
        logger.info(f"Member {member.agent_id} added to team {team_name}")
        return True

    def get_members_by_role(self, team_name: str, role: AgentRole) -> list[TeamMember]:
        """获取指定角色的成员"""
        team = self.get_team(team_name)
        if not team:
            return []
        return [m for m in team.members if m.role == role]

    def dispatch(
        self,
        team_name: str,
        task: str,
        strategy: Literal["leader", "broadcast", "round_robin"] = "leader",
    ) -> list[TaskResult]:
        """分发任务给团队成员

        注意：完整实现需要访问 SubagentRunner。
        这里返回 TaskResult 列表，实际调度由工具层完成。
        """
        team = self.get_team(team_name)
        if not team:
            return []

        results = []
        if strategy == "leader":
            leaders = self.get_members_by_role(team_name, AgentRole.LEADER)
            if leaders:
                results.append(TaskResult(
                    agent_id=leaders[0].agent_id,
                    task_id=f"task-{int(time.time())}",
                    output=f"[Dispatch to leader {leaders[0].agent_id}]: {task}",
                ))
        elif strategy == "broadcast":
            for member in team.members:
                results.append(TaskResult(
                    agent_id=member.agent_id,
                    task_id=f"task-{int(time.time())}-{member.agent_id}",
                    output=f"[Broadcast to {member.agent_id}]: {task}",
                ))
        elif strategy == "round_robin":
            workers = self.get_members_by_role(team_name, AgentRole.WORKER)
            if workers:
                results.append(TaskResult(
                    agent_id=workers[0].agent_id,
                    task_id=f"task-{int(time.time())}",
                    output=f"[Round-robin to {workers[0].agent_id}]: {task}",
                ))

        return results

    def orchestrate(
        self,
        team_name: str,
        task: str,
        phases: list[OrchestrationPhase] | None = None,
    ) -> list[TaskResult]:
        """多阶段编排

        默认四阶段：research -> plan -> implement -> review
        """
        if phases is None:
            phases = [
                OrchestrationPhase("research", AgentRole.EXPLORER, "Research: {task}"),
                OrchestrationPhase("plan", AgentRole.LEADER, "Based on research, create implementation plan for: {task}"),
                OrchestrationPhase("implement", AgentRole.WORKER, "Implement according to plan: {task}"),
                OrchestrationPhase("review", AgentRole.REVIEWER, "Review the implementation: {task}"),
            ]

        results = []
        context = task
        for phase in phases:
            prompt = phase.prompt_template.format(task=context)
            members = self.get_members_by_role(team_name, phase.role)
            if not members:
                # 回退到任何可用成员
                team = self.get_team(team_name)
                members = team.members if team else []

            for member in members:
                result = TaskResult(
                    agent_id=member.agent_id,
                    task_id=f"orch-{phase.name}-{int(time.time())}",
                    output=f"[{phase.name}] {member.agent_id}: {prompt}",
                )
                results.append(result)
                context = prompt  # 将输出传递到下一阶段

        return results
