"""Unit tests for kimi_cli.harness.tools.base - ToolRegistry, KosongToolAdapter, toolset_to_registry."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kimi_cli.harness.tools.base import (
    BaseTool,
    DynamicToolInput,
    HarnessToolResult,
    KosongToolAdapter,
    ToolExecutionContext,
    ToolInput,
    ToolRegistry,
    toolset_to_registry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _DummyTool(BaseTool):
    """最小 BaseTool 实现，用于测试。"""

    def __init__(
        self,
        name: str = "dummy",
        description: str = "A dummy tool",
    ) -> None:
        self.name = name
        self.description = description
        self.input_model = ToolInput

    async def execute(
        self,
        arguments: ToolInput,
        context: ToolExecutionContext,
    ) -> HarnessToolResult:
        return HarnessToolResult(output="ok")


def _make_kosong_tool(
    name: str = "test_tool",
    description: str = "A test kosong tool",
    parameters: dict[str, Any] | None = None,
) -> MagicMock:
    """创建模拟的 kosong CallableTool。"""
    tool = MagicMock()
    tool.name = name
    tool.description = description
    tool.parameters = parameters or {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }
    tool.call = AsyncMock(return_value=MagicMock())
    return tool


# ---------------------------------------------------------------------------
# TestToolRegistry
# ---------------------------------------------------------------------------


class TestToolRegistry:

    def test_register_and_get(self) -> None:
        """注册工具后可以通过 get 获取。"""
        reg = ToolRegistry()
        tool = _DummyTool("foo", "Foo tool")
        reg.register(tool)
        assert reg.get("foo") is tool

    def test_register_duplicate_overwrites(self) -> None:
        """注册同名工具会覆盖旧工具。"""
        reg = ToolRegistry()
        tool_a = _DummyTool("foo", "Tool A")
        tool_b = _DummyTool("foo", "Tool B")
        reg.register(tool_a)
        reg.register(tool_b)
        assert reg.get("foo") is tool_b
        assert reg.get("foo").description == "Tool B"

    def test_get_nonexistent_returns_none(self) -> None:
        """获取不存在的工具返回 None。"""
        reg = ToolRegistry()
        assert reg.get("nonexistent") is None

    def test_unregister_existing(self) -> None:
        """移除已注册的工具返回 True。"""
        reg = ToolRegistry()
        tool = _DummyTool("bar")
        reg.register(tool)
        assert reg.unregister("bar") is True
        assert reg.get("bar") is None

    def test_unregister_nonexistent(self) -> None:
        """移除不存在的工具返回 False。"""
        reg = ToolRegistry()
        assert reg.unregister("ghost") is False

    def test_list_names(self) -> None:
        """list_names 返回所有已注册工具名称。"""
        reg = ToolRegistry()
        reg.register(_DummyTool("alpha"))
        reg.register(_DummyTool("beta"))
        reg.register(_DummyTool("gamma"))
        names = reg.list_names()
        assert set(names) == {"alpha", "beta", "gamma"}

    def test_list_tools(self) -> None:
        """list_tools 返回所有已注册工具实例。"""
        reg = ToolRegistry()
        t1 = _DummyTool("x")
        t2 = _DummyTool("y")
        reg.register(t1)
        reg.register(t2)
        tools = reg.list_tools()
        assert set(tools) == {t1, t2}

    def test_len(self) -> None:
        """__len__ 返回工具数量。"""
        reg = ToolRegistry()
        assert len(reg) == 0
        reg.register(_DummyTool("a"))
        assert len(reg) == 1
        reg.register(_DummyTool("b"))
        assert len(reg) == 2

    def test_contains(self) -> None:
        """__contains__ 支持名称检查。"""
        reg = ToolRegistry()
        reg.register(_DummyTool("hello"))
        assert "hello" in reg
        assert "world" not in reg

    def test_has(self) -> None:
        """has 方法检查工具是否已注册。"""
        reg = ToolRegistry()
        reg.register(_DummyTool("yes"))
        assert reg.has("yes") is True
        assert reg.has("no") is False

    def test_to_api_schemas(self) -> None:
        """to_api_schemas 返回所有工具的 API Schema 列表。"""
        reg = ToolRegistry()
        reg.register(_DummyTool("t1", "desc1"))
        reg.register(_DummyTool("t2", "desc2"))
        schemas = reg.to_api_schemas()
        assert len(schemas) == 2
        names = {s["name"] for s in schemas}
        assert names == {"t1", "t2"}


# ---------------------------------------------------------------------------
# TestKosongToolAdapter
# ---------------------------------------------------------------------------


class TestKosongToolAdapter:

    def test_name_passed_through(self) -> None:
        """name 正确传递。"""
        kosong = _make_kosong_tool(name="my_search")
        adapter = KosongToolAdapter(kosong)
        assert adapter.name == "my_search"

    def test_description_passed_through(self) -> None:
        """description 正确传递。"""
        kosong = _make_kosong_tool(description="Search the web")
        adapter = KosongToolAdapter(kosong)
        assert adapter.description == "Search the web"

    def test_description_default(self) -> None:
        """description 为 None 时使用默认值。"""
        kosong = _make_kosong_tool()
        kosong.description = None
        adapter = KosongToolAdapter(kosong)
        assert adapter.description == "No description provided."

    def test_schema_built_from_parameters(self) -> None:
        """input_model 从 kosong 工具的 parameters 构建。"""
        kosong = _make_kosong_tool(parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        })
        adapter = KosongToolAdapter(kosong)
        schema = adapter.input_model.model_json_schema()
        assert "query" in schema.get("properties", {})
        assert "limit" in schema.get("properties", {})

    def test_schema_empty_properties(self) -> None:
        """parameters 无 properties 时仍能正常构建。"""
        kosong = _make_kosong_tool(parameters={
            "type": "object",
            "properties": {},
        })
        adapter = KosongToolAdapter(kosong)
        assert adapter.input_model is not None

    @pytest.mark.asyncio
    @patch("kimi_cli.harness.tools.base.KosongToolAdapter._convert_result")
    async def test_execute_calls_kosong_tool(self, mock_convert) -> None:
        """execute 调用底层 kosong 工具的 call 方法。"""
        mock_convert.return_value = HarnessToolResult(output="ok")
        kosong = _make_kosong_tool()
        adapter = KosongToolAdapter(kosong)
        ctx = ToolExecutionContext(cwd=Path("/tmp"))
        args = DynamicToolInput(params={"query": "hello"})
        result = await adapter.execute(args, ctx)
        kosong.call.assert_awaited_once()
        call_args = kosong.call.call_args[0][0]
        assert call_args["query"] == "hello"
        assert isinstance(result, HarnessToolResult)

    @pytest.mark.asyncio
    @patch("kimi_cli.harness.tools.base.KosongToolAdapter._convert_result")
    async def test_execute_returns_result_on_success(self, mock_convert) -> None:
        """execute 成功时返回 HarnessToolResult。"""
        mock_convert.return_value = HarnessToolResult(output="ok")
        kosong = _make_kosong_tool()
        adapter = KosongToolAdapter(kosong)
        ctx = ToolExecutionContext(cwd=Path("/tmp"))
        args = DynamicToolInput(params={})
        result = await adapter.execute(args, ctx)
        assert isinstance(result, HarnessToolResult)

    @pytest.mark.asyncio
    async def test_execute_handles_exception(self) -> None:
        """execute 在底层工具抛异常时返回错误结果。"""
        kosong = _make_kosong_tool()
        kosong.call = AsyncMock(side_effect=RuntimeError("boom"))
        adapter = KosongToolAdapter(kosong)
        ctx = ToolExecutionContext(cwd=Path("/tmp"))
        args = DynamicToolInput(params={})
        result = await adapter.execute(args, ctx)
        assert result.is_error is True
        assert "boom" in result.output

    def test_is_read_only_known_tool(self) -> None:
        """已知只读工具返回 True。"""
        kosong = _make_kosong_tool(name="read_file")
        adapter = KosongToolAdapter(kosong)
        assert adapter.is_read_only(DynamicToolInput()) is True

    def test_is_read_only_unknown_tool(self) -> None:
        """未知工具默认返回 False。"""
        kosong = _make_kosong_tool(name="bash")
        adapter = KosongToolAdapter(kosong)
        assert adapter.is_read_only(DynamicToolInput()) is False

    def test_to_api_schema(self) -> None:
        """to_api_schema 返回包含 name、description、input_schema 的字典。"""
        kosong = _make_kosong_tool(name="web_search", description="Search")
        adapter = KosongToolAdapter(kosong)
        schema = adapter.to_api_schema()
        assert schema["name"] == "web_search"
        assert schema["description"] == "Search"
        assert "input_schema" in schema


# ---------------------------------------------------------------------------
# TestToolsetToRegistry
# ---------------------------------------------------------------------------


class TestToolsetToRegistry:

    def test_empty_toolset_returns_empty_registry(self) -> None:
        """空工具集返回空注册表。"""
        mock_toolset = MagicMock()
        mock_toolset._tool_dict = {}
        mock_toolset._hidden_tools = set()
        reg = toolset_to_registry(mock_toolset)
        assert len(reg) == 0

    def test_tools_bridged_to_registry(self) -> None:
        """KimiToolset 中的工具被桥接到 ToolRegistry。"""
        mock_toolset = MagicMock()
        t1 = _make_kosong_tool(name="tool_a", description="Tool A")
        t2 = _make_kosong_tool(name="tool_b", description="Tool B")
        mock_toolset._tool_dict = {"tool_a": t1, "tool_b": t2}
        mock_toolset._hidden_tools = set()
        reg = toolset_to_registry(mock_toolset)
        assert len(reg) == 2
        assert reg.has("tool_a") is True
        assert reg.has("tool_b") is True

    def test_hidden_tools_skipped(self) -> None:
        """隐藏工具被跳过。"""
        mock_toolset = MagicMock()
        t1 = _make_kosong_tool(name="visible")
        t2 = _make_kosong_tool(name="hidden_tool")
        mock_toolset._tool_dict = {"visible": t1, "hidden_tool": t2}
        mock_toolset._hidden_tools = {"hidden_tool"}
        reg = toolset_to_registry(mock_toolset)
        assert len(reg) == 1
        assert reg.has("visible") is True
        assert reg.has("hidden_tool") is False

    def test_broken_tool_skipped(self) -> None:
        """适配失败的工具被跳过，不抛异常。"""
        mock_toolset = MagicMock()
        good = _make_kosong_tool(name="good")
        bad = MagicMock(spec=[])  # 空 spec，访问任何属性都抛 AttributeError
        bad.name = "bad"
        mock_toolset._tool_dict = {"good": good, "bad": bad}
        mock_toolset._hidden_tools = set()
        # 在导入 kimi_cli 之前注入 mock logger，避免触发 loguru 导入
        import types
        mock_logger = MagicMock()
        mock_kimi_cli = types.ModuleType("kimi_cli")
        mock_kimi_cli.logger = mock_logger
        with patch.dict("sys.modules", {"kimi_cli": mock_kimi_cli}):
            # 重新导入 toolset_to_registry 使其使用 mock 的 kimi_cli
            import importlib
            from kimi_cli.harness.tools import base as base_mod
            importlib.reload(base_mod)
            reg = base_mod.toolset_to_registry(mock_toolset)
            assert reg.has("good") is True
            assert reg.has("bad") is False
            mock_logger.warning.assert_called_once()
