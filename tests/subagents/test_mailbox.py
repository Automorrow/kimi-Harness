from __future__ import annotations

import pytest

from kimi_cli.subagents.mailbox import (
    TeammateMailbox,
    create_shutdown_request,
    create_user_message,
    write_to_mailbox,
)


@pytest.fixture
def mailbox(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "kimi_cli.subagents.mailbox._mailbox_base_dir",
        lambda: tmp_path,
    )
    return TeammateMailbox("test-agent")


async def test_mailbox_write_and_read(mailbox: TeammateMailbox):
    msg = create_user_message("sender", "test-agent", "hello")
    await mailbox.write(msg)

    messages = await mailbox.read_all(unread_only=True)
    assert len(messages) == 1
    assert messages[0].payload["content"] == "hello"


async def test_mailbox_mark_read(mailbox: TeammateMailbox):
    msg = create_user_message("sender", "test-agent", "hello")
    await mailbox.write(msg)

    await mailbox.mark_read(msg.id)
    messages = await mailbox.read_all(unread_only=True)
    assert len(messages) == 0

    messages = await mailbox.read_all(unread_only=False)
    assert len(messages) == 1
    assert messages[0].read is True


async def test_mailbox_clear(mailbox: TeammateMailbox):
    await mailbox.write(create_user_message("s", "test-agent", "a"))
    await mailbox.write(create_shutdown_request("s", "test-agent"))
    await mailbox.clear()
    assert await mailbox.read_all(unread_only=False) == []


async def test_write_to_mailbox(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "kimi_cli.subagents.mailbox._mailbox_base_dir",
        lambda: tmp_path,
    )
    msg = create_user_message("root", "agent-1", "do this")
    await write_to_mailbox("agent-1", msg)

    mbox = TeammateMailbox("agent-1")
    messages = await mbox.read_all()
    assert len(messages) == 1
    assert messages[0].payload["content"] == "do this"
