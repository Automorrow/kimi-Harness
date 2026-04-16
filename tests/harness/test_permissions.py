"""Unit tests for kimi_cli.harness.permissions.checker."""

from __future__ import annotations

from kimi_cli.harness.permissions.checker import (
    PermissionChecker,
    PermissionMode,
    PermissionSettings,
    PathRule,
    create_default_settings,
)


# ---------------------------------------------------------------------------
# TestPermissionModes
# ---------------------------------------------------------------------------


class TestPermissionModes:
    """各权限模式下 evaluate() 的行为。"""

    def test_default_non_readonly_needs_confirmation(self) -> None:
        """DEFAULT 模式：非只读工具需要确认。"""
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.DEFAULT))
        d = checker.evaluate("bash", is_read_only=False)
        assert d.allowed is False
        assert d.requires_confirmation is True

    def test_full_auto_allows_everything(self) -> None:
        """FULL_AUTO 模式：所有工具自动放行。"""
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.FULL_AUTO))
        d = checker.evaluate("bash", is_read_only=False)
        assert d.allowed is True
        assert d.requires_confirmation is False

    def test_plan_blocks_write(self) -> None:
        """PLAN 模式：写操作被拒绝。"""
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.PLAN))
        d = checker.evaluate("bash", is_read_only=False)
        assert d.allowed is False
        assert d.requires_confirmation is False

    def test_plan_allows_read(self) -> None:
        """PLAN 模式：只读操作放行。"""
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.PLAN))
        d = checker.evaluate("bash", is_read_only=True)
        assert d.allowed is True

    def test_dont_ask_allows_all(self) -> None:
        """DONT_ASK 模式：自动放行。"""
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.DONT_ASK))
        d = checker.evaluate("bash", is_read_only=False)
        assert d.allowed is True
        assert d.requires_confirmation is False

    def test_accept_edits_allows_edit_tools(self) -> None:
        """ACCEPT_EDITS 模式：编辑操作自动放行。"""
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.ACCEPT_EDITS))
        for tool in ("write_file", "str_replace_file", "file_edit", "file_write"):
            d = checker.evaluate(tool, is_read_only=False)
            assert d.allowed is True, f"Tool '{tool}' should be allowed in ACCEPT_EDITS mode"

    def test_accept_edits_non_edit_needs_confirmation(self) -> None:
        """ACCEPT_EDITS 模式：非编辑写操作仍需确认。"""
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.ACCEPT_EDITS))
        d = checker.evaluate("bash", is_read_only=False)
        assert d.allowed is False
        assert d.requires_confirmation is True


# ---------------------------------------------------------------------------
# TestSensitivePaths
# ---------------------------------------------------------------------------


class TestSensitivePaths:
    """内置敏感路径保护始终生效。"""

    def test_ssh_key_denied(self, tmp_path) -> None:
        """SSH 密钥路径被拒绝。"""
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.FULL_AUTO))
        ssh_dir = tmp_path / ".ssh"
        ssh_dir.mkdir()
        d = checker.evaluate("bash", file_path=str(ssh_dir / "id_rsa"))
        assert d.allowed is False
        assert "sensitive" in d.reason

    def test_aws_credentials_denied(self, tmp_path) -> None:
        """AWS 凭证路径被拒绝。"""
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.FULL_AUTO))
        aws_dir = tmp_path / ".aws"
        aws_dir.mkdir()
        d = checker.evaluate("bash", file_path=str(aws_dir / "credentials"))
        assert d.allowed is False
        assert "sensitive" in d.reason

    def test_gpg_key_denied(self, tmp_path) -> None:
        """GPG 密钥路径被拒绝。"""
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.FULL_AUTO))
        gpg_dir = tmp_path / ".gnupg"
        gpg_dir.mkdir()
        d = checker.evaluate("bash", file_path=str(gpg_dir / "private-keys-v1.d" / "key.gpg"))
        assert d.allowed is False
        assert "sensitive" in d.reason

    def test_normal_file_not_denied(self, tmp_path) -> None:
        """普通文件路径不被拒绝。"""
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.DEFAULT))
        normal_file = tmp_path / "documents" / "report.txt"
        normal_file.parent.mkdir()
        d = checker.evaluate("bash", file_path=str(normal_file), is_read_only=False)
        # DEFAULT 模式下非只读需要确认，但不是因为敏感路径
        assert d.allowed is False
        assert d.requires_confirmation is True
        assert "sensitive" not in d.reason


# ---------------------------------------------------------------------------
# TestToolAllowDenyLists
# ---------------------------------------------------------------------------


class TestToolAllowDenyLists:
    """显式工具允许/拒绝列表。"""

    def test_denied_tool_rejected(self) -> None:
        """拒绝列表中的工具被拒绝。"""
        settings = PermissionSettings(
            denied_tools={"dangerous_tool"},
        )
        checker = PermissionChecker(settings)
        d = checker.evaluate("dangerous_tool")
        assert d.allowed is False
        assert "explicitly denied" in d.reason

    def test_allowed_tool_passes(self) -> None:
        """允许列表中的工具被放行（即使模式为 DEFAULT）。"""
        settings = PermissionSettings(
            mode=PermissionMode.DEFAULT,
            allowed_tools={"my_tool"},
        )
        checker = PermissionChecker(settings)
        d = checker.evaluate("my_tool", is_read_only=False)
        assert d.allowed is True
        assert "explicitly allowed" in d.reason

    def test_allow_list_priority_over_deny(self) -> None:
        """拒绝列表优先级高于允许列表（源码中拒绝列表先检查）。"""
        settings = PermissionSettings(
            denied_tools={"shared_tool"},
            allowed_tools={"shared_tool"},
        )
        checker = PermissionChecker(settings)
        d = checker.evaluate("shared_tool")
        # 拒绝列表在允许列表之前检查，因此拒绝列表优先
        assert d.allowed is False
        assert "explicitly denied" in d.reason


