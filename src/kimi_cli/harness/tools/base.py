"""Harness 工具抽象 - BaseTool 接口、ToolRegistry、KosongToolAdapter.

提供与 OpenHarness 对齐的标准化工具抽象层，同时通过适配器模式
兼容 kimi-cli 现有的 kosong 工具系统，无需重写现有工具。
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from kosong.tooling import CallableTool, CallableTool2


# ---------------------------------------------------------------------------
# 工具输入 / 输出 / 上下文 数据模型
# ---------------------------------------------------------------------------


class ToolInput(BaseModel):
    """所有工具输入的基类。

    每个具体工具应继承此类并定义自己的字段，利用 Pydantic
    提供的类型安全验证和自动 JSON Schema 生成。
    """

    model_config = {"extra": "allow"}


class DynamicToolInput(ToolInput):
    """动态工具输入 - 用于适配无法预知 schema 的 kosong 工具。

    将原始 JSON 字典作为 ``params`` 承载，同时保留类型安全的外壳。
    """

    params: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class HarnessToolResult:
    """标准化工具执行结果。

    Attributes:
        output: 工具输出的文本内容。
        is_error: 是否为错误结果。
        metadata: 附加元数据（如耗时、token 数等）。
    """

    output: str
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolExecutionContext:
    """工具执行上下文。

    Attributes:
        cwd: 当前工作目录。
        metadata: 附加元数据（含 tool_registry、ask_user_prompt 等）。
    """

    cwd: Path
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# BaseTool 抽象基类
# ---------------------------------------------------------------------------


class BaseTool(ABC):
    """所有 Harness 工具的抽象基类。

    对齐 OpenHarness 的 ``BaseTool`` 接口，提供：
    - ``name`` / ``description``: 工具自描述
    - ``input_model``: Pydantic 模型，结构化类型安全输入
    - ``execute()``: 异步执行入口
    - ``is_read_only()``: 是否只读（用于权限判断）
    - ``to_api_schema()``: 自动生成 JSON Schema（供 LLM 理解工具能力）
    """

    name: str
    description: str
    input_model: type[ToolInput]

    @abstractmethod
    async def execute(
        self,
        arguments: ToolInput,
        context: ToolExecutionContext,
    ) -> HarnessToolResult:
        """执行工具。

        Args:
            arguments: 经过 Pydantic 验证的输入参数。
            context: 执行上下文（含 cwd、metadata）。

        Returns:
            标准化的工具执行结果。
        """

    def is_read_only(self, arguments: ToolInput) -> bool:
        """返回此工具调用是否为只读操作。

        只读工具在权限检查中自动放行。
        """
        del arguments
        return False

    def to_api_schema(self) -> dict[str, Any]:
        """生成供 LLM API 使用的工具 Schema。

        返回格式兼容 Anthropic Messages API 的 tool 定义。
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
        }


# ---------------------------------------------------------------------------
# ToolRegistry - 独立的工具注册表
# ---------------------------------------------------------------------------


class ToolRegistry:
    """工具注册表 - 只负责工具的注册、查找和 Schema 导出。

    从 ``KimiToolset`` 中分离出来的纯注册职责，使工具管理
    与工具执行、Hook 集成、MCP 桥接解耦。
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册一个工具实例。

        Args:
            tool: 实现 ``BaseTool`` 接口的工具实例。
        """
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> bool:
        """移除一个已注册的工具。

        Returns:
            是否成功移除（工具不存在时返回 False）。
        """
        return self._tools.pop(name, None) is not None

    def get(self, name: str) -> BaseTool | None:
        """按名称查找工具。

        Returns:
            工具实例，未找到时返回 None。
        """
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        """检查工具是否已注册。"""
        return name in self._tools

    def list_tools(self) -> list[BaseTool]:
        """返回所有已注册的工具。"""
        return list(self._tools.values())

    def list_names(self) -> list[str]:
        """返回所有已注册的工具名称。"""
        return list(self._tools.keys())

    def to_api_schemas(self) -> list[dict[str, Any]]:
        """返回所有工具的 API Schema 列表。"""
        return [tool.to_api_schema() for tool in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


# ---------------------------------------------------------------------------
# KosongToolAdapter - 将 kosong 工具适配为 BaseTool
# ---------------------------------------------------------------------------


def _build_dynamic_input_model(
    parameters: dict[str, Any],
) -> type[DynamicToolInput]:
    """从 kosong 工具的 parameters JSON Schema 动态构建 Pydantic 模型。

    Args:
        parameters: kosong 工具的 JSON Schema 参数定义。

    Returns:
        一个继承 ``DynamicToolInput`` 的 Pydantic 模型类。
    """
    properties = parameters.get("properties", {})
    required = set(parameters.get("required", []))

    fields: dict[str, Any] = {}
    for prop_name, prop_schema in properties.items():
        prop_type = _json_schema_to_python_type(prop_schema)
        if prop_name in required:
            fields[prop_name] = (prop_type, ...)
        else:
            fields[prop_name] = (prop_type | None, None)

    model_name = "KosongAdapterInput"
    return type(model_name, (DynamicToolInput,), fields)  # type: ignore[return-value]


def _json_schema_to_python_type(schema: dict[str, Any]) -> type:
    """将 JSON Schema 类型映射为 Python 类型。

    支持基本类型、数组、对象和枚举。
    """
    json_type = schema.get("type", "string")

    type_map: dict[str, type] = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "null": type(None),
        "array": list,
        "object": dict,
    }

    if "enum" in schema:
        return str  # 枚举统一用 str

    if json_type == "array":
        items_type = _json_schema_to_python_type(schema.get("items", {}))
        return list[items_type]  # type: ignore[return-value]

    if json_type == "object":
        return dict[str, Any]

    return type_map.get(json_type, str)


