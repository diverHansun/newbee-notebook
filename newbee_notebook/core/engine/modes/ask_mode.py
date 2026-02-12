"""Ask mode implementation using ReActAgent with RAG.

This mode provides deep Q&A with:
- ReActAgent for reasoning and acting
- Hybrid retrieval (pgvector + Elasticsearch BM25)
- RAG for grounded responses
- Optional external web tools (Zhipu search/reader) when enabled

The agent uses a think-act-observe loop to answer complex questions.
"""

from typing import Optional, List, Callable
import os
import logging
from llama_index.core.llms import LLM, ChatMessage, MessageRole
from llama_index.core.memory import BaseMemory
from llama_index.core.tools import BaseTool, QueryEngineTool, ToolMetadata
from llama_index.core import VectorStoreIndex
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore
from llama_index.core.schema import QueryBundle

from newbee_notebook.core.engine.modes.base import BaseMode, ModeConfig, ModeType
from newbee_notebook.core.agent import ReActAgentRunner
from newbee_notebook.core.rag.retrieval import HybridRetriever, RRFFusion, build_hybrid_retriever
from newbee_notebook.core.rag.retrieval.filters import build_document_filters
from newbee_notebook.core.prompts import load_prompt
from newbee_notebook.core.common.node_utils import extract_document_id
from newbee_notebook.core.tools.zhipu_tools import (
    build_zhipu_web_search_tool,
    build_zhipu_web_crawl_tool,
)
from newbee_notebook.core.tools.time import build_current_time_tool
from newbee_notebook.core.common.config import get_zhipu_tools_config

DEFAULT_ASK_SYSTEM_PROMPT = load_prompt("ask.md")
logger = logging.getLogger(__name__)


class _TitleAwareFallbackRetriever(BaseRetriever):
    """Retriever wrapper that retries once with notebook title hints."""

    def __init__(
        self,
        base_retriever: BaseRetriever,
        fallback_query_builder: Callable[[str], Optional[str]],
    ):
        super().__init__()
        self._base_retriever = base_retriever
        self._fallback_query_builder = fallback_query_builder
        self._last_fallback_query: Optional[str] = None
        self._fallback_used: bool = False

    @property
    def last_fallback_query(self) -> Optional[str]:
        """Return fallback query used by the latest retrieval call."""
        return self._last_fallback_query

    @property
    def fallback_used(self) -> bool:
        """Whether fallback retrieval was attempted in latest call."""
        return self._fallback_used

    def _prepare_fallback_query(self, query_bundle: QueryBundle) -> Optional[str]:
        query_text = (query_bundle.query_str or "").strip()
        fallback_query = (self._fallback_query_builder(query_text) or "").strip()
        if not fallback_query or fallback_query == query_text:
            self._fallback_used = False
            self._last_fallback_query = None
            return None
        self._fallback_used = True
        self._last_fallback_query = fallback_query
        return fallback_query

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        self._fallback_used = False
        self._last_fallback_query = None

        results = self._base_retriever.retrieve(query_bundle)
        if results:
            return results

        fallback_query = self._prepare_fallback_query(query_bundle)
        if not fallback_query:
            return []
        return self._base_retriever.retrieve(QueryBundle(fallback_query))

    async def _aretrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        self._fallback_used = False
        self._last_fallback_query = None

        base_aretrieve = getattr(self._base_retriever, "aretrieve", None)
        if callable(base_aretrieve):
            results = await base_aretrieve(query_bundle)
        else:
            results = self._base_retriever.retrieve(query_bundle)

        if results:
            return results

        fallback_query = self._prepare_fallback_query(query_bundle)
        if not fallback_query:
            return []

        if callable(base_aretrieve):
            return await base_aretrieve(QueryBundle(fallback_query))
        return self._base_retriever.retrieve(QueryBundle(fallback_query))


