from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from newbee_notebook.core.engine.agent_loop import AgentLoop
from newbee_notebook.core.engine.mode_config import ModeConfigFactory
from newbee_notebook.core.tools.contracts import SourceItem, ToolCallResult, ToolDefinition, ToolQualityMeta


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeLLMClient:
    def __init__(self, *, chat_responses=None, stream_chunks=None, chat_exceptions=None):
        self.chat_responses = list(chat_responses or [])
        self.stream_chunks = list(stream_chunks or [])
        self.chat_exceptions = list(chat_exceptions or [])
        self.chat_calls: list[dict] = []
        self.stream_calls: list[dict] = []

    async def chat(self, **kwargs):
        self.chat_calls.append(kwargs)
        if self.chat_exceptions:
            exc = self.chat_exceptions.pop(0)
            if exc is not None:
                raise exc
        return self.chat_responses.pop(0)

    async def chat_stream(self, **kwargs):
        self.stream_calls.append(kwargs)
        for chunk in self.stream_chunks:
            yield chunk


class _AwaitableStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def __aiter__(self):
        self._iter = iter(self._chunks)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _RealShapedLLMClient(_FakeLLMClient):
    async def chat_stream(self, **kwargs):
        self.stream_calls.append(kwargs)
        return _AwaitableStream(self.stream_chunks)


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


def _object_tool_call(name: str, arguments: dict, tool_call_id: str = "call-1"):
    return SimpleNamespace(
        id=tool_call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def _quality(quality_band: str) -> ToolQualityMeta:
    return ToolQualityMeta(
        scope_used="document",
        search_type="keyword",
        result_count=1 if quality_band != "empty" else 0,
        max_score=0.8 if quality_band == "high" else 0.3,
        quality_band=quality_band,
        scope_relaxation_recommended=quality_band != "high",
    )


def _tool(name: str, result: ToolCallResult) -> ToolDefinition:
    async def _execute(_: dict) -> ToolCallResult:
        return result

    return ToolDefinition(
        name=name,
        description=f"{name} tool",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}},
        execute=_execute,
    )


def _recording_tool(name: str, results: list[ToolCallResult], captured_payloads: list[dict]) -> ToolDefinition:
    async def _execute(payload: dict) -> ToolCallResult:
        captured_payloads.append(dict(payload))
        return results.pop(0)

    return ToolDefinition(
        name=name,
        description=f"{name} tool",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}},
        execute=_execute,
    )


@pytest.mark.anyio
async def test_agent_loop_open_loop_falls_back_to_synthesis_stream_when_final_reasoning_content_is_empty():
    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "x"})]),
            _chat_response(content=''),
        ],
        stream_chunks=[_stream_chunk('Hello'), _stream_chunk(' world')],
    )
    tool = _tool(
        "knowledge_base",
        ToolCallResult(
            content="1. [Doc] evidence",
            sources=[SourceItem(document_id="doc-1", chunk_id="chunk-1", title="Doc", text="evidence", score=0.8)],
            quality_meta=_quality("medium"),
        ),
    )
    config = ModeConfigFactory.build(mode="agent", tools=[tool])
    loop = AgentLoop(llm_client=llm, tools=[tool], mode_config=config)

    result = await loop.run(message="question", chat_history=[])

    assert result.response == "Hello world"
    assert result.tool_calls_made == ["knowledge_base"]
    assert len(result.sources) == 1
    assert result.iterations == 2
    assert len(llm.chat_calls) == 2
    assert len(llm.stream_calls) == 1


