from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kimi_cli.soul.agent import Runtime
from kimi_cli.subagents.mailbox import TeammateMailbox
from kimi_cli.tools.send_message import SendMessage, SendMessageParams


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "kimi_cli.subagents.mailbox._mailbox_base_dir",
        lambda: tmp_path,
    )
    rt = MagicMock(spec=Runtime)
    rt.role = "root"
    rt.subagent_store = MagicMock()
    # Simulate an existing agent
    rt.subagent_store.meta_path.return_value = tmp_path / "agent-123" / "meta.json"
    rt.subagent_store.meta_path.return_value.parent.mkdir(parents=True, exist_ok=True)
    rt.subagent_store.meta_path.return_value.write_text("{}", encoding="utf-8")
    return rt


async def test_send_message_to_existing_agent(runtime):
    tool = SendMessage(runtime)
    result = await tool(SendMessageParams(to="agent-123", message="hello there"))

    assert result.is_error is False
    assert "Sent message to agent agent-123" in result.output

    # Verify mailbox
    mbox = TeammateMailbox("agent-123")
    messages = await mbox.read_all()
    assert len(messages) == 1
    assert messages[0].payload["content"] == "hello there"


async def test_send_message_rejects_non_root(runtime):
    runtime.role = "subagent"
    tool = SendMessage(runtime)
    result = await tool(SendMessageParams(to="agent-123", message="hello"))
    assert result.is_error is True
    assert "root agent" in result.message


async def test_send_message_rejects_missing_agent(runtime):
    runtime.subagent_store.meta_path.return_value = (
        runtime.subagent_store.meta_path.return_value.parent.parent / "nonexistent" / "meta.json"
    )
    tool = SendMessage(runtime)
    result = await tool(SendMessageParams(to="no-such-agent", message="hello"))
    assert result.is_error is True
    assert "No agent found" in result.message


async def test_send_message_supports_team_name_suffix(runtime):
    tool = SendMessage(runtime)
    result = await tool(SendMessageParams(to="agent-123@my-team", message="hello"))
    assert result.is_error is False
    assert "agent-123" in result.output
