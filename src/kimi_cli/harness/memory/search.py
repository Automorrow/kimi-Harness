"""Simple heuristic memory search for Harness."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from kimi_cli.harness.memory.manager import MemoryManager


@dataclass
class MemoryHeader:
    """A lightweight header for a memory file."""

    path: Path
    title: str
    description: str
    modified_at: float
    body_preview: str


def _tokenize(text: str) -> set[str]:
    """Extract search tokens from *text*, handling ASCII and Han ideographs."""
    ascii_tokens = {t for t in re.findall(r"[A-Za-z0-9_]+", text.lower()) if len(t) >= 3}
    han_chars = set(re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]", text))
    return ascii_tokens | han_chars


def scan_memory_files(cwd: str | Path, *, max_files: int = 50) -> list[MemoryHeader]:
    """Return memory headers sorted by newest first."""
    memory_dir = MemoryManager(cwd).project_memory_dir
    headers: list[MemoryHeader] = []
    for path in memory_dir.glob("*.md"):
        if path.name == "MEMORY.md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        header = _parse_memory_file(path, text)
        headers.append(header)
    headers.sort(key=lambda item: item.modified_at, reverse=True)
    return headers[:max_files]


def _parse_memory_file(path: Path, content: str) -> MemoryHeader:
    """Parse a memory file, extracting YAML frontmatter when present."""
    lines = content.splitlines()
    title = path.stem.replace("_", " ").title()
    description = ""
    body_start = 0

    # Parse YAML frontmatter (--- ... ---)
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                for fm_line in lines[1:i]:
                    key, _, value = fm_line.partition(":")
                    key = key.strip()
                    value = value.strip().strip("'\"")
                    if not value:
                        continue
                    if key == "name":
                        title = value
                    elif key == "description":
                        description = value
                body_start = i + 1
                break

    # Fallback: first non-empty, non-frontmatter line as description
    desc_line_idx: int | None = None
    if not description:
        for idx, line in enumerate(lines[body_start:body_start + 10], body_start):
            stripped = line.strip()
            if stripped and stripped != "---" and not stripped.startswith("#"):
                description = stripped[:200]
                desc_line_idx = idx
                break

    # Build body preview from content after frontmatter
    body_lines = [
        line.strip()
        for idx, line in enumerate(lines[body_start:], body_start)
        if line.strip()
        and not line.strip().startswith("#")
        and idx != desc_line_idx
    ]
    body_preview = " ".join(body_lines)[:300]

    return MemoryHeader(
        path=path,
        title=title,
        description=description,
        modified_at=path.stat().st_mtime,
        body_preview=body_preview,
    )


def find_relevant_memories(
    query: str,
    cwd: str | Path,
    *,
    max_results: int = 5,
) -> list[MemoryHeader]:
    """Return the memory files whose metadata and content overlap the query."""
    tokens = _tokenize(query)
    if not tokens:
        return []

    scored: list[tuple[float, MemoryHeader]] = []
    for header in scan_memory_files(cwd, max_files=100):
        meta = f"{header.title} {header.description}".lower()
        body = header.body_preview.lower()

        meta_hits = sum(1 for t in tokens if t in meta)
        body_hits = sum(1 for t in tokens if t in body)
        score = meta_hits * 2.0 + body_hits
        if score > 0:
            scored.append((score, header))

    scored.sort(key=lambda item: (-item[0], -item[1].modified_at))
    return [header for _, header in scored[:max_results]]
