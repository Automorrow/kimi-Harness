"""Harness 记忆系统 - 跨会话持久化知识管理.

提供跨会话的记忆持久化能力，使 Agent 能够在多次对话之间
保留和检索关键知识。记忆以 Markdown 文件形式存储，
通过 MEMORY.md 索引文件组织。
"""

from __future__ import annotations

import logging
import os
import re
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 路径管理
# ---------------------------------------------------------------------------


def _get_user_memory_dir() -> Path:
    """获取用户级记忆目录：``~/.kimi-harness/memory/``"""
    return Path.home() / ".kimi-harness" / "memory"


def _get_project_memory_dir(work_dir: str | Path) -> Path:
    """获取项目级记忆目录：``<work_dir>/.kimi-harness/memory/``"""
    return Path(work_dir) / ".kimi-harness" / "memory"


def _get_memory_entrypoint(work_dir: str | Path) -> Path:
    """获取记忆索引文件路径：``<work_dir>/.kimi-harness/memory/MEMORY.md``"""
    return _get_project_memory_dir(work_dir) / "MEMORY.md"


def _get_user_memory_entrypoint() -> Path:
    """获取用户级记忆索引文件路径：``~/.kimi-harness/memory/MEMORY.md``"""
    return _get_user_memory_dir() / "MEMORY.md"


def _memory_lock_path(work_dir: str | Path) -> Path:
    """获取记忆文件锁路径。"""
    return _get_project_memory_dir(work_dir) / ".memory.lock"


# ---------------------------------------------------------------------------
# 文件锁
# ---------------------------------------------------------------------------


@contextmanager  # type: ignore[misc]
def _exclusive_file_lock(lock_path: Path):
    """跨进程互斥文件锁上下文管理器。

    Unix 使用 fcntl.flock，Windows 使用 msvcrt.locking 作为降级方案。
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_WRONLY)
    try:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(fd)


# ---------------------------------------------------------------------------
# 原子写入
# ---------------------------------------------------------------------------


def _atomic_write_text(path: Path, content: str) -> None:
    """原子写入文本文件（先写临时文件再 rename）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# 记忆条目
# ---------------------------------------------------------------------------


@dataclass
class MemoryEntry:
    """单条记忆条目。

    Attributes:
        name: 记忆条目标识（文件名去掉 .md 后缀）。
        title: 记忆标题。
        path: 记忆文件的完整路径。
        content: 记忆内容。
    """

    name: str
    title: str
    path: Path
    content: str


# ---------------------------------------------------------------------------
# MemoryManager
# ---------------------------------------------------------------------------


