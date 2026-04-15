import asyncio

from newbee_notebook.api.models.requests import ChatRequest
from newbee_notebook.api.routers.health import system_info
from newbee_notebook.api.routers.sessions import _parse_mode_filter
from newbee_notebook.domain.value_objects.mode_type import ModeType


def test_chat_request_defaults_to_agent_mode():
    request = ChatRequest(message="hello")

    assert request.mode == "agent"


def test_session_message_mode_filter_normalizes_chat_alias_to_agent():
    assert _parse_mode_filter("chat,ask") == [ModeType.AGENT, ModeType.ASK]


def test_system_info_reports_agent_as_canonical_chat_mode():
    payload = asyncio.run(system_info())

    assert payload["features"]["chat_modes"] == ["agent", "ask", "explain", "conclude"]


def test_legacy_runtime_exports_are_removed_from_public_packages():
    import newbee_notebook.core.rag as rag
    import newbee_notebook.infrastructure as infrastructure

    assert not hasattr(rag, "build_query_engine")
    assert not hasattr(rag, "build_simple_query_engine")
    assert not hasattr(rag, "build_chat_engine")
    assert not hasattr(rag, "build_simple_chat_engine")
    assert not hasattr(infrastructure, "ChatSessionStore")