@pytest.mark.anyio
async def test_ask_loop_repairs_first_turn_without_tool_call_once():
    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(content="I need more information."),
            _chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "x"})]),
            _chat_response(content="Here is the grounded answer."),
        ],
        stream_chunks=[_stream_chunk("Grounded"), _stream_chunk(" answer")],
    )
    tool = _tool(
        "knowledge_base",
        ToolCallResult(
            content="evidence",
            sources=[SourceItem(document_id="doc-1", chunk_id="chunk-1", title="Doc", text="evidence", score=0.7)],
            quality_meta=_quality("medium"),
        ),
    )
    config = ModeConfigFactory.build(mode="ask", tools=[tool, _tool("time", ToolCallResult(content="now"))])
    loop = AgentLoop(llm_client=llm, tools=[tool], mode_config=config)

    result = await loop.run(message="ask", chat_history=[])

    assert result.response == "Here is the grounded answer."
    assert result.tool_calls_made == ["knowledge_base"]
    assert len(llm.chat_calls) == 3
    assert llm.chat_calls[0]["tool_choice"] is None
    assert llm.chat_calls[1]["tool_choice"] == {
        "type": "function",
        "function": {"name": "knowledge_base"},
    }
    assert llm.chat_calls[2]["tool_choice"] is None
    assert len(llm.stream_calls) == 0
    repair_messages = [msg for msg in llm.chat_calls[1]["messages"] if msg.get("role") == "system" and "knowledge_base" in str(msg.get("content"))]
    assert repair_messages


@pytest.mark.anyio
async def test_agent_loop_can_require_a_first_turn_tool_call_for_skill_runs():
    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(tool_calls=[_tool_call("list_notes", {})]),
            _chat_response(content="I found the note and can continue."),
        ],
        stream_chunks=[_stream_chunk("I found the note and can continue.")],
    )
    tool = _tool(
        "list_notes",
        ToolCallResult(content="Found 1 note", quality_meta=_quality("medium")),
    )
    config = ModeConfigFactory.build(mode="agent", tools=[tool])
    loop = AgentLoop(
        llm_client=llm,
        tools=[tool],
        mode_config=config,
        force_first_tool_call=True,
    )

    result = await loop.run(message="delete the note", chat_history=[])

    assert result.tool_calls_made == ["list_notes"]
    assert llm.chat_calls[0]["tool_choice"] == "required"
    assert llm.chat_calls[1]["tool_choice"] is None


@pytest.mark.anyio
async def test_agent_loop_early_synthesizes_when_quality_gate_is_high():
    llm = _FakeLLMClient(
        chat_responses=[_chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "x"})])],
        stream_chunks=[_stream_chunk("Grounded answer")],
    )
    tool = _tool(
        "knowledge_base",
        ToolCallResult(
            content="evidence",
            sources=[SourceItem(document_id="doc-1", chunk_id="chunk-1", title="Doc", text="evidence", score=0.9)],
            quality_meta=_quality("high"),
        ),
    )
    config = ModeConfigFactory.build(mode="explain", tools=[tool])
    loop = AgentLoop(llm_client=llm, tools=[tool], mode_config=config)

    result = await loop.run(message="explain", chat_history=[])

    assert result.response == "Grounded answer"
    assert result.iterations == 1
    assert len(llm.chat_calls) == 1
    assert len(llm.stream_calls) == 1


@pytest.mark.anyio
async def test_agent_loop_forces_synthesis_at_retrieval_limit():
    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "x1"}, "call-1")]),
            _chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "x2"}, "call-2")]),
            _chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "x3"}, "call-3")]),
        ],
        stream_chunks=[_stream_chunk("Synthesized")],
    )
    tool = _tool(
        "knowledge_base",
        ToolCallResult(
            content="weak evidence",
            sources=[SourceItem(document_id="doc-1", chunk_id="chunk-1", title="Doc", text="weak evidence", score=0.2)],
            quality_meta=_quality("low"),
        ),
    )
    config = ModeConfigFactory.build(mode="conclude", tools=[tool])
    loop = AgentLoop(llm_client=llm, tools=[tool], mode_config=config)

    result = await loop.run(message="conclude", chat_history=[])

    assert result.response == "Synthesized"
    assert result.iterations == 3
    assert len(llm.chat_calls) == 3
    assert len(llm.stream_calls) == 1