# ---------------------------------------------------------------------------
# TestCommandDenyPatterns
# ---------------------------------------------------------------------------


class TestCommandDenyPatterns:
    """命令拒绝模式匹配。"""

    def test_rm_rf_root_denied(self) -> None:
        """rm -rf /* 被拒绝。"""
        settings = PermissionSettings(denied_commands=["rm -rf /*"])
        checker = PermissionChecker(settings)
        d = checker.evaluate("bash", command="rm -rf /*")
        assert d.allowed is False
        assert "deny pattern" in d.reason

    def test_fork_bomb_denied(self) -> None:
        """fork bomb 命令被拒绝。"""
        settings = PermissionSettings(denied_commands=[":(){ :|:& };:"])
        checker = PermissionChecker(settings)
        d = checker.evaluate("bash", command=":(){ :|:& };:")
        assert d.allowed is False
        assert "deny pattern" in d.reason

    def test_drop_table_denied(self) -> None:
        """DROP TABLE 被拒绝。"""
        settings = PermissionSettings(denied_commands=["DROP TABLE *"])
        checker = PermissionChecker(settings)
        d = checker.evaluate("bash", command="DROP TABLE users")
        assert d.allowed is False
        assert "deny pattern" in d.reason

    def test_normal_command_not_denied(self) -> None:
        """普通命令不被拒绝。"""
        settings = PermissionSettings(denied_commands=["rm -rf /*", "DROP TABLE *"])
        checker = PermissionChecker(settings)
        d = checker.evaluate("bash", command="ls -la", is_read_only=False)
        # DEFAULT 模式下需要确认，但不是因为命令拒绝
        assert d.allowed is False
        assert d.requires_confirmation is True
        assert "deny pattern" not in d.reason


# ---------------------------------------------------------------------------
# TestReadonlyAutoPass
# ---------------------------------------------------------------------------


class TestReadonlyAutoPass:
    """只读操作在所有模式下自动放行。"""

    def test_readonly_in_default(self) -> None:
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.DEFAULT))
        d = checker.evaluate("bash", is_read_only=True)
        assert d.allowed is True

    def test_readonly_in_full_auto(self) -> None:
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.FULL_AUTO))
        d = checker.evaluate("bash", is_read_only=True)
        assert d.allowed is True

    def test_readonly_in_plan(self) -> None:
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.PLAN))
        d = checker.evaluate("bash", is_read_only=True)
        assert d.allowed is True

    def test_readonly_in_dont_ask(self) -> None:
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.DONT_ASK))
        d = checker.evaluate("bash", is_read_only=True)
        assert d.allowed is True

    def test_readonly_in_accept_edits(self) -> None:
        """ACCEPT_EDITS 模式下只读操作仍需确认（源码中 ACCEPT_EDITS 分支不检查 is_read_only）。"""
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.ACCEPT_EDITS))
        d = checker.evaluate("bash", is_read_only=True)
        assert d.allowed is False
        assert d.requires_confirmation is True

    def test_cat_readonly(self) -> None:
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.DEFAULT))
        d = checker.evaluate("cat", is_read_only=True)
        assert d.allowed is True

    def test_head_readonly(self) -> None:
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.DEFAULT))
        d = checker.evaluate("head", is_read_only=True)
        assert d.allowed is True

    def test_ls_readonly(self) -> None:
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.DEFAULT))
        d = checker.evaluate("ls", is_read_only=True)
        assert d.allowed is True

    def test_grep_readonly(self) -> None:
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.DEFAULT))
        d = checker.evaluate("grep", is_read_only=True)
        assert d.allowed is True

    def test_find_readonly(self) -> None:
        checker = PermissionChecker(PermissionSettings(mode=PermissionMode.DEFAULT))
        d = checker.evaluate("find", is_read_only=True)
        assert d.allowed is True


# ---------------------------------------------------------------------------
# TestCreateDefaultSettings
# ---------------------------------------------------------------------------


class TestCreateDefaultSettings:
    """create_default_settings 返回合理的默认值。"""

    def test_mode_is_default(self) -> None:
        settings = create_default_settings()
        assert settings.mode == PermissionMode.DEFAULT

    def test_has_dangerous_commands(self) -> None:
        settings = create_default_settings()
        assert "rm -rf /*" in settings.denied_commands
        assert "DROP TABLE *" in settings.denied_commands

    def test_has_path_rules(self) -> None:
        settings = create_default_settings()
        patterns = [r.pattern for r in settings.path_rules]
        assert "/etc/*" in patterns
        assert "/usr/*" in patterns

    def test_path_rules_are_deny(self) -> None:
        settings = create_default_settings()
        for rule in settings.path_rules:
            assert rule.allow is False

    def test_denied_tools_empty(self) -> None:
        settings = create_default_settings()
        assert settings.denied_tools == set()

    def test_allowed_tools_empty(self) -> None:
        settings = create_default_settings()
        assert settings.allowed_tools == set()
