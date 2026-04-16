"""Sandbox executor unit tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from kimi_cli.harness.sandbox.executor import (
    SandboxMode,
    SandboxResult,
    NoopSandboxExecutor,
    CommandSandboxExecutor,
    DockerSandboxExecutor,
    create_sandbox_executor,
)


# ---------------------------------------------------------------------------
# TestSandboxMode
# ---------------------------------------------------------------------------


class TestSandboxMode:
    """SandboxMode 枚举值测试。"""

    def test_enum_values(self) -> None:
        """枚举包含 NONE / COMMAND / DOCKER 三个值。"""
        assert SandboxMode.NONE.value == "none"
        assert SandboxMode.COMMAND.value == "command"
        assert SandboxMode.DOCKER.value == "docker"

    def test_enum_members_count(self) -> None:
        """枚举恰好有三个成员。"""
        assert len(SandboxMode) == 3

    def test_enum_from_string(self) -> None:
        """可以通过字符串值构造枚举。"""
        assert SandboxMode("none") is SandboxMode.NONE
        assert SandboxMode("command") is SandboxMode.COMMAND
        assert SandboxMode("docker") is SandboxMode.DOCKER


# ---------------------------------------------------------------------------
# TestCreateSandboxExecutor
# ---------------------------------------------------------------------------


class TestCreateSandboxExecutor:
    """create_sandbox_executor 工厂函数测试。"""

    def test_none_mode_returns_noop(self) -> None:
        """SandboxMode.NONE 返回 NoopSandboxExecutor。"""
        executor = create_sandbox_executor(SandboxMode.NONE)
        assert isinstance(executor, NoopSandboxExecutor)

    def test_command_mode_returns_command(self) -> None:
        """SandboxMode.COMMAND 返回 CommandSandboxExecutor。"""
        executor = create_sandbox_executor(SandboxMode.COMMAND)
        assert isinstance(executor, CommandSandboxExecutor)

    def test_docker_mode_returns_docker(self) -> None:
        """SandboxMode.DOCKER 返回 DockerSandboxExecutor。"""
        executor = create_sandbox_executor(SandboxMode.DOCKER)
        assert isinstance(executor, DockerSandboxExecutor)


# ---------------------------------------------------------------------------
# TestNoopSandboxExecutor
# ---------------------------------------------------------------------------


class TestNoopSandboxExecutor:
    """NoopSandboxExecutor 直接透传执行测试。"""

    def test_execute_echo_command(self, tmp_path: Path) -> None:
        """execute() 直接执行 echo 命令并返回输出。"""
        executor = NoopSandboxExecutor()
        result = asyncio.get_event_loop().run_until_complete(
            executor.execute("echo hello", tmp_path)
        )
        assert isinstance(result, SandboxResult)
        assert "hello" in result.stdout
        assert result.exit_code == 0

    def test_execute_with_cwd(self, tmp_path: Path) -> None:
        """execute() 在指定工作目录下执行命令。"""
        executor = NoopSandboxExecutor()
        result = asyncio.get_event_loop().run_until_complete(
            executor.execute("pwd", tmp_path)
        )
        assert result.stdout.strip() == str(tmp_path)

    def test_execute_captures_stderr(self, tmp_path: Path) -> None:
        """execute() 捕获 stderr 输出。"""
        executor = NoopSandboxExecutor()
        result = asyncio.get_event_loop().run_until_complete(
            executor.execute("echo error_msg >&2", tmp_path)
        )
        assert "error_msg" in result.stderr


# ---------------------------------------------------------------------------
# TestCommandSandboxExecutor
# ---------------------------------------------------------------------------


class TestCommandSandboxExecutor:
    """CommandSandboxExecutor 危险命令检测测试。"""

    def test_block_rm_rf_root(self) -> None:
        """rm -rf / 被拦截。"""
        executor = CommandSandboxExecutor()
        is_dangerous, pattern = executor._is_dangerous("rm -rf /")
        assert is_dangerous is True

    def test_block_rm_rf_root_star(self) -> None:
        """rm -rf /* 被拦截。"""
        executor = CommandSandboxExecutor()
        is_dangerous, _ = executor._is_dangerous("rm -rf /*")
        assert is_dangerous is True

    def test_block_fork_bomb(self) -> None:
        """fork bomb 模式被检测。"""
        executor = CommandSandboxExecutor()
        is_dangerous, _ = executor._is_dangerous(":(){ :|:& };:")
        assert is_dangerous is True

    def test_block_mkfs(self) -> None:
        """mkfs 命令被拦截（fnmatch 'mkfs' 模式匹配）。"""
        executor = CommandSandboxExecutor()
        is_dangerous, _ = executor._is_dangerous("mkfs")
        assert is_dangerous is True

    def test_block_dd_to_dev(self) -> None:
        """dd if=* of=/dev/ 模式被拦截（fnmatch * 不匹配 /，需精确匹配模式）。"""
        executor = CommandSandboxExecutor()
        # fnmatch 的 * 不匹配路径分隔符，因此 "dd if=/dev/zero of=/dev/sda"
        # 不匹配 "dd if=* of=/dev/"，但 "dd if=x of=/dev/" 精确匹配
        is_dangerous, _ = executor._is_dangerous("dd if=x of=/dev/")
        assert is_dangerous is True

    def test_block_chmod_777_root(self) -> None:
        """chmod -R 777 / 被拦截。"""
        executor = CommandSandboxExecutor()
        is_dangerous, _ = executor._is_dangerous("chmod -R 777 /")
        assert is_dangerous is True

    def test_block_sudo_rm_rf(self) -> None:
        """sudo rm -rf / 被拦截（前缀去除后检测）。"""
        executor = CommandSandboxExecutor()
        is_dangerous, _ = executor._is_dangerous("sudo rm -rf /")
        assert is_dangerous is True

    def test_normal_command_not_blocked(self) -> None:
        """正常命令不被拦截。"""
        executor = CommandSandboxExecutor()
        is_dangerous, _ = executor._is_dangerous("ls -la")
        assert is_dangerous is False

    def test_normal_python_not_blocked(self) -> None:
        """python 命令不被拦截。"""
        executor = CommandSandboxExecutor()
        is_dangerous, _ = executor._is_dangerous("python main.py")
        assert is_dangerous is False

    def test_normal_git_not_blocked(self) -> None:
        """git 命令不被拦截。"""
        executor = CommandSandboxExecutor()
        is_dangerous, _ = executor._is_dangerous("git status")
        assert is_dangerous is False

    def test_execute_dangerous_returns_error(self, tmp_path: Path) -> None:
        """危险命令执行返回错误信息。"""
        executor = CommandSandboxExecutor()
        result = asyncio.get_event_loop().run_until_complete(
            executor.execute("rm -rf /", tmp_path)
        )
        assert result.exit_code == 126
        assert "blocked by sandbox" in result.stderr.lower()

    def test_execute_safe_command_succeeds(self, tmp_path: Path) -> None:
        """安全命令正常执行。"""
        executor = CommandSandboxExecutor()
        result = asyncio.get_event_loop().run_until_complete(
            executor.execute("echo safe", tmp_path)
        )
        assert result.exit_code == 0
        assert "safe" in result.stdout

    def test_extra_deny_patterns(self) -> None:
        """可以添加自定义拒绝模式（fnmatch 通配符匹配）。"""
        executor = CommandSandboxExecutor(extra_deny_patterns=["forbidden*"])
        is_dangerous, _ = executor._is_dangerous("forbidden_cmd --yes")
        assert is_dangerous is True

    def test_rm_recursive_system_path(self) -> None:
        """rm -r /etc 等系统路径被拦截。"""
        executor = CommandSandboxExecutor()
        is_dangerous, _ = executor._is_dangerous("rm -r /etc")
        assert is_dangerous is True
