from __future__ import annotations

from newbee_notebook.application.services.chat_service import ChatService
from newbee_notebook.core.tools.image_generation import DEFAULT_REQUEST_TIMEOUT_SECONDS
from newbee_notebook.domain.value_objects.mode_type import ModeType


def test_agent_and_chat_stream_timeout_budget_covers_image_generation_retry_window():
    required_budget = int(DEFAULT_REQUEST_TIMEOUT_SECONDS * 2)

    assert ChatService._get_stream_chunk_timeout_seconds(ModeType.AGENT) >= required_budget
    assert ChatService._get_stream_chunk_timeout_seconds(ModeType.CHAT) >= required_budget
