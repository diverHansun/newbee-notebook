"""Unit tests for mode selector and session management.

This test file validates:
- ModeSelector mode creation and caching
- Mode parsing from user input
- SessionManager initialization
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from medimind_agent.core.engine.modes.base import ModeType
from medimind_agent.core.engine.selector import (
    ModeSelector,
    parse_mode_from_input,
    get_mode_help,
)
from medimind_agent.core.engine.session import SessionManager


class TestModeSelector:
    """Test ModeSelector functionality."""
    
    def test_available_modes(self):
        """Test available modes list."""
        mock_llm = MagicMock()
        selector = ModeSelector(llm=mock_llm)
        
        modes = selector.available_modes
        assert len(modes) == 4
        assert ModeType.CHAT in modes
        assert ModeType.ASK in modes
        assert ModeType.CONCLUDE in modes
        assert ModeType.EXPLAIN in modes
    
    def test_get_mode_creates_mode(self):
        """Test that get_mode creates the requested mode."""
        mock_llm = MagicMock()
        selector = ModeSelector(llm=mock_llm)
        
        mode = selector.get_mode(ModeType.CHAT)
        
        assert mode is not None
        assert mode.mode_type == ModeType.CHAT
        assert selector.current_mode == ModeType.CHAT
    
    def test_get_mode_caches_mode(self):
        """Test that modes are cached after creation."""
        mock_llm = MagicMock()
        selector = ModeSelector(llm=mock_llm)
        
        mode1 = selector.get_mode(ModeType.CHAT)
        mode2 = selector.get_mode(ModeType.CHAT)
        
        assert mode1 is mode2
    
    def test_get_mode_info(self):
        """Test mode information retrieval."""
        mock_llm = MagicMock()
        selector = ModeSelector(llm=mock_llm)
        
        info = selector.get_mode_info(ModeType.CHAT)
        
        assert info["name"] == "Chat"
        assert info["has_memory"] is True
        assert info["has_rag"] is False
        
        info = selector.get_mode_info(ModeType.ASK)
        assert info["name"] == "Ask"
        assert info["has_rag"] is True


class TestParseModeFromInput:
    """Test mode parsing from user input."""
    
    def test_parse_mode_command(self):
        """Test /mode command parsing."""
        mode, message = parse_mode_from_input("/mode chat")
        assert mode == ModeType.CHAT
        assert message == ""
        
        mode, message = parse_mode_from_input("/mode ask")
        assert mode == ModeType.ASK
        assert message == ""
    
    def test_parse_shorthand_command(self):
        """Test shorthand command parsing."""
        mode, message = parse_mode_from_input("/chat")
        assert mode == ModeType.CHAT
        assert message == ""
        
        mode, message = parse_mode_from_input("/ask")
        assert mode == ModeType.ASK
    
    def test_parse_at_command_with_message(self):
        """Test @ command with message."""
        mode, message = parse_mode_from_input("@chat hello world")
        assert mode == ModeType.CHAT
        assert message == "hello world"
        
        mode, message = parse_mode_from_input("@ask what is diabetes?")
        assert mode == ModeType.ASK
        assert message == "what is diabetes?"
    
    def test_parse_regular_message(self):
        """Test regular message without mode command."""
        mode, message = parse_mode_from_input("Hello, how are you?")
        assert mode is None
        assert message == "Hello, how are you?"
    
    def test_parse_invalid_mode(self):
        """Test invalid mode command."""
        mode, message = parse_mode_from_input("/mode invalid")
        assert mode is None
        assert message == "/mode invalid"


class TestGetModeHelp:
    """Test help text generation."""
    
    def test_help_contains_modes(self):
        """Test help text contains all modes."""
        help_text = get_mode_help()
        
        assert "chat" in help_text
        assert "ask" in help_text
        assert "conclude" in help_text
        assert "explain" in help_text
    
    def test_help_contains_commands(self):
        """Test help text contains commands."""
        help_text = get_mode_help()
        
        assert "/help" in help_text
        assert "/status" in help_text
        assert "/reset" in help_text
        assert "/quit" in help_text


class TestSessionManager:
    """Test SessionManager functionality."""
    
    def test_initialization(self):
        """Test SessionManager initialization."""
        mock_llm = MagicMock()
        manager = SessionManager(llm=mock_llm)
        
        assert manager.current_mode == ModeType.CHAT
        assert manager.session_id is None
        assert manager.mode_selector is not None
    
    def test_switch_mode(self):
        """Test mode switching."""
        mock_llm = MagicMock()
        manager = SessionManager(llm=mock_llm)
        
        manager.switch_mode(ModeType.ASK)
        assert manager.current_mode == ModeType.ASK
        
        manager.switch_mode(ModeType.EXPLAIN)
        assert manager.current_mode == ModeType.EXPLAIN
    
    def test_get_status(self):
        """Test status retrieval."""
        mock_llm = MagicMock()
        manager = SessionManager(llm=mock_llm)
        
        status = manager.get_status()
        
        assert "session_id" in status
        assert "current_mode" in status
        assert "mode_info" in status
        assert "has_persistence" in status
        assert "memory_messages" in status
        
        assert status["current_mode"] == "chat"
        assert status["has_persistence"] is False


