"""Harness 权限系统 - 多级权限检查与安全治理.

提供对齐 OpenHarness 的多级权限检查能力，在 kimi-cli 现有
Approval 审批机制之上增加路径级规则、命令拒绝模式和敏感路径保护。
"""

from __future__ import annotations

import fnmatch
import logging
import os
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 敏感路径保护（内置，不可被用户配置覆盖）
# ---------------------------------------------------------------------------

SENSITIVE_PATH_PATTERNS: tuple[str, ...] = (
    # SSH 密钥和配置
    "*/.ssh/*",
    # AWS 凭证
    "*/.aws/credentials",
    "*/.aws/config",
    # GCP 凭证
    "*/.config/gcloud/*",
    # Azure 凭证
    "*/.azure/*",
    # GPG 密钥
    "*/.gnupg/*",
    # Docker 凭证
    "*/.docker/config.json",
    # Kubernetes 凭证
    "*/.kube/config",
    # Kimi Harness 自身凭证
    "*/.kimi-harness/credentials*",
    "*/.kimi-harness/oauth*",
)


# ---------------------------------------------------------------------------
# 权限模式
# ---------------------------------------------------------------------------


class PermissionMode(str, Enum):
    """权限模式枚举。

    Attributes:
        DEFAULT: 默认模式 - 写操作需用户确认。
        FULL_AUTO: 全自动模式 - 允许一切（适用于沙箱环境）。
        PLAN: 计划模式 - 阻止所有写操作。
        DONT_ASK: 不询问模式 - 自动批准写操作。
        ACCEPT_EDITS: 接受编辑模式 - 自动批准文件编辑。
    """

    DEFAULT = "default"
    FULL_AUTO = "full_auto"
    PLAN = "plan"
    DONT_ASK = "dont_ask"
    ACCEPT_EDITS = "accept_edits"


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PermissionDecision:
    """权限检查结果。

    Attributes:
        allowed: 是否允许执行。
        requires_confirmation: 是否需要用户确认。
        reason: 决策原因（用于日志和 UI 显示）。
    """

    allowed: bool
    requires_confirmation: bool = False
    reason: str = ""

    @staticmethod
    def allow(reason: str = "") -> PermissionDecision:
        return PermissionDecision(allowed=True, reason=reason)

    @staticmethod
    def deny(reason: str = "") -> PermissionDecision:
        return PermissionDecision(allowed=False, reason=reason)

    @staticmethod
    def confirm(reason: str = "") -> PermissionDecision:
        return PermissionDecision(allowed=False, requires_confirmation=True, reason=reason)


@dataclass(frozen=True)
class PathRule:
    """路径级权限规则。

    Attributes:
        pattern: Glob 匹配模式（如 ``/etc/*``）。
        allow: True 表示允许，False 表示拒绝。
    """

    pattern: str
    allow: bool


@dataclass
class PermissionSettings:
    """权限配置。

    Attributes:
        mode: 权限模式。
        denied_tools: 显式拒绝的工具名称集合。
        allowed_tools: 显式允许的工具名称集合。
        denied_commands: 拒绝的命令模式列表（fnmatch 语法）。
        path_rules: 路径级权限规则列表。
    """

    mode: PermissionMode = PermissionMode.DEFAULT
    denied_tools: set[str] = field(default_factory=set)
    allowed_tools: set[str] = field(default_factory=set)
    denied_commands: list[str] = field(default_factory=list)
    path_rules: list[PathRule] = field(default_factory=list)


# ---------------------------------------------------------------------------
# PermissionChecker
# ---------------------------------------------------------------------------


