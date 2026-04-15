"""Integration tests for magic word detection in KimiSoul.run()."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from kosong import StepResult
from kosong.message import ContentPart, Message
from kosong.tooling.empty import EmptyToolset

import kimi_cli.soul.kimisoul as kimisoul_module
from kimi_cli.soul.agent import Agent, Runtime
from kimi_cli.soul.approval import Approval
from kimi_cli.soul.context import Context
from kimi_cli.soul.kimisoul import KimiSoul
from kimi_cli.wire.types import ImageURLPart, StepBegin, TextPart, TurnBegin, TurnEnd


@pytest.fixture
def approval() -> Approval:
    """Override global yolo=True fixture; magic word tests don't need yolo."""
    return Approval(yolo=False)


def _make_soul(runtime: Runtime, tmp_path: Path) -> KimiSoul:
    agent = Agent(
        name="Magic Word Test Agent",
        system_prompt="Test prompt.",
        toolset=EmptyToolset(),
        runtime=runtime,
    )
    return KimiSoul(agent, context=Context(file_backend=tmp_path / "history.jsonl"))


def _setup_soul_run(
    soul: KimiSoul,
    monkeypatch: pytest.MonkeyPatch,
) -> list[object]:
    """Common setup for soul.run() tests: mock step, checkpoint, wire_send."""
    sent: list[object] = []

    async def fake_step() -> StepResult:
        return StepResult(message=Message.assistant("done"))

    async def fake_checkpoint() -> None:
        return None

    monkeypatch.setattr(soul, "_step", fake_step)
    monkeypatch.setattr(soul, "_checkpoint", fake_checkpoint)
    monkeypatch.setattr(
        soul._denwa_renji, "set_n_checkpoints", lambda _n: None
    )
    monkeypatch.setattr(kimisoul_module, "wire_send", lambda msg: sent.append(msg))
    return sent


class TestStringInput:
    """Magic word detection with str input to soul.run()."""

    @pytest.mark.asyncio
    async def test_harness_activates_plan_mode(
        self,
        runtime: Runtime,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        soul = _make_soul(runtime, tmp_path)
        sent = _setup_soul_run(soul, monkeypatch)

        assert soul._plan_mode is False

        await soul.run("harness fix this")

        assert soul._plan_mode is True
        # TurnBegin should contain cleaned input (without "harness")
        turn_begins = [m for m in sent if isinstance(m, TurnBegin)]
        assert len(turn_begins) == 1
        assert turn_begins[0].user_input == "fix this"

    @pytest.mark.asyncio
    async def test_hns_activates_plan_mode(
        self,
        runtime: Runtime,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        soul = _make_soul(runtime, tmp_path)
        _setup_soul_run(soul, monkeypatch)

        await soul.run("hns do something")

        assert soul._plan_mode is True
        turn_begins = [m for m in sent if isinstance(m, TurnBegin)]
        assert len(turn_begins) == 1
        assert turn_begins[0].user_input == "do something"

    @pytest.mark.asyncio
    async def test_no_magic_word_no_plan_mode(
        self,
        runtime: Runtime,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        soul = _make_soul(runtime, tmp_path)
        _setup_soul_run(soul, monkeypatch)

        await soul.run("fix this bug")

        assert soul._plan_mode is False
        turn_begins = [m for m in sent if isinstance(m, TurnBegin)]
        assert len(turn_begins) == 1
        assert turn_begins[0].user_input == "fix this bug"

    @pytest.mark.asyncio
    async def test_permission_checker_enabled(
        self,
        runtime: Runtime,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        soul = _make_soul(runtime, tmp_path)
        _setup_soul_run(soul, monkeypatch)

        await soul.run("harness fix this")

        assert runtime.approval.has_permission_checker is True


class TestContentPartInput:
    """Magic word detection with list[ContentPart] input."""

    @pytest.mark.asyncio
    async def test_text_part_with_magic_word(
        self,
        runtime: Runtime,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        soul = _make_soul(runtime, tmp_path)
        sent = _setup_soul_run(soul, monkeypatch)

        user_input: list[ContentPart] = [
            TextPart(type="text", text="harness fix this"),
            ImageURLPart(type="image_url", url="https://example.com/img.png"),
        ]
        await soul.run(user_input)

        assert soul._plan_mode is True
        turn_begins = [m for m in sent if isinstance(m, TurnBegin)]
        assert len(turn_begins) == 1
        # The TextPart should be cleaned
        assert turn_begins[0].user_input == "fix this"

    @pytest.mark.asyncio
    async def test_only_image_parts_no_trigger(
        self,
        runtime: Runtime,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        soul = _make_soul(runtime, tmp_path)
        _setup_soul_run(soul, monkeypatch)

        user_input: list[ContentPart] = [
            ImageURLPart(type="image_url", url="https://example.com/img.png"),
        ]
        await soul.run(user_input)

        assert soul._plan_mode is False


class TestIdempotency:
    """Magic word should not re-inject when already in plan mode."""

    @pytest.mark.asyncio
    async def test_already_in_plan_mode_no_double_set(
        self,
        runtime: Runtime,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        soul = _make_soul(runtime, tmp_path)
        _setup_soul_run(soul, monkeypatch)

        # Pre-set plan mode
        soul._plan_mode = True
        original_set_plan_mode = soul._set_plan_mode
        call_count = 0

        def tracked_set_plan_mode(enabled: bool, *, source: str) -> bool:
            nonlocal call_count
            call_count += 1
            return original_set_plan_mode(enabled, source=source)

        monkeypatch.setattr(soul, "_set_plan_mode", tracked_set_plan_mode)

        await soul.run("harness fix this")

        # _set_plan_mode should NOT be called again since already in plan mode
        assert call_count == 0
        assert soul._plan_mode is True
