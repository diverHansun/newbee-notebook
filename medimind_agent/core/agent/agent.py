"""
MediMind Agent - Simple Agent Wrapper

Minimal implementation to satisfy unit tests:
- Delegates chat to provided chat_engine
- Optional safety check before chat
- Fallback response uses llm directly
"""

from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class MediMindAgent:
    """Lightweight agent facade."""

    def __init__(self, llm: Any, chat_engine: Any, safety: Optional[Any] = None):
        self.llm = llm
        self.chat_engine = chat_engine
        self.safety = safety

    def chat(self, message: str) -> str:
        """
        Run a chat turn with optional safety and fallback handling.
        """
        # Safety check
        if self.safety:
            safety_result = self.safety.check(message)
            if not safety_result.is_safe:
                return safety_result.response

        # Primary chat path
        response = self.chat_engine.chat(message)
        response_text = str(response)

        if not response_text or response_text.lower().startswith("empty"):
            return self._fallback_response(message)

        return response_text

    def _fallback_response(self, query: str) -> str:
        """
        Call underlying LLM directly as a fallback.
        """
        try:
            llm_response = self.llm.chat(query)
            return getattr(llm_response, "message", llm_response).content
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Fallback response failed: %s", exc)
            return "Sorry, I'm unable to process that right now."

    def reset_conversation(self) -> None:
        """Reset conversation state."""
        if hasattr(self.chat_engine, "reset"):
            self.chat_engine.reset()


