"""Conclude mode implementation using ChatEngine.

This mode provides document summarization and conclusion generation:
- ChatEngine with condense_plus_context mode
- RAG for retrieving relevant documents
- Optimized for summarization tasks

No conversation memory - each query is treated independently.
"""

from typing import Optional
from llama_index.core.llms import LLM
from llama_index.core.memory import BaseMemory
from llama_index.core.chat_engine.types import BaseChatEngine
from llama_index.core import VectorStoreIndex

from src.engine.modes.base import BaseMode, ModeConfig, ModeType
from src.prompts import load_prompt


DEFAULT_CONTEXT_PROMPT = """Based on the following documents, provide a comprehensive summary or conclusion.

Documents:
{context_str}

Please analyze the above and provide your summary."""


class ConcludeMode(BaseMode):
    """Conclude mode using ChatEngine for summarization.
    
    This mode provides:
    - Document summarization and conclusion generation
    - RAG for retrieving relevant documents
    - condense_plus_context mode for optimal summarization
    
    Note: This mode does NOT maintain conversation memory.
    Each query is treated as an independent summarization request.
    
    Attributes:
        _chat_engine: ChatEngine instance for summarization
        _index: VectorStoreIndex for retrieval
    """
    
    def __init__(
        self,
        llm: LLM,
        index: Optional[VectorStoreIndex] = None,
        memory: Optional[BaseMemory] = None,
        config: Optional[ModeConfig] = None,
        similarity_top_k: int = 10,
        response_mode: str = "tree_summarize",
    ):
        """Initialize ConcludeMode.
        
        Args:
            llm: LLM instance
            index: VectorStoreIndex for document retrieval
            memory: Conversation memory (optional, for multi-turn summaries)
            config: Mode configuration
            similarity_top_k: Number of documents to retrieve
            response_mode: Response synthesis mode (tree_summarize recommended)
        """
        super().__init__(llm=llm, memory=memory, config=config)
        
        self._index = index
        self._similarity_top_k = similarity_top_k
        self._response_mode = response_mode
        
        self._chat_engine: Optional[BaseChatEngine] = None
    
    def _default_config(self) -> ModeConfig:
        """Return default Conclude mode configuration."""
        return ModeConfig(
            mode_type=ModeType.CONCLUDE,
            has_memory=False,  # No memory for conclude mode
            system_prompt=load_prompt("conclude.md"),
            verbose=False,
        )
    
    async def _initialize(self) -> None:
        """Initialize the ChatEngine for summarization."""
        if self._index is None:
            raise ValueError("ConcludeMode requires an index for RAG")
        
        system_prompt = self._config.system_prompt or load_prompt("conclude.md")
        
        # Create chat engine optimized for summarization
        self._chat_engine = self._index.as_chat_engine(
            chat_mode="condense_plus_context",
            llm=self._llm,
            similarity_top_k=self._similarity_top_k,
            response_mode=self._response_mode,
            system_prompt=system_prompt,
            context_prompt=DEFAULT_CONTEXT_PROMPT,
            verbose=self._config.verbose,
            memory=self._memory,
        )
    
    async def _process(self, message: str) -> str:
        """Process summarization request using ChatEngine.
        
        Args:
            message: User's summarization request
            
        Returns:
            Generated summary or conclusion
        """
        # Use chat method (async if available)
        try:
            response = await self._chat_engine.achat(message)
        except AttributeError:
            # Fallback to sync if async not available
            response = self._chat_engine.chat(message)
        
        return str(response)
    
    @property
    def chat_engine(self) -> Optional[BaseChatEngine]:
        """Get the ChatEngine instance."""
        return self._chat_engine
    
    async def reset(self) -> None:
        """Reset conversation memory if available."""
        if self._memory is not None:
            self._memory.reset()


def build_conclude_mode(
    llm: LLM,
    index: VectorStoreIndex,
    similarity_top_k: int = 10,
    response_mode: str = "tree_summarize",
) -> ConcludeMode:
    """Build a ConcludeMode instance.
    
    Convenience function for creating a ConcludeMode with common settings.
    
    Args:
        llm: LLM instance
        index: VectorStoreIndex for retrieval
        similarity_top_k: Number of documents to retrieve
        response_mode: Response synthesis mode
        
    Returns:
        Configured ConcludeMode instance
    """
    return ConcludeMode(
        llm=llm,
        index=index,
        similarity_top_k=similarity_top_k,
        response_mode=response_mode,
    )
