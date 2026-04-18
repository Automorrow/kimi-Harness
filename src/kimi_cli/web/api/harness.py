"""Harness REST API"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()

_ALLOWED_WORK_DIRS: list[str] = []


def _get_work_dir(work_dir: str) -> Path:
    """验证 work_dir 在允许范围内"""
    p = Path(work_dir).resolve()
    allowed = [Path(d).resolve() for d in _ALLOWED_WORK_DIRS]
    if not any(str(p).startswith(str(a)) for a in allowed):
        raise HTTPException(status_code=403, detail="Work directory not allowed")
    return p


@router.get("/status")
async def harness_status() -> dict[str, Any]:
    """获取 Harness 整体状态"""
    return {"status": "ok", "harness": "enabled"}


@router.get("/memory")
async def list_memory(work_dir: str) -> list[dict[str, Any]]:
    """列出记忆条目"""
    from kimi_cli.harness.memory.manager import MemoryManager

    base = _get_work_dir(work_dir)
    mgr = MemoryManager(work_dir=base)
    return mgr.list_entries()


@router.post("/memory")
async def add_memory(work_dir: str, title: str, content: str, user_level: bool = False) -> dict[str, Any]:
    """添加记忆条目"""
    from kimi_cli.harness.memory.manager import MemoryManager

    base = _get_work_dir(work_dir)
    mgr = MemoryManager(work_dir=base)
    path = mgr.add_entry(title=title, content=content, user_level=user_level)
    return {"status": "ok", "path": str(path)}


@router.delete("/memory/{name}")
async def remove_memory(work_dir: str, name: str) -> dict[str, Any]:
    """删除记忆条目"""
    from kimi_cli.harness.memory.manager import MemoryManager

    base = _get_work_dir(work_dir)
    mgr = MemoryManager(work_dir=base)
    success = mgr.remove_entry(name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Memory entry '{name}' not found")
    return {"status": "ok"}


@router.get("/memory/search")
async def search_memory(work_dir: str, query: str) -> list[dict[str, Any]]:
    """搜索记忆条目"""
    from kimi_cli.harness.memory.manager import MemoryManager

    base = _get_work_dir(work_dir)
    mgr = MemoryManager(work_dir=base)
    return mgr.search_entries(query)


@router.get("/teams")
async def list_teams(work_dir: str) -> list[dict[str, Any]]:
    """列出 Agent 团队"""
    from kimi_cli.harness.coordinator.team import TeamCoordinator

    base = _get_work_dir(work_dir)
    coord = TeamCoordinator(work_dir=base)
    teams = coord.list_teams()
    return [
        {"name": t.name, "members": len(t.members), "created_at": t.created_at}
        for t in teams
    ]
