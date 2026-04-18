from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

NAME = "Kimi Code CLI"

if TYPE_CHECKING:
    VERSION: str
    USER_AGENT: str


@cache
def get_version() -> str:
    from importlib import metadata
    from pathlib import Path
    
    try:
        return metadata.version("kimi-cli")
    except Exception:
        try:
            return metadata.version("kimi-harness")
        except Exception:
            # Fallback to pyproject.toml or unknown
            try:
                import tomlkit
                
                pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
                if pyproject_path.exists():
                    try:
                        with open(pyproject_path, "r", encoding="utf-8") as f:
                            pyproject = tomlkit.load(f)
                        return str(pyproject["project"]["version"])
                    except Exception:
                        pass
            except Exception:
                pass
            
            return "1.36.0"


@cache
def get_user_agent() -> str:
    return f"KimiCLI/{get_version()}"


def __getattr__(name: str) -> str:
    if name == "VERSION":
        return get_version()
    if name == "USER_AGENT":
        return get_user_agent()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["NAME", "VERSION", "USER_AGENT", "get_version", "get_user_agent"]
