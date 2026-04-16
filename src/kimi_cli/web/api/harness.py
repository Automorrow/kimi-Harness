"""Harness API routes."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from kimi_cli import logger
from kimi_cli.harness.memory.manager import MemoryManager

router = APIRouter(prefix="/api/harness", tags=["harness"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class HarnessStatusResponse(BaseModel):
    """Harness 整体状态响应。"""

    harness_enabled: bool = Field(description="Harness 模块是否可用")
    capabilities: dict[str, bool] = Field(description="各子能力是否可用")
    message: str = Field(description="状态说明")


class MemoryEntryResponse(BaseModel):
    """单条记忆条目响应。"""

    name: str = Field(description="记忆条目标识")
    title: str = Field(description="记忆标题")
    content: str = Field(description="记忆内容")
    path: str = Field(description="记忆文件路径")


class MemoryListResponse(BaseModel):
    """记忆列表响应。"""

    entries: list[MemoryEntryResponse] = Field(description="记忆条目列表")
    count: int = Field(description="条目数量")


class AddMemoryRequest(BaseModel):
    """添加记忆请求。"""

    title: str = Field(description="记忆标题")
    content: str = Field(description="记忆内容（Markdown 格式）")
    tags: list[str] | None = Field(default=None, description="标签列表（可选）")


class AddMemoryResponse(BaseModel):
    """添加记忆响应。"""

    success: bool = Field(description="是否成功")
    name: str = Field(description="记忆条目标识")
    path: str = Field(description="记忆文件路径")


class DeleteMemoryResponse(BaseModel):
    """删除记忆响应。"""

    success: bool = Field(description="是否成功")
    message: str = Field(default="", description="附加说明")


class TeamInfo(BaseModel):
    """团队信息。"""

    name: str = Field(description="团队名称")
    members: list[str] = Field(default_factory=list, description="成员列表")


class TeamListResponse(BaseModel):
    """团队列表响应。"""

    teams: list[TeamInfo] = Field(description="团队列表")
    message: str = Field(default="", description="附加说明")


# ---------------------------------------------------------------------------
# 路径遍历保护
# ---------------------------------------------------------------------------

_ALLOWED_ROOTS: list[Path] | None = None


def _get_allowed_roots() -> list[Path]:
    """获取允许的根路径列表。"""
    global _ALLOWED_ROOTS
    if _ALLOWED_ROOTS is not None:
        return _ALLOWED_ROOTS

    env_dirs = os.environ.get("KIMI_WEB_ALLOWED_WORK_DIRS", "")
    if env_dirs.strip():
        _ALLOWED_ROOTS = [Path(d).resolve() for d in env_dirs.split(",") if d.strip()]
    else:
        _ALLOWED_ROOTS = [Path.cwd(), Path.home()]
    return _ALLOWED_ROOTS


def _validate_work_dir(work_dir: str) -> Path:
    """验证 work_dir 是否在允许的范围内，防止路径遍历攻击。"""
    try:
        resolved = Path(work_dir).resolve()
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid work_dir path: {exc}",
        ) from exc

    allowed_roots = _get_allowed_roots()
    for root in allowed_roots:
        try:
            resolved.relative_to(root.resolve())
            return resolved
        except ValueError:
            continue

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"work_dir '{work_dir}' is outside allowed directories",
    )


# ---------------------------------------------------------------------------
# 端点：整体状态
# ---------------------------------------------------------------------------


@router.get("/status", summary="Get Harness overall status")
async def get_harness_status() -> HarnessStatusResponse:
    """返回 Harness 整体状态。"""
    return HarnessStatusResponse(
        harness_enabled=True,
        capabilities={
            "memory": True,
            "teams": False,
        },
        message="Harness module loaded. Memory is available; teams require a live runtime session.",
    )


# ---------------------------------------------------------------------------
# 端点：记忆
# ---------------------------------------------------------------------------


@router.get("/memory", summary="List memory entries")
async def list_memory_entries(
    work_dir: str = Query(default="", description="Project working directory path"),
) -> MemoryListResponse:
    """列出项目级记忆条目。"""
    if not work_dir:
        return MemoryListResponse(entries=[], count=0)
    resolved = _validate_work_dir(work_dir)

    try:
        manager = MemoryManager(resolved)
        entries = manager.list_entries()
    except Exception as exc:
        logger.warning("Failed to list memory entries: {error}", error=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list memory entries: {exc}",
        ) from exc

    return MemoryListResponse(
        entries=[
            MemoryEntryResponse(
                name=e.name,
                title=e.title,
                content=e.content,
                path=str(e.path),
            )
            for e in entries
        ],
        count=len(entries),
    )


@router.post("/memory", summary="Add a memory entry")
async def add_memory_entry(
    request: AddMemoryRequest,
    work_dir: str = Query(default="", description="Project working directory path"),
) -> AddMemoryResponse:
    """添加一条记忆条目。"""
    if not work_dir:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="work_dir is required")
    resolved = _validate_work_dir(work_dir)

    try:
        manager = MemoryManager(resolved)
        content = request.content
        if request.tags:
            tags_line = ", ".join(request.tags)
            content = f"**Tags:** {tags_line}\n\n{content}"
        path = manager.add_entry(title=request.title, content=content)
    except Exception as exc:
        logger.warning("Failed to add memory entry: {error}", error=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add memory entry: {exc}",
        ) from exc

    return AddMemoryResponse(
        success=True,
        name=path.stem,
        path=str(path),
    )


@router.delete("/memory/{name}", summary="Delete a memory entry")
async def delete_memory_entry(
    name: str,
    work_dir: str = Query(default="", description="Project working directory path"),
) -> DeleteMemoryResponse:
    """删除一条记忆条目。"""
    if not work_dir:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="work_dir is required")
    resolved = _validate_work_dir(work_dir)

    try:
        manager = MemoryManager(resolved)
        deleted = manager.remove_entry(name)
    except Exception as exc:
        logger.warning("Failed to delete memory entry: {error}", error=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete memory entry: {exc}",
        ) from exc

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory entry '{name}' not found",
        )

    return DeleteMemoryResponse(
        success=True,
        message=f"Memory entry '{name}' deleted",
    )


@router.get("/memory/search", summary="Search memory entries")
async def search_memory_entries(
    q: str = Query(description="Search query string"),
    work_dir: str = Query(default="", description="Project working directory path"),
) -> MemoryListResponse:
    """搜索记忆条目（在标题和内容中进行子串匹配）。"""
    if not work_dir:
        return MemoryListResponse(entries=[], count=0)
    resolved = _validate_work_dir(work_dir)

    try:
        manager = MemoryManager(resolved)
        all_entries = manager.list_entries()
    except Exception as exc:
        logger.warning("Failed to search memory entries: {error}", error=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search memory entries: {exc}",
        ) from exc

    query_lower = q.lower()
    matched = [
        e for e in all_entries
        if query_lower in e.title.lower() or query_lower in e.content.lower()
    ]

    return MemoryListResponse(
        entries=[
            MemoryEntryResponse(
                name=e.name,
                title=e.title,
                content=e.content,
                path=str(e.path),
            )
            for e in matched
        ],
        count=len(matched),
    )


# ---------------------------------------------------------------------------
# 端点：团队
# ---------------------------------------------------------------------------


@router.get("/teams", summary="List teams")
async def list_teams() -> TeamListResponse:
    """列出 Agent 团队。"""
    return TeamListResponse(
        teams=[],
        message="Teams are not accessible without a live runtime session.",
    )