class PermissionChecker:
    """多级权限检查器.

    检查流程：
    1. 内置敏感路径保护（始终生效，不可覆盖）
    2. 显式工具拒绝列表
    3. 显式工具允许列表
    4. 路径级 glob 规则
    5. 命令拒绝模式
    6. 权限模式判断（FULL_AUTO / PLAN / DEFAULT）
    7. 只读工具自动放行

    Usage::

        settings = PermissionSettings(
            mode=PermissionMode.DEFAULT,
            denied_commands=["rm -rf /*", "DROP TABLE *"],
        )
        checker = PermissionChecker(settings)
        decision = checker.evaluate("bash", is_read_only=False, command="rm -rf /")
        if not decision.allowed:
            print(f"Blocked: {decision.reason}")
    """

    def __init__(self, settings: PermissionSettings | None = None) -> None:
        self._settings = settings or PermissionSettings()

    @property
    def mode(self) -> PermissionMode:
        """当前权限模式。"""
        return self._settings.mode

    def set_mode(self, mode: PermissionMode) -> None:
        """动态切换权限模式。"""
        old_mode = self._settings.mode
        self._settings.mode = mode
        logger.info("Permission mode changed: %s -> %s", old_mode, mode)

    def evaluate(
        self,
        tool_name: str,
        *,
        is_read_only: bool = False,
        file_path: str | None = None,
        command: str | None = None,
    ) -> PermissionDecision:
        """评估工具调用是否被允许。

        Args:
            tool_name: 工具名称。
            is_read_only: 是否为只读操作。
            file_path: 操作的文件路径（用于路径规则匹配）。
            command: 要执行的命令（用于命令拒绝模式匹配）。

        Returns:
            权限决策结果。
        """
        # 0. 规范化文件路径，防止 /etc/./passwd 等变体绕过
        if file_path:
            file_path = os.path.normpath(file_path)

        # 1. 内置敏感路径保护
        if file_path:
            for candidate_path in _policy_match_paths(file_path):
                for pattern in SENSITIVE_PATH_PATTERNS:
                    if fnmatch.fnmatch(candidate_path, pattern):
                        return PermissionDecision.deny(
                            f"Access denied: {file_path} matches sensitive path pattern '{pattern}'"
                        )

        # 2. 显式工具拒绝列表
        if tool_name in self._settings.denied_tools:
            return PermissionDecision.deny(f"Tool '{tool_name}' is explicitly denied")

        # 3. 显式工具允许列表
        if tool_name in self._settings.allowed_tools:
            return PermissionDecision.allow(f"Tool '{tool_name}' is explicitly allowed")

        # 4. 路径级规则
        if file_path and self._settings.path_rules:
            for candidate_path in _policy_match_paths(file_path):
                for rule in self._settings.path_rules:
                    if fnmatch.fnmatch(candidate_path, rule.pattern):
                        if not rule.allow:
                            return PermissionDecision.deny(
                                f"Path {file_path} matches deny rule: {rule.pattern}"
                            )
                        return PermissionDecision.allow(
                            f"Path {file_path} matches allow rule: {rule.pattern}"
                        )

        # 5. 命令拒绝模式
        if command:
            for pattern in self._settings.denied_commands:
                if fnmatch.fnmatch(command, pattern):
                    return PermissionDecision.deny(
                        f"Command matches deny pattern: {pattern}"
                    )

        # 6. 权限模式判断
        mode = self._settings.mode

        if mode == PermissionMode.FULL_AUTO:
            return PermissionDecision.allow("Full auto mode allows all tools")

        if mode == PermissionMode.DONT_ASK:
            return PermissionDecision.allow("Dont-ask mode allows all tools")

        if mode == PermissionMode.ACCEPT_EDITS:
            # 编辑类工具自动放行，其他写操作仍需确认
            edit_tools = {"write_file", "str_replace_file", "file_edit", "file_write"}
            if tool_name.lower() in edit_tools:
                return PermissionDecision.allow("Accept-edits mode allows file edits")
            return PermissionDecision.confirm(
                "Non-edit mutating tools require confirmation in accept-edits mode"
            )

        if mode == PermissionMode.PLAN:
            if is_read_only:
                return PermissionDecision.allow("Read-only tools are allowed in plan mode")
            return PermissionDecision.deny(
                "Plan mode blocks mutating tools until the user exits plan mode"
            )

        # 7. 只读工具自动放行
        if is_read_only:
            return PermissionDecision.allow("Read-only tools are always allowed")

        # 8. 默认模式：需要用户确认
        return PermissionDecision.confirm(
            "Mutating tools require user confirmation in default mode"
        )


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _policy_match_paths(file_path: str) -> tuple[str, ...]:
    """返回参与策略匹配的路径形式。

    目录级工具（如 grep、glob）可能操作目录根路径，
    追加 ``/`` 后缀使 ``*/.ssh/*`` 等 glob 模式能匹配目录本身。
    """
    normalized = file_path.rstrip("/")
    if not normalized:
        return (file_path,)
    return (normalized, normalized + "/")


def create_default_settings() -> PermissionSettings:
    """创建默认权限配置。

    包含常见的危险命令拒绝模式。
    """
    return PermissionSettings(
        mode=PermissionMode.DEFAULT,
        denied_commands=[
            "rm -rf /*",
            "rm -rf /",
            "DROP TABLE *",
            "DROP DATABASE *",
            "mkfs.*",
            "dd if=* of=/dev/*",
            ":(){ :|:& };:",  # fork bomb
            "chmod -R 777 /*",
            "chown -R * /*",
        ],
        path_rules=[
            PathRule(pattern="/etc/*", allow=False),
            PathRule(pattern="/System/*", allow=False),
            PathRule(pattern="/usr/*", allow=False),
            PathRule(pattern="/bin/*", allow=False),
            PathRule(pattern="/sbin/*", allow=False),
        ],
    )