@pytest.mark.anyio
async def test_conclude_loop_can_early_synthesize_on_medium_quality():
    llm = _FakeLLMClient(
        chat_responses=[_chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "x"})])],
        stream_chunks=[_stream_chunk("Concluded")],
    )
    tool = _tool(
        "knowledge_base",
        ToolCallResult(
            content="enough evidence",
            sources=[SourceItem(document_id="doc-1", chunk_id="chunk-1", title="Doc", text="evidence", score=0.45)],
            quality_meta=_quality("medium"),
        ),
    )
    config = ModeConfigFactory.build(mode="conclude", tools=[tool])
    loop = AgentLoop(llm_client=llm, tools=[tool], mode_config=config)

    result = await loop.run(message="conclude", chat_history=[])

    assert result.response == "Concluded"
    assert result.iterations == 1
    assert len(llm.chat_calls) == 1
    assert len(llm.stream_calls) == 1


@pytest.mark.anyio
async def test_explain_loop_relaxes_scope_from_document_to_notebook_after_low_quality_result():
    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "focus"}, "call-1")]),
            _chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "focus more"}, "call-2")]),
        ],
        stream_chunks=[_stream_chunk("Explained")],
    )
    captured_payloads: list[dict] = []
    tool = _recording_tool(
        "knowledge_base",
        [
            ToolCallResult(content="weak", quality_meta=_quality("low")),
            ToolCallResult(content="strong", quality_meta=_quality("high")),
        ],
        captured_payloads,
    )
    config = ModeConfigFactory.build(mode="explain", tools=[tool])
    loop = AgentLoop(
        llm_client=llm,
        tools=[tool],
        mode_config=config,
        tool_argument_defaults={
            "knowledge_base": {
                "allowed_document_ids": ["doc-1", "doc-2"],
                "filter_document_id": "doc-1",
            }
        },
    )

    result = await loop.run(message="explain", chat_history=[])

    assert result.response == "Explained"
    assert captured_payloads[0]["filter_document_id"] == "doc-1"
    assert captured_payloads[1]["allowed_document_ids"] == ["doc-1", "doc-2"]
    assert "filter_document_id" not in captured_payloads[1]






@pytest.mark.anyio
async def test_agent_loop_open_loop_uses_final_reasoning_content_without_extra_synthesis_call():
    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(tool_calls=[_tool_call('knowledge_base', {'query': 'paper title'})]),
            _chat_response(content='The paper title is Example Title.'),
        ],
        stream_chunks=[],
    )
    tool = _tool(
        'knowledge_base',
        ToolCallResult(
            content='paper title evidence',
            sources=[SourceItem(document_id='doc-1', chunk_id='chunk-1', title='Doc', text='paper title evidence', score=0.9)],
            quality_meta=_quality('medium'),
        ),
    )
    config = ModeConfigFactory.build(mode='agent', tools=[tool])
    loop = AgentLoop(llm_client=llm, tools=[tool], mode_config=config)

    result = await loop.run(message='question', chat_history=[])

    assert result.response == 'The paper title is Example Title.'
    assert result.tool_calls_made == ['knowledge_base']
    assert len(llm.stream_calls) == 0


@pytest.mark.anyio
async def test_agent_loop_disables_provider_thinking_for_runtime_calls():
    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "paper title"})]),
            _chat_response(content="Final answer"),
        ],
        stream_chunks=[],
    )
    tool = _tool(
        "knowledge_base",
        ToolCallResult(
            content="paper title evidence",
            sources=[SourceItem(document_id="doc-1", chunk_id="chunk-1", title="Doc", text="paper title evidence", score=0.9)],
            quality_meta=_quality("medium"),
        ),
    )
    config = ModeConfigFactory.build(mode="agent", tools=[tool])
    loop = AgentLoop(llm_client=llm, tools=[tool], mode_config=config)

    result = await loop.run(message="question", chat_history=[])

    assert result.response == "Final answer"
    assert llm.chat_calls[0]["disable_thinking"] is True
    assert llm.chat_calls[1]["disable_thinking"] is True


