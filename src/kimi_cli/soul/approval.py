from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Literal

from kimi_cli.approval_runtime import (
    ApprovalCancelledError,
    ApprovalRuntime,
    ApprovalSource,
    get_current_approval_source_or_none,
)
from kimi_cli.soul.toolset import get_current_tool_call_or_none
from kimi_cli.tools.utils import ToolRejectedError
from kimi_cli.utils.logging import logger
from kimi_cli.wire.types import DisplayBlock

type Response = Literal["approve", "approve_for_session", "reject"]


class ApprovalResult:
    """Result of an approval request. Behaves as bool for backward compatibility."""

    __slots__ = ("approved", "feedback")

    def __init__(self, approved: bool, feedback: str = ""):
        self.approved = approved
        self.feedback = feedback

    def __bool__(self) -> bool:
        return self.approved

    def rejection_error(self) -> ToolRejectedError:
        if self.feedback:
            return ToolRejectedError(
                message=(f"The tool call is rejected by the user. User feedback: {self.feedback}"),
                brief=f"Rejected: {self.feedback}",
                has_feedback=True,
            )
        source = get_current_approval_source_or_none()
        is_subagent = source is not None and source.agent_id is not None
        if is_subagent:
            return ToolRejectedError(
                message=(
                    "The tool call is rejected by the user. "
                    "Try a different approach to complete your task, or explain the "
                    "limitation in your summary if no alternative is available. "
                    "Do not retry the same tool call, and do not attempt to bypass "
                    "this restriction through indirect means."
                ),
            )
        return ToolRejectedError()


class ApprovalState:
    def __init__(
        self,
        yolo: bool = False,
        auto_approve_actions: set[str] | None = None,
        on_change: Callable[[], None] | None = None,
    ):
        self.yolo = yolo
        self.auto_approve_actions: set[str] = auto_approve_actions or set()
        """Set of action names that should automatically be approved."""
        self._on_change = on_change

    def notify_change(self) -> None:
        if self._on_change is not None:
            self._on_change()


class Approval:
    def __init__(
        self,
        yolo: bool = False,
        *,
        state: ApprovalState | None = None,
        runtime: ApprovalRuntime | None = None,
    ):
        self._state = state or ApprovalState(yolo=yolo)
        self._runtime = runtime or ApprovalRuntime()
        self._permission_checker: Any = None

    def share(self) -> Approval:
        """Create a new approval queue that shares state (yolo + auto-approve)."""
        shared = Approval(state=self._state, runtime=self._runtime)
        shared._permission_checker = self._permission_checker
        return shared

    def set_runtime(self, runtime: ApprovalRuntime) -> None:
        self._runtime = runtime

    def set_permission_checker(self, checker: Any) -> None:
        """Set the Harness PermissionChecker for programmatic permission evaluation.

        When set, the checker runs before yolo/auto-approve logic.
        DENY decisions are final and cannot be overridden by yolo.
        CONFIRM decisions fall through to normal user confirmation.
        """
        self._permission_checker = checker

    @property
    def runtime(self) -> ApprovalRuntime:
        return self._runtime

    def set_yolo(self, yolo: bool) -> None:
        self._state.yolo = yolo
        self._state.notify_change()

    def is_yolo(self) -> bool:
        return self._state.yolo

    async def request(
        self,
        sender: str,
        action: str,
        description: str,
        display: list[DisplayBlock] | None = None,
    ) -> ApprovalResult:
        """
        Request approval for the given action. Intended to be called by tools.

        Args:
            sender (str): The name of the sender.
            action (str): The action to request approval for.
                This is used to identify the action for auto-approval.
            description (str): The description of the action. This is used to display to the user.

        Returns:
            ApprovalResult: Result with ``approved`` flag and optional ``feedback``.
                Behaves as ``bool`` via ``__bool__``, so ``if not result:`` works.

        Raises:
            RuntimeError: If the approval is requested from outside a tool call.
        """
        tool_call = get_current_tool_call_or_none()
        if tool_call is None:
            raise RuntimeError("Approval must be requested from a tool call.")

        logger.debug(
            "{tool_name} ({tool_call_id}) requesting approval: {action} {description}",
            tool_name=tool_call.function.name,
            tool_call_id=tool_call.id,
            action=action,
            description=description,
        )

        # --- Harness PermissionChecker 前置检查 ---
        if self._permission_checker is not None:
            try:
                # 尝试从 description 中提取文件路径
                _file_path: str | None = None
                if description:
                    for prefix in ("file ", "path "):
                        if prefix in description.lower():
                            idx = description.lower().index(prefix)
                            _file_path = description[idx + len(prefix):].strip().split()[0]
                            break

                decision = self._permission_checker.evaluate(
                    tool_call.function.name,
                    is_read_only=(action in _READONLY_ACTIONS),
                    file_path=_file_path,
                    command=description if "command" in action.lower() else None,
                )
                if not decision.allowed and not decision.requires_confirmation:
                    logger.info(
                        "Permission denied by harness checker: {tool} - {reason}",
                        tool=tool_call.function.name,
                        reason=decision.reason,
                    )
                    return ApprovalResult(approved=False, feedback=decision.reason)
                if decision.requires_confirmation:
                    # CONFIRM 决策跳过 yolo/auto-approve，直接走用户确认
                    logger.info(
                        "Permission requires confirmation by harness checker: {tool} - {reason}",
                        tool=tool_call.function.name,
                        reason=decision.reason,
                    )
                    # 不 return，fall-through 到用户确认流程（跳过下面的 yolo 检查）
                    _harness_confirmed = True
                else:
                    _harness_confirmed = False
            except Exception:
                logger.debug("Harness permission check failed, falling back to default", exc_info=True)
                _harness_confirmed = False
        else:
            _harness_confirmed = False

        if not _harness_confirmed and self._state.yolo:
            return ApprovalResult(approved=True)

        if action in self._state.auto_approve_actions:
            return ApprovalResult(approved=True)

        request_id = str(uuid.uuid4())
        display_blocks = display or []
        source = get_current_approval_source_or_none() or ApprovalSource(
            kind="foreground_turn",
            id=tool_call.id,
        )
        self._runtime.create_request(
            request_id=request_id,
            tool_call_id=tool_call.id,
            sender=sender,
            action=action,
            description=description,
            display=display_blocks,
            source=source,
        )
        try:
            response, feedback = await self._runtime.wait_for_response(request_id)
        except ApprovalCancelledError:
            return ApprovalResult(approved=False)
        match response:
            case "approve":
                return ApprovalResult(approved=True)
            case "approve_for_session":
                self._state.auto_approve_actions.add(action)
                self._state.notify_change()
                for pending in self._runtime.list_pending():
                    if pending.action == action:
                        self._runtime.resolve(pending.id, "approve")
                return ApprovalResult(approved=True)
            case "reject":
                return ApprovalResult(approved=False, feedback=feedback)
            case _:
                return ApprovalResult(approved=False)


# Actions that are considered read-only for permission checking.
_READONLY_ACTIONS: frozenset[str] = frozenset({
    "read file",
    "list directory",
    "search",
    "web search",
    "web fetch",
    "list mcp resources",
    "read mcp resource",
    "tool search",
    "ask user",
    "brief",
    "config",
})
