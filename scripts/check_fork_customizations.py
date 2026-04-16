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
    # --- Package identity ---
    (
        "pyproject.toml",
        'Package name must be "kimi-harness"',
        re.compile(r'^name\s*=\s*"kimi-harness"', re.MULTILINE),
    ),
    (
        "pyproject.toml",
        'Must NOT have "kimi" or "kimi-cli" script entries (only kh/kimi-harness)',
        re.compile(r'^kimi(?:-cli)?\s*=', re.MULTILINE),
        invert=True,
    ),
    # --- Branding ---
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
        "src/kimi_cli/constant.py",
        'User-Agent must be "KimiHarness"',
        re.compile(r'KimiHarness/'),
    ),
    (
        "src/kimi_cli/__main__.py",
        'Version output must show "kh (Kimi Harness)"',
        re.compile(r'kh \(Kimi Harness\), version'),
    ),
    # --- Data directory ---
    (
        "src/kimi_cli/share.py",
        "Share directory must be ~/.kimi-harness",
        re.compile(r'Path\.home\(\)\s*/\s*"\.kimi-harness"'),
    ),
    # --- Process identity ---
    (
        "src/kimi_cli/utils/proctitle.py",
        'Process name default must be "Kimi Harness"',
        re.compile(r'def init_process_name\(name:\s*str\s*=\s*"Kimi Harness"\)'),
    ),
    # --- Web port ---
    (
        "src/kimi_cli/web/app.py",
        "Web default port must be 5496",
        re.compile(r'DEFAULT_PORT\s*=\s*5496'),
    ),
    # --- Keyring ---
    (
        "src/kimi_cli/auth/oauth.py",
        'Keyring service must be "kimi-harness"',
        re.compile(r'KEYRING_SERVICE\s*=\s*"kimi-harness"'),
    ),
    # --- Plans directory ---
    (
        "src/kimi_cli/tools/plan/heroes.py",
        "Plans directory must be ~/.kimi-harness/plans",
        re.compile(r'"\.kimi-harness"\s*/\s*"plans"'),
    ),
    # --- Skills directory ---
    (
        "src/kimi_cli/skill/__init__.py",
        "User-level skills directory must be ~/.kimi-harness/skills",
        re.compile(r'"\.kimi-harness"\s*/\s*"skills"'),
    ),
]


def main() -> None:
    errors: list[str] = []

    for item in CHECKS:
        rel_path = item[0]
        description = item[1]
        pattern = item[2]
        invert = item[3] if len(item) > 3 else False

        full_path = ROOT / rel_path
        if not full_path.exists():
            errors.append(f"MISSING FILE: {rel_path}")
            continue

        content = full_path.read_text(encoding="utf-8")
        found = bool(pattern.search(content))

        if invert:
            if found:
                errors.append(f"CHECK FAILED: {rel_path} — {description}")
        else:
            if not found:
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
