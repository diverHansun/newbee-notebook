from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest

from newbee_notebook.core.prompts import load_prompt
from newbee_notebook.core.session import session_manager as session_manager_module
from newbee_notebook.core.engine.stream_events import ContentEvent, SourceEvent, WarningEvent
from newbee_notebook.core.session.session_manager import SessionManager
from newbee_notebook.core.tools.contracts import SourceItem
from newbee_notebook.domain.entities.message import Message
from newbee_notebook.domain.entities.session import Session
from newbee_notebook.domain.value_objects.mode_type import MessageRole, ModeType


@dataclass
class _LoopCall:
    message: str
    chat_history: list[dict]
    tool_argument_defaults: dict | None = None


class RecordingLoop:
    instances: list["RecordingLoop"] = []
    stream_events: list = []

    def __init__(self, *, llm_client, tools, mode_config, llm_retry_attempts=1, tool_argument_defaults=None):
        self.llm_client = llm_client
        self.tools = tools
        self.mode_config = mode_config
        self.llm_retry_attempts = llm_retry_attempts
        self.tool_argument_defaults = tool_argument_defaults
        self.calls: list[_LoopCall] = []
        self.__class__.instances.append(self)

    async def stream(self, *, message: str, chat_history: list[dict]):
        self.calls.append(
            _LoopCall(
                message=message,
                chat_history=chat_history,
                tool_argument_defaults=self.tool_argument_defaults,
            )
        )
        for event in list(self.__class__.stream_events):
            yield event


class DummyToolRegistry:
    def __init__(self):
        self.calls: list[str] = []

    def get_tools(self, mode, external_tools=None):
        self.calls.append(str(mode))
        return []


class DummyLLMClient:
    pass


@pytest.fixture(autouse=True)
def _reset_recording_loop():
    RecordingLoop.instances = []
    RecordingLoop.stream_events = []


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_chat_aggregates_stream_events_into_result():
    session_repo = AsyncMock()
    session_repo.get.return_value = Session(session_id="s1", notebook_id="nb1")
    message_repo = AsyncMock()
    message_repo.list_by_session.side_effect = [[], []]
    tool_registry = DummyToolRegistry()
    manager = SessionManager(
        session_repo=session_repo,
        message_repo=message_repo,
        llm_client=DummyLLMClient(),
        tool_registry=tool_registry,
        lock_manager=None,
        agent_loop_cls=RecordingLoop,
        system_prompt_provider=lambda mode: f"prompt:{mode.value}",
    )
    await manager.start_session(session_id="s1")

    source = SourceItem(
        document_id="doc-1",
        chunk_id="chunk-1",
        title="Doc 1",
        text="fact",
        score=0.9,
        source_type="retrieval",
    )
    RecordingLoop.stream_events = [
        WarningEvent(message="partial documents", code="partial_documents"),
        ContentEvent(delta="Hello"),
        ContentEvent(delta=" world"),
        SourceEvent(sources=[source]),
    ]

    result = await manager.chat(message="question", mode_type=ModeType.ASK)

    assert result.content == "Hello world"
    assert result.sources == [source]
    assert result.warnings == [{"message": "partial documents", "code": "partial_documents"}]


