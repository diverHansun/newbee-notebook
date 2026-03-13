"""Unit tests for ChatEngine building utilities.

Tests for:
- build_chat_engine() function
- build_simple_chat_engine() function
- Parameter validation
- Error handling
"""

import asyncio
import pytest
from unittest.mock import Mock, MagicMock, patch
from types import SimpleNamespace
from unittest.mock import AsyncMock

from newbee_notebook.application.services.chat_service import ChatService
from newbee_notebook.core.session import SessionRunResult
from newbee_notebook.core.tools.contracts import SourceItem
from newbee_notebook.core.rag.generation.chat_engine import build_chat_engine, build_simple_chat_engine
from newbee_notebook.domain.value_objects.document_status import DocumentStatus
from newbee_notebook.domain.value_objects.mode_type import ModeType


class TestBuildChatEngine:
    """Tests for build_chat_engine function."""

    def test_build_chat_engine_with_valid_params(self):
        """Test building chat engine with valid parameters."""
        mock_index = Mock()
        mock_llm = Mock()
        mock_memory = Mock()
        mock_chat_engine = Mock()

        # Mock the as_chat_engine method
        mock_index.as_chat_engine.return_value = mock_chat_engine

        result = build_chat_engine(
            index=mock_index,
            llm=mock_llm,
            memory=mock_memory
        )

        assert result == mock_chat_engine
        mock_index.as_chat_engine.assert_called_once()

    def test_build_chat_engine_with_custom_params(self):
        """Test building chat engine with custom parameters."""
        mock_index = Mock()
        mock_llm = Mock()
        mock_memory = Mock()
        mock_chat_engine = Mock()

        mock_index.as_chat_engine.return_value = mock_chat_engine

        result = build_chat_engine(
            index=mock_index,
            llm=mock_llm,
            memory=mock_memory,
            chat_mode="simple",
            response_mode="tree_summarize",
            similarity_top_k=5,
            similarity_cutoff=0.25,
            verbose=True
        )

        assert result == mock_chat_engine

        # Verify the parameters were passed correctly
        call_kwargs = mock_index.as_chat_engine.call_args[1]
        assert call_kwargs["chat_mode"] == "simple"
        assert call_kwargs["response_mode"] == "tree_summarize"
        assert call_kwargs["similarity_top_k"] == 5
        assert call_kwargs["verbose"] is True
        assert call_kwargs["llm"] == mock_llm
        assert call_kwargs["memory"] == mock_memory

    def test_build_chat_engine_validates_similarity_top_k(self):
        """Test that similarity_top_k must be >= 1."""
        mock_index = Mock()
        mock_llm = Mock()
        mock_memory = Mock()

        with pytest.raises(ValueError, match="similarity_top_k must be at least 1"):
            build_chat_engine(
                index=mock_index,
                llm=mock_llm,
                memory=mock_memory,
                similarity_top_k=0
            )

        with pytest.raises(ValueError, match="similarity_top_k must be at least 1"):
            build_chat_engine(
                index=mock_index,
                llm=mock_llm,
                memory=mock_memory,
                similarity_top_k=-1
            )

    def test_build_chat_engine_validates_similarity_cutoff(self):
        """Test that similarity_cutoff must be between 0 and 1."""
        mock_index = Mock()
        mock_llm = Mock()
        mock_memory = Mock()

        with pytest.raises(ValueError, match="similarity_cutoff must be between 0 and 1"):
            build_chat_engine(
                index=mock_index,
                llm=mock_llm,
                memory=mock_memory,
                similarity_cutoff=-0.1
            )

        with pytest.raises(ValueError, match="similarity_cutoff must be between 0 and 1"):
            build_chat_engine(
                index=mock_index,
                llm=mock_llm,
                memory=mock_memory,
                similarity_cutoff=1.5
            )

    def test_build_chat_engine_similarity_cutoff_boundaries(self):
        """Test similarity_cutoff with boundary values."""
        mock_index = Mock()
        mock_llm = Mock()
        mock_memory = Mock()
        mock_chat_engine = Mock()

        mock_index.as_chat_engine.return_value = mock_chat_engine

        # Test with 0 (valid boundary)
        result = build_chat_engine(
            index=mock_index,
            llm=mock_llm,
            memory=mock_memory,
            similarity_cutoff=0.0
        )
        assert result == mock_chat_engine

        # Test with 1 (valid boundary)
        result = build_chat_engine(
            index=mock_index,
            llm=mock_llm,
            memory=mock_memory,
            similarity_cutoff=1.0
        )
        assert result == mock_chat_engine

    def test_build_chat_engine_creates_postprocessor(self):
        """Test that build_chat_engine creates SimilarityPostprocessor."""
        mock_index = Mock()
        mock_llm = Mock()
        mock_memory = Mock()
        mock_chat_engine = Mock()

        mock_index.as_chat_engine.return_value = mock_chat_engine

        build_chat_engine(
            index=mock_index,
            llm=mock_llm,
            memory=mock_memory,
            similarity_cutoff=0.3
        )

        # Verify postprocessors were passed
        call_kwargs = mock_index.as_chat_engine.call_args[1]
        postprocessors = call_kwargs["node_postprocessors"]
        assert postprocessors is not None
        assert len(postprocessors) == 1

    def test_build_chat_engine_passes_extra_kwargs(self):
        """Test that extra kwargs are passed through to as_chat_engine."""
        mock_index = Mock()
        mock_llm = Mock()
        mock_memory = Mock()
        mock_chat_engine = Mock()

        mock_index.as_chat_engine.return_value = mock_chat_engine

        build_chat_engine(
            index=mock_index,
            llm=mock_llm,
            memory=mock_memory,
            extra_param1="value1",
            extra_param2=42
        )

        call_kwargs = mock_index.as_chat_engine.call_args[1]
        assert call_kwargs["extra_param1"] == "value1"
        assert call_kwargs["extra_param2"] == 42


