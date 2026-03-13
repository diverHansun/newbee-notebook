"""Built-in runtime tool provider for the batch-2 agent runtime."""

from __future__ import annotations

from typing import Iterable

from newbee_notebook.core.tools.contracts import ToolCallResult, ToolDefinition
from newbee_notebook.core.tools.time import get_current_datetime


async def _not_implemented_knowledge_base(_: dict) -> ToolCallResult:
    raise NotImplementedError("knowledge_base runtime tool is implemented in the next phase")


async def _time_tool(_: dict) -> ToolCallResult:
    return ToolCallResult(content=get_current_datetime())


class BuiltinToolProvider:
    def _build_knowledge_base_tool(self) -> ToolDefinition:
        return ToolDefinition(
            name="knowledge_base",
            description="Retrieve notebook or document-grounded knowledge.",
            parameters={"type": "object", "properties": {"query": {"type": "string"}}},
            execute=_not_implemented_knowledge_base,
        )

    def _build_time_tool(self) -> ToolDefinition:
        return ToolDefinition(
            name="time",
            description="Get the current local date and time.",
            parameters={"type": "object", "properties": {}},
            execute=_time_tool,
        )

    def get_tools(self, mode: str) -> list[ToolDefinition]:
        normalized = str(mode).strip().lower()
        knowledge_base = self._build_knowledge_base_tool()
        if normalized in {"explain", "conclude"}:
            return [knowledge_base]
        if normalized in {"ask", "agent", "chat"}:
            return [knowledge_base, self._build_time_tool()]
        return []
