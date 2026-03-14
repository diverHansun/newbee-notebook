"""Built-in runtime tool provider for the batch-2 agent runtime."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

from newbee_notebook.core.tools.contracts import ToolCallResult, ToolDefinition
from newbee_notebook.core.tools.knowledge_base import build_knowledge_base_tool
from newbee_notebook.core.tools.time import get_current_datetime

SearchExecutor = Callable[[dict], Awaitable[list[dict]]]


async def _time_tool(_: dict) -> ToolCallResult:
    return ToolCallResult(content=get_current_datetime())


class BuiltinToolProvider:
    def __init__(
        self,
        *,
        hybrid_search: SearchExecutor | None = None,
        semantic_search: SearchExecutor | None = None,
        keyword_search: SearchExecutor | None = None,
        default_allowed_document_ids: Sequence[str] | None = None,
    ):
        self._hybrid_search = hybrid_search
        self._semantic_search = semantic_search
        self._keyword_search = keyword_search
        self._default_allowed_document_ids = list(default_allowed_document_ids) if default_allowed_document_ids is not None else None

    def _build_knowledge_base_tool(
        self,
        *,
        default_search_type: str = "hybrid",
        default_max_results: int = 5,
    ) -> ToolDefinition:
        return build_knowledge_base_tool(
            hybrid_search=self._hybrid_search,
            semantic_search=self._semantic_search,
            keyword_search=self._keyword_search,
            allowed_document_ids=self._default_allowed_document_ids,
            default_search_type=default_search_type,
            default_max_results=default_max_results,
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
        if normalized in {"explain", "conclude"}:
            if normalized == "explain":
                knowledge_base = self._build_knowledge_base_tool(
                    default_search_type="keyword",
                    default_max_results=5,
                )
            else:
                knowledge_base = self._build_knowledge_base_tool(
                    default_search_type="hybrid",
                    default_max_results=8,
                )
            return [knowledge_base]
        if normalized in {"ask", "agent", "chat"}:
            knowledge_base = self._build_knowledge_base_tool(
                default_search_type="hybrid",
                default_max_results=5,
            )
            return [knowledge_base, self._build_time_tool()]
        return []
