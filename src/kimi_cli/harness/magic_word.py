"""Harness 魔法词检测与处理.

当用户输入中包含 ``harness`` 或 ``hns`` 时，
自动启用 Harness 能力（memory=global, teams）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 匹配独立单词 "harness" 或 "hns"
# 使用负向回顾/前瞻确保不匹配 "harnessing" 等派生词
# 同时兼容中文紧邻（如 "harness中文"）
_MAGIC_WORD_PATTERN = re.compile(
    r"(?<![a-zA-Z])(?:harness|hns)(?![a-zA-Z])",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class MagicWordResult:
    """魔法词检测结果。"""

    detected: bool
    """是否检测到魔法词。"""
    cleaned_input: str
    """去除魔法词后的用户输入。"""
    memory: str = "global"


def detect_magic_word(user_input: str) -> MagicWordResult:
    """检测用户输入中的魔法词。

    处理规则：
    - 魔法词可以出现在输入的开头、中间或末尾
    - 仅匹配独立单词（不会匹配 "harnessing" 等派生词）
    - 去除魔法词及其前后的标点/空白后返回 cleaned_input
    - 大小写不敏感

    Args:
        user_input: 原始用户输入。

    Returns:
        MagicWordResult 包含检测结果和处理后的输入。
    """
    if not _MAGIC_WORD_PATTERN.search(user_input):
        return MagicWordResult(detected=False, cleaned_input=user_input)

    # 去除魔法词：替换匹配项及周围的多余空白
    cleaned = _MAGIC_WORD_PATTERN.sub("", user_input)
    # 清理多余的空格和标点
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"^[\s,;:]+|[\s,;:]+$", "", cleaned)
    cleaned = cleaned.strip()

    return MagicWordResult(
        detected=True,
        cleaned_input=cleaned,
        memory="global",
    )
