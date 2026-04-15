"""Tests for WireServer prompt queueing."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from kosong.tooling.empty import EmptyToolset

from kimi_cli.soul.agent import Agent, Runtime
from kimi_cli.soul.context import Context
from kimi_cli.soul.kimisoul import KimiSoul
from kimi_cli.wire.jsonrpc import (
    ErrorCodes,
    JSONRPCErrorResponse,
    JSONRPCPromptMessage,
    JSONRPCSuccessResponse,
    Statuses,
)
from kimi_cli.wire.server import WireServer
from kimi_cli.wire.types import TextPart


def _make_soul(runtime: Runtime, tmp_path: Path) -> KimiSoul:
    agent = Agent(
        name="Queue Test Agent",
        system_prompt="Test prompt.",
        toolset=EmptyToolset(),
        runtime=runtime,
    )
    return KimiSoul(agent, context=Context(file_backend=tmp_path / "history.jsonl"))


@pytest.mark.asyncio
async def test_handle_prompt_queues_when_streaming(
    runtime: Runtime,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    soul = _make_soul(runtime, tmp_path)
    server = WireServer(soul)
    block_event = asyncio.Event()

    async def fake_run_soul(*args, **kwargs):
        await block_event.wait()

    monkeypatch.setattr("kimi_cli.wire.server.run_soul", fake_run_soul)

    # Start the first prompt (blocks on fake_run_soul)
    task1 = asyncio.create_task(
        server._handle_prompt(
            JSONRPCPromptMessage(
                id="p1",
                params=JSONRPCPromptMessage.Params(user_input=[TextPart(text="first")]),
            )
        )
    )

    # Wait until the server marks itself as streaming
    for _ in range(100):
        if server._is_streaming:
            break
        await asyncio.sleep(0.01)
    assert server._is_streaming

    # Second prompt should be queued, not rejected
    task2 = asyncio.create_task(
        server._handle_prompt(
            JSONRPCPromptMessage(
                id="p2",
                params=JSONRPCPromptMessage.Params(user_input=[TextPart(text="second")]),
            )
        )
    )

    # Give task2 a moment to enter the queue
    await asyncio.sleep(0.05)
    assert not task2.done()

    # Unblock the first prompt
    block_event.set()

    resp1 = await asyncio.wait_for(task1, timeout=2.0)
    resp2 = await asyncio.wait_for(task2, timeout=2.0)

    assert isinstance(resp1, JSONRPCSuccessResponse)
    assert resp1.result == {"status": Statuses.FINISHED}
    assert isinstance(resp2, JSONRPCSuccessResponse)
    assert resp2.result == {"status": Statuses.FINISHED}


@pytest.mark.asyncio
async def test_shutdown_rejects_queued_prompts(
    runtime: Runtime,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    soul = _make_soul(runtime, tmp_path)
    server = WireServer(soul)
    block_event = asyncio.Event()

    async def fake_run_soul(*args, **kwargs):
        await block_event.wait()

    monkeypatch.setattr("kimi_cli.wire.server.run_soul", fake_run_soul)

    # Start a prompt to occupy the server
    task1 = asyncio.create_task(
        server._handle_prompt(
            JSONRPCPromptMessage(
                id="p1",
                params=JSONRPCPromptMessage.Params(user_input=[TextPart(text="first")]),
            )
        )
    )

    while not server._is_streaming:
        await asyncio.sleep(0.01)

    # Queue a second prompt
    task2 = asyncio.create_task(
        server._handle_prompt(
            JSONRPCPromptMessage(
                id="p2",
                params=JSONRPCPromptMessage.Params(user_input=[TextPart(text="second")]),
            )
        )
    )

    await asyncio.sleep(0.05)

    # Shut down without unblocking the first prompt
    await server._shutdown()

    # The queued prompt should receive an error response
    resp2 = await asyncio.wait_for(task2, timeout=2.0)
    assert isinstance(resp2, JSONRPCErrorResponse)
    assert resp2.error.code == ErrorCodes.INVALID_STATE
    assert "shut down" in resp2.error.message

    # Clean up the blocked task
    block_event.set()
    try:
        await asyncio.wait_for(task1, timeout=1.0)
    except Exception:
        pass