@pytest.mark.anyio
async def test_agent_loop_open_loop_forces_synthesis_after_three_low_quality_knowledge_base_results():
    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "paper title"})]),
            _chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "title"})]),
            _chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "document"})]),
        ],
        stream_chunks=[_stream_chunk("Insufficient"), _stream_chunk(" evidence")],
    )
    tool = _tool(
        "knowledge_base",
        ToolCallResult(
            content="no evidence",
            sources=[],
            quality_meta=_quality("low"),
        ),
    )
    config = ModeConfigFactory.build(mode="agent", tools=[tool])
    loop = AgentLoop(llm_client=llm, tools=[tool], mode_config=config)

    result = await loop.run(message="question", chat_history=[])

    assert result.response == "Insufficient evidence"
    assert result.tool_calls_made == ["knowledge_base", "knowledge_base", "knowledge_base"]
    assert len(llm.chat_calls) == 3
    assert len(llm.stream_calls) == 1


@pytest.mark.anyio
async def test_agent_loop_open_loop_allows_third_knowledge_base_attempt_before_low_quality_synthesis():
    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "title of the paper"})]),
            _chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "paper title"})]),
            _chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "document", "search_type": "semantic", "max_results": 5})]),
            _chat_response(content="The paper title is The response of flow duration curves to afforestation."),
        ],
        stream_chunks=[],
    )
    follow_up_tool = _recording_tool(
        "knowledge_base",
        [
            ToolCallResult(content="no evidence", sources=[], quality_meta=_quality("empty")),
            ToolCallResult(content="no evidence", sources=[], quality_meta=_quality("empty")),
            ToolCallResult(
                content="title evidence",
                sources=[
                    SourceItem(
                        document_id="doc-1",
                        chunk_id="chunk-1",
                        title="demo1.pdf",
                        text="The response of flow duration curves to afforestation",
                        score=0.51,
                    )
                ],
                quality_meta=ToolQualityMeta(
                    scope_used="document",
                    search_type="semantic",
                    result_count=2,
                    max_score=0.51,
                    quality_band="medium",
                    scope_relaxation_recommended=False,
                ),
            ),
        ],
        [],
    )
    config = ModeConfigFactory.build(mode="agent", tools=[follow_up_tool])
    loop = AgentLoop(llm_client=llm, tools=[follow_up_tool], mode_config=config)

    result = await loop.run(message="what is the paper title?", chat_history=[])

    assert result.response == "The paper title is The response of flow duration curves to afforestation."
    assert result.tool_calls_made == ["knowledge_base", "knowledge_base", "knowledge_base"]
    assert len(llm.chat_calls) == 4
    assert len(llm.stream_calls) == 0


@pytest.mark.anyio
async def test_agent_loop_parses_textual_tool_call_markup_from_content():
    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(
                content=(
                    '<tool_call>knowledge_base'
                    '<arg_key>query</arg_key><arg_value>paper title</arg_value>'
                    '<arg_key>search_type</arg_key><arg_value>keyword</arg_value>'
                    '<arg_key>max_results</arg_key><arg_value>5</arg_value>'
                    '</tool_call>'
                ),
                finish_reason='stop',
            ),
            _chat_response(content='Grounded title'),
        ],
        stream_chunks=[],
    )
    captured_payloads: list[dict] = []
    tool = _recording_tool(
        'knowledge_base',
        [
            ToolCallResult(
                content='paper title evidence',
                sources=[
                    SourceItem(
                        document_id='doc-1',
                        chunk_id='chunk-1',
                        title='Doc',
                        text='paper title evidence',
                        score=0.92,
                    )
                ],
                quality_meta=_quality('high'),
            )
        ],
        captured_payloads,
    )
    config = ModeConfigFactory.build(mode='agent', tools=[tool])
    loop = AgentLoop(llm_client=llm, tools=[tool], mode_config=config)

    result = await loop.run(message='question', chat_history=[])

    assert result.response == 'Grounded title'
    assert result.tool_calls_made == ['knowledge_base']
    assert captured_payloads == [{'query': 'paper title', 'search_type': 'keyword', 'max_results': 5}]
    assert len(llm.stream_calls) == 0


