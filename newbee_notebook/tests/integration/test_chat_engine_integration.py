import copy
import json
from collections import defaultdict
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from newbee_notebook.api.dependencies import get_chat_service, get_session_service
from newbee_notebook.api.routers.chat import router as chat_router
from newbee_notebook.application.services.chat_service import ChatService
from newbee_notebook.application.services.session_service import SessionService
from newbee_notebook.core.session import SessionManager
from newbee_notebook.core.tools.builtin_provider import BuiltinToolProvider
from newbee_notebook.core.tools.registry import ToolRegistry
from newbee_notebook.domain.entities.message import Message
from newbee_notebook.domain.entities.session import Session
from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.domain.value_objects.mode_type import MessageRole, ModeType


class _InMemoryNotebookRepo:
    def __init__(self):
        self._notebooks = {"nb-1": SimpleNamespace(notebook_id="nb-1", session_count=0)}

    async def get(self, notebook_id: str):
        return self._notebooks.get(notebook_id)

    async def increment_session_count(self, notebook_id: str, delta: int = 1):
        notebook = self._notebooks[notebook_id]
        notebook.session_count += delta


class _InMemorySessionRepo:
    def __init__(self):
        self._sessions: dict[str, Session] = {}

    async def get(self, session_id: str):
        return self._sessions.get(session_id)

    async def create(self, session: Session):
        self._sessions[session.session_id] = session
        return session

    async def count_by_notebook(self, notebook_id: str):
        return sum(1 for item in self._sessions.values() if item.notebook_id == notebook_id)

    async def increment_message_count(self, session_id: str, delta: int):
        self._sessions[session_id].increment_message_count(delta)

    async def update_compaction_boundary(self, session_id: str, compaction_boundary_id: int | None):
        self._sessions[session_id].compaction_boundary_id = compaction_boundary_id


class _InMemoryMessageRepo:
    def __init__(self):
        self.messages: list[Message] = []
        self._next_id = 1

    async def create(self, message: Message):
        if message.message_id is None:
            message.message_id = self._next_id
            self._next_id += 1
        self.messages.append(message)
        return message

    async def create_batch(self, batch):
        created = []
        for message in batch:
            created.append(await self.create(message))
        return created

    async def list_by_session(self, session_id: str, limit: int = 50, offset: int = 0, modes=None):
        allowed = None if modes is None else {mode.value if hasattr(mode, "value") else str(mode) for mode in modes}
        rows = [item for item in self.messages if item.session_id == session_id]
        if allowed is not None:
            rows = [item for item in rows if (item.mode.value if hasattr(item.mode, "value") else str(item.mode)) in allowed]
        return rows[offset: offset + limit]

    async def list_after_boundary(self, session_id: str, boundary_message_id: int | None, track_modes=None):
        allowed = None if track_modes is None else {
            mode.value if hasattr(mode, "value") else str(mode) for mode in track_modes
        }
        rows = [item for item in self.messages if item.session_id == session_id]
        if boundary_message_id is not None:
            rows = [
                item
                for item in rows
                if item.message_id is not None and item.message_id >= boundary_message_id
            ]
        if allowed is not None:
            rows = [item for item in rows if (item.mode.value if hasattr(item.mode, "value") else str(item.mode)) in allowed]
        return rows

    async def count_by_session(self, session_id: str, modes=None):
        return len(await self.list_by_session(session_id=session_id, limit=10_000, modes=modes))


class _InMemoryReferenceRepo:
    def __init__(self):
        self.references = []

    async def create_batch(self, refs):
        self.references.extend(refs)


class _InMemoryNotebookDocumentRefRepo:
    def __init__(self, notebook_docs: dict[str, list[str]]):
        self._notebook_docs = notebook_docs

    async def list_by_notebook(self, notebook_id: str):
        return [SimpleNamespace(document_id=document_id) for document_id in self._notebook_docs.get(notebook_id, [])]


class _InMemoryDocumentRepo:
    def __init__(self, documents: dict[str, object]):
        self._documents = documents

    async def get_batch(self, document_ids):
        return [self._documents[item] for item in document_ids if item in self._documents]

    async def get(self, document_id: str):
        return self._documents.get(document_id)


class _FakeLLMClient:
    def __init__(self, *, chat_responses, stream_chunks):
        self.chat_responses = list(chat_responses)
        self.stream_chunks = list(stream_chunks)
        self.chat_calls: list[dict] = []
        self.stream_calls: list[dict] = []

    async def chat(self, **kwargs):
        self.chat_calls.append(copy.deepcopy(kwargs))
        return self.chat_responses.pop(0)

    async def chat_stream(self, **kwargs):
        self.stream_calls.append(copy.deepcopy(kwargs))
        for chunk in self.stream_chunks:
            yield chunk


class _RecordingSearchExecutor:
    def __init__(self, *result_batches):
        self.payloads: list[dict] = []
        self._result_batches = list(result_batches)

    async def __call__(self, payload: dict):
        self.payloads.append(dict(payload))
        if self._result_batches:
            return self._result_batches.pop(0)
        return []


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