@pytest.mark.anyio
async def test_request_scoped_manager_builds_fresh_context_from_db_history():
    session = Session(session_id="s1", notebook_id="nb1")
    history = [
        Message(session_id="s1", mode=ModeType.CHAT, role=MessageRole.USER, content="older question"),
        Message(session_id="s1", mode=ModeType.CHAT, role=MessageRole.ASSISTANT, content="older answer"),
    ]
    session_repo = AsyncMock()
    session_repo.get.return_value = session
    message_repo = AsyncMock()
    message_repo.list_by_session.side_effect = [history, [], history, []]
    tool_registry = DummyToolRegistry()

    manager_a = SessionManager(
        session_repo=session_repo,
        message_repo=message_repo,
        llm_client=DummyLLMClient(),
        tool_registry=tool_registry,
        lock_manager=None,
        agent_loop_cls=RecordingLoop,
        system_prompt_provider=lambda mode: f"prompt:{mode.value}",
    )
    manager_b = SessionManager(
        session_repo=session_repo,
        message_repo=message_repo,
        llm_client=DummyLLMClient(),
        tool_registry=tool_registry,
        lock_manager=None,
        agent_loop_cls=RecordingLoop,
        system_prompt_provider=lambda mode: f"prompt:{mode.value}",
    )

    RecordingLoop.stream_events = [ContentEvent(delta="ok")]

    await manager_a.start_session(session_id="s1")
    await manager_a.chat(message="follow up", mode_type=ModeType.CHAT)
    first_history = RecordingLoop.instances[-1].calls[-1].chat_history

    await manager_b.start_session(session_id="s1")
    await manager_b.chat(message="follow up", mode_type=ModeType.CHAT)
    second_history = RecordingLoop.instances[-1].calls[-1].chat_history

    assert first_history == second_history
    assert first_history == [
        {"role": "system", "content": "prompt:agent"},
        {"role": "user", "content": "older question"},
        {"role": "assistant", "content": "older answer"},
    ]


@pytest.mark.anyio
async def test_explain_injects_main_track_history_into_side_context():
    session_repo = AsyncMock()
    session_repo.get.return_value = Session(session_id="s1", notebook_id="nb1")
    message_repo = AsyncMock()
    message_repo.list_by_session.side_effect = [
        [
            Message(session_id="s1", mode=ModeType.CHAT, role=MessageRole.USER, content="main question"),
            Message(session_id="s1", mode=ModeType.CHAT, role=MessageRole.ASSISTANT, content="main answer"),
        ],
        [
            Message(session_id="s1", mode=ModeType.EXPLAIN, role=MessageRole.USER, content="explain this"),
            Message(session_id="s1", mode=ModeType.EXPLAIN, role=MessageRole.ASSISTANT, content="prior explain"),
        ],
    ]
    manager = SessionManager(
        session_repo=session_repo,
        message_repo=message_repo,
        llm_client=DummyLLMClient(),
        tool_registry=DummyToolRegistry(),
        lock_manager=None,
        agent_loop_cls=RecordingLoop,
        system_prompt_provider=lambda mode: f"prompt:{mode.value}",
    )

    RecordingLoop.stream_events = [ContentEvent(delta="done")]

    await manager.start_session(session_id="s1")
    await manager.chat(message="why", mode_type=ModeType.EXPLAIN)
    history = RecordingLoop.instances[-1].calls[-1].chat_history

    assert history[0] == {"role": "system", "content": "prompt:explain"}
    assert history[1]["role"] == "system"
    assert "main question" in history[1]["content"]
    assert history[-2:] == [
        {"role": "user", "content": "explain this"},
        {"role": "assistant", "content": "prior explain"},
    ]


@pytest.mark.anyio
async def test_explain_builds_runtime_message_and_document_scope_defaults():
    session_repo = AsyncMock()
    session_repo.get.return_value = Session(session_id="s1", notebook_id="nb1")
    message_repo = AsyncMock()
    message_repo.list_by_session.side_effect = [[], []]
    manager = SessionManager(
        session_repo=session_repo,
        message_repo=message_repo,
        llm_client=DummyLLMClient(),
        tool_registry=DummyToolRegistry(),
        lock_manager=None,
        agent_loop_cls=RecordingLoop,
        system_prompt_provider=lambda mode: f"prompt:{mode.value}",
    )
    RecordingLoop.stream_events = [ContentEvent(delta="done")]

    await manager.start_session(session_id="s1")
    await manager.chat(
        message="explain the relation",
        mode_type=ModeType.EXPLAIN,
        allowed_document_ids=["doc-1", "doc-2"],
        context={"selected_text": "selected sentence", "document_id": "doc-1"},
    )

    call = RecordingLoop.instances[-1].calls[-1]
    assert "selected sentence" in call.message
    assert "explain the relation" in call.message
    assert call.tool_argument_defaults["knowledge_base"]["filter_document_id"] == "doc-1"
    assert call.tool_argument_defaults["knowledge_base"]["allowed_document_ids"] == ["doc-1", "doc-2"]


