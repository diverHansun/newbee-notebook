"""Runtime tool registry for batch-2."""

from __future__ import annotations

from typing import Iterable

from newbee_notebook.core.tools.builtin_provider import BuiltinToolProvider
from newbee_notebook.core.tools.contracts import ToolDefinition


class ToolRegistry:
    def __init__(self, builtin_provider: BuiltinToolProvider):
        self._builtin_provider = builtin_provider

    def get_tools(
        self,
        mode: str,
        external_tools: Iterable[ToolDefinition] | None = None,
    ) -> list[ToolDefinition]:
        tools = list(self._builtin_provider.get_tools(mode))
        if str(mode).strip().lower() == "agent" and external_tools:
            tools.extend(list(external_tools))
        return tools
