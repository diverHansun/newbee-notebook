"""Adapter from MCP tool metadata to runtime ToolDefinition."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from newbee_notebook.core.mcp.types import MCPToolInfo
from newbee_notebook.core.tools.contracts import ToolCallResult, ToolDefinition

MCPToolInvoker = Callable[[str, dict[str, Any]], Awaitable[Any]]


class MCPToolAdapter:
    @staticmethod
    def adapt(tool_info: MCPToolInfo, *, invoke_tool: MCPToolInvoker) -> ToolDefinition:
        async def _execute(payload: dict[str, Any]) -> ToolCallResult:
            try:
                response = await invoke_tool(tool_info.name, payload)
            except Exception as exc:  # pragma: no cover
                return ToolCallResult(
                    content=str(exc),
                    error=str(exc),
                    metadata={"server_name": tool_info.server_name, "tool_name": tool_info.name},
                )

            result = MCPToolAdapter.convert_response(response)
            metadata = dict(result.metadata)
            metadata.update({"server_name": tool_info.server_name, "tool_name": tool_info.name})
            return ToolCallResult(
                content=result.content,
                sources=result.sources,
                quality_meta=result.quality_meta,
                metadata=metadata,
                error=result.error,
            )

        return ToolDefinition(
            name=tool_info.qualified_name,
            description=tool_info.description,
            parameters=tool_info.input_schema,
            execute=_execute,
        )

    @staticmethod
    def convert_response(response: Any) -> ToolCallResult:
        content_items = MCPToolAdapter._get_value(response, "content") or []
        texts: list[str] = []
        for item in content_items:
            item_type = MCPToolAdapter._get_value(item, "type")
            if item_type == "text":
                text = MCPToolAdapter._get_value(item, "text")
                if text:
                    texts.append(str(text))

        content = "\n".join(texts).strip()
        is_error = bool(MCPToolAdapter._get_value(response, "isError"))
        error = content or "MCP tool error" if is_error else None
        return ToolCallResult(content=content, error=error)

    @staticmethod
    def _get_value(payload: Any, key: str) -> Any:
        if isinstance(payload, dict):
            return payload.get(key)
        return getattr(payload, key, None)
