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

# Each check: (file_path, description, pattern, should_match)
# should_match=True: pattern MUST be found (positive check)
# should_match=False: pattern MUST NOT be found (negative check)
CHECKS: list[tuple[str, str, re.Pattern[str], bool]] = [
    # --- Package identity ---
    (
        "pyproject.toml",
        'Package name must be "kimi-harness"',
        re.compile(r'^name\s*=\s*"kimi-harness"', re.MULTILINE),
        True,
    ),
    (
        "pyproject.toml",
        'Must NOT have "kimi" or "kimi-cli" script entries',
        re.compile(r'^kimi(?:-cli)?\s*=\s*"', re.MULTILINE),
        False,
    ),
    # --- Branding ---
    (
        "src/kimi_cli/constant.py",
        'Product name must be "Kimi Harness"',
        re.compile(r'^NAME\s*=\s*"Kimi Harness"', re.MULTILINE),
        True,
    ),
    (
        "src/kimi_cli/constant.py",
        'metadata.version must reference "kimi-harness"',
        re.compile(r'metadata\.version\("kimi-harness"\)'),
        True,
    ),
    (
        "src/kimi_cli/constant.py",
        'User-Agent must be "KimiHarness"',
        re.compile(r'KimiHarness/'),
        True,
    ),
    (
        "src/kimi_cli/__main__.py",
        'Version output must show "kh (Kimi Harness)"',
        re.compile(r'kh \(Kimi Harness\), version'),
        True,
    ),
    # --- Data directory ---
    (
        "src/kimi_cli/share.py",
        "Share directory must be ~/.kimi-harness",
        re.compile(r'Path\.home\(\)\s*/\s*"\.kimi-harness"'),
        True,
    ),
    # --- Process identity ---
    (
        "src/kimi_cli/utils/proctitle.py",
        'Process name default must be "Kimi Harness"',
        re.compile(r'def init_process_name\(name:\s*str\s*=\s*"Kimi Harness"\)'),
        True,
    ),
    # --- Web port ---
    (
        "src/kimi_cli/web/app.py",
        "Web default port must be 5496",
        re.compile(r'DEFAULT_PORT\s*=\s*5496'),
        True,
    ),
    (
        "src/kimi_cli/cli/web.py",
        "CLI web command default port must be 5496",
        re.compile(r'port.*=\s*5496'),
        True,
    ),
    # --- Keyring ---
    (
        "src/kimi_cli/auth/oauth.py",
        'Keyring service must be "kimi-harness"',
        re.compile(r'KEYRING_SERVICE\s*=\s*"kimi-harness"'),
        True,
    ),
    # --- Plans directory ---
    (
        "src/kimi_cli/tools/plan/heroes.py",
        "Plans directory must be ~/.kimi-harness/plans",
        re.compile(r'"\.kimi-harness"\s*/\s*"plans"'),
        True,
    ),
    # --- Skills directory ---
    (
        "src/kimi_cli/skill/__init__.py",
        "User-level skills directory must be ~/.kimi-harness/skills",
        re.compile(r'"\.kimi-harness"\s*/\s*"skills"'),
        True,
    ),
    # --- Auto-update ---
    (
        "src/kimi_cli/ui/shell/update.py",
        'Upgrade command must target "kimi-harness"',
        re.compile(r'uv tool upgrade kimi-harness'),
        True,
    ),
    (
        "src/kimi_cli/ui/shell/update.py",
        'Install binary must be "kh" not "kimi"',
        re.compile(r'INSTALL_DIR\s*/\s*"kh"'),
        True,
    ),
    # --- Temp file prefixes (negative: must NOT contain kimi- prefix) ---
    (
        "src/kimi_cli/ui/shell/update.py",
        'Temp prefix must be "kh-" not "kimi-cli-"',
        re.compile(r'prefix="kimi-cli-"'),
        False,
    ),
    (
        "src/kimi_cli/tools/file/grep_local.py",
        'Temp prefix must be "kh-rg-" not "kimi-rg-"',
        re.compile(r'prefix="kimi-rg-"'),
        False,
    ),
    (
        "src/kimi_cli/utils/editor.py",
        'Temp prefix must be "kh-edit-" not "kimi-edit-"',
        re.compile(r'prefix="kimi-edit-"'),
        False,
    ),
    (
        "src/kimi_cli/cli/plugin.py",
        'Temp prefix must be "kh-plugin-" not "kimi-plugin-"',
        re.compile(r'prefix="kimi-plugin-"'),
        False,
    ),
    # --- CLI help text ---
    (
        "src/kimi_cli/cli/__init__.py",
        'Config help text must reference ~/.kimi-harness/config.toml',
        re.compile(r'~/.kimi-harness/config\.toml'),
        True,
    ),
]


def main() -> None:
    errors: list[str] = []

    for rel_path, description, pattern, should_match in CHECKS:
        full_path = ROOT / rel_path
        if not full_path.exists():
            errors.append(f"MISSING FILE: {rel_path}")
            continue

        content = full_path.read_text(encoding="utf-8")
        found = bool(pattern.search(content))

        if should_match and not found:
            errors.append(f"CHECK FAILED: {rel_path} — {description}")
        elif not should_match and found:
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
