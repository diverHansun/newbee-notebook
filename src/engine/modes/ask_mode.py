"""Ask mode implementation using ReActAgent with RAG.

This mode provides deep Q&A with:
- ReActAgent for reasoning and acting
- Hybrid retrieval (pgvector + Elasticsearch BM25)
- RAG for grounded responses
- Optional external web tools (Zhipu search/reader) when enabled

The agent uses a think-act-observe loop to answer complex questions.
"""

from typing import Optional, List
import os
from llama_index.core.llms import LLM, ChatMessage, MessageRole
from llama_index.core.memory import BaseMemory
from llama_index.core.tools import BaseTool, QueryEngineTool, ToolMetadata
from llama_index.core import VectorStoreIndex

from src.engine.modes.base import BaseMode, ModeConfig, ModeType
from src.agent import ReActAgentRunner
from src.rag.retrieval import HybridRetriever, RRFFusion, build_hybrid_retriever
from src.prompts import load_prompt
from src.tools.zhipu_tools import (
    build_zhipu_web_search_tool,
    build_zhipu_web_crawl_tool,
)
from src.tools.time import build_current_time_tool
from src.common.config import get_zhipu_tools_config


class AskMode(BaseMode):
    """Ask mode implementation.
    
    This mode uses a ReActAgent with access to a hybrid retrieval tool
    to answer complex questions based on the knowledge base.
    """
    
    def __init__(
        self,
        llm: LLM,
        pgvector_index: Optional[VectorStoreIndex],
        es_index: Optional[VectorStoreIndex],
        memory: Optional[BaseMemory] = None,
        pgvector_top_k: int = 5,
        es_top_k: int = 5,
        final_top_k: int = 5,
    ):
        """Initialize AskMode.
        
        Args:
            llm: LLM instance
            pgvector_index: Vector store index (semantic search)
            es_index: Elasticsearch index (keyword search)
            memory: Conversation memory
            pgvector_top_k: Number of semantic results
            es_top_k: Number of keyword results
            final_top_k: Number of final RRF results
        """
        super().__init__(llm, memory)
        self._pgvector_index = pgvector_index
        self._es_index = es_index
        self._pgvector_top_k = pgvector_top_k
        self._es_top_k = es_top_k
        self._final_top_k = final_top_k
        
        self._runner: Optional[ReActAgentRunner] = None
        self._retriever: Optional[HybridRetriever] = None
        self._query_engine = None
    
    def _default_config(self) -> ModeConfig:
        """Return default Ask mode configuration."""
        return ModeConfig(
            mode_type=ModeType.ASK,
            has_memory=True,
            system_prompt=load_prompt("ask.md"),
            verbose=False,
        )
    
    def _build_tools(self) -> List[BaseTool]:
        """Build the list of tools for this mode.
        
        Returns:
            List containing the knowledge base search tool
        """
        tools: List[BaseTool] = []

        # Current time tool (always available; no external deps)
        tools.append(build_current_time_tool())

        # Knowledge base query tool (always available when retriever is ready)
        if self._query_engine is not None:
            tools.append(
                QueryEngineTool(
                    query_engine=self._query_engine,
                    metadata=ToolMetadata(
                        name="knowledge_base",
                        description="Search the medical knowledge base for information. Usage: input the question or topic.",
                    ),
                )
            )

        # Optional Zhipu web tools (require API key + enabled config)
        api_key = os.getenv("ZHIPU_API_KEY")
        if api_key:
            zhipu_cfg = get_zhipu_tools_config() or {}
            zhipu_tools_cfg = zhipu_cfg.get("zhipu_tools", {}) or {}

            web_search_cfg = zhipu_tools_cfg.get("web_search", {}) or {}
            if web_search_cfg.get("enabled", False):
                try:
                    tools.append(build_zhipu_web_search_tool())
                except Exception as exc:
                    print(f"[AskMode] Warning: failed to init zhipu_web_search: {exc}")

            web_crawl_cfg = zhipu_tools_cfg.get("web_crawl", {}) or {}
            if web_crawl_cfg.get("enabled", False):
                try:
                    tools.append(build_zhipu_web_crawl_tool())
                except Exception as exc:
                    print(f"[AskMode] Warning: failed to init zhipu_web_crawl: {exc}")

        return tools
    
    async def _initialize(self) -> None:
        """Initialize retriever and agent."""
        # 1. Setup Retrieval Strategy (Hybrid)
        if self._pgvector_index and self._es_index:
            # Full hybrid retrieval
            self._retriever = build_hybrid_retriever(
                pgvector_index=self._pgvector_index,
                es_index=self._es_index,
                pgvector_top_k=self._pgvector_top_k,
                es_top_k=self._es_top_k,
                final_top_k=self._final_top_k,
                fusion_strategy=RRFFusion(),
            )
            print("AskMode: Initialized with Hybrid Retrieval (pgvector + Elasticsearch)")
            
        elif self._pgvector_index:
            # Fallback to just vector search
            self._retriever = self._pgvector_index.as_retriever(
                similarity_top_k=self._final_top_k
            )
            print("AskMode: Initialized with Vector Search only (pgvector)")
            
        else:
            raise ValueError("AskMode requires at least pgvector_index")
        
        # 2. Create Query Engine
        from llama_index.core.query_engine import RetrieverQueryEngine
        
        self._query_engine = RetrieverQueryEngine.from_args(
            retriever=self._retriever,
            llm=self._llm,
        )
        
        # 3. Create Tools
        tools = self._build_tools()
        tool_names = []
        for tool in tools:
            name = getattr(getattr(tool, "metadata", None), "name", None)
            if not name:
                name = getattr(tool, "name", tool.__class__.__name__)
            tool_names.append(name)

        # 4. Get system prompt
        system_prompt = self._config.system_prompt or load_prompt("ask.md")

        # 5. Create ReActAgentRunner
        self._runner = ReActAgentRunner(
            llm=self._llm,
            tools=tools,
            system_prompt=system_prompt,
            verbose=self._config.verbose,
        )
        tool_count = len(tools)
        retriever_type = type(self._retriever).__name__ if self._retriever else "None"
        tool_names_str = ", ".join(tool_names) if tool_names else "none"
        print(f"[AskMode] Initialized ReActAgentRunner with {tool_count} tool(s), retriever={retriever_type}. Tools: {tool_names_str}")
        
        self._initialized = True
    
    async def _process(self, message: str) -> str:
        """Process message using ReActAgentRunner.
        
        Args:
            message: User message
            
        Returns:
            Agent response with RAG-grounded information
        """
        # Get chat history for context
        chat_history = []
        if self._memory is not None:
            chat_history = self._memory.get_all()
        
        # Run agent through runner (SRP: runner handles LlamaIndex API)
        response = await self._runner.run(
            message=message,
            chat_history=chat_history,
        )
        
        # Store in memory if available
        if self._memory is not None:
            self._memory.put(ChatMessage(role=MessageRole.USER, content=message))
            self._memory.put(ChatMessage(role=MessageRole.ASSISTANT, content=response))
        
        return response
    
    @property
    def retriever(self) -> Optional[HybridRetriever]:
        """Get the retriever instance."""
        return self._retriever
