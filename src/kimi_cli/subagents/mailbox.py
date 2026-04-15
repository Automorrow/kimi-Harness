"""File-based async message queue for agent-to-agent communication.

Each message is stored as an individual JSON file:
    ~/.kimi-harness/mailbox/<agent_id>/<timestamp>_<message_id>.json

Atomic writes use a .tmp file followed by os.rename to prevent partial reads.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from kimi_cli.harness.memory.manager import _exclusive_file_lock

MessageType = Literal[
    "user_message",
    "shutdown",
    "idle_notification",
]


@dataclass
class MailboxMessage:
    """A single message exchanged between agents."""

    id: str
    type: MessageType
    sender: str
    recipient: str
    payload: dict[str, Any]
    timestamp: float
    read: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "sender": self.sender,
            "recipient": self.recipient,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "read": self.read,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MailboxMessage":
        return cls(
            id=data["id"],
            type=data["type"],
            sender=data["sender"],
            recipient=data["recipient"],
            payload=data.get("payload", {}),
            timestamp=data["timestamp"],
            read=data.get("read", False),
        )


def _mailbox_base_dir() -> Path:
    return Path.home() / ".kimi-harness" / "mailbox"


def get_agent_mailbox_dir(agent_id: str) -> Path:
    """Return ~/.kimi-harness/mailbox/<agent_id>/"""
    inbox = _mailbox_base_dir() / agent_id
    inbox.mkdir(parents=True, exist_ok=True)
    return inbox


class TeammateMailbox:
    """File-based mailbox for a single agent.

    Each message lives in its own JSON file named ``<timestamp>_<id>.json``
    inside the agent's mailbox directory.  Writes are atomic: the payload is
    first written to a ``.tmp`` file, then renamed into place.
    """

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id

    def get_mailbox_dir(self) -> Path:
        """Return the mailbox directory path, creating it if necessary."""
        return get_agent_mailbox_dir(self.agent_id)

    def _lock_path(self) -> Path:
        return self.get_mailbox_dir() / ".write_lock"

    async def write(self, msg: MailboxMessage) -> None:
        """Atomically write *msg* to the mailbox as a JSON file."""
        inbox = self.get_mailbox_dir()
        filename = f"{msg.timestamp:.6f}_{msg.id}.json"
        final_path = inbox / filename
        tmp_path = inbox / f"{filename}.tmp"
        lock_path = self._lock_path()

        payload = json.dumps(msg.to_dict(), indent=2)

        def _write_atomic() -> None:
            with _exclusive_file_lock(lock_path):
                tmp_path.write_text(payload, encoding="utf-8")
                os.replace(tmp_path, final_path)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _write_atomic)

    async def read_all(self, unread_only: bool = True) -> list[MailboxMessage]:
        """Return messages from the mailbox, sorted by timestamp (oldest first)."""
        inbox = self.get_mailbox_dir()

        def _read_all() -> list[MailboxMessage]:
            messages: list[MailboxMessage] = []
            for path in sorted(inbox.glob("*.json")):
                if path.name.startswith(".") or path.name.endswith(".tmp"):
                    continue
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    msg = MailboxMessage.from_dict(data)
                    if not unread_only or not msg.read:
                        messages.append(msg)
                except (json.JSONDecodeError, KeyError):
                    continue
            return messages

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _read_all)

    async def mark_read(self, message_id: str) -> None:
        """Mark the message with *message_id* as read (in-place update)."""
        inbox = self.get_mailbox_dir()
        lock_path = self._lock_path()

        def _mark_read() -> bool:
            with _exclusive_file_lock(lock_path):
                for path in inbox.glob("*.json"):
                    if path.name.startswith(".") or path.name.endswith(".tmp"):
                        continue
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, OSError):
                        continue

                    if data.get("id") == message_id:
                        data["read"] = True
                        tmp_path = path.with_suffix(".json.tmp")
                        tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                        os.replace(tmp_path, path)
                        return True
                return False

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _mark_read)

    async def clear(self) -> None:
        """Remove all message files from the mailbox."""
        inbox = self.get_mailbox_dir()
        lock_path = self._lock_path()

        def _clear() -> None:
            with _exclusive_file_lock(lock_path):
                for path in inbox.glob("*.json"):
                    if path.name.startswith("."):
                        continue
                    try:
                        path.unlink()
                    except OSError:
                        pass

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _clear)


def _make_message(
    msg_type: MessageType,
    sender: str,
    recipient: str,
    payload: dict[str, Any],
) -> MailboxMessage:
    return MailboxMessage(
        id=str(uuid.uuid4()),
        type=msg_type,
        sender=sender,
        recipient=recipient,
        payload=payload,
        timestamp=time.time(),
    )


def create_user_message(sender: str, recipient: str, content: str) -> MailboxMessage:
    """Create a plain text user message."""
    return _make_message("user_message", sender, recipient, {"content": content})


def create_shutdown_request(sender: str, recipient: str) -> MailboxMessage:
    """Create a shutdown request message."""
    return _make_message("shutdown", sender, recipient, {})


async def write_to_mailbox(agent_id: str, msg: MailboxMessage) -> None:
    """Convenience helper to write a message to an agent's mailbox."""
    mailbox = TeammateMailbox(agent_id)
    await mailbox.write(msg)