def _build_client(*, llm_client: _FakeLLMClient, hybrid_results=(), keyword_results=()):
    notebook_repo = _InMemoryNotebookRepo()
    session_repo = _InMemorySessionRepo()
    message_repo = _InMemoryMessageRepo()
    reference_repo = _InMemoryReferenceRepo()
    notebook_ref_repo = _InMemoryNotebookDocumentRefRepo({"nb-1": ["doc-1"]})
    document_repo = _InMemoryDocumentRepo(
        {
            "doc-1": SimpleNamespace(
                document_id="doc-1",
                status=DocumentStatus.COMPLETED,
                title="Doc 1",
            )
        }
    )
    hybrid_search = _RecordingSearchExecutor(*hybrid_results)
    keyword_search = _RecordingSearchExecutor(*keyword_results)
    tool_registry = ToolRegistry(
        BuiltinToolProvider(
            hybrid_search=hybrid_search,
            keyword_search=keyword_search,
        )
    )
    session_manager = SessionManager(
        session_repo=session_repo,
        message_repo=message_repo,
        llm_client=llm_client,
        tool_registry=tool_registry,
        system_prompt_provider=lambda mode: f"prompt:{mode.value}",
    )
    chat_service = ChatService(
        session_repo=session_repo,
        notebook_repo=notebook_repo,
        reference_repo=reference_repo,
        document_repo=document_repo,
        ref_repo=notebook_ref_repo,
        message_repo=message_repo,
        session_manager=session_manager,
    )
    session_service = SessionService(
        session_repo=session_repo,
        notebook_repo=notebook_repo,
        message_repo=message_repo,
    )

    app = FastAPI()
    app.include_router(chat_router, prefix="/api/v1")
    app.dependency_overrides[get_chat_service] = lambda: chat_service
    app.dependency_overrides[get_session_service] = lambda: session_service

    return (
        TestClient(app),
        llm_client,
        hybrid_search,
        keyword_search,
        message_repo,
        reference_repo,
    )


def _collect_sse_events(response) -> list[dict]:
    events = []
    for line in response.iter_lines():
        if not line:
            continue
        if isinstance(line, bytes):
            line = line.decode("utf-8")
        if not line.startswith("data: "):
            continue
        events.append(json.loads(line[6:]))
    return events


@pytest.mark.integration
def test_non_stream_ask_route_runs_runtime_pipeline_and_persists_messages():
    client, llm_client, hybrid_search, _, message_repo, reference_repo = _build_client(
        llm_client=_FakeLLMClient(
            chat_responses=[
                _chat_response(tool_calls=[_tool_call("knowledge_base", {"query": "What is doc 1?"})]),
                _chat_response(content="ready for synthesis"),
            ],
            stream_chunks=[_stream_chunk("Grounded "), _stream_chunk("answer")],
        ),
        hybrid_results=[
            [
                {
                    "document_id": "doc-1",
                    "chunk_id": "chunk-1",
                    "title": "Doc 1",
                    "text": "Doc 1 says hello.",
                    "score": 0.82,
                    "source_type": "retrieval",
                }
            ]
        ],
    )

    response = client.post(
        "/api/v1/chat/notebooks/nb-1/chat",
        json={"message": "What is doc 1?", "mode": "ask"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "ask"
    assert body["content"] == "ready for synthesis"
    assert body["sources"][0]["document_id"] == "doc-1"
    assert len(message_repo.messages) == 2
    assert message_repo.messages[0].role == MessageRole.USER
    assert message_repo.messages[0].mode == ModeType.ASK
    assert message_repo.messages[1].role == MessageRole.ASSISTANT
    assert message_repo.messages[1].content == "ready for synthesis"
    assert len(reference_repo.references) == 1
    assert hybrid_search.payloads[0]["allowed_document_ids"] == ["doc-1"]
    assert hybrid_search.payloads[0]["search_type"] == "hybrid"
    assert hybrid_search.payloads[0]["max_results"] == 5
    assert llm_client.chat_calls[0]["messages"][0] == {"role": "system", "content": "prompt:ask"}


@pytest.mark.integration
def test_stream_explain_route_uses_document_scope_and_emits_runtime_events():
    client, llm_client, _, keyword_search, _, _ = _build_client(
        llm_client=_FakeLLMClient(
            chat_responses=[
                _chat_response(
                    tool_calls=[
                        _tool_call(
                            "knowledge_base",
                            {
                                "query": "Explain the selected sentence",
                                "search_type": "keyword",
                                "max_results": 4,
                            },
                        )
                    ]
                )
            ],
            stream_chunks=[_stream_chunk("Explained"), _stream_chunk(" answer")],
        ),
        keyword_results=[
            [
                {
                    "document_id": "doc-1",
                    "chunk_id": "chunk-2",
                    "title": "Doc 1",
                    "text": "Focused evidence.",
                    "score": 0.91,
                    "source_type": "retrieval",
                },
                {
                    "document_id": "doc-1",
                    "chunk_id": "chunk-3",
                    "title": "Doc 1",
                    "text": "Supporting evidence.",
                    "score": 0.84,
                    "source_type": "retrieval",
                },
            ]
        ],
    )

    with client.stream(
        "POST",
        "/api/v1/chat/notebooks/nb-1/chat/stream",
        json={
            "message": "Explain this line",
            "mode": "explain",
            "context": {"selected_text": "Selected sentence", "document_id": "doc-1"},
        },
    ) as response:
        events = _collect_sse_events(response)

    assert response.status_code == 200
    event_types = [event["type"] for event in events]
    assert event_types[0] == "start"
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "phase" in event_types
    assert "thinking" in event_types
    assert event_types[-2:] == ["sources", "done"]

    tool_call_event = next(event for event in events if event["type"] == "tool_call")
    assert tool_call_event["tool_name"] == "knowledge_base"
    tool_result_event = next(event for event in events if event["type"] == "tool_result")
    assert tool_result_event["quality_meta"]["quality_band"] == "high"
    assert keyword_search.payloads[0]["filter_document_id"] == "doc-1"
    assert keyword_search.payloads[0]["allowed_document_ids"] == ["doc-1"]
    assert keyword_search.payloads[0]["search_type"] == "keyword"
    assert keyword_search.payloads[0]["max_results"] == 4
    assert "Selected text:\nSelected sentence" in llm_client.chat_calls[0]["messages"][-1]["content"]



