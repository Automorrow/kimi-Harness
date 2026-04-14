"""Harness 统一流式事件 - 可观测性基础设施.

提供标准化的 Agent 生命周期事件，使 Agent 的每个行为
都可以被外部监控、记录和分析。对齐 OpenHarness 的
StreamEvent 设计，同时适配 kimi-cli 的 WireMessage。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Union


# ---------------------------------------------------------------------------
# 事件类型定义
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AssistantTextDelta:
    """增量助手文本输出。"""

    text: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ToolExecutionStarted:
    """工具执行开始。"""

    tool_name: str
    tool_input: dict[str, Any]
    tool_call_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ToolExecutionCompleted:
    """工具执行完成。"""

    tool_name: str
    output: str
    is_error: bool = False
    tool_call_id: str = ""
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ErrorEvent:
    """错误事件。"""

    message: str
    recoverable: bool = True
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class StatusEvent:
    """状态事件。"""

    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class CompactProgressEvent:
    """上下文压缩进度事件。"""

    phase: Literal[
        "hooks_start",
        "context_collapse_start",
        "context_collapse_end",
        "session_memory_start",
        "session_memory_end",
        "compact_start",
        "compact_retry",
        "compact_end",
        "compact_failed",
    ]
    trigger: Literal["auto", "manual", "reactive"] = "auto"
    message: str | None = None
    attempt: int | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class SubagentEvent:
    """子 Agent 事件。"""

    agent_id: str
    agent_type: str
    event_type: Literal["started", "completed", "failed", "output"]
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class TurnEvent:
    """Turn 级别事件。"""

    event_type: Literal["turn_begin", "turn_end", "step_begin", "step_end", "step_interrupted"]
    turn_count: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class PermissionEvent:
    """权限检查事件。"""

    tool_name: str
    decision: Literal["allowed", "denied", "confirm"]
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# 联合类型
# ---------------------------------------------------------------------------

HarnessStreamEvent = Union[
    AssistantTextDelta,
    ToolExecutionStarted,
    ToolExecutionCompleted,
    ErrorEvent,
    StatusEvent,
    CompactProgressEvent,
    SubagentEvent,
    TurnEvent,
    PermissionEvent,
]

# 事件类型名称映射（用于 JSON 序列化）
_EVENT_TYPE_MAP: dict[type, str] = {
    AssistantTextDelta: "assistant_text_delta",
    ToolExecutionStarted: "tool_execution_started",
    ToolExecutionCompleted: "tool_execution_completed",
    ErrorEvent: "error",
    StatusEvent: "status",
    CompactProgressEvent: "compact_progress",
    SubagentEvent: "subagent",
    TurnEvent: "turn",
    PermissionEvent: "permission",
}


# ---------------------------------------------------------------------------
# JSON 序列化
# ---------------------------------------------------------------------------


def event_to_json(event: HarnessStreamEvent) -> str:
    """将事件序列化为 JSON 字符串。

    用于 ``--output-format stream-json`` 模式下的实时输出。

    Args:
        event: 任一 HarnessStreamEvent 子类实例。

    Returns:
        JSON 格式的事件字符串。
    """
    event_type = _EVENT_TYPE_MAP.get(type(event), "unknown")
    data = {
        "type": event_type,
        "timestamp": event.timestamp.isoformat(),
    }
    # 将 dataclass 字段加入 data
    for f in field(event):  # type: ignore[arg-type]
        value = getattr(event, f.name)
        if f.name == "timestamp":
            continue
        data[f.name] = value

    return json.dumps(data, ensure_ascii=False, default=str)


def event_from_dict(data: dict[str, Any]) -> HarnessStreamEvent:
    """从字典反序列化事件。"""
    event_type = data.get("type", "")
    ts = datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(timezone.utc)

    match event_type:
        case "assistant_text_delta":
            return AssistantTextDelta(text=data["text"], timestamp=ts)
        case "tool_execution_started":
            return ToolExecutionStarted(
                tool_name=data["tool_name"],
                tool_input=data.get("tool_input", {}),
                tool_call_id=data.get("tool_call_id", ""),
                timestamp=ts,
            )
        case "tool_execution_completed":
            return ToolExecutionCompleted(
                tool_name=data["tool_name"],
                output=data.get("output", ""),
                is_error=data.get("is_error", False),
                tool_call_id=data.get("tool_call_id", ""),
                duration_ms=data.get("duration_ms", 0.0),
                timestamp=ts,
            )
        case "error":
            return ErrorEvent(
                message=data["message"],
                recoverable=data.get("recoverable", True),
                timestamp=ts,
            )
        case "status":
            return StatusEvent(message=data["message"], timestamp=ts)
        case "compact_progress":
            return CompactProgressEvent(
                phase=data["phase"],
                trigger=data.get("trigger", "auto"),
                message=data.get("message"),
                attempt=data.get("attempt"),
                timestamp=ts,
            )
        case "subagent":
            return SubagentEvent(
                agent_id=data["agent_id"],
                agent_type=data["agent_type"],
                event_type=data.get("event_type", "started"),
                message=data.get("message", ""),
                timestamp=ts,
            )
        case "turn":
            return TurnEvent(
                event_type=data.get("event_type", "turn_begin"),
                turn_count=data.get("turn_count", 0),
                timestamp=ts,
            )
        case "permission":
            return PermissionEvent(
                tool_name=data["tool_name"],
                decision=data.get("decision", "confirm"),
                reason=data.get("reason", ""),
                timestamp=ts,
            )
        case _:
            return StatusEvent(message=f"Unknown event type: {event_type}", timestamp=ts)


# ---------------------------------------------------------------------------
# WireMessage → HarnessStreamEvent 适配器
# ---------------------------------------------------------------------------


class WireToStreamAdapter:
    """将 kimi-cli 的 WireMessage 转换为 HarnessStreamEvent.

    在 Wire 事件流和 Harness 标准事件之间建立桥梁，
    使外部监控工具可以使用统一的事件格式。
    """

    @staticmethod
    def convert(wire_message: Any) -> HarnessStreamEvent | None:
        """将 WireMessage 转换为 HarnessStreamEvent.

        Args:
            wire_message: kimi-cli 的 WireMessage 实例。

        Returns:
            对应的 HarnessStreamEvent，无法识别的消息返回 None。
        """
        # 延迟导入以避免循环依赖
        try:
            from kimi_cli.wire.types import (
                ContentPart,
                TextPart,
                ToolCall,
                ToolResult as WireToolResult,
                TurnBegin,
                TurnEnd,
                StepBegin,
                StepInterrupted,
            )
        except ImportError:
            return None

        match wire_message:
            case TextPart():
                return AssistantTextDelta(text=wire_message.text)
            case ToolCall():
                try:
                    args = json.loads(wire_message.function.arguments or "{}")
                except (json.JSONDecodeError, TypeError):
                    args = {}
                return ToolExecutionStarted(
                    tool_name=wire_message.function.name,
                    tool_input=args,
                    tool_call_id=wire_message.id,
                )
            case WireToolResult():
                is_error = hasattr(wire_message.return_value, "is_error")
                output = ""
                if hasattr(wire_message.return_value, "message"):
                    output = wire_message.return_value.message or ""
                elif hasattr(wire_message.return_value, "output"):
                    output = str(wire_message.return_value.output or "")
                _tool_name = getattr(wire_message, 'tool_name', '') or ''
                return ToolExecutionCompleted(
                    tool_name=_tool_name,
                    output=output,
                    is_error=is_error,
                    tool_call_id=wire_message.tool_call_id,
                )
            case TurnBegin():
                return TurnEvent(event_type="turn_begin", turn_count=0)
            case TurnEnd():
                return TurnEvent(event_type="turn_end", turn_count=0)
            case StepBegin():
                return TurnEvent(event_type="step_begin", turn_count=getattr(wire_message, 'n', 0))
            case StepInterrupted():
                return TurnEvent(event_type="step_interrupted", turn_count=0)
            case _:
                # 其他 WireMessage 类型转换为通用 StatusEvent
                msg_type = type(wire_message).__name__
                try:
                    data = wire_message.model_dump(mode="json", exclude_none=True)
                except Exception:
                    data = {}
                return StatusEvent(
                    message=f"wire:{msg_type}",
                    metadata={"wire_type": msg_type, "data": data},
                )
