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
        return StepResult(message=Message(role="assistant", content=[TextPart(type="text", text="done")]))

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
    async def test_harness_enables_memory(
        self,
        runtime: Runtime,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        soul = _make_soul(runtime, tmp_path)
        sent = _setup_soul_run(soul, monkeypatch)

        assert runtime.memory_manager is None

        await soul.run("harness fix this")

        assert runtime.memory_manager is not None
        # TurnBegin should contain cleaned input (without "harness")
        turn_begins = [m for m in sent if isinstance(m, TurnBegin)]
        assert len(turn_begins) == 1
        assert turn_begins[0].user_input == "fix this"

    @pytest.mark.asyncio
    async def test_hns_enables_memory(
        self,
        runtime: Runtime,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        soul = _make_soul(runtime, tmp_path)
        _setup_soul_run(soul, monkeypatch)

        await soul.run("hns do something")

        assert runtime.memory_manager is not None
        turn_begins = [m for m in sent if isinstance(m, TurnBegin)]
        assert len(turn_begins) == 1
        assert turn_begins[0].user_input == "do something"

    @pytest.mark.asyncio
    async def test_no_magic_word_no_memory(
        self,
        runtime: Runtime,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        soul = _make_soul(runtime, tmp_path)
        _setup_soul_run(soul, monkeypatch)

        await soul.run("fix this bug")

        assert runtime.memory_manager is None
        turn_begins = [m for m in sent if isinstance(m, TurnBegin)]
        assert len(turn_begins) == 1
        assert turn_begins[0].user_input == "fix this bug"



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

        assert runtime.memory_manager is None


class TestIdempotency:
    """Magic word should not re-inject when already enabled."""

    @pytest.mark.asyncio
    async def test_already_enabled_no_double_init(
        self,
        runtime: Runtime,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        soul = _make_soul(runtime, tmp_path)
        _setup_soul_run(soul, monkeypatch)

        # Pre-enable memory manager
        from kimi_cli.harness.memory.manager import MemoryManager
        mm = MemoryManager(work_dir=str(tmp_path))
        runtime.memory_manager = mm

        await soul.run("harness fix this")

        # memory_manager should still be the same instance (idempotent)
        assert runtime.memory_manager is mm
