"""Harness 沙箱执行环境.

提供工具执行的沙箱隔离能力，防止 Agent 操作影响宿主系统。
支持轻量级（命令级）和容器级（Docker）两种隔离模式。
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 沙箱模式
# ---------------------------------------------------------------------------


class SandboxMode(str, Enum):
    """沙箱隔离模式。

    Attributes:
        NONE: 无隔离（直接执行）。
        COMMAND: 命令级隔离（过滤危险命令）。
        DOCKER: 容器级隔离（Docker 容器内执行）。
    """

    NONE = "none"
    COMMAND = "command"
    DOCKER = "docker"


# ---------------------------------------------------------------------------
# 执行结果
# ---------------------------------------------------------------------------


@dataclass
class SandboxResult:
    """沙箱执行结果。

    Attributes:
        stdout: 标准输出。
        stderr: 标准错误。
        exit_code: 退出码。
        timed_out: 是否超时。
    """

    stdout: str
    stderr: str
    exit_code: int = 0
    timed_out: bool = False


# ---------------------------------------------------------------------------
# 沙箱执行器抽象
# ---------------------------------------------------------------------------


class SandboxExecutor(ABC):
    """沙箱执行器抽象基类。"""

    @abstractmethod
    async def execute(
        self,
        command: str,
        cwd: str | Path,
        *,
        timeout_seconds: float = 120,
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        """在沙箱中执行命令。"""


# ---------------------------------------------------------------------------
# 无隔离执行器
# ---------------------------------------------------------------------------


class NoopSandboxExecutor(SandboxExecutor):
    """无隔离执行器 - 直接在宿主系统执行命令。"""

    async def execute(
        self,
        command: str,
        cwd: str | Path,
        *,
        timeout_seconds: float = 120,
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        """直接执行命令（无隔离）。"""
        import asyncio

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_seconds,
            )
            return SandboxResult(
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                exit_code=proc.returncode or 0,
            )
        except asyncio.TimeoutError:
            proc.kill()  # type: ignore[union-attr]
            await proc.wait()  # type: ignore[union-attr]
            return SandboxResult(
                stdout="",
                stderr=f"Command timed out after {timeout_seconds}s",
                exit_code=-1,
                timed_out=True,
            )


# ---------------------------------------------------------------------------
# 命令级隔离执行器
# ---------------------------------------------------------------------------


# 危险命令模式
_DANGEROUS_COMMAND_PATTERNS: list[str] = [
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=* of=/dev/",
    "chmod -R 777 /",
    "chown -R",
    ":(){ :|:& };:",
]


class CommandSandboxExecutor(SandboxExecutor):
    """命令级隔离执行器 - 过滤危险命令后执行。

    在执行前检查命令是否匹配危险模式，匹配则拒绝执行。
    """

    def __init__(self, extra_deny_patterns: list[str] | None = None) -> None:
        self._deny_patterns = list(_DANGEROUS_COMMAND_PATTERNS)
        if extra_deny_patterns:
            self._deny_patterns.extend(extra_deny_patterns)

    async def execute(
        self,
        command: str,
        cwd: str | Path,
        *,
        timeout_seconds: float = 120,
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        """检查命令安全性后执行。"""
        import fnmatch

        stripped = command.strip()
        for pattern in self._deny_patterns:
            if fnmatch.fnmatch(stripped, pattern):
                return SandboxResult(
                    stdout="",
                    stderr=f"Command blocked by sandbox: matches dangerous pattern '{pattern}'",
                    exit_code=126,
                )

        # 安全检查通过，委托给 NoopExecutor
        executor = NoopSandboxExecutor()
        return await executor.execute(
            command, cwd,
            timeout_seconds=timeout_seconds,
            env=env,
        )


# ---------------------------------------------------------------------------
# Docker 沙箱执行器
# ---------------------------------------------------------------------------


class DockerSandboxExecutor(SandboxExecutor):
    """Docker 容器级隔离执行器.

    在 Docker 容器中执行命令，提供完整的文件系统隔离。
    """

    def __init__(
        self,
        *,
        image: str = "python:3.12-slim",
        network_disabled: bool = True,
        memory_limit: str = "512m",
        cpu_limit: float = 1.0,
    ) -> None:
        self._image = image
        self._network_disabled = network_disabled
        self._memory_limit = memory_limit
        self._cpu_limit = cpu_limit

    async def execute(
        self,
        command: str,
        cwd: str | Path,
        *,
        timeout_seconds: float = 120,
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        """在 Docker 容器中执行命令。"""
        if not shutil.which("docker"):
            return SandboxResult(
                stdout="",
                stderr="Docker is not available. Please install Docker first.",
                exit_code=127,
            )

        import asyncio

        docker_cmd = [
            "docker", "run", "--rm",
            f"--memory={self._memory_limit}",
            f"--cpus={self._cpu_limit}",
            "-v", f"{cwd}:/workspace",
            "-w", "/workspace",
        ]

        if self._network_disabled:
            docker_cmd.append("--network=none")

        if env:
            for k, v in env.items():
                docker_cmd.extend(["-e", f"{k}={v}"])

        docker_cmd.extend([self._image, "sh", "-c", command])

        try:
            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_seconds,
            )
            return SandboxResult(
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                exit_code=proc.returncode or 0,
            )
        except asyncio.TimeoutError:
            proc.kill()  # type: ignore[union-attr]
            await proc.wait()  # type: ignore[union-attr]
            return SandboxResult(
                stdout="",
                stderr=f"Docker command timed out after {timeout_seconds}s",
                exit_code=-1,
                timed_out=True,
            )


# ---------------------------------------------------------------------------
# 沙箱工厂
# ---------------------------------------------------------------------------


def create_sandbox_executor(mode: SandboxMode) -> SandboxExecutor:
    """根据模式创建沙箱执行器。

    Args:
        mode: 沙箱隔离模式。

    Returns:
        对应的沙箱执行器实例。
    """
    match mode:
        case SandboxMode.NONE:
            return NoopSandboxExecutor()
        case SandboxMode.COMMAND:
            return CommandSandboxExecutor()
        case SandboxMode.DOCKER:
            return DockerSandboxExecutor()
        case _:
            logger.warning("Unknown sandbox mode: {mode}, falling back to noop", mode=mode)
            return NoopSandboxExecutor()
