"""魔法词检测 - 当用户输入包含 'harness' 或 'hns' 时触发 Harness 能力"""

from __future__ import annotations

import re
from dataclasses import dataclass

_MAGIC_WORD_RE = re.compile(r"(?<![a-zA-Z])(?:harness|hns)(?![a-zA-Z])", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class MagicWordResult:
    """魔法词检测结果"""
    detected: bool
    cleaned_input: str


def detect_magic_word(text: str) -> MagicWordResult:
    """检测文本中是否包含魔法词，返回清理后的文本"""
    match = _MAGIC_WORD_RE.search(text)
    if not match:
        return MagicWordResult(detected=False, cleaned_input=text)

    cleaned = _MAGIC_WORD_RE.sub("", text).strip()
    return MagicWordResult(detected=True, cleaned_input=cleaned)
