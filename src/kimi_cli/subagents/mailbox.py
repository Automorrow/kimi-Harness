"""Agent 间异步消息队列 - 基于文件的 mailbox 系统"""

from __future__ import annotations

import fcntl
import json
import msvcrt
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class MailMessage:
    id: str
    from_agent: str
    to_agent: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    read: bool = False


class Mailbox:
    """文件型异步消息队列"""

    def __init__(self, base_dir: Path | str):
        self.base_dir = Path(base_dir) / "mailbox"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _agent_dir(self, agent_id: str) -> Path:
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in agent_id)
        return self.base_dir / safe_id

    def _lock_file(self, filepath: Path) -> Any:
        lock_path = filepath.with_suffix(filepath.suffix + ".lock")
        lock_path.touch(exist_ok=True)
        if os.name == "nt":
            fd = lock_path.open("r+")
            msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, 1)
            return fd
        else:
            fd = lock_path.open("r+")
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
            return fd

    def _unlock_file(self, lock_fd: Any) -> None:
        try:
            if os.name == "nt":
                msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            lock_fd.close()
        except Exception:
            pass

    def send(self, from_agent: str, to_agent: str, content: str) -> str:
        """发送消息"""
        msg = MailMessage(
            id=str(uuid.uuid4())[:8],
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
        )

        agent_dir = self._agent_dir(to_agent)
        agent_dir.mkdir(parents=True, exist_ok=True)
        msg_path = agent_dir / f"{msg.id}.json"

        lock = self._lock_file(msg_path)
        try:
            tmp = msg_path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps({
                    "id": msg.id,
                    "from_agent": msg.from_agent,
                    "to_agent": msg.to_agent,
                    "content": msg.content,
                    "timestamp": msg.timestamp,
                    "read": False,
                }, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp.replace(msg_path)
        finally:
            self._unlock_file(lock)

        logger.debug(f"Mail sent: {msg.id} from {from_agent} to {to_agent}")
        return msg.id

    def receive(self, agent_id: str, unread_only: bool = True) -> list[MailMessage]:
        """接收消息"""
        agent_dir = self._agent_dir(agent_id)
        if not agent_dir.exists():
            return []

        messages = []
        for f in sorted(agent_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if unread_only and data.get("read", False):
                    continue
                msg = MailMessage(**data)
                messages.append(msg)

                # 标记为已读
                data["read"] = True
                lock = self._lock_file(f)
                try:
                    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                finally:
                    self._unlock_file(lock)
            except Exception as e:
                logger.warning(f"Failed to read mail {f}: {e}")

        return messages

    def count_unread(self, agent_id: str) -> int:
        """统计未读消息数"""
        agent_dir = self._agent_dir(agent_id)
        if not agent_dir.exists():
            return 0
        count = 0
        for f in agent_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if not data.get("read", False):
                    count += 1
            except Exception:
                continue
        return count
