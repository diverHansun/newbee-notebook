"""Policy-driven runtime loop for the batch-2 migration."""

from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator
from uuid import uuid4

from newbee_notebook.core.engine.confirmation import ConfirmationGateway
from newbee_notebook.core.skills.contracts import ConfirmationMeta
from newbee_notebook.core.engine.mode_config import ModeConfig
from newbee_notebook.core.engine.stream_events import (
    ConfirmationRequestEvent,
    ContentEvent,
    DoneEvent,
    ErrorEvent,
    IntermediateContentEvent,
    PhaseEvent,
    SourceEvent,
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


@dataclass
class _ToolCallAccumulator:
    index: int
    tool_call_id: str = ""
    tool_type: str = "function"
    function_name: str = ""
    function_arguments: list[str] = field(default_factory=list)

    def merge(self, delta: dict[str, Any]) -> None:
        if not self.tool_call_id:
            self.tool_call_id = str(delta.get("id") or "")
        delta_type = str(delta.get("type") or "")
        if delta_type:
            self.tool_type = delta_type

        function_payload = delta.get("function") or {}
        name_fragment = str(function_payload.get("name") or "")
        if name_fragment:
            self.function_name += name_fragment

        arguments_fragment = function_payload.get("arguments")
        if arguments_fragment is not None:
            self.function_arguments.append(str(arguments_fragment))

    def to_tool_call(self) -> dict[str, Any]:
        return {
            "id": self.tool_call_id or f"stream-tool-call-{self.index + 1}",
            "type": self.tool_type or "function",
            "function": {
                "name": self.function_name,
                "arguments": "".join(self.function_arguments) or "{}",
            },
        }


@dataclass
class _StreamReasoningResult:
    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    used_structured_tool_calls: bool = False


class AgentLoop:
    def __init__(
        self,
        *,
        llm_client: Any,
        tools: list[ToolDefinition],
        mode_config: ModeConfig,
        llm_retry_attempts: int = 1,
        tool_argument_defaults: dict[str, dict[str, Any]] | None = None,
        confirmation_required: frozenset[str] | None = None,
        confirmation_meta: dict[str, ConfirmationMeta] | None = None,
        confirmation_gateway: ConfirmationGateway | None = None,
        force_first_tool_call: bool = False,
        required_tool_call_before_response: str | frozenset[str] | None = None,
    ):
        self._llm_client = llm_client
        self._tools = {tool.name: tool for tool in tools}
        self._mode_config = mode_config
        self._llm_retry_attempts = max(1, llm_retry_attempts)
        self._tool_argument_defaults = {
            str(name): dict(values)
            for name, values in (tool_argument_defaults or {}).items()
        }
        self._confirmation_required = confirmation_required or frozenset()
        self._confirmation_meta = confirmation_meta or {}
        self._confirmation_gateway = confirmation_gateway
        self._force_first_tool_call = force_first_tool_call
        self._required_tool_call_before_response = required_tool_call_before_response
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
    def _extract_message_content(cls, response: Any) -> str:
        message = cls._extract_message(response)
        if isinstance(message, dict):
            return str(message.get("content") or "")
        return str(getattr(message, "content", "") or "")

    @classmethod
    def _extract_tool_calls(cls, response: Any) -> list[dict[str, Any]]:
        message = cls._extract_message(response)
        if isinstance(message, dict):
            tool_calls = list(message.get("tool_calls") or [])
            content = str(message.get("content") or "")
        else:
            tool_calls = list(getattr(message, "tool_calls", []) or [])
            content = str(getattr(message, "content", "") or "")
        normalized = [cls._normalize_tool_call(item) for item in tool_calls]
        if normalized:
            return normalized
        return cls._parse_textual_tool_calls(content)

    @staticmethod
    def _normalize_tool_call(tool_call: Any) -> dict[str, Any]:
        if isinstance(tool_call, dict):
            function_payload = tool_call.get("function") or {}
            return {
                "id": str(tool_call.get("id") or ""),
                "type": str(tool_call.get("type") or "function"),
                "function": {
                    "name": str(function_payload.get("name") or ""),
                    "arguments": str(function_payload.get("arguments") or "{}"),
                },
            }

        function_payload = getattr(tool_call, "function", None)
        return {
            "id": str(getattr(tool_call, "id", "") or ""),
            "type": str(getattr(tool_call, "type", "function") or "function"),
            "function": {
                "name": str(getattr(function_payload, "name", "") or ""),
                "arguments": str(getattr(function_payload, "arguments", "{}") or "{}"),
            },
        }

    @staticmethod
    def _coerce_markup_value(value: str) -> Any:
        normalized = value.strip()
        if not normalized:
            return ""
        try:
            return json.loads(normalized)
        except json.JSONDecodeError:
            pass
        lowered = normalized.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if lowered == "null":
            return None
        try:
            return int(normalized)
        except ValueError:
            pass
        try:
            return float(normalized)
        except ValueError:
            return normalized

    @classmethod
    def _parse_textual_tool_calls(cls, content: str) -> list[dict[str, Any]]:
        if not content or "<tool_call>" not in content:
            return []
        matches = re.findall(r"<tool_call>(.*?)</tool_call>", content, flags=re.DOTALL)
        parsed_calls: list[dict[str, Any]] = []
        for index, body in enumerate(matches, start=1):
            inner = str(body or "").strip()
            if not inner:
                continue
            name_fragment, _, args_fragment = inner.partition("<arg_key>")
            tool_name = name_fragment.strip()
            if not tool_name:
                continue
            arguments: dict[str, Any] = {}
            if args_fragment:
                reconstructed = "<arg_key>" + args_fragment
                pairs = re.findall(
                    r"<arg_key>(.*?)</arg_key>\s*<arg_value>(.*?)</arg_value>",
                    reconstructed,
                    flags=re.DOTALL,
                )
                for key, value in pairs:
                    normalized_key = str(key or "").strip()
                    if not normalized_key:
                        continue
                    arguments[normalized_key] = cls._coerce_markup_value(str(value or ""))
            parsed_calls.append(
                {
                    "id": f"text-tool-call-{index}",
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(arguments, ensure_ascii=False),
                    },
                }
            )
        return parsed_calls

    @staticmethod
    def _coerce_stream_tool_call_index(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _normalize_stream_tool_call_delta(cls, tool_call: Any) -> dict[str, Any]:
        if isinstance(tool_call, dict):
            function_payload = tool_call.get("function") or {}
            return {
                "index": cls._coerce_stream_tool_call_index(tool_call.get("index")),
                "id": str(tool_call.get("id") or ""),
                "type": str(tool_call.get("type") or "function"),
                "function": {
                    "name": str(function_payload.get("name") or ""),
                    "arguments": function_payload.get("arguments"),
                },
            }

        function_payload = getattr(tool_call, "function", None)
        return {
            "index": cls._coerce_stream_tool_call_index(getattr(tool_call, "index", 0)),
            "id": str(getattr(tool_call, "id", "") or ""),
            "type": str(getattr(tool_call, "type", "function") or "function"),
            "function": {
                "name": str(getattr(function_payload, "name", "") or ""),
                "arguments": getattr(function_payload, "arguments", None),
            },
        }


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

    @classmethod
    def _extract_stream_tool_call_deltas(cls, chunk: Any) -> list[dict[str, Any]]:
        choice = cls._extract_choice(chunk)
        if isinstance(choice, dict):
            delta = choice.get("delta") or {}
            tool_calls = delta.get("tool_calls") or []
            return [cls._normalize_stream_tool_call_delta(item) for item in tool_calls]

        delta = getattr(choice, "delta", None)
        if delta is None:
            return []
        if isinstance(delta, dict):
            tool_calls = delta.get("tool_calls") or []
        else:
            tool_calls = getattr(delta, "tool_calls", []) or []
        return [cls._normalize_stream_tool_call_delta(item) for item in tool_calls]

    @staticmethod
    def _build_stream_tool_calls(
        accumulators: dict[int, _ToolCallAccumulator],
    ) -> list[dict[str, Any]]:
        return [accumulators[index].to_tool_call() for index in sorted(accumulators)]

    def _required_tool_choice(self) -> dict[str, Any] | None:
        required = self._mode_config.loop_policy.required_tool_name
        if not required:
            return None
        return {"type": "function", "function": {"name": required}}

    def _resolve_tool_arguments(self, tool_name: str, parsed_arguments: dict[str, Any]) -> dict[str, Any]:
        effective_arguments = dict(self._tool_argument_defaults.get(tool_name, {}))
        effective_arguments.update(parsed_arguments)
        return effective_arguments

    def _relax_scope_if_needed(self, tool_name: str, result: ToolCallResult) -> None:
        quality_meta = result.quality_meta
        if (
            not quality_meta
            or not quality_meta.scope_relaxation_recommended
            or not self._mode_config.tool_policy.allow_scope_relaxation
        ):
            return
        defaults = self._tool_argument_defaults.get(tool_name)
        if not defaults or "filter_document_id" not in defaults:
            return
        defaults = dict(defaults)
        defaults.pop("filter_document_id", None)
        self._tool_argument_defaults[tool_name] = defaults

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
    def _assistant_tool_message(
        tool_calls: list[dict[str, Any]],
        content: str | None = None,
    ) -> dict[str, Any]:
        return {"role": "assistant", "content": content or None, "tool_calls": tool_calls}

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

    def _completion_tool_repair_message(self) -> dict[str, str]:
        required = self._required_tool_call_before_response
        if isinstance(required, frozenset):
            if required:
                required_text = ", ".join(sorted(required))
                requirement_text = f"at least one of: {required_text}"
            else:
                requirement_text = "the required tool"
        else:
            requirement_text = required or "the required tool"
        return {
            "role": "system",
            "content": (
                f"Repair: before you answer the user, you must call {requirement_text}. "
                "Do not provide a prose-only reply yet. Generate a valid tool call now."
            ),
        }

    def _required_tool_satisfied(self, tool_calls_made: list[str]) -> bool:
        required = self._required_tool_call_before_response
        if not required:
            return True
        if isinstance(required, frozenset):
            return bool(required.intersection(tool_calls_made))
        return required in tool_calls_made

    def _required_tool_enforcement_choice(self) -> dict[str, Any] | str | None:
        required = self._required_tool_call_before_response
        if not required:
            return None
        if isinstance(required, frozenset):
            return "required"
        return {
            "type": "function",
            "function": {"name": required},
        }

    @staticmethod
    def _confirmation_args_summary(arguments: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in arguments.items() if key != "content"}

    def _first_turn_tool_repair_message(self) -> dict[str, str]:
        tool_name = self._mode_config.loop_policy.first_turn_tool_repair_name or "the relevant tool"
        return {
            "role": "system",
            "content": (
                f"The current notebook already has grounded context available. "
                f"For this request, you should consider calling {tool_name} first so the answer is based on notebook evidence "
                f"instead of a generic response."
            ),
        }

    @staticmethod
    def _force_first_tool_repair_message() -> dict[str, str]:
        return {
            "role": "system",
            "content": (
                "Repair: this skill run requires calling at least one tool before giving a prose answer. "
                "Generate a valid tool call now."
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
        accepted_bands = self._mode_config.loop_policy.synthesis_quality_bands
        return bool(quality_band and quality_band in accepted_bands)

    async def _stream_reasoning(
        self,
        *,
        messages: list[dict[str, Any]],
        tool_specs: list[dict[str, Any]] | None,
        tool_choice: dict[str, Any] | str | None,
        result: _StreamReasoningResult,
    ) -> AsyncGenerator[IntermediateContentEvent, None]:
        last_error: Exception | None = None

        for attempt in range(self._llm_retry_attempts):
            accumulated_content: list[str] = []
            content_buffer: list[str] = []
            structured_tool_calls: dict[int, _ToolCallAccumulator] = {}
            emitted_business_event = False

            try:
                stream = await self._resolve_stream(
                    self._llm_client.chat_stream(
                        messages=messages,
                        tools=tool_specs,
                        tool_choice=tool_choice,
                        disable_thinking=True,
                    )
                )

                async for chunk in stream:
                    content_delta = self._extract_stream_delta(chunk)
                    if content_delta:
                        accumulated_content.append(content_delta)
                        if structured_tool_calls:
                            emitted_business_event = True
                            yield IntermediateContentEvent(delta=content_delta)
                        else:
                            content_buffer.append(content_delta)

                    tool_call_deltas = self._extract_stream_tool_call_deltas(chunk)
                    if not tool_call_deltas:
                        continue

                    for tool_call_delta in tool_call_deltas:
                        index = int(tool_call_delta.get("index", 0))
                        accumulator = structured_tool_calls.setdefault(
                            index,
                            _ToolCallAccumulator(index=index),
                        )
                        accumulator.merge(tool_call_delta)

                    if content_buffer:
                        emitted_business_event = True
                        yield IntermediateContentEvent(delta="".join(content_buffer))
                        content_buffer.clear()

                result.content = "".join(accumulated_content)
                result.tool_calls = self._build_stream_tool_calls(structured_tool_calls)
                result.used_structured_tool_calls = bool(result.tool_calls)
                if not result.tool_calls:
                    result.tool_calls = self._parse_textual_tool_calls(result.content)
                return
            except Exception as exc:  # pragma: no cover - retry branch verified by tests
                if emitted_business_event or attempt == self._llm_retry_attempts - 1:
                    raise
                last_error = exc

        assert last_error is not None
        raise last_error

    async def stream(
        self,
        *,
        message: str,
        chat_history: list[dict[str, Any]],
    ) -> AsyncGenerator[
        StartEvent
        | WarningEvent
        | PhaseEvent
        | IntermediateContentEvent
        | ConfirmationRequestEvent
        | ToolCallEvent
        | ToolResultEvent
        | SourceEvent
        | ContentEvent
        | DoneEvent
        | ErrorEvent,
        None,
    ]:
        messages = list(chat_history) + [{"role": "user", "content": message}]
        tool_specs = self._tool_specs(list(self._tools.values()))
        collected_sources: list[SourceItem] = []
        tool_calls_made: list[str] = []
        iterations = 0
        retrieval_iterations = 0
        low_quality_tool_streak = 0
        repair_attempts = 0
        first_turn_repair_attempts = 0
        force_first_tool_repair_attempts = 0
        force_synthesis = False
        self._last_iterations = 0
        forced_tool_choice: dict[str, Any] | str | None = (
            "required" if self._force_first_tool_call and tool_specs else None
        )

        yield StartEvent(message_id="runtime")

        while True:
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
                reasoning_result = _StreamReasoningResult()
                async for event in self._stream_reasoning(
                    messages=messages,
                    tool_specs=tool_specs or None,
                    tool_choice=forced_tool_choice or self._required_tool_choice(),
                    result=reasoning_result,
                ):
                    yield event
                iterations += 1
                self._last_iterations = iterations

                tool_calls = reasoning_result.tool_calls
                assistant_content = reasoning_result.content.strip()
                if not tool_calls:
                    if self._force_first_tool_call and not tool_calls_made:
                        if force_first_tool_repair_attempts >= self._mode_config.loop_policy.invalid_tool_repair_limit:
                            yield ErrorEvent(
                                code="invalid_tool_output",
                                message="first turn required a tool call but none was produced",
                                retriable=False,
                            )
                            return
                        force_first_tool_repair_attempts += 1
                        messages.append(self._force_first_tool_repair_message())
                        forced_tool_choice = "required"
                        continue
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
                    first_turn_tool_name = self._mode_config.loop_policy.first_turn_tool_repair_name
                    if (
                        first_turn_tool_name
                        and iterations == 1
                        and first_turn_repair_attempts < self._mode_config.loop_policy.first_turn_tool_repair_limit
                    ):
                        first_turn_repair_attempts += 1
                        messages.append(self._first_turn_tool_repair_message())
                        if self._mode_config.loop_policy.first_turn_tool_repair_force_choice:
                            forced_tool_choice = {
                                "type": "function",
                                "function": {"name": first_turn_tool_name},
                            }
                        continue
                    if (
                        assistant_content
                        and self._required_tool_call_before_response
                        and not self._required_tool_satisfied(tool_calls_made)
                    ):
                        messages.append(self._completion_tool_repair_message())
                        forced_tool_choice = self._required_tool_enforcement_choice()
                        continue
                    if assistant_content and not self._mode_config.loop_policy.require_tool_every_iteration:
                        yield PhaseEvent(stage="synthesizing")
                        yield ContentEvent(delta=assistant_content)
                        self._last_sources = self._dedupe_sources(collected_sources)
                        if self._last_sources:
                            yield SourceEvent(sources=self._last_sources)
                        yield DoneEvent()
                        return
                    break

                repair_attempts = 0
                force_first_tool_repair_attempts = 0
                forced_tool_choice = None
                structured_assistant_content = (
                    assistant_content if reasoning_result.used_structured_tool_calls else None
                )
                messages.append(
                    self._assistant_tool_message(
                        tool_calls,
                        content=structured_assistant_content,
                    )
                )
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
                    effective_arguments = self._resolve_tool_arguments(tool_name, parsed_arguments)
                    tool = self._tools[tool_name]

                    if tool_name in self._confirmation_required and self._confirmation_gateway:
                        request_id = str(uuid4())
                        self._confirmation_gateway.create(request_id)
                        meta = self._confirmation_meta.get(tool_name)
                        yield ConfirmationRequestEvent(
                            request_id=request_id,
                            tool_name=tool_name,
                            args_summary=self._confirmation_args_summary(effective_arguments),
                            description=f"Agent requested to run {tool_name}",
                            action_type=meta.action_type if meta else "confirm",
                            target_type=meta.target_type if meta else "unknown",
                        )
                        approved = await self._confirmation_gateway.wait(request_id, timeout=180.0)
                        if not approved:
                            rejection_result = ToolCallResult(
                                content="The user did not approve this action. The tool call was cancelled.",
                                error="user_rejected",
                            )
                            messages.append(
                                self._tool_result_message(str(tool_call.get("id") or ""), rejection_result)
                            )
                            yield ToolResultEvent(
                                tool_name=tool_name,
                                tool_call_id=str(tool_call.get("id") or ""),
                                success=False,
                                content_preview=rejection_result.content[:200],
                                quality_meta=None,
                            )
                            continue

                    yield ToolCallEvent(
                        tool_name=tool_name,
                        tool_call_id=str(tool_call.get("id") or ""),
                        tool_input=effective_arguments,
                    )
                    result = await tool.execute(effective_arguments)
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
                    self._relax_scope_if_needed(tool_name, result)
                    if (
                        self._required_tool_call_before_response
                        and not self._required_tool_satisfied(tool_calls_made)
                        and result.error is None
                    ):
                        forced_tool_choice = self._required_tool_enforcement_choice()

                    if self._mode_config.loop_policy.require_tool_every_iteration:
                        retrieval_iterations += 1
                        if self._should_enter_synthesis(
                            result,
                            retrieval_iterations=retrieval_iterations,
                        ):
                            force_synthesis = True
                            break
                    else:
                        low_quality_tool_name = self._mode_config.loop_policy.low_quality_tool_name
                        low_quality_bands = self._mode_config.loop_policy.low_quality_bands
                        max_low_quality_tool_streak = self._mode_config.loop_policy.max_low_quality_tool_streak
                        quality_band = getattr(result.quality_meta, "quality_band", None)
                        if (
                            max_low_quality_tool_streak > 0
                            and tool_name == low_quality_tool_name
                            and quality_band in low_quality_bands
                        ):
                            low_quality_tool_streak += 1
                        else:
                            low_quality_tool_streak = 0
                        if low_quality_tool_streak >= max_low_quality_tool_streak > 0:
                            force_synthesis = True
                            break
                else:
                    continue

                if force_synthesis:
                    break

            yield PhaseEvent(stage="synthesizing")
            stream = await self._resolve_stream(
                self._llm_client.chat_stream(
                    messages=messages,
                    tools=None,
                    tool_choice=None,
                    disable_thinking=True,
                )
            )
            synthesis_chunks: list[str] = []
            async for chunk in stream:
                delta = self._extract_stream_delta(chunk)
                if delta:
                    synthesis_chunks.append(delta)

            synthesized_response = "".join(synthesis_chunks).strip()
            synthesis_tool_calls = self._parse_textual_tool_calls(synthesized_response)
            if synthesis_tool_calls:
                messages.append(self._assistant_tool_message(synthesis_tool_calls))
                yield PhaseEvent(stage="retrieving")

                for tool_call in synthesis_tool_calls:
                    function_payload = tool_call.get("function") or {}
                    tool_name = str(function_payload.get("name") or "")
                    raw_arguments = function_payload.get("arguments") or "{}"
                    try:
                        parsed_arguments = json.loads(raw_arguments)
                    except json.JSONDecodeError:
                        parsed_arguments = {}
                    effective_arguments = self._resolve_tool_arguments(tool_name, parsed_arguments)
                    tool = self._tools[tool_name]

                    if tool_name in self._confirmation_required and self._confirmation_gateway:
                        request_id = str(uuid4())
                        self._confirmation_gateway.create(request_id)
                        meta = self._confirmation_meta.get(tool_name)
                        yield ConfirmationRequestEvent(
                            request_id=request_id,
                            tool_name=tool_name,
                            args_summary=self._confirmation_args_summary(effective_arguments),
                            description=f"Agent requested to run {tool_name}",
                            action_type=meta.action_type if meta else "confirm",
                            target_type=meta.target_type if meta else "unknown",
                        )
                        approved = await self._confirmation_gateway.wait(request_id, timeout=180.0)
                        if not approved:
                            rejection_result = ToolCallResult(
                                content="The user did not approve this action. The tool call was cancelled.",
                                error="user_rejected",
                            )
                            messages.append(
                                self._tool_result_message(str(tool_call.get("id") or ""), rejection_result)
                            )
                            yield ToolResultEvent(
                                tool_name=tool_name,
                                tool_call_id=str(tool_call.get("id") or ""),
                                success=False,
                                content_preview=rejection_result.content[:200],
                                quality_meta=None,
                            )
                            continue

                    yield ToolCallEvent(
                        tool_name=tool_name,
                        tool_call_id=str(tool_call.get("id") or ""),
                        tool_input=effective_arguments,
                    )
                    result = await tool.execute(effective_arguments)
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
                    self._relax_scope_if_needed(tool_name, result)
                    if (
                        self._required_tool_call_before_response
                        and not self._required_tool_satisfied(tool_calls_made)
                        and result.error is None
                    ):
                        forced_tool_choice = self._required_tool_enforcement_choice()

                force_synthesis = False
                continue

            if (
                synthesized_response
                and self._required_tool_call_before_response
                and not self._required_tool_satisfied(tool_calls_made)
            ):
                messages.append(self._completion_tool_repair_message())
                forced_tool_choice = self._required_tool_enforcement_choice()
                force_synthesis = False
                continue

            if synthesized_response:
                yield ContentEvent(delta=synthesized_response)
            self._last_sources = self._dedupe_sources(collected_sources)
            if self._last_sources:
                yield SourceEvent(sources=self._last_sources)
            yield DoneEvent()
            return

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

    @staticmethod
    async def _resolve_stream(stream_or_awaitable: Any) -> Any:
        if inspect.isawaitable(stream_or_awaitable):
            return await stream_or_awaitable
        return stream_or_awaitable

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
            elif isinstance(event, SourceEvent):
                sources = list(event.sources)
            elif isinstance(event, ErrorEvent):
                raise RuntimeError(event.message)

        iterations = max(iterations, int(getattr(self, "_last_iterations", 0)))
        if not iterations:
            iterations = max(1, len(getattr(self._llm_client, "chat_calls", [])))

        return AgentResult(
            response="".join(response_chunks),
            sources=sources or getattr(self, "_last_sources", []),
            tool_calls_made=tool_calls_made,
            iterations=max(iterations, len(getattr(self._llm_client, "chat_calls", []))),
        )
