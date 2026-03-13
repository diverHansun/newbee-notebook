"""Policy-driven runtime loop for the batch-2 migration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from newbee_notebook.core.engine.mode_config import ModeConfig
from newbee_notebook.core.engine.stream_events import (
    ContentEvent,
    DoneEvent,
    ErrorEvent,
    PhaseEvent,
    StartEvent,
    ToolCallEvent,
    ToolResultEvent,
    WarningEvent,
)
from newbee_notebook.core.tools.contracts import SourceItem, ToolCallResult, ToolDefinition


@dataclass(frozen=True)
class AgentResult:
    response: str
    sources: list[SourceItem] = field(default_factory=list)
    tool_calls_made: list[str] = field(default_factory=list)
    iterations: int = 0


class AgentLoop:
    def __init__(
        self,
        *,
        llm_client: Any,
        tools: list[ToolDefinition],
        mode_config: ModeConfig,
        llm_retry_attempts: int = 1,
    ):
        self._llm_client = llm_client
        self._tools = {tool.name: tool for tool in tools}
        self._mode_config = mode_config
        self._llm_retry_attempts = max(1, llm_retry_attempts)
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @staticmethod
    def _tool_specs(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]

    @staticmethod
    def _extract_choice(response: Any) -> dict[str, Any]:
        if isinstance(response, dict):
            return (response.get("choices") or [{}])[0]
        return getattr(response, "choices", [{}])[0]

    @classmethod
    def _extract_message(cls, response: Any) -> dict[str, Any]:
        choice = cls._extract_choice(response)
        if isinstance(choice, dict):
            return choice.get("message") or {}
        return getattr(choice, "message", {}) or {}

    @classmethod
    def _extract_tool_calls(cls, response: Any) -> list[dict[str, Any]]:
        message = cls._extract_message(response)
        if isinstance(message, dict):
            return list(message.get("tool_calls") or [])
        return list(getattr(message, "tool_calls", []) or [])

    @classmethod
    def _extract_stream_delta(cls, chunk: Any) -> str:
        choice = cls._extract_choice(chunk)
        if isinstance(choice, dict):
            delta = choice.get("delta") or {}
            return str(delta.get("content") or "")
        delta = getattr(choice, "delta", {}) or {}
        if isinstance(delta, dict):
            return str(delta.get("content") or "")
        return str(getattr(delta, "content", "") or "")

    def _required_tool_choice(self) -> dict[str, Any] | None:
        required = self._mode_config.loop_policy.required_tool_name
        if not required:
            return None
        return {"type": "function", "function": {"name": required}}

    async def _chat_with_retry(self, **kwargs) -> Any:
        last_error: Exception | None = None
        for _ in range(self._llm_retry_attempts):
            try:
                return await self._llm_client.chat(**kwargs)
            except Exception as exc:  # pragma: no cover - retry branch verified by tests
                last_error = exc
        assert last_error is not None
        raise last_error

    @staticmethod
    def _assistant_tool_message(tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
        return {"role": "assistant", "content": None, "tool_calls": tool_calls}

    @staticmethod
    def _tool_result_message(tool_call_id: str, result: ToolCallResult) -> dict[str, Any]:
        if result.error:
            content = f"Error: {result.error}"
        else:
            content = result.content
        return {"role": "tool", "tool_call_id": tool_call_id, "content": content}

    def _repair_message(self) -> dict[str, str]:
        required = self._mode_config.loop_policy.required_tool_name or "the required tool"
        return {
            "role": "system",
            "content": (
                f"Repair: this mode must call {required} before producing the final answer. "
                f"Generate a valid {required} tool call now."
            ),
        }

    def _should_enter_synthesis(
        self,
        result: ToolCallResult,
        *,
        retrieval_iterations: int,
    ) -> bool:
        if not self._mode_config.loop_policy.require_tool_every_iteration:
            return False
        if retrieval_iterations >= self._mode_config.loop_policy.max_retrieval_iterations:
            return True
        quality_band = getattr(result.quality_meta, "quality_band", None)
        return quality_band == "high"

    async def stream(
        self,
        *,
        message: str,
        chat_history: list[dict[str, Any]],
    ) -> AsyncGenerator[
        StartEvent | WarningEvent | PhaseEvent | ToolCallEvent | ToolResultEvent | ContentEvent | DoneEvent | ErrorEvent,
        None,
    ]:
        messages = list(chat_history) + [{"role": "user", "content": message}]
        tool_specs = self._tool_specs(list(self._tools.values()))
        collected_sources: list[SourceItem] = []
        tool_calls_made: list[str] = []
        iterations = 0
        retrieval_iterations = 0
        repair_attempts = 0
        force_synthesis = False

        yield StartEvent(message_id="runtime")

        while not force_synthesis:
            if self._cancelled:
                yield DoneEvent()
                return
            if iterations >= self._mode_config.loop_policy.max_total_iterations:
                yield ErrorEvent(
                    code="iteration_limit",
                    message="maximum runtime iterations exceeded",
                    retriable=False,
                )
                return

            yield PhaseEvent(stage="reasoning")
            response = await self._chat_with_retry(
                messages=messages,
                tools=tool_specs or None,
                tool_choice=self._required_tool_choice(),
            )
            iterations += 1

            tool_calls = self._extract_tool_calls(response)
            if not tool_calls:
                if (
                    self._mode_config.loop_policy.require_tool_every_iteration
                    and retrieval_iterations < self._mode_config.loop_policy.max_retrieval_iterations
                ):
                    if repair_attempts >= self._mode_config.loop_policy.invalid_tool_repair_limit:
                        yield ErrorEvent(
                            code="invalid_tool_output",
                            message="required tool call was not produced",
                            retriable=False,
                        )
                        return
                    repair_attempts += 1
                    messages.append(self._repair_message())
                    continue
                break

            repair_attempts = 0
            messages.append(self._assistant_tool_message(tool_calls))
            yield PhaseEvent(stage="retrieving")

            for tool_call in tool_calls:
                function_payload = tool_call.get("function") or {}
                tool_name = str(function_payload.get("name") or "")
                if (
                    self._mode_config.loop_policy.require_tool_every_iteration
                    and tool_name != self._mode_config.loop_policy.required_tool_name
                ):
                    if repair_attempts >= self._mode_config.loop_policy.invalid_tool_repair_limit:
                        yield ErrorEvent(
                            code="invalid_tool_output",
                            message="unexpected tool used in retrieval-required mode",
                            retriable=False,
                        )
                        return
                    repair_attempts += 1
                    messages.append(self._repair_message())
                    break

                raw_arguments = function_payload.get("arguments") or "{}"
                try:
                    parsed_arguments = json.loads(raw_arguments)
                except json.JSONDecodeError:
                    parsed_arguments = {}

                yield ToolCallEvent(
                    tool_name=tool_name,
                    tool_call_id=str(tool_call.get("id") or ""),
                    tool_input=parsed_arguments,
                )
                tool = self._tools[tool_name]
                result = await tool.execute(parsed_arguments)
                tool_calls_made.append(tool_name)
                collected_sources.extend(result.sources)
                messages.append(self._tool_result_message(str(tool_call.get("id") or ""), result))
                yield ToolResultEvent(
                    tool_name=tool_name,
                    tool_call_id=str(tool_call.get("id") or ""),
                    success=result.error is None,
                    content_preview=result.content[:200],
                    quality_meta=result.quality_meta,
                )

                if self._mode_config.loop_policy.require_tool_every_iteration:
                    retrieval_iterations += 1
                    if self._should_enter_synthesis(
                        result,
                        retrieval_iterations=retrieval_iterations,
                    ):
                        force_synthesis = True
                        break
            else:
                continue

            if force_synthesis:
                break

        yield PhaseEvent(stage="synthesizing")
        async for chunk in self._llm_client.chat_stream(
            messages=messages,
            tools=None,
            tool_choice=None,
        ):
            delta = self._extract_stream_delta(chunk)
            if delta:
                yield ContentEvent(delta=delta)
        self._last_sources = self._dedupe_sources(collected_sources)
        yield DoneEvent()

    @staticmethod
    def _dedupe_sources(sources: list[SourceItem]) -> list[SourceItem]:
        deduped: list[SourceItem] = []
        seen: set[tuple[str, str, str]] = set()
        for item in sources:
            key = (item.document_id, item.chunk_id, item.text)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    async def run(
        self,
        *,
        message: str,
        chat_history: list[dict[str, Any]],
    ) -> AgentResult:
        response_chunks: list[str] = []
        sources: list[SourceItem] = []
        tool_calls_made: list[str] = []
        iterations = 0

        async for event in self.stream(message=message, chat_history=chat_history):
            if isinstance(event, ContentEvent):
                response_chunks.append(event.delta)
            elif isinstance(event, ToolCallEvent):
                tool_calls_made.append(event.tool_name)
            elif isinstance(event, ErrorEvent):
                raise RuntimeError(event.message)

        # A plain open-loop answer may not call any tool but still uses one reasoning iteration.
        if not iterations:
            iterations = max(1, len(getattr(self._llm_client, "chat_calls", [])))

        return AgentResult(
            response="".join(response_chunks),
            sources=getattr(self, "_last_sources", []),
            tool_calls_made=tool_calls_made,
            iterations=max(iterations, len(getattr(self._llm_client, "chat_calls", []))),
        )