class KosongToolAdapter(BaseTool):
    """将 kosong CallableTool / CallableTool2 适配为 Harness BaseTool。

    通过适配器模式，使现有 kosong 工具无需重写即可接入
    Harness 的 ToolRegistry 和标准化执行流程。

    Usage::

        kosong_tool = SomeKosongTool()
        adapter = KosongToolAdapter(kosong_tool)
        registry.register(adapter)
    """

    def __init__(self, kosong_tool: CallableTool[Any] | CallableTool2[Any]) -> None:
        self._inner = kosong_tool
        self.name = kosong_tool.name
        self.description = kosong_tool.description or "No description provided."
        self.input_model = _build_dynamic_input_model(kosong_tool.parameters)

    async def execute(
        self,
        arguments: ToolInput,
        context: ToolExecutionContext,
    ) -> HarnessToolResult:
        """执行 kosong 工具并转换结果。"""
        # 将 Pydantic 模型转为原始 dict 供 kosong 使用
        raw_args = arguments.model_dump(exclude_none=True)
        # DynamicToolInput 的 params 需要展开
        if isinstance(arguments, DynamicToolInput) and "params" in raw_args:
            raw_args = raw_args["params"]

        try:
            ret = await self._inner.call(raw_args)
        except Exception as e:
            return HarnessToolResult(
                output=str(e),
                is_error=True,
                metadata={"exception_type": type(e).__name__},
            )

        # 将 kosong 返回值转换为 HarnessToolResult
        return self._convert_result(ret)

    def is_read_only(self, arguments: ToolInput) -> bool:
        """根据工具名称推断是否只读。

        已知的只读工具：ReadFile, Glob, Grep, WebSearch, WebFetch, LSP
        """
        readonly_names = {
            "read_file", "glob", "grep", "web_search", "web_fetch",
            "list_mcp_resources", "read_mcp_resource", "tool_search",
            "lsp", "brief", "config", "ask_user_question",
        }
        return self.name.lower() in readonly_names

    def to_api_schema(self) -> dict[str, Any]:
        """直接使用 kosong 工具的原始 schema，确保兼容性。"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self._inner.parameters,
        }

    @staticmethod
    def _convert_result(ret: Any) -> HarnessToolResult:
        """将 kosong ToolOk / ToolError 转换为 HarnessToolResult。"""
        from kosong.tooling import ToolError, ToolOk

        if isinstance(ret, ToolOk):
            output_parts: list[str] = []
            if hasattr(ret, "output") and ret.output:
                for part in ret.output:
                    if hasattr(part, "text"):
                        output_parts.append(part.text)
                    elif isinstance(part, str):
                        output_parts.append(part)
            return HarnessToolResult(
                output="\n".join(output_parts) if output_parts else "",
                is_error=False,
            )
        elif isinstance(ret, ToolError):
            return HarnessToolResult(
                output=ret.message or str(ret),
                is_error=True,
                metadata={"brief": getattr(ret, "brief", "")},
            )
        else:
            return HarnessToolResult(
                output=str(ret) if ret else "",
                is_error=False,
            )


# ---------------------------------------------------------------------------
# KimiToolset → ToolRegistry 桥接
# ---------------------------------------------------------------------------


def toolset_to_registry(toolset: Any) -> ToolRegistry:
    """将现有的 ``KimiToolset`` 实例桥接为 ``ToolRegistry``。

    遍历 toolset 中所有已注册的 kosong 工具，为每个工具创建
    ``KosongToolAdapter`` 并注册到新的 ``ToolRegistry`` 中。
    跳过适配失败的工具并记录警告。

    Args:
        toolset: ``KimiToolset`` 实例。

    Returns:
        包含所有工具适配器的 ``ToolRegistry``。
    """
    from kimi_cli import logger

    registry = ToolRegistry()
    for tool in toolset.tools:
        try:
            adapter = KosongToolAdapter(tool)
            registry.register(adapter)
        except Exception as e:
            logger.warning(
                "Failed to bridge tool '{name}' to ToolRegistry: {error}",
                name=getattr(tool, "name", "?"),
                error=e,
            )
    return registry
