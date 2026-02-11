"""Unit tests for NewbeeNotebookAgent.

Tests for:
- Agent initialization
- chat() method
- _fallback_response() method
- reset_conversation() method
"""

import pytest
from unittest.mock import Mock, MagicMock

from newbee_notebook.core.agent.agent import NewbeeNotebookAgent


class TestNewbeeNotebookAgentInit:
    """Tests for NewbeeNotebookAgent initialization."""

    def test_agent_init_with_required_params(self):
        """Test agent initialization with required parameters."""
        mock_llm = Mock()
        mock_chat_engine = Mock()

        agent = NewbeeNotebookAgent(llm=mock_llm, chat_engine=mock_chat_engine)

        assert agent.llm == mock_llm
        assert agent.chat_engine == mock_chat_engine
        assert agent.safety is None

    def test_agent_init_with_safety(self):
        """Test agent initialization with safety module."""
        mock_llm = Mock()
        mock_chat_engine = Mock()
        mock_safety = Mock()

        agent = NewbeeNotebookAgent(
            llm=mock_llm,
            chat_engine=mock_chat_engine,
            safety=mock_safety
        )

        assert agent.safety == mock_safety


class TestAgentChat:
    """Tests for Agent chat method."""

    def test_chat_returns_response(self):
        """Test that chat() returns a response string."""
        mock_llm = Mock()
        mock_chat_engine = Mock()
        mock_response = Mock()
        mock_response.__str__ = Mock(return_value="Test response")
        mock_chat_engine.chat.return_value = mock_response

        agent = NewbeeNotebookAgent(llm=mock_llm, chat_engine=mock_chat_engine)
        result = agent.chat("Test message")

        assert isinstance(result, str)
        assert result == "Test response"
        mock_chat_engine.chat.assert_called_once_with("Test message")

    def test_chat_with_empty_response_triggers_fallback(self):
        """Test that empty response triggers fallback mechanism."""
        mock_llm = Mock()
        mock_chat_engine = Mock()
        mock_response = Mock()
        mock_response.__str__ = Mock(return_value="Empty Response")
        mock_chat_engine.chat.return_value = mock_response

        # Mock fallback response
        mock_fallback_llm_response = Mock()
        mock_fallback_llm_response.message.content = "Fallback response"
        mock_llm.chat.return_value = mock_fallback_llm_response

        agent = NewbeeNotebookAgent(llm=mock_llm, chat_engine=mock_chat_engine)
        result = agent.chat("Test message")

        assert result == "Fallback response"
        mock_llm.chat.assert_called_once()

    def test_chat_with_safety_check(self):
        """Test that safety checks are applied before chat."""
        mock_llm = Mock()
        mock_chat_engine = Mock()
        mock_safety = Mock()
        mock_safety_check = Mock()
        mock_safety_check.is_safe = False
        mock_safety_check.response = "Safety blocked"
        mock_safety.check.return_value = mock_safety_check

        agent = NewbeeNotebookAgent(
            llm=mock_llm,
            chat_engine=mock_chat_engine,
            safety=mock_safety
        )
        result = agent.chat("Unsafe message")

        assert result == "Safety blocked"
        mock_chat_engine.chat.assert_not_called()


class TestAgentFallbackResponse:
    """Tests for Agent fallback response method."""

    def test_fallback_response_uses_llm_directly(self):
        """Test that fallback response calls LLM directly."""
        mock_llm = Mock()
        mock_chat_engine = Mock()
        mock_llm_response = Mock()
        mock_llm_response.message.content = "Direct LLM response"
        mock_llm.chat.return_value = mock_llm_response

        agent = NewbeeNotebookAgent(llm=mock_llm, chat_engine=mock_chat_engine)
        result = agent._fallback_response("Test query")

        assert result == "Direct LLM response"
        mock_llm.chat.assert_called_once()

    def test_fallback_response_error_handling(self):
        """Test that fallback response handles LLM errors gracefully."""
        mock_llm = Mock()
        mock_llm.chat.side_effect = Exception("LLM error")
        mock_chat_engine = Mock()

        agent = NewbeeNotebookAgent(llm=mock_llm, chat_engine=mock_chat_engine)
        result = agent._fallback_response("Test query")

        assert "unable to process" in result.lower()


class TestAgentResetConversation:
    """Tests for Agent reset conversation method."""

    def test_reset_conversation_calls_chat_engine_reset(self):
        """Test that reset_conversation() calls chat_engine.reset()."""
        mock_llm = Mock()
        mock_chat_engine = Mock()

        agent = NewbeeNotebookAgent(llm=mock_llm, chat_engine=mock_chat_engine)
        agent.reset_conversation()

        mock_chat_engine.reset.assert_called_once()


