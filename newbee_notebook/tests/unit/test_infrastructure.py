"""Unit tests for infrastructure layer components.

This test file validates the basic functionality of:
- PGVectorStore configuration
- ElasticsearchStore configuration  
- ChatSessionStore models

Note: These tests don't require actual database connections.
"""

import pytest
from uuid import uuid4
from datetime import datetime

from newbee_notebook.infrastructure.pgvector.config import PGVectorConfig
from newbee_notebook.infrastructure.elasticsearch.config import ElasticsearchConfig
from newbee_notebook.infrastructure.session.models import (
    ChatSession,
    ChatMessage,
    ModeType,
    MessageRole,
)


class TestPGVectorConfig:
    """Test PGVectorConfig functionality."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = PGVectorConfig()
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "newbee_notebook"
        assert config.user == "postgres"
        assert config.table_name == "documents"
        assert config.embedding_dimension == 1024
        assert config.distance_metric == "cosine"
    
    def test_connection_string(self):
        """Test connection string generation."""
        config = PGVectorConfig(
            user="testuser",
            password="testpass",
            host="testhost",
            port=5433,
            database="testdb"
        )
        expected = "postgresql://testuser:testpass@testhost:5433/testdb"
        assert config.connection_string == expected
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = PGVectorConfig(
            table_name="custom_docs",
            embedding_dimension=768,
            distance_metric="l2"
        )
        assert config.table_name == "custom_docs"
        assert config.embedding_dimension == 768
        assert config.distance_metric == "l2"


class TestElasticsearchConfig:
    """Test ElasticsearchConfig functionality."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ElasticsearchConfig()
        assert config.url == "http://localhost:9200"
        assert config.index_name == "newbee_notebook_docs"
        assert config.api_key is None
        assert config.cloud_id is None
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = ElasticsearchConfig(
            url="http://es-server:9200",
            index_name="custom_index",
            api_key="test_key",
            cloud_id="test_cloud"
        )
        assert config.url == "http://es-server:9200"
        assert config.index_name == "custom_index"
        assert config.api_key == "test_key"
        assert config.cloud_id == "test_cloud"


class TestChatSessionModels:
    """Test chat session data models."""
    
    def test_chat_session_creation(self):
        """Test ChatSession model creation."""
        session = ChatSession()
        assert session.session_id is not None
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.updated_at, datetime)
    
    def test_chat_session_with_id(self):
        """Test ChatSession with specific UUID."""
        session_id = uuid4()
        session = ChatSession(session_id=session_id)
        assert session.session_id == session_id
    
    def test_chat_message_creation(self):
        """Test ChatMessage model creation."""
        session_id = uuid4()
        message = ChatMessage(
            session_id=session_id,
            mode=ModeType.CHAT,
            role=MessageRole.USER,
            content="Test message"
        )
        assert message.session_id == session_id
        assert message.mode == ModeType.CHAT
        assert message.role == MessageRole.USER
        assert message.content == "Test message"
        assert isinstance(message.created_at, datetime)
    
    def test_mode_types(self):
        """Test all mode types."""
        modes = [ModeType.CHAT, ModeType.ASK, ModeType.CONCLUDE, ModeType.EXPLAIN]
        assert len(modes) == 4
        assert ModeType.CHAT.value == "chat"
        assert ModeType.ASK.value == "ask"
    
    def test_message_roles(self):
        """Test all message roles."""
        roles = [MessageRole.USER, MessageRole.ASSISTANT, MessageRole.SYSTEM]
        assert len(roles) == 3
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"


