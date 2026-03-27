"""Compaction orchestration for long-running session context."""

from __future__ import annotations

import logging
from typing import Any

from newbee_notebook.core.context.budget import ContextBudget
from newbee_notebook.core.context.compressor import Compressor
from newbee_notebook.core.context.compaction_prompt import build_compaction_messages
from newbee_notebook.core.context.token_counter import TokenCounter
from newbee_notebook.domain.entities.message import Message
from newbee_notebook.domain.entities.session import Session
from newbee_notebook.domain.repositories.message_repository import MessageRepository
from newbee_notebook.domain.repositories.session_repository import SessionRepository
from newbee_notebook.domain.value_objects.mode_type import MessageRole, MessageType, ModeType

logger = logging.getLogger(__name__)


class CompactionService:
    def __init__(
        self,
        *,
        message_repo: MessageRepository,
        session_repo: SessionRepository,
        llm_client: Any,
        token_counter: TokenCounter,
        compressor: Compressor,
        budget: ContextBudget,
    ):
        self._message_repo = message_repo
        self._session_repo = session_repo
        self._llm_client = llm_client
        self._token_counter = token_counter
        self._compressor = compressor
        self._budget = budget

    async def compact_if_needed(
        self,
        *,
        session: Session,
        track_modes: list[ModeType],
    ) -> bool:
        history = await self._message_repo.list_after_boundary(
            session.session_id,
            session.compaction_boundary_id,
            track_modes=track_modes,
        )
        if not history:
            return False

        if self._token_counter.count_messages(self._to_chat_messages(history)) < self._budget.compaction_threshold:
            return False

        try:
            response = await self._llm_client.chat(
                messages=build_compaction_messages(history),
                max_tokens=self._budget.summary,
                disable_thinking=True,
            )
            summary = self._extract_summary_text(response)
        except Exception as exc:
            logger.warning(
                "context compaction failed for session %s at boundary %s: %s",
                session.session_id,
                session.compaction_boundary_id,
                exc,
            )
            return False

        summary = self._compressor.truncate(summary, self._budget.summary).strip()
        if not summary:
            logger.warning(
                "context compaction produced empty summary for session %s at boundary %s",
                session.session_id,
                session.compaction_boundary_id,
            )
            return False

        created = await self._message_repo.create(
            Message(
                session_id=session.session_id,
                mode=ModeType.AGENT,
                role=MessageRole.ASSISTANT,
                message_type=MessageType.SUMMARY,
                content=summary,
            )
        )
        await self._session_repo.update_compaction_boundary(session.session_id, created.message_id)
        session.compaction_boundary_id = created.message_id
        return True

    @staticmethod
    def _to_chat_messages(messages: list[Message]) -> list[dict[str, str]]:
        return [{"role": item.role.value, "content": item.content} for item in messages]

    @classmethod
    def _extract_summary_text(cls, response: Any) -> str:
        message = cls._extract_message(response)
        if isinstance(message, dict):
            return cls._normalize_content(message.get("content"))
        return cls._normalize_content(getattr(message, "content", ""))

    @staticmethod
    def _extract_message(response: Any) -> Any:
        if isinstance(response, dict):
            return (response.get("choices") or [{}])[0].get("message") or {}
        return getattr((getattr(response, "choices", None) or [{}])[0], "message", {}) or {}

    @staticmethod
    def _normalize_content(content: Any) -> str:
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(str(item.get("text") or ""))
                else:
                    parts.append(str(getattr(item, "text", "") or ""))
            return "".join(parts).strip()
        return str(content or "").strip()
