"""MemoryManager and memory search unit tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from kimi_cli.harness.memory.manager import MemoryManager, MemoryEntry
from kimi_cli.harness.memory.search import find_relevant_memories, scan_memory_files


# ---------------------------------------------------------------------------
# TestMemoryManagerCRUD
# ---------------------------------------------------------------------------


class TestMemoryManagerCRUD:
    """MemoryManager 增删改查测试。"""

    def test_add_and_get_memory(self, tmp_path: Path) -> None:
        """添加记忆后可以通过 list_entries 获取。"""
        mgr = MemoryManager(tmp_path)
        mgr.add_entry("架构决策", "我们选择了 PostgreSQL 作为主数据库。")

        entries = mgr.list_entries()
        assert len(entries) == 1
        assert entries[0].name == "架构决策"
        assert "PostgreSQL" in entries[0].content

    def test_add_duplicate_name_updates(self, tmp_path: Path) -> None:
        """添加同名记忆应覆盖而非重复。"""
        mgr = MemoryManager(tmp_path)
        mgr.add_entry("架构决策", "版本一")
        mgr.add_entry("架构决策", "版本二")

        entries = mgr.list_entries()
        assert len(entries) == 1
        assert entries[0].content.strip() == "版本二"

    def test_list_memories_empty(self, tmp_path: Path) -> None:
        """无记忆时 list_entries 返回空列表。"""
        mgr = MemoryManager(tmp_path)
        assert mgr.list_entries() == []

    def test_list_memories_sorted(self, tmp_path: Path) -> None:
        """list_entries 按文件名排序。"""
        mgr = MemoryManager(tmp_path)
        mgr.add_entry("beta", "b")
        mgr.add_entry("alpha", "a")

        names = [e.name for e in mgr.list_entries()]
        assert names == ["alpha", "beta"]

    def test_remove_entry(self, tmp_path: Path) -> None:
        """删除记忆后 list_entries 不再包含该条目。"""
        mgr = MemoryManager(tmp_path)
        mgr.add_entry("临时笔记", "临时内容")
        assert len(mgr.list_entries()) == 1

        removed = mgr.remove_entry("临时笔记")
        assert removed is True
        assert mgr.list_entries() == []

    def test_remove_nonexistent_entry(self, tmp_path: Path) -> None:
        """删除不存在的记忆返回 False。"""
        mgr = MemoryManager(tmp_path)
        assert mgr.remove_entry("不存在") is False

    def test_get_memory_not_found(self, tmp_path: Path) -> None:
        """获取不存在的记忆返回 None（通过 list_entries 过滤）。"""
        mgr = MemoryManager(tmp_path)
        entries = [e for e in mgr.list_entries() if e.name == "不存在"]
        assert entries == []

    def test_add_multiple_memories(self, tmp_path: Path) -> None:
        """添加多条记忆后 list_entries 返回全部。"""
        mgr = MemoryManager(tmp_path)
        mgr.add_entry("数据库选型", "PostgreSQL")
        mgr.add_entry("缓存方案", "Redis")
        mgr.add_entry("消息队列", "Kafka")

        assert len(mgr.list_entries()) == 3


# ---------------------------------------------------------------------------
# TestMemoryLevels
# ---------------------------------------------------------------------------


class TestMemoryLevels:
    """项目级与用户级记忆存储路径测试。"""

    def test_project_memory_dir(self, tmp_path: Path) -> None:
        """项目级记忆存储在 work_dir/.kimi-harness/memory/。"""
        mgr = MemoryManager(tmp_path)
        expected = tmp_path / ".kimi-harness" / "memory"
        assert mgr.project_memory_dir == expected

    def test_user_memory_dir_default(self, tmp_path: Path) -> None:
        """用户级记忆默认存储在 ~/.kimi-harness/memory/。"""
        from kimi_cli.harness.memory.manager import _get_user_memory_dir

        mgr = MemoryManager(tmp_path)
        assert mgr.user_memory_dir == _get_user_memory_dir()

    def test_user_memory_dir_custom(self, tmp_path: Path) -> None:
        """可以自定义用户级记忆目录。"""
        custom_dir = tmp_path / "custom_user_memory"
        mgr = MemoryManager(tmp_path, user_memory_dir=custom_dir)
        assert mgr.user_memory_dir == custom_dir

    def test_project_memory_stored_on_disk(self, tmp_path: Path) -> None:
        """添加项目级记忆后文件实际存储在项目目录下。"""
        mgr = MemoryManager(tmp_path)
        mgr.add_entry("测试记忆", "内容")

        memory_file = mgr.project_memory_dir / "测试记忆.md"
        assert memory_file.exists()
        assert memory_file.read_text(encoding="utf-8").strip() == "内容"


# ---------------------------------------------------------------------------
# TestMemoryIndex
# ---------------------------------------------------------------------------


class TestMemoryIndex:
    """MEMORY.md 索引文件同步测试。"""

    def test_index_created_on_add(self, tmp_path: Path) -> None:
        """添加记忆时自动创建 MEMORY.md 索引文件。"""
        mgr = MemoryManager(tmp_path)
        mgr.add_entry("架构决策", "PostgreSQL")

        index_path = mgr.project_memory_dir / "MEMORY.md"
        assert index_path.exists()
        content = index_path.read_text(encoding="utf-8")
        assert "架构决策" in content

    def test_index_updated_on_add(self, tmp_path: Path) -> None:
        """添加多条记忆时索引文件包含所有条目。"""
        mgr = MemoryManager(tmp_path)
        mgr.add_entry("第一条", "a")
        mgr.add_entry("第二条", "b")

        index_path = mgr.project_memory_dir / "MEMORY.md"
        content = index_path.read_text(encoding="utf-8")
        assert "第一条" in content
        assert "第二条" in content

    def test_index_updated_on_remove(self, tmp_path: Path) -> None:
        """删除记忆时索引文件同步移除对应条目。"""
        mgr = MemoryManager(tmp_path)
        mgr.add_entry("保留", "keep")
        mgr.add_entry("删除", "remove")
        mgr.remove_entry("删除")

        index_path = mgr.project_memory_dir / "MEMORY.md"
        content = index_path.read_text(encoding="utf-8")
        assert "保留" in content
        assert "删除" not in content


# ---------------------------------------------------------------------------
# TestLoadMemoryPrompt
# ---------------------------------------------------------------------------


class TestLoadMemoryPrompt:
    """load_memory_prompt 测试。"""

    def test_returns_memory_content(self, tmp_path: Path) -> None:
        """有记忆时返回包含记忆内容的字符串。"""
        mgr = MemoryManager(tmp_path)
        mgr.add_entry("架构决策", "使用 PostgreSQL")

        prompt = mgr.load_memory_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "Memory" in prompt

    def test_returns_empty_when_no_memory(self, tmp_path: Path) -> None:
        """无记忆时返回空字符串。"""
        mgr = MemoryManager(tmp_path)
        assert mgr.load_memory_prompt() == ""

    def test_prompt_contains_project_section(self, tmp_path: Path) -> None:
        """返回的提示词包含 Project Memory 段落。"""
        mgr = MemoryManager(tmp_path)
        mgr.add_entry("项目配置", "Python 3.12")

        prompt = mgr.load_memory_prompt()
        assert "Project Memory" in prompt


# ---------------------------------------------------------------------------
# TestMemorySearch
# ---------------------------------------------------------------------------


class TestMemorySearch:
    """记忆搜索功能测试。"""

    def test_find_relevant_by_keyword(self, tmp_path: Path) -> None:
        """基于关键词搜索能找到匹配的记忆。"""
        mgr = MemoryManager(tmp_path)
        mgr.add_entry("数据库选型", "项目使用 PostgreSQL 作为关系型数据库")

        results = find_relevant_memories("PostgreSQL", tmp_path)
        assert len(results) >= 1
        assert any("数据库" in h.title or "PostgreSQL" in h.body_preview.lower() for h in results)

    def test_empty_query_returns_empty(self, tmp_path: Path) -> None:
        """空查询返回空列表。"""
        mgr = MemoryManager(tmp_path)
        mgr.add_entry("测试", "内容")

        assert find_relevant_memories("", tmp_path) == []
        assert find_relevant_memories("   ", tmp_path) == []

    def test_chinese_token_search(self, tmp_path: Path) -> None:
        """中文分词搜索能匹配单个汉字。"""
        mgr = MemoryManager(tmp_path)
        mgr.add_entry("缓存方案", "使用 Redis 作为缓存层")

        results = find_relevant_memories("缓存", tmp_path)
        assert len(results) >= 1

    def test_no_match_returns_empty(self, tmp_path: Path) -> None:
        """无匹配结果时返回空列表。"""
        mgr = MemoryManager(tmp_path)
        mgr.add_entry("数据库", "PostgreSQL")

        results = find_relevant_memories("量子计算", tmp_path)
        assert results == []

    def test_scan_memory_files(self, tmp_path: Path) -> None:
        """scan_memory_files 返回所有记忆文件头信息。"""
        mgr = MemoryManager(tmp_path)
        mgr.add_entry("笔记一", "内容一")
        mgr.add_entry("笔记二", "内容二")

        headers = scan_memory_files(tmp_path)
        assert len(headers) == 2
        titles = {h.title for h in headers}
        assert "笔记一" in titles or "笔记一".replace("_", " ").title() in titles
