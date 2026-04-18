"""记忆搜索 - 基于 token 的启发式搜索"""

from __future__ import annotations

import re
from pathlib import Path


def tokenize(text: str) -> list[str]:
    """简单分词，支持 ASCII 和汉字"""
    # 分离 ASCII 单词和汉字
    tokens = re.findall(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]", text.lower())
    return tokens


def search_entries(query: str, entries: list[dict], top_k: int = 3) -> list[dict]:
    """搜索记忆条目，返回 top_k 个最相关的"""
    query_tokens = set(tokenize(query))
    if not query_tokens:
        return entries[:top_k]

    scored = []
    for entry in entries:
        content = entry.get("content", entry.get("title", ""))
        content_tokens = set(tokenize(content))
        # 简单的 token 重叠度评分
        overlap = len(query_tokens & content_tokens)
        if overlap > 0:
            scored.append((overlap, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [entry for _, entry in scored[:top_k]]