@pytest.mark.anyio
async def test_ask_builds_runtime_message_with_notebook_scope_hint():
    session_repo = AsyncMock()
    session_repo.get.return_value = Session(session_id="s1", notebook_id="nb1")
    message_repo = AsyncMock()
    message_repo.list_by_session.side_effect = [[], []]
    manager = SessionManager(
        session_repo=session_repo,
        message_repo=message_repo,
        llm_client=DummyLLMClient(),
        tool_registry=DummyToolRegistry(),
        lock_manager=None,
        agent_loop_cls=RecordingLoop,
        system_prompt_provider=lambda mode: f"prompt:{mode.value}",
    )
    RecordingLoop.stream_events = [ContentEvent(delta="done")]

    await manager.start_session(session_id="s1")
    await manager.chat(
        message="这个文档主要讨论什么？",
        mode_type=ModeType.ASK,
        allowed_document_ids=["doc-1"],
    )

    call = RecordingLoop.instances[-1].calls[-1]
    assert "current notebook already contains 1 completed document" in call.message
    assert "knowledge_base" in call.message
    assert "这个文档主要讨论什么？" in call.message


def test_default_system_prompt_loads_mode_prompt_files(monkeypatch):
    loaded_files: list[str] = []

    def _fake_load_prompt(file_name: str) -> str:
        loaded_files.append(file_name)
        return f"prompt:{file_name}"

    session_manager_module._load_mode_prompt.cache_clear()
    monkeypatch.setattr(session_manager_module, "load_prompt", _fake_load_prompt)

    assert SessionManager._default_system_prompt(ModeType.AGENT) == "prompt:chat.md"
    assert SessionManager._default_system_prompt(ModeType.ASK) == "prompt:ask.md"
    assert SessionManager._default_system_prompt(ModeType.EXPLAIN) == "prompt:explain.md"
    assert SessionManager._default_system_prompt(ModeType.CONCLUDE) == "prompt:conclude.md"
    assert loaded_files == ["chat.md", "ask.md", "explain.md", "conclude.md"]
    session_manager_module._load_mode_prompt.cache_clear()


def test_ask_prompt_matches_runtime_tool_contract():
    prompt = load_prompt("ask.md")

    assert "knowledge_base" in prompt
    assert "time" in prompt
    assert "query" in prompt
    assert "search_type" in prompt
    assert "max_results" in prompt
    assert "filter_document_id" in prompt
    assert "allowed_document_ids" in prompt
    assert "keyword" in prompt
    assert "semantic" in prompt
    assert "hybrid" in prompt
    assert "Do not ask the user to upload a file" in prompt
    assert "zhipu_web_search" not in prompt
    assert "zhipu_web_crawl" not in prompt


def test_agent_prompt_explains_knowledge_base_argument_strategy():
    prompt = load_prompt("chat.md")

    assert "knowledge_base" in prompt
    assert "query" in prompt
    assert "search_type" in prompt
    assert "max_results" in prompt
    assert "filter_document_id" in prompt
    assert "allowed_document_ids" in prompt
    assert "Avoid generic queries" in prompt


def test_explain_and_conclude_prompts_explain_document_scoped_retrieval_arguments():
    explain_prompt = load_prompt("explain.md")
    conclude_prompt = load_prompt("conclude.md")

    for prompt in (explain_prompt, conclude_prompt):
        assert "knowledge_base" in prompt
        assert "query" in prompt
        assert "search_type" in prompt
        assert "max_results" in prompt
        assert "filter_document_id" in prompt
        assert "allowed_document_ids" in prompt

    assert "keyword" in explain_prompt
    assert "hybrid" in conclude_prompt
