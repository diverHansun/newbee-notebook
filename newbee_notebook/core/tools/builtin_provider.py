"""Built-in runtime tool provider for the batch-2 agent runtime."""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable, Sequence

from newbee_notebook.core.tools.contracts import ToolCallResult, ToolDefinition
from newbee_notebook.core.shell import (
    BackgroundBashTaskManager,
    ShellEnvironment,
    build_default_shell_environment,
)
from newbee_notebook.core.sandbox import SandboxExecutor
from newbee_notebook.core.tools.bash import build_bash_tool
from newbee_notebook.core.tools.bash_tasks import (
    build_bash_task_list_tool,
    build_bash_task_output_tool,
    build_bash_task_stop_tool,
)
from newbee_notebook.core.tools.filesystem import build_filesystem_tools
from newbee_notebook.core.tools.knowledge_base import build_knowledge_base_tool
from newbee_notebook.core.tools.tavily_tools import (
    build_tavily_crawl_runtime_tool,
    build_tavily_search_runtime_tool,
)
from newbee_notebook.core.tools.time import get_current_datetime
from newbee_notebook.core.tools.zhipu_tools import (
    build_zhipu_web_crawl_runtime_tool,
    build_zhipu_web_search_runtime_tool,
)

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
        filesystem_environment: ShellEnvironment | None = None,
        enable_filesystem_tools: bool = True,
        sandbox_executor: SandboxExecutor | None = None,
        enable_bash_tool: bool = True,
        background_task_manager: BackgroundBashTaskManager | None = None,
    ):
        self._hybrid_search = hybrid_search
        self._semantic_search = semantic_search
        self._keyword_search = keyword_search
        self._default_allowed_document_ids = list(default_allowed_document_ids) if default_allowed_document_ids is not None else None
        self._filesystem_environment = filesystem_environment
        self._enable_filesystem_tools = enable_filesystem_tools
        self._sandbox_executor = sandbox_executor
        self._enable_bash_tool = enable_bash_tool
        self._background_task_manager = background_task_manager
        self._background_task_managers: dict[str, BackgroundBashTaskManager] = {}

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

    def _build_agent_web_tools(self) -> list[ToolDefinition]:
        tools: list[ToolDefinition] = []
        if os.getenv("TAVILY_API_KEY"):
            tools.extend([
                build_tavily_search_runtime_tool(),
                build_tavily_crawl_runtime_tool(),
            ])
        if os.getenv("ZHIPU_API_KEY"):
            tools.extend([
                build_zhipu_web_search_runtime_tool(),
                build_zhipu_web_crawl_runtime_tool(),
            ])
        return tools

    def _resolve_filesystem_environment(
        self,
        filesystem_environment: ShellEnvironment | None,
    ) -> ShellEnvironment:
        return (
            filesystem_environment
            or self._filesystem_environment
            or build_default_shell_environment()
        )

    def _build_agent_filesystem_tools(
        self,
        filesystem_environment: ShellEnvironment | None = None,
    ) -> list[ToolDefinition]:
        if not self._enable_filesystem_tools:
            return []
        environment = self._resolve_filesystem_environment(filesystem_environment)
        return build_filesystem_tools(environment)

    def _build_agent_bash_tools(
        self,
        filesystem_environment: ShellEnvironment | None = None,
    ) -> list[ToolDefinition]:
        if not self._enable_bash_tool:
            return []
        environment = self._resolve_filesystem_environment(filesystem_environment)
        return [
            build_bash_tool(
                environment,
                sandbox_executor=self._sandbox_executor,
                background_task_manager=self._resolve_background_task_manager(environment),
            )
        ]

    def _build_agent_background_task_tools(
        self,
        filesystem_environment: ShellEnvironment | None = None,
    ) -> list[ToolDefinition]:
        if not self._enable_bash_tool:
            return []
        environment = self._resolve_filesystem_environment(filesystem_environment)
        manager = self._resolve_background_task_manager(environment)
        return [
            build_bash_task_list_tool(manager),
            build_bash_task_output_tool(manager),
            build_bash_task_stop_tool(manager),
        ]

    def _resolve_background_task_manager(
        self,
        environment: ShellEnvironment,
    ) -> BackgroundBashTaskManager:
        if self._background_task_manager is not None:
            return self._background_task_manager
        root = (environment.run_dir or environment.cwd) / ".newbee-background-tasks"
        key = str(root.resolve(strict=False)).casefold()
        manager = self._background_task_managers.get(key)
        if manager is None:
            manager = BackgroundBashTaskManager(tasks_root=root)
            self._background_task_managers[key] = manager
        return manager

    def get_tools(
        self,
        mode: str,
        *,
        filesystem_environment: ShellEnvironment | None = None,
    ) -> list[ToolDefinition]:
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
            tools = [knowledge_base, self._build_time_tool()]
            if normalized in {"agent", "chat"}:
                tools.extend(self._build_agent_web_tools())
                tools.extend(
                    self._build_agent_filesystem_tools(filesystem_environment)
                )
                tools.extend(self._build_agent_bash_tools(filesystem_environment))
                tools.extend(
                    self._build_agent_background_task_tools(filesystem_environment)
                )
            return tools
        return []