@pytest.mark.anyio
async def test_agent_loop_executes_textual_tool_call_emitted_during_final_synthesis():
    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "teaching plan"})]),
            _chat_response(content=""),
            _chat_response(content="Diagram created successfully."),
        ],
        stream_chunks=[
            _stream_chunk(
                '<tool_call>create_diagram'
                '<arg_key>title</arg_key><arg_value>Teaching Plan</arg_value>'
                '<arg_key>diagram_type</arg_key><arg_value>mindmap</arg_value>'
                '<arg_key>content</arg_key><arg_value>{"nodes":[{"id":"root","label":"Plan"}],"edges":[]}</arg_value>'
                '</tool_call>'
            )
        ],
    )
    create_payloads: list[dict] = []
    knowledge_tool = _tool(
        "knowledge_base",
        ToolCallResult(
            content="teaching plan evidence",
            sources=[
                SourceItem(
                    document_id="doc-1",
                    chunk_id="chunk-1",
                    title="Plan",
                    text="teaching plan evidence",
                    score=0.88,
                )
            ],
            quality_meta=_quality("medium"),
        ),
    )
    create_tool = _recording_tool(
        "create_diagram",
        [ToolCallResult(content="Diagram created: [Teaching Plan], ID: diag-1")],
        create_payloads,
    )
    config = ModeConfigFactory.build(mode="agent", tools=[knowledge_tool, create_tool])
    loop = AgentLoop(
        llm_client=llm,
        tools=[knowledge_tool, create_tool],
        mode_config=config,
    )

    result = await loop.run(message="create a diagram", chat_history=[])

    assert result.response == "Diagram created successfully."
    assert result.tool_calls_made == ["knowledge_base", "create_diagram"]
    assert create_payloads == [
        {
            "title": "Teaching Plan",
            "diagram_type": "mindmap",
            "content": {"nodes": [{"id": "root", "label": "Plan"}], "edges": []},
        }
    ]
    assert len(llm.stream_calls) == 1


@pytest.mark.anyio
async def test_agent_loop_requires_completion_tool_before_open_loop_response():
    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "plan"})]),
            _chat_response(content="Here is a summary of the notebook."),
            _chat_response(
                tool_calls=[
                    _tool_call(
                        "create_diagram",
                        {
                            "title": "Teaching Plan",
                            "diagram_type": "mindmap",
                            "content": '{"nodes":[{"id":"root","label":"Plan"}],"edges":[]}',
                        },
                    )
                ]
            ),
            _chat_response(content="Diagram created successfully."),
        ],
        stream_chunks=[],
    )
    create_payloads: list[dict] = []
    knowledge_tool = _tool(
        "knowledge_base",
        ToolCallResult(
            content="plan evidence",
            sources=[
                SourceItem(
                    document_id="doc-1",
                    chunk_id="chunk-1",
                    title="Plan",
                    text="plan evidence",
                    score=0.8,
                )
            ],
            quality_meta=_quality("medium"),
        ),
    )
    create_tool = _recording_tool(
        "create_diagram",
        [ToolCallResult(content="Diagram created: [Teaching Plan], ID: diag-1")],
        create_payloads,
    )
    config = ModeConfigFactory.build(mode="agent", tools=[knowledge_tool, create_tool])
    loop = AgentLoop(
        llm_client=llm,
        tools=[knowledge_tool, create_tool],
        mode_config=config,
        required_tool_call_before_response="create_diagram",
    )

    result = await loop.run(message="create a diagram", chat_history=[])

    assert result.response == "Diagram created successfully."
    assert result.tool_calls_made == ["knowledge_base", "create_diagram"]
    assert create_payloads[0]["title"] == "Teaching Plan"
    assert llm.chat_calls[2]["tool_choice"] == {
        "type": "function",
        "function": {"name": "create_diagram"},
    }


