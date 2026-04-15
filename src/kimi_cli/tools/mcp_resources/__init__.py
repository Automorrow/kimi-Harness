"""MCP resource tools for listing and reading MCP resources."""

from __future__ import annotations

from kosong.tooling import CallableTool2, ToolError, ToolReturnValue
from pydantic import BaseModel, Field

from kimi_cli.soul.agent import Runtime
from kimi_cli.soul.toolset import KimiToolset


class ListMcpResourcesParams(BaseModel):
    """No-op input model for MCP resource listing."""


class ReadMcpResourceParams(BaseModel):
    """Arguments for reading an MCP resource."""

    server: str = Field(description="MCP server name")
    uri: str = Field(description="Resource URI")


class ListMcpResources(CallableTool2[ListMcpResourcesParams]):
    """List MCP resources available from connected servers."""

    name: str = "ListMcpResources"
    description: str = "List MCP resources discovered from connected servers."
    params: type[ListMcpResourcesParams] = ListMcpResourcesParams

    def __init__(self, runtime: Runtime):
        super().__init__()
        self._runtime = runtime

    async def __call__(self, params: ListMcpResourcesParams) -> ToolReturnValue:
        toolset = self._runtime.agent.toolset
        if not isinstance(toolset, KimiToolset):
            return ToolError(
                message="MCP resources are not available.",
                brief="MCP not available",
            )
        try:
            resources = await toolset.list_mcp_resources()
        except Exception as e:
            return ToolError(
                message=f"Failed to list MCP resources: {e}",
                brief="MCP resource list failed",
            )
        if not resources:
            return ToolReturnValue(
                is_error=False,
                output="(no MCP resources)",
                message="No MCP resources available.",
            )
        lines = [
            f"{item['server']}:{item['uri']} {item['description']}".strip()
            for item in resources
        ]
        return ToolReturnValue(
            is_error=False,
            output="\n".join(lines),
            message=f"Listed {len(resources)} MCP resource(s).",
        )


class ReadMcpResource(CallableTool2[ReadMcpResourceParams]):
    """Read one resource from an MCP server."""

    name: str = "ReadMcpResource"
    description: str = "Read an MCP resource by server and URI."
    params: type[ReadMcpResourceParams] = ReadMcpResourceParams

    def __init__(self, runtime: Runtime):
        super().__init__()
        self._runtime = runtime

    async def __call__(self, params: ReadMcpResourceParams) -> ToolReturnValue:
        toolset = self._runtime.agent.toolset
        if not isinstance(toolset, KimiToolset):
            return ToolError(
                message="MCP resources are not available.",
                brief="MCP not available",
            )
        try:
            output = await toolset.read_mcp_resource(params.server, params.uri)
        except RuntimeError as e:
            return ToolError(
                message=str(e),
                brief="MCP server not connected",
            )
        except Exception as e:
            return ToolError(
                message=f"Failed to read MCP resource: {e}",
                brief="MCP resource read failed",
            )
        return ToolReturnValue(
            is_error=False,
            output=output,
            message=f"Read MCP resource {params.uri} from {params.server}.",
        )
