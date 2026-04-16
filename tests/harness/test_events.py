"""Unit tests for kimi_cli.harness.events.stream - Event serialization & WireToStreamAdapter."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

from kimi_cli.harness.events.stream import (
    AssistantTextDelta,
    AssistantTurnComplete,
    CompactProgressEvent,
    ErrorEvent,
    PermissionEvent,
    StatusEvent,
    SubagentEvent,
    ToolExecutionCompleted,
    ToolExecutionStarted,
    TurnEvent,
    WireToStreamAdapter,
    event_from_dict,
    event_to_json,
)


# ---------------------------------------------------------------------------
# TestEventSerialization
# ---------------------------------------------------------------------------


class TestEventSerialization:

    def _roundtrip(self, event) -> Any:
        """序列化再反序列化，验证往返一致性。"""
        json_str = event_to_json(event)
        data = json.loads(json_str)
        restored = event_from_dict(data)
        return restored

    def test_assistant_text_delta_roundtrip(self) -> None:
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        event = AssistantTextDelta(text="Hello world", timestamp=ts)
        restored = self._roundtrip(event)
        assert isinstance(restored, AssistantTextDelta)
        assert restored.text == "Hello world"

    def test_tool_execution_started_roundtrip(self) -> None:
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        event = ToolExecutionStarted(
            tool_name="bash",
            tool_input={"cmd": "ls"},
            tool_call_id="call_123",
            timestamp=ts,
        )
        restored = self._roundtrip(event)
        assert isinstance(restored, ToolExecutionStarted)
        assert restored.tool_name == "bash"
        assert restored.tool_input == {"cmd": "ls"}
        assert restored.tool_call_id == "call_123"

    def test_tool_execution_completed_roundtrip(self) -> None:
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        event = ToolExecutionCompleted(
            tool_name="bash",
            output="file1.txt\nfile2.txt",
            is_error=False,
            tool_call_id="call_123",
            duration_ms=42.5,
            timestamp=ts,
        )
        restored = self._roundtrip(event)
        assert isinstance(restored, ToolExecutionCompleted)
        assert restored.tool_name == "bash"
        assert restored.output == "file1.txt\nfile2.txt"
        assert restored.is_error is False
        assert restored.duration_ms == 42.5

    def test_error_event_roundtrip(self) -> None:
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        event = ErrorEvent(message="Something went wrong", recoverable=True, timestamp=ts)
        restored = self._roundtrip(event)
        assert isinstance(restored, ErrorEvent)
        assert restored.message == "Something went wrong"
        assert restored.recoverable is True

    def test_status_event_roundtrip(self) -> None:
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        event = StatusEvent(message="Processing...", timestamp=ts)
        restored = self._roundtrip(event)
        assert isinstance(restored, StatusEvent)
        assert restored.message == "Processing..."

    def test_compact_progress_event_roundtrip(self) -> None:
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        event = CompactProgressEvent(
            phase="compact_start",
            trigger="manual",
            message="Starting compaction",
            attempt=2,
            timestamp=ts,
        )
        restored = self._roundtrip(event)
        assert isinstance(restored, CompactProgressEvent)
        assert restored.phase == "compact_start"
        assert restored.trigger == "manual"
        assert restored.message == "Starting compaction"
        assert restored.attempt == 2

    def test_subagent_event_roundtrip(self) -> None:
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        event = SubagentEvent(
            agent_id="agent-1",
            agent_type="explore",
            event_type="completed",
            message="Done exploring",
            timestamp=ts,
        )
        restored = self._roundtrip(event)
        assert isinstance(restored, SubagentEvent)
        assert restored.agent_id == "agent-1"
        assert restored.agent_type == "explore"
        assert restored.event_type == "completed"
        assert restored.message == "Done exploring"

    def test_turn_event_roundtrip(self) -> None:
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        event = TurnEvent(event_type="turn_begin", turn_count=3, timestamp=ts)
        restored = self._roundtrip(event)
        assert isinstance(restored, TurnEvent)
        assert restored.event_type == "turn_begin"
        assert restored.turn_count == 3

    def test_permission_event_roundtrip(self) -> None:
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        event = PermissionEvent(
            tool_name="bash",
            decision="denied",
            reason="Dangerous command",
            timestamp=ts,
        )
        restored = self._roundtrip(event)
        assert isinstance(restored, PermissionEvent)
        assert restored.tool_name == "bash"
        assert restored.decision == "denied"
        assert restored.reason == "Dangerous command"

    def test_assistant_turn_complete_roundtrip(self) -> None:
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        event = AssistantTurnComplete(
            message={"role": "assistant", "content": "Done"},
            usage={"input_tokens": 100, "output_tokens": 50},
            timestamp=ts,
        )
        restored = self._roundtrip(event)
        assert isinstance(restored, AssistantTurnComplete)
        assert restored.message == {"role": "assistant", "content": "Done"}
        assert restored.usage == {"input_tokens": 100, "output_tokens": 50}

    def test_unknown_event_type_falls_back_to_status(self) -> None:
        """未知事件类型反序列化为 StatusEvent。"""
        data = {
            "type": "unknown_type",
            "timestamp": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        }
        restored = event_from_dict(data)
        assert isinstance(restored, StatusEvent)
        assert "Unknown event type" in restored.message

    def test_event_to_json_is_valid_json(self) -> None:
        """event_to_json 输出是合法 JSON 字符串。"""
        event = AssistantTextDelta(text="test")
        json_str = event_to_json(event)
        parsed = json.loads(json_str)
        assert parsed["type"] == "assistant_text_delta"
        assert parsed["text"] == "test"

    def test_event_from_dict_missing_timestamp_uses_now(self) -> None:
        """缺少 timestamp 时使用当前时间。"""
        data = {"type": "status", "message": "ok"}
        restored = event_from_dict(data)
        assert isinstance(restored, StatusEvent)
        assert restored.message == "ok"


# ---------------------------------------------------------------------------
# TestWireToStreamAdapter
# ---------------------------------------------------------------------------

# 用于 mock kimi_cli.wire.types 的类型占位符
_MOCK_WIRE_TYPES = MagicMock(
    TextPart=type("TextPart", (), {}),
    ToolCall=type("ToolCall", (), {}),
    TurnBegin=type("TurnBegin", (), {}),
    TurnEnd=type("TurnEnd", (), {}),
    StepBegin=type("StepBegin", (), {}),
    StepInterrupted=type("StepInterrupted", (), {}),
    ToolResult=type("ToolResult", (), {}),
)

_MOCK_WIRE_MODULES = {
    "kimi_cli.wire": MagicMock(),
    "kimi_cli.wire.types": _MOCK_WIRE_TYPES,
}


class TestWireToStreamAdapter:

    def test_unknown_message_no_crash(self) -> None:
        """未知消息类型不崩溃，返回 None（ImportError 路径）。"""
        unknown = MagicMock()
        unknown.__class__.__name__ = "TotallyUnknownMessage"
        result = WireToStreamAdapter.convert(unknown)
        # 当 kimi_cli.wire.types 不存在时返回 None
        assert result is None

    def test_convert_text_part(self) -> None:
        """TextPart 正确转换为 AssistantTextDelta。"""
        mock_text_part = MagicMock()
        mock_text_part.text = "Hello wire"

        with patch.dict(sys.modules, _MOCK_WIRE_MODULES, clear=False):
            # 需要清除模块缓存使延迟导入重新加载
            for mod_name in list(_MOCK_WIRE_MODULES.keys()):
                sys.modules.pop(mod_name, None)
            with patch.dict(sys.modules, _MOCK_WIRE_MODULES):
                import kimi_cli.wire.types as wt  # type: ignore[import-untyped]
                mock_text_part.__class__ = wt.TextPart
                result = WireToStreamAdapter.convert(mock_text_part)
                assert isinstance(result, AssistantTextDelta)
                assert result.text == "Hello wire"

    def test_convert_tool_call(self) -> None:
        """ToolCall 正确转换为 ToolExecutionStarted。"""
        mock_func = MagicMock()
        mock_func.name = "bash"
        mock_func.arguments = '{"cmd": "ls -la"}'

        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_abc"
        mock_tool_call.function = mock_func

        with patch.dict(sys.modules, _MOCK_WIRE_MODULES, clear=False):
            for mod_name in list(_MOCK_WIRE_MODULES.keys()):
                sys.modules.pop(mod_name, None)
            with patch.dict(sys.modules, _MOCK_WIRE_MODULES):
                import kimi_cli.wire.types as wt  # type: ignore[import-untyped]
                mock_tool_call.__class__ = wt.ToolCall
                result = WireToStreamAdapter.convert(mock_tool_call)
                assert isinstance(result, ToolExecutionStarted)
                assert result.tool_name == "bash"
                assert result.tool_input == {"cmd": "ls -la"}
                assert result.tool_call_id == "call_abc"

    def test_convert_tool_call_invalid_json(self) -> None:
        """ToolCall 的 arguments 不是合法 JSON 时不崩溃。"""
        mock_func = MagicMock()
        mock_func.name = "bash"
        mock_func.arguments = "not-json{{{"

        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_xyz"
        mock_tool_call.function = mock_func

        with patch.dict(sys.modules, _MOCK_WIRE_MODULES, clear=False):
            for mod_name in list(_MOCK_WIRE_MODULES.keys()):
                sys.modules.pop(mod_name, None)
            with patch.dict(sys.modules, _MOCK_WIRE_MODULES):
                import kimi_cli.wire.types as wt  # type: ignore[import-untyped]
                mock_tool_call.__class__ = wt.ToolCall
                result = WireToStreamAdapter.convert(mock_tool_call)
                assert isinstance(result, ToolExecutionStarted)
                assert result.tool_input == {}

    def test_convert_tool_result(self) -> None:
        """ToolResult 正确转换为 ToolExecutionCompleted。"""
        mock_ret_val = MagicMock()
        mock_ret_val.is_error = False
        mock_ret_val.message = "output text"

        mock_tool_result = MagicMock()
        mock_tool_result.return_value = mock_ret_val
        mock_tool_result.tool_call_id = "call_abc"
        mock_tool_result.tool_name = "bash"

        with patch.dict(sys.modules, _MOCK_WIRE_MODULES, clear=False):
            for mod_name in list(_MOCK_WIRE_MODULES.keys()):
                sys.modules.pop(mod_name, None)
            with patch.dict(sys.modules, _MOCK_WIRE_MODULES):
                import kimi_cli.wire.types as wt  # type: ignore[import-untyped]
                mock_tool_result.__class__ = wt.ToolResult
                result = WireToStreamAdapter.convert(mock_tool_result)
                assert isinstance(result, ToolExecutionCompleted)
                assert result.tool_name == "bash"
                assert result.output == "output text"
                assert result.is_error is False

    def test_convert_turn_begin(self) -> None:
        """TurnBegin 转换为 TurnEvent(turn_begin)。"""
        mock_turn_begin = MagicMock()

        with patch.dict(sys.modules, _MOCK_WIRE_MODULES, clear=False):
            for mod_name in list(_MOCK_WIRE_MODULES.keys()):
                sys.modules.pop(mod_name, None)
            with patch.dict(sys.modules, _MOCK_WIRE_MODULES):
                import kimi_cli.wire.types as wt  # type: ignore[import-untyped]
                mock_turn_begin.__class__ = wt.TurnBegin
                result = WireToStreamAdapter.convert(mock_turn_begin)
                assert isinstance(result, TurnEvent)
                assert result.event_type == "turn_begin"

    def test_convert_turn_end(self) -> None:
        """TurnEnd 转换为 TurnEvent(turn_end)。"""
        mock_turn_end = MagicMock()

        with patch.dict(sys.modules, _MOCK_WIRE_MODULES, clear=False):
            for mod_name in list(_MOCK_WIRE_MODULES.keys()):
                sys.modules.pop(mod_name, None)
            with patch.dict(sys.modules, _MOCK_WIRE_MODULES):
                import kimi_cli.wire.types as wt  # type: ignore[import-untyped]
                mock_turn_end.__class__ = wt.TurnEnd
                result = WireToStreamAdapter.convert(mock_turn_end)
                assert isinstance(result, TurnEvent)
                assert result.event_type == "turn_end"

    def test_convert_step_begin(self) -> None:
        """StepBegin 转换为 TurnEvent(step_begin)。"""
        mock_step_begin = MagicMock()
        mock_step_begin.n = 5

        with patch.dict(sys.modules, _MOCK_WIRE_MODULES, clear=False):
            for mod_name in list(_MOCK_WIRE_MODULES.keys()):
                sys.modules.pop(mod_name, None)
            with patch.dict(sys.modules, _MOCK_WIRE_MODULES):
                import kimi_cli.wire.types as wt  # type: ignore[import-untyped]
                mock_step_begin.__class__ = wt.StepBegin
                result = WireToStreamAdapter.convert(mock_step_begin)
                assert isinstance(result, TurnEvent)
                assert result.event_type == "step_begin"
                assert result.turn_count == 5

    def test_convert_step_interrupted(self) -> None:
        """StepInterrupted 转换为 TurnEvent(step_interrupted)。"""
        mock_step_interrupted = MagicMock()

        with patch.dict(sys.modules, _MOCK_WIRE_MODULES, clear=False):
            for mod_name in list(_MOCK_WIRE_MODULES.keys()):
                sys.modules.pop(mod_name, None)
            with patch.dict(sys.modules, _MOCK_WIRE_MODULES):
                import kimi_cli.wire.types as wt  # type: ignore[import-untyped]
                mock_step_interrupted.__class__ = wt.StepInterrupted
                result = WireToStreamAdapter.convert(mock_step_interrupted)
                assert isinstance(result, TurnEvent)
                assert result.event_type == "step_interrupted"

    def test_convert_unknown_wire_message_returns_status(self) -> None:
        """无法识别的 WireMessage 类型转换为 StatusEvent。"""
        mock_unknown = MagicMock()
        mock_unknown.model_dump = MagicMock(return_value={"key": "value"})

        with patch.dict(sys.modules, _MOCK_WIRE_MODULES, clear=False):
            for mod_name in list(_MOCK_WIRE_MODULES.keys()):
                sys.modules.pop(mod_name, None)
            with patch.dict(sys.modules, _MOCK_WIRE_MODULES):
                # mock_unknown 不是任何已知类型，应落入 default case
                result = WireToStreamAdapter.convert(mock_unknown)
                assert isinstance(result, StatusEvent)
                assert "wire:" in result.message