@pytest.mark.anyio
async def test_agent_loop_forces_completion_tool_after_supporting_tool_call():
    llm = _FakeLLMClient(
        chat_responses=[
            _chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "plan"})]),
            _chat_response(
                tool_calls=[
                    _tool_call(
                        "create_diagram",
                        {
                            "title": "Teaching Plan",
                            "diagram_type": "mindmap",
                            "content": '{"nodes":[{"id":"root","label":"Plan"}],"edges":[]}',
                        },
                    )
                ]
            ),
            _chat_response(content="Diagram created successfully."),
        ],
        stream_chunks=[],
    )
    knowledge_tool = _tool(
        "knowledge_base",
        ToolCallResult(
            content="plan evidence",
            sources=[
                SourceItem(
                    document_id="doc-1",
                    chunk_id="chunk-1",
                    title="Plan",
                    text="plan evidence",
                    score=0.8,
                )
            ],
            quality_meta=_quality("medium"),
        ),
    )
    create_tool = _recording_tool(
        "create_diagram",
        [ToolCallResult(content="Diagram created: [Teaching Plan], ID: diag-1")],
        [],
    )
    config = ModeConfigFactory.build(mode="agent", tools=[knowledge_tool, create_tool])
    loop = AgentLoop(
        llm_client=llm,
        tools=[knowledge_tool, create_tool],
        mode_config=config,
        required_tool_call_before_response="create_diagram",
    )

    result = await loop.run(message="create a diagram", chat_history=[])

    assert result.response == "Diagram created successfully."
    assert llm.chat_calls[1]["tool_choice"] == {
        "type": "function",
        "function": {"name": "create_diagram"},
    }


@pytest.mark.anyio
async def test_agent_loop_accepts_real_llm_client_stream_shape():
    llm = _RealShapedLLMClient(
        chat_responses=[_chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "x"})])],
        stream_chunks=[_stream_chunk("Real"), _stream_chunk(" stream")],
    )
    tool = _tool(
        "knowledge_base",
        ToolCallResult(
            content="evidence",
            sources=[SourceItem(document_id="doc-1", chunk_id="chunk-1", title="Doc", text="evidence", score=0.9)],
            quality_meta=_quality("high"),
        ),
    )
    config = ModeConfigFactory.build(mode="explain", tools=[tool])
    loop = AgentLoop(llm_client=llm, tools=[tool], mode_config=config)

    result = await loop.run(message="explain", chat_history=[])

    assert result.response == "Real stream"
    assert len(llm.stream_calls) == 1


@pytest.mark.anyio
async def test_agent_loop_normalizes_openai_tool_call_objects():
    llm = _FakeLLMClient(
        chat_responses=[_chat_response(tool_calls=[_object_tool_call("knowledge_base", {"query": "x"})])],
        stream_chunks=[_stream_chunk("Normalized")],
    )
    tool = _tool(
        "knowledge_base",
        ToolCallResult(
            content="evidence",
            sources=[SourceItem(document_id="doc-1", chunk_id="chunk-1", title="Doc", text="evidence", score=0.9)],
            quality_meta=_quality("high"),
        ),
    )
    config = ModeConfigFactory.build(mode="explain", tools=[tool])
    loop = AgentLoop(llm_client=llm, tools=[tool], mode_config=config)

    result = await loop.run(message="explain", chat_history=[])

    assert result.response == "Normalized"
