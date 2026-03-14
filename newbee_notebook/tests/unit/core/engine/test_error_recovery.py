from __future__ import annotations

import json

import pytest

from newbee_notebook.core.engine.agent_loop import AgentLoop
from newbee_notebook.core.engine.mode_config import ModeConfigFactory
from newbee_notebook.core.tools.contracts import ToolCallResult, ToolDefinition, ToolQualityMeta


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeLLMClient:
    def __init__(self, *, chat_responses=None, stream_chunks=None, chat_exceptions=None):
        self.chat_responses = list(chat_responses or [])
        self.stream_chunks = list(stream_chunks or [])
        self.chat_exceptions = list(chat_exceptions or [])
        self.chat_calls: list[dict] = []

    async def chat(self, **kwargs):
        self.chat_calls.append(kwargs)
        if self.chat_exceptions:
            exc = self.chat_exceptions.pop(0)
            if exc is not None:
                raise exc
        return self.chat_responses.pop(0)

    async def chat_stream(self, **kwargs):
        for chunk in self.stream_chunks:
            yield chunk


def _tool_call(name: str, arguments: dict, tool_call_id: str = "call-1") -> dict:
    return {
        "id": tool_call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def _chat_response(*, tool_calls=None, content=None, finish_reason=None) -> dict:
    if finish_reason is None:
        finish_reason = "tool_calls" if tool_calls else "stop"
    return {
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls,
                },
            }
        ]
    }


def _stream_chunk(delta: str) -> dict:
    return {"choices": [{"delta": {"content": delta}}]}


def _tool() -> ToolDefinition:
    async def _execute(_: dict) -> ToolCallResult:
        return ToolCallResult(
            content="evidence",
            quality_meta=ToolQualityMeta(
                scope_used="document",
                search_type="keyword",
                result_count=1,
                max_score=0.9,
                quality_band="high",
                scope_relaxation_recommended=False,
            ),
        )

    return ToolDefinition(
        name="knowledge_base",
        description="kb",
        parameters={"type": "object", "properties": {}},
        execute=_execute,
    )


@pytest.mark.anyio
async def test_agent_loop_repairs_missing_required_tool_before_synthesis():
    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(content="I will answer directly"),
            _chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "repair"})]),
        ],
        stream_chunks=[_stream_chunk("Recovered")],
    )
    config = ModeConfigFactory.build(mode="explain", tools=[_tool()])
    loop = AgentLoop(llm_client=llm, tools=[_tool()], mode_config=config)

    result = await loop.run(message="explain", chat_history=[])

    assert result.response == "Recovered"
    assert len(llm.chat_calls) == 2
    repair_messages = llm.chat_calls[1]["messages"]
    assert any("knowledge_base" in str(message.get("content", "")) for message in repair_messages)


@pytest.mark.anyio
async def test_agent_loop_retries_llm_chat_failures():
    llm = _FakeLLMClient(
        chat_responses=[_chat_response(content="done")],
        stream_chunks=[_stream_chunk("final")],
        chat_exceptions=[RuntimeError("transient"), None],
    )
    config = ModeConfigFactory.build(mode="agent", tools=[])
    loop = AgentLoop(llm_client=llm, tools=[], mode_config=config, llm_retry_attempts=2)

    result = await loop.run(message="hello", chat_history=[])

    assert result.response == "done"
    assert len(llm.chat_calls) == 2
