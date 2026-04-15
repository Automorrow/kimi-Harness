"""Tests for ACPServer.fork_session."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kimi_cli.acp.server import ACPServer
from kimi_cli.soul.toolset import KimiToolset


@pytest.mark.asyncio
async def test_fork_session_creates_new_session_and_registers_it() -> None:
    server = ACPServer()
    server._auth_methods = []
    server.client_capabilities = MagicMock()
    server.conn = AsyncMock()

    # Mock source session
    source_session = MagicMock()
    source_session.dir = Path("/tmp/sessions/source")
    source_session.work_dir = "kaos:///tmp/project"
    source_session.title = "Source Session"

    source_cli = MagicMock()
    source_cli.soul.runtime.session = source_session
    source_acp_session = MagicMock()
    source_acp_session.cli = source_cli

    server.sessions["source-id"] = (source_acp_session, MagicMock())

    new_session_id = "forked-id"
    new_session = MagicMock()
    new_session.id = new_session_id
    new_session.work_dir = "kaos:///tmp/project"

    with (
        patch.object(
            ACPServer, "_check_token_usable", return_value=None
        ) as _mock_auth,
        patch(
            "kimi_cli.session_fork.fork_session", return_value=new_session_id
        ) as _mock_fork,
        patch(
            "kimi_cli.acp.server.Session.find", new=AsyncMock(return_value=new_session)
        ) as _mock_find,
        patch(
            "kimi_cli.acp.server.KimiCLI.create", new=AsyncMock()
        ) as mock_kimi_create,
        patch(
            "kimi_cli.acp.server.replace_tools"
        ) as mock_replace_tools,
    ):
        mock_toolset = MagicMock(spec=KimiToolset)
        mock_kimi_create.return_value.soul.runtime.config.default_model = "scripted"
        mock_kimi_create.return_value.soul.runtime.config.default_thinking = False
        mock_kimi_create.return_value.soul.agent.toolset = mock_toolset

        resp = await server.fork_session(
            cwd="/tmp/project",
            session_id="source-id",
        )

    assert resp.session_id == new_session_id
    assert new_session_id in server.sessions
    _mock_fork.assert_awaited_once()
    mock_kimi_create.assert_awaited_once()
    assert mock_kimi_create.await_args is not None
    assert mock_kimi_create.await_args.args[0] == new_session
    mock_replace_tools.assert_called_once()


@pytest.mark.asyncio
async def test_fork_session_missing_source_raises_error() -> None:
    server = ACPServer()
    server._auth_methods = []

    with patch.object(ACPServer, "_check_token_usable", return_value=None):
        with pytest.raises(Exception) as exc_info:
            await server.fork_session(
                cwd="/tmp/project",
                session_id="missing-id",
            )
    assert "Session not found" in str(exc_info.value.data)


@pytest.mark.asyncio
async def test_ext_method_returns_error() -> None:
    server = ACPServer()
    with pytest.raises(Exception) as exc_info:
        await server.ext_method("custom/method", {"foo": "bar"})
    assert "not supported" in str(exc_info.value.data)


@pytest.mark.asyncio
async def test_ext_notification_is_noop() -> None:
    server = ACPServer()
    # Should not raise
    await server.ext_notification("custom/notification", {"foo": "bar"})
