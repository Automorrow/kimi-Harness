"""Harness runtime state - shared between kimisoul and harness tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kimi_cli.soul.agent import Runtime

_runtime: Runtime | None = None


def set_harness_runtime(runtime: Runtime) -> None:
    """Register the current runtime so harness tools can access it."""
    global _runtime
    _runtime = runtime


def get_harness_runtime() -> Runtime | None:
    """Retrieve the registered runtime (or None if harness is not active)."""
    return _runtime
