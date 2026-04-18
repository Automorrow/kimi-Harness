"""跨会话记忆管理器 - Markdown 文件存储"""

from __future__ import annotations

import fcntl
import json
import msvcrt
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger


class MemoryManager:
    """跨会话记忆管理器

    双层存储：
    - 项目级：<work_dir>/.kimi/memory/
    - 用户级：~/.kimi/memory/
    """

    def __init__(self, work_dir: Path | str, share_dir: Path | str | None = None):
        self.work_dir = Path(work_dir)
        self.project_memory_dir = self.work_dir / ".kimi" / "memory"

        if share_dir:
            self.user_memory_dir = Path(share_dir) / "memory"
        else:
            self.user_memory_dir = Path.home() / ".kimi" / "memory"

        self.project_memory_dir.mkdir(parents=True, exist_ok=True)
        self.user_memory_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.project_memory_dir / "MEMORY.md"

    def _acquire_lock(self, filepath: Path) -> Any:
        """跨平台文件锁"""
        lock_file = filepath.with_suffix(filepath.suffix + ".lock")
        lock_file.touch(exist_ok=True)
        if os.name == "nt":
            fd = lock_file.open("r+")
            msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, 1)
            return fd
        else:
            fd = lock_file.open("r+")
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
            return fd

    def _release_lock(self, lock_fd: Any) -> None:
        """释放文件锁"""
        try:
            if os.name == "nt":
                msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            lock_fd.close()
        except Exception:
            pass

    def _entry_path(self, name: str, user_level: bool = False) -> Path:
        """获取记忆条目文件路径"""
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        directory = self.user_memory_dir if user_level else self.project_memory_dir
        return directory / f"{safe_name}.md"

    def add_entry(self, title: str, content: str, user_level: bool = False) -> Path:
        """添加记忆条目"""
        entry_path = self._entry_path(title, user_level)
        lock = self._acquire_lock(entry_path)
        try:
            now = datetime.now(timezone.utc).isoformat()
            frontmatter = f"""---
title: {title}
created: {now}
---

{content}
"""
            # 原子写入
            tmp_path = entry_path.with_suffix(".tmp")
            tmp_path.write_text(frontmatter, encoding="utf-8")
            tmp_path.replace(entry_path)

            self._update_index()
            logger.info(f"Memory entry saved: {title}")
            return entry_path
        finally:
            self._release_lock(lock)

    def remove_entry(self, title: str, user_level: bool = False) -> bool:
        """删除记忆条目"""
        entry_path = self._entry_path(title, user_level)
        if not entry_path.exists():
            return False
        lock = self._acquire_lock(entry_path)
        try:
            entry_path.unlink()
            self._update_index()
            logger.info(f"Memory entry removed: {title}")
            return True
        finally:
            self._release_lock(lock)

    def list_entries(self, user_level: bool = False) -> list[dict[str, Any]]:
        """列出所有记忆条目"""
        directory = self.user_memory_dir if user_level else self.project_memory_dir
        entries = []
        for f in sorted(directory.glob("*.md")):
            if f.name == "MEMORY.md":
                continue
            try:
                text = f.read_text(encoding="utf-8")
                entries.append(self._parse_entry(text, f.name))
            except Exception:
                continue
        return entries

    def list_user_entries(self) -> list[dict[str, Any]]:
        """列出用户级记忆"""
        return self.list_entries(user_level=True)

    def _parse_entry(self, text: str, filename: str) -> dict[str, Any]:
        """解析记忆条目"""
        title = filename[:-3]  # 去掉 .md
        created = ""
        if text.startswith("---"):
            end = text.find("---", 3)
            if end > 0:
                fm = text[3:end].strip()
                for line in fm.split("\n"):
                    if line.startswith("title:"):
                        title = line.split(":", 1)[1].strip()
                    elif line.startswith("created:"):
                        created = line.split(":", 1)[1].strip()
        return {"title": title, "created": created, "filename": filename}

    def _update_index(self) -> None:
        """更新 MEMORY.md 索引文件"""
        entries = self.list_entries()
        user_entries = self.list_user_entries()

        lines = ["# Memory Index\n"]
        lines.append("## Project Memories\n")
        for e in entries:
            lines.append(f"- **{e['title']}** ({e['created']})")
        lines.append("\n## User Memories\n")
        for e in user_entries:
            lines.append(f"- **{e['title']}** ({e['created']})")

        lock = self._acquire_lock(self._index_path)
        try:
            tmp = self._index_path.with_suffix(".tmp")
            tmp.write_text("\n".join(lines), encoding="utf-8")
            tmp.replace(self._index_path)
        finally:
            self._release_lock(lock)

    def load_memory_prompt(self) -> str:
        """加载记忆提示词（MEMORY.md 索引）"""
        if not self._index_path.exists():
            return ""
        text = self._index_path.read_text(encoding="utf-8")
        lines = text.split("\n")
        if len(lines) > 200:
            text = "\n".join(lines[:200]) + "\n... (truncated)"
        return text

    def search_entries(self, query: str, user_level: bool = False) -> list[dict[str, Any]]:
        """搜索记忆条目"""
        entries = self.list_entries(user_level)
        results = []
        query_lower = query.lower()
        for entry in entries:
            entry_path = self._entry_path(entry["title"], user_level)
            try:
                content = entry_path.read_text(encoding="utf-8").lower()
                if query_lower in content:
                    # 读取完整内容
                    full = entry_path.read_text(encoding="utf-8")
                    if len(full) > 8000:
                        full = full[:8000] + "... (truncated)"
                    results.append({**entry, "content": full})
            except Exception:
                continue
        return results