class MemoryManager:
    """跨会话持久化记忆管理器.

    记忆以 Markdown 文件形式存储在 ``.kimi-harness/memory/`` 目录下，
    通过 ``MEMORY.md`` 索引文件组织。支持项目级和用户级两层记忆。

    Usage::

        manager = MemoryManager(work_dir="/path/to/project")
        await manager.add_entry("架构决策", "我们选择了 PostgreSQL 作为主数据库...")
        entries = await manager.list_entries()
        prompt = await manager.load_memory_prompt()
    """

    def __init__(
        self,
        work_dir: str | Path,
        *,
        user_memory_dir: Path | None = None,
    ) -> None:
        self._work_dir = Path(work_dir)
        self._project_memory_dir = _get_project_memory_dir(work_dir)
        self._user_memory_dir = user_memory_dir or _get_user_memory_dir()
        self._project_entrypoint = _get_memory_entrypoint(work_dir)

    @property
    def project_memory_dir(self) -> Path:
        """项目级记忆目录。"""
        return self._project_memory_dir

    @property
    def user_memory_dir(self) -> Path:
        """用户级记忆目录。"""
        return self._user_memory_dir

    # --- CRUD ---

    def add_entry(self, title: str, content: str) -> Path:
        """添加一条记忆。

        创建 ``<slug>.md`` 文件，并将其追加到 ``MEMORY.md`` 索引。

        Args:
            title: 记忆标题（用于生成文件名 slug）。
            content: 记忆内容（Markdown 格式）。

        Returns:
            创建的记忆文件路径。
        """
        memory_dir = self._project_memory_dir
        slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", title.strip().lower()).strip("_")
        slug = slug or "memory"
        path = memory_dir / f"{slug}.md"

        with _exclusive_file_lock(_memory_lock_path(self._work_dir)):
            _atomic_write_text(path, content.strip() + "\n")

            entrypoint = self._project_entrypoint
            existing = (
                entrypoint.read_text(encoding="utf-8")
                if entrypoint.exists()
                else "# Memory Index\n"
            )
            if path.name not in existing:
                existing = existing.rstrip() + f"\n- [{title}]({path.name})\n"
                _atomic_write_text(entrypoint, existing)

        logger.info("Memory entry added: {title} -> {path}", title=title, path=path)
        return path

    def remove_entry(self, name: str) -> bool:
        """删除一条记忆。

        Args:
            name: 记忆条目标识（文件名或 slug）。

        Returns:
            是否成功删除。
        """
        memory_dir = self._project_memory_dir
        matches = [
            p for p in memory_dir.glob("*.md")
            if p.stem == name or p.name == name
        ]
        if not matches:
            return False

        path = matches[0]
        with _exclusive_file_lock(_memory_lock_path(self._work_dir)):
            if path.exists():
                path.unlink()

            entrypoint = self._project_entrypoint
            if entrypoint.exists():
                lines = [
                    line
                    for line in entrypoint.read_text(encoding="utf-8").splitlines()
                    if path.name not in line
                ]
                _atomic_write_text(entrypoint, "\n".join(lines).rstrip() + "\n")

        logger.info("Memory entry removed: {name}", name=name)
        return True

    def list_entries(self) -> list[MemoryEntry]:
        """列出项目级所有记忆条目。

        Returns:
            记忆条目列表，按文件名排序。
        """
        memory_dir = self._project_memory_dir
        if not memory_dir.is_dir():
            return []

        entries: list[MemoryEntry] = []
        for path in sorted(memory_dir.glob("*.md")):
            if path.name == "MEMORY.md":
                continue
            try:
                content = path.read_text(encoding="utf-8")
                title = path.stem.replace("_", " ").title()
                entries.append(MemoryEntry(
                    name=path.stem,
                    title=title,
                    path=path,
                    content=content,
                ))
            except OSError as exc:
                logger.warning("Failed to read memory file {path}: {error}", path=path, error=exc)

        return entries

    def list_user_entries(self) -> list[MemoryEntry]:
        """列出用户级所有记忆条目。"""
        if not self._user_memory_dir.is_dir():
            return []

        entries: list[MemoryEntry] = []
        for path in sorted(self._user_memory_dir.glob("*.md")):
            if path.name == "MEMORY.md":
                continue
            try:
                content = path.read_text(encoding="utf-8")
                title = path.stem.replace("_", " ").title()
                entries.append(MemoryEntry(
                    name=path.stem,
                    title=title,
                    path=path,
                    content=content,
                ))
            except OSError as exc:
                logger.warning(
                    "Failed to read user memory file {path}: {error}",
                    path=path,
                    error=exc,
                )

        return entries

    # --- 提示词注入 ---

    def load_memory_prompt(self) -> str:
        """加载记忆作为系统提示词的一部分。

        读取项目级和用户级的 MEMORY.md 索引，组合为
        可注入系统提示词的文本。

        Returns:
            记忆提示词文本。如果没有记忆则返回空字符串。
        """
        sections: list[str] = []

        # 项目级记忆
        project_memory = self._load_index(self._project_entrypoint)
        if project_memory:
            sections.append("## Project Memory\n" + project_memory)

        # 用户级记忆
        user_entrypoint = _get_user_memory_entrypoint()
        user_memory = self._load_index(user_entrypoint)
        if user_memory:
            sections.append("## User Memory\n" + user_memory)

        if not sections:
            return ""

        return (
            "# Memory Context\n\n"
            "The following is persistent memory from previous sessions. "
            "Use this context to maintain continuity across conversations.\n\n"
            + "\n\n".join(sections)
        )

    def scan_project_memory(self) -> list[str]:
        """扫描项目级记忆文件，返回所有记忆内容。

        Returns:
            每条记忆的内容文本列表。
        """
        entries = self.list_entries()
        return [entry.content for entry in entries]

    @staticmethod
    def _load_index(entrypoint: Path) -> str:
        """读取索引文件内容。"""
        if not entrypoint.exists():
            return ""
        try:
            content = entrypoint.read_text(encoding="utf-8").strip()
            # 去掉标题行
            lines = content.splitlines()
            if lines and lines[0].startswith("# "):
                lines = lines[1:]
            return "\n".join(line for line in lines if line.strip())
        except OSError:
            return ""


# ---------------------------------------------------------------------------
# contextmanager import (延迟以避免兼容问题)
# ---------------------------------------------------------------------------

