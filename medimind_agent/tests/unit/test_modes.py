"""Unit tests for engine modes.

This test file validates:
- BaseMode interface and configuration
- Mode configuration defaults
- ModeType enum values

Note: These tests don't require actual LLM or database connections.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from medimind_agent.core.engine.modes.base import BaseMode, ModeConfig, ModeType
from medimind_agent.core.engine.modes.chat_mode import ChatMode, DEFAULT_CHAT_SYSTEM_PROMPT
from medimind_agent.core.engine.modes.ask_mode import AskMode, DEFAULT_ASK_SYSTEM_PROMPT
from medimind_agent.core.engine.modes.conclude_mode import ConcludeMode, DEFAULT_CONCLUDE_SYSTEM_PROMPT
from medimind_agent.core.engine.modes.explain_mode import ExplainMode, DEFAULT_EXPLAIN_SYSTEM_PROMPT


class TestModeType:
    """Test ModeType enum."""
    
    def test_mode_type_values(self):
        """Test that all expected mode types exist."""
        assert ModeType.CHAT.value == "chat"
        assert ModeType.ASK.value == "ask"
        assert ModeType.CONCLUDE.value == "conclude"
        assert ModeType.EXPLAIN.value == "explain"
    
    def test_mode_type_count(self):
        """Test that we have exactly 4 mode types."""
        assert len(ModeType) == 4


class TestModeConfig:
    """Test ModeConfig model."""
    
    def test_default_values(self):
        """Test ModeConfig with minimal required fields."""
        config = ModeConfig(mode_type=ModeType.CHAT)
        assert config.mode_type == ModeType.CHAT
        assert config.has_memory is True
        assert config.system_prompt is None
        assert config.verbose is False
    
    def test_custom_values(self):
        """Test ModeConfig with custom values."""
        config = ModeConfig(
            mode_type=ModeType.ASK,
            has_memory=False,
            system_prompt="Custom prompt",
            verbose=True,
        )
        assert config.mode_type == ModeType.ASK
        assert config.has_memory is False
        assert config.system_prompt == "Custom prompt"
        assert config.verbose is True


class TestChatMode:
    """Test ChatMode configuration and setup."""
    
    def test_default_config(self):
        """Test ChatMode returns correct default config."""
        mock_llm = MagicMock()
        mode = ChatMode(llm=mock_llm)
        
        assert mode.mode_type == ModeType.CHAT
        assert mode.config.has_memory is True
        assert DEFAULT_CHAT_SYSTEM_PROMPT in mode.config.system_prompt
    
    def test_custom_tools_config(self):
        """Test ChatMode with custom tool settings."""
        mock_llm = MagicMock()
        mode = ChatMode(
            llm=mock_llm,
            enable_tavily=False,
            enable_es_search=True,
            es_index_name="custom_index",
        )
        
        assert mode._enable_tavily is False
        assert mode._enable_es_search is True
        assert mode._es_index_name == "custom_index"
    
    def test_not_initialized_before_run(self):
        """Test that mode is not initialized until run is called."""
        mock_llm = MagicMock()
        mode = ChatMode(llm=mock_llm)
        
        assert mode._initialized is False
        assert mode._agent is None


class TestAskMode:
    """Test AskMode configuration and setup."""
    
    def test_default_config(self):
        """Test AskMode returns correct default config."""
        mock_llm = MagicMock()
        mode = AskMode(llm=mock_llm)
        
        assert mode.mode_type == ModeType.ASK
        assert mode.config.has_memory is True
        assert DEFAULT_ASK_SYSTEM_PROMPT in mode.config.system_prompt
    
    def test_retrieval_settings(self):
        """Test AskMode retrieval configuration."""
        mock_llm = MagicMock()
        mode = AskMode(
            llm=mock_llm,
            pgvector_top_k=15,
            es_top_k=15,
            final_top_k=10,
        )
        
        assert mode._pgvector_top_k == 15
        assert mode._es_top_k == 15
        assert mode._final_top_k == 10


class TestConcludeMode:
    """Test ConcludeMode configuration and setup."""
    
    def test_default_config(self):
        """Test ConcludeMode returns correct default config."""
        mock_llm = MagicMock()
        mode = ConcludeMode(llm=mock_llm)
        
        assert mode.mode_type == ModeType.CONCLUDE
        assert mode.config.has_memory is False  # No memory for conclude
        assert DEFAULT_CONCLUDE_SYSTEM_PROMPT in mode.config.system_prompt
    
    def test_memory_forced_to_none(self):
        """Test that memory is always None for ConcludeMode."""
        mock_llm = MagicMock()
        mock_memory = MagicMock()
        
        mode = ConcludeMode(llm=mock_llm, memory=mock_memory)
        
        assert mode.memory is None
        assert mode.has_memory is False
    
    def test_response_mode_settings(self):
        """Test ConcludeMode response settings."""
        mock_llm = MagicMock()
        mode = ConcludeMode(
            llm=mock_llm,
            similarity_top_k=15,
            response_mode="compact",
        )
        
        assert mode._similarity_top_k == 15
        assert mode._response_mode == "compact"


class TestExplainMode:
    """Test ExplainMode configuration and setup."""
    
    def test_default_config(self):
        """Test ExplainMode returns correct default config."""
        mock_llm = MagicMock()
        mode = ExplainMode(llm=mock_llm)
        
        assert mode.mode_type == ModeType.EXPLAIN
        assert mode.config.has_memory is False  # No memory for explain
        assert DEFAULT_EXPLAIN_SYSTEM_PROMPT in mode.config.system_prompt
    
    def test_memory_forced_to_none(self):
        """Test that memory is always None for ExplainMode."""
        mock_llm = MagicMock()
        mock_memory = MagicMock()
        
        mode = ExplainMode(llm=mock_llm, memory=mock_memory)
        
        assert mode.memory is None
        assert mode.has_memory is False
    
    def test_query_settings(self):
        """Test ExplainMode query settings."""
        mock_llm = MagicMock()
        mode = ExplainMode(
            llm=mock_llm,
            similarity_top_k=3,
            response_mode="tree_summarize",
        )
        
        assert mode._similarity_top_k == 3
        assert mode._response_mode == "tree_summarize"


class TestModeMemoryBehavior:
    """Test memory behavior across different modes."""
    
    def test_chat_mode_has_memory(self):
        """Test Chat mode maintains memory."""
        mock_llm = MagicMock()
        mock_memory = MagicMock()
        
        mode = ChatMode(llm=mock_llm, memory=mock_memory)
        
        assert mode.has_memory is True
    
    def test_ask_mode_has_memory(self):
        """Test Ask mode maintains memory."""
        mock_llm = MagicMock()
        mock_memory = MagicMock()
        
        mode = AskMode(llm=mock_llm, memory=mock_memory)
        
        assert mode.has_memory is True
    
    def test_conclude_mode_no_memory(self):
        """Test Conclude mode has no memory."""
        mock_llm = MagicMock()
        mock_memory = MagicMock()
        
        mode = ConcludeMode(llm=mock_llm, memory=mock_memory)
        
        assert mode.has_memory is False
    
    def test_explain_mode_no_memory(self):
        """Test Explain mode has no memory."""
        mock_llm = MagicMock()
        mock_memory = MagicMock()
        
        mode = ExplainMode(llm=mock_llm, memory=mock_memory)
        
        assert mode.has_memory is False