class TestBuildSimpleChatEngine:
    """Tests for build_simple_chat_engine function."""

    def test_build_simple_chat_engine(self):
        """Test building simple chat engine with defaults."""
        mock_index = Mock()
        mock_llm = Mock()
        mock_memory = Mock()
        mock_chat_engine = Mock()

        mock_index.as_chat_engine.return_value = mock_chat_engine

        result = build_simple_chat_engine(
            index=mock_index,
            llm=mock_llm,
            memory=mock_memory
        )

        assert result == mock_chat_engine

    def test_build_simple_chat_engine_uses_default_params(self):
        """Test that build_simple_chat_engine uses default parameters."""
        mock_index = Mock()
        mock_llm = Mock()
        mock_memory = Mock()
        mock_chat_engine = Mock()

        mock_index.as_chat_engine.return_value = mock_chat_engine

        build_simple_chat_engine(
            index=mock_index,
            llm=mock_llm,
            memory=mock_memory
        )

        # Verify defaults: similarity_top_k=5, similarity_cutoff=0.25
        call_kwargs = mock_index.as_chat_engine.call_args[1]
        assert call_kwargs["similarity_top_k"] == 5

        # similarity_cutoff is used to create postprocessor, not passed directly
        postprocessors = call_kwargs["node_postprocessors"]
        assert postprocessors is not None
        assert len(postprocessors) == 1


class _DummyRuntimeAskSessionManager:
    def __init__(self):
        self.started_with: list[str] = []
        self.chat_kwargs = None

    async def start_session(self, session_id: str):
        self.started_with.append(session_id)

    async def chat(self, **kwargs):
        self.chat_kwargs = kwargs
        return SessionRunResult(
            content="runtime ask answer",
            sources=[
                SourceItem(
                    document_id="doc-1",
                    chunk_id="chunk-1",
                    title="Doc 1",
                    text="runtime ask source",
                    score=0.91,
                    source_type="retrieval",
                )
            ],
        )


class TestAskRuntimeRouting:
    def test_chat_service_routes_ask_to_runtime_manager(self):
        session_repo = AsyncMock()
        session_repo.get.return_value = SimpleNamespace(
            session_id="session-1",
            notebook_id="nb-1",
            message_count=0,
            include_ec_context=False,
        )
        ref_repo = AsyncMock()
        ref_repo.list_by_notebook.return_value = [SimpleNamespace(document_id="doc-1")]
        document_repo = AsyncMock()
        document_repo.get_batch.return_value = [
            SimpleNamespace(document_id="doc-1", status=DocumentStatus.COMPLETED, title="Doc 1")
        ]
        document_repo.get.return_value = SimpleNamespace(document_id="doc-1")
        message_repo = AsyncMock()
        runtime_manager = _DummyRuntimeAskSessionManager()

        service = ChatService(
            session_repo=session_repo,
            notebook_repo=AsyncMock(),
            reference_repo=AsyncMock(),
            document_repo=document_repo,
            ref_repo=ref_repo,
            message_repo=message_repo,
            session_manager=runtime_manager,
        )

        result = asyncio.run(service.chat(session_id="session-1", message="hi", mode="ask"))

        assert result.content == "runtime ask answer"
        assert result.mode == ModeType.ASK
        assert runtime_manager.started_with == ["session-1"]
        assert runtime_manager.chat_kwargs["mode_type"] == ModeType.ASK