class AskMode(BaseMode):
    """Ask mode implementation.
    
    This mode uses a ReActAgent with access to a hybrid retrieval tool
    to answer complex questions based on the knowledge base.
    """
    
    def __init__(
        self,
        llm: LLM,
        pgvector_index: Optional[VectorStoreIndex] = None,
        es_index: Optional[VectorStoreIndex] = None,
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
        self._base_retriever: Optional[HybridRetriever] = None
        self._retriever: Optional[BaseRetriever] = None
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
        if not (self._pgvector_index and self._es_index):
            raise ValueError("AskMode requires both pgvector_index and es_index")
        await self._refresh_retriever()

    async def _refresh_retriever(self) -> None:
        """(Re)build retriever and query_engine with current filters."""
        pg_filters, es_filters, allowed_ids = build_document_filters(self.allowed_doc_ids, key="ref_doc_id")
        # Build base hybrid retriever with notebook scope.
        self._base_retriever = build_hybrid_retriever(
            pgvector_index=self._pgvector_index,
            es_index=self._es_index,
            pgvector_top_k=self._pgvector_top_k,
            es_top_k=self._es_top_k,
            final_top_k=self._final_top_k,
            fusion_strategy=RRFFusion(),
            pg_filters=pg_filters,
            es_filters=es_filters,
            allowed_doc_ids=allowed_ids,
        )
        # Retry once with notebook title hints when strict scope yields empty recall.
        self._retriever = _TitleAwareFallbackRetriever(
            base_retriever=self._base_retriever,
            fallback_query_builder=self._build_title_fallback_query,
        )
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

    def _get_allowed_document_titles(self) -> List[str]:
        """Read notebook titles injected by ChatService context."""
        if not isinstance(self.context, dict):
            return []

        raw_titles = self.context.get("allowed_document_titles")
        if not isinstance(raw_titles, list):
            return []

        deduped: List[str] = []
        seen = set()
        for value in raw_titles:
            if not isinstance(value, str):
                continue
            title = value.strip()
            if not title or title in seen:
                continue
            seen.add(title)
            deduped.append(title)
        return deduped

    def _build_title_fallback_query(self, query: str) -> Optional[str]:
        """Build one retry query by prefixing notebook titles."""
        normalized_query = (query or "").strip()
        if not normalized_query:
            return None

        titles = self._get_allowed_document_titles()
        if not titles:
            return None

        # Keep fallback query compact to avoid noisy prompt expansion.
        title_prefix = " ".join(title[:80] for title in titles[:2]).strip()
        if not title_prefix:
            return None

        return f"{title_prefix} {normalized_query}"
    
    async def _process(self, message: str) -> str:
        """Process message using ReActAgentRunner.
        
        Args:
            message: User message
            
        Returns:
            Agent response with RAG-grounded information
        """
        # Refresh retriever if document scope changed
        if self.scope_changed():
            await self._refresh_retriever()
        # Get chat history for context
        chat_history = []
        if self._memory is not None:
            chat_history = self._memory.get_all()
        chat_history = self._augment_chat_history_with_ec_summary(chat_history)
        
        # Run agent through runner (SRP: runner handles LlamaIndex API)
        response = await self._runner.run(
            message=message,
            chat_history=chat_history,
        )

        # Collect sources via retriever (single shot to avoid coupling to agent internals)
        sources = []
        if self._retriever is not None:
            try:
                results = await self._retriever.aretrieve(QueryBundle(message))
            except AttributeError:
                results = self._retriever.retrieve(QueryBundle(message))
            fallback_query = getattr(self._retriever, "last_fallback_query", None)
            if fallback_query:
                logger.debug(
                    "AskMode retrieval fallback applied. query=%r fallback=%r",
                    message,
                    fallback_query,
                )
            for node in results:
                doc_id = extract_document_id(node)
                meta = getattr(node.node, "metadata", {}) if hasattr(node, "node") else {}
                sources.append(
                    {
                        "document_id": doc_id,
                        "chunk_id": getattr(node.node, "node_id", ""),
                        "text": node.node.get_content() if hasattr(node, "node") else "",
                        "score": getattr(node, "score", 0.0),
                        "title": meta.get("title", meta.get("file_name", "")),
                    }
                )
        self._last_sources = sources
        
        # Store in memory if available
        if self._memory is not None:
            self._memory.put(ChatMessage(role=MessageRole.USER, content=message))
            self._memory.put(ChatMessage(role=MessageRole.ASSISTANT, content=response))
        
        return response

    async def _stream(self, message: str):
        """Stream response using LLM directly with retrieved context."""
        # ensure retriever up to date
        if self.scope_changed():
            await self._refresh_retriever()
        # simple: run non-stream process (for sources) then stream llm
        base_response = await self._process(message)
        # stream from llm best-effort
        try:
            stream = await self._llm.astream_chat(message)
            async for chunk in stream:
                delta = getattr(chunk, "delta", "") or getattr(chunk, "text", "")
                if delta:
                    yield delta
        except Exception:
            yield base_response
    
    @property
    def retriever(self) -> Optional[BaseRetriever]:
        """Get the retriever instance."""
        return self._retriever

    def _augment_chat_history_with_ec_summary(self, history: List[ChatMessage]) -> List[ChatMessage]:
        """Inject optional EC summary as a transient system message."""
        if not isinstance(self.context, dict):
            return history
        ec_summary = (self.context.get("ec_context_summary") or "").strip()
        if not ec_summary:
            return history
        summary_message = ChatMessage(
            role=MessageRole.SYSTEM,
            content=f"[Recent Explain/Conclude Context]\n{ec_summary}",
        )
        return [summary_message, *history]
