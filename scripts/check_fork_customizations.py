#!/usr/bin/env python3
"""Check that fork-specific customizations are preserved after upstream sync.

This script verifies critical customization lines that differentiate
kimi-harness from upstream kimi-cli. Run it in CI to catch accidental
overwrites during upstream merges.

Exit code 0 = all checks pass, 1 = customization missing.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CHECKS: list[tuple[str, str, re.Pattern[str]]] = [
    # (file_path, description, expected_pattern)
    (
        "pyproject.toml",
        'Package name must be "kimi-harness"',
        re.compile(r'^name\s*=\s*"kimi-harness"', re.MULTILINE),
    ),
    (
        "src/kimi_cli/constant.py",
        'Product name must be "Kimi Harness"',
        re.compile(r'^NAME\s*=\s*"Kimi Harness"', re.MULTILINE),
    ),
    (
        "src/kimi_cli/constant.py",
        'metadata.version must reference "kimi-harness"',
        re.compile(r'metadata\.version\("kimi-harness"\)'),
    ),
    (
        "src/kimi_cli/share.py",
        "Share directory must be ~/.kimi-harness",
        re.compile(r'Path\.home\(\)\s*/\s*"\.kimi-harness"'),
    ),
]


def main() -> None:
    errors: list[str] = []

    for rel_path, description, pattern in CHECKS:
        full_path = ROOT / rel_path
        if not full_path.exists():
            errors.append(f"MISSING FILE: {rel_path}")
            continue

        content = full_path.read_text(encoding="utf-8")
        if not pattern.search(content):
            errors.append(f"CHECK FAILED: {rel_path} — {description}")

    if errors:
        print("Fork customization check FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  ✗ {e}", file=sys.stderr)
        sys.exit(1)
    else:
        print("Fork customization check PASSED — all customizations preserved.")
        sys.exit(0)


if __name__ == "__main__":
    main()
