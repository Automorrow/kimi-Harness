#!/usr/bin/env bash
# Build kimi-harness wheel using hatchling (not uv_build) and install it.
# uv_build strips non-Python files; hatchling + artifacts preserves them.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Building wheel with hatchling..."
uv run --with hatchling --with build python -m build --wheel -o dist/

WHEEL=$(ls -t dist/kimi_harness-*.whl 2>/dev/null | head -1)
if [ -z "$WHEEL" ]; then
    echo "ERROR: No wheel found in dist/"
    exit 1
fi
echo "==> Built: $WHEEL"

echo "==> Installing..."
uv tool install "$WHEEL" --force --reinstall

echo "==> Done! Run 'kh' or 'kh web' to start."
