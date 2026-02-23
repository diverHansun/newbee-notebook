"""Chat mode implementation using FunctionAgent.

This mode uses the FunctionAgent (Workflow-based) to handle standard
conversation with tool support.
"""

from typing import List, Optional, AsyncGenerator

from llama_index.core.tools import BaseTool
from llama_index.core.memory import BaseMemory
from llama_index.core.llms import LLM, ChatMessage, MessageRole

from newbee_notebook.core.engine.modes.base import BaseMode, ModeConfig, ModeType
from newbee_notebook.core.tools.tool_registry import build_tool_registry
from newbee_notebook.core.agent import FunctionAgentRunner
from newbee_notebook.core.prompts import load_prompt
from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator
from newbee_notebook.core.rag.retrieval.filters import build_document_filters
from newbee_notebook.core.common.node_utils import extract_document_id

# Backward-compatible exported prompt constant for tests
DEFAULT_CHAT_SYSTEM_PROMPT = load_prompt("chat.md")
PHASE_MARKER = "__PHASE__"


def build_phase_marker(stage: str) -> str:
    return f"{PHASE_MARKER}:{stage}"


class ChatMode(BaseMode):
    """Chat mode implementation.
    
    This mode uses a FunctionAgent to handle conversational interactions
    with support for tools (web search, etc.).
    """
    
    def __init__(
        self,
        llm: LLM,
        memory: Optional[BaseMemory] = None,
        es_index_name: str = "newbee_notebook_docs",
        enable_tavily: bool = True,
        enable_es_search: bool = True,
        vector_index=None,
    ):
        """Initialize ChatMode.
        
        Args:
            llm: LLM instance
            memory: Conversation memory
            es_index_name: Elasticsearch index name (unused in this mode but kept for interface consistency)
            enable_tavily: Compatibility flag for tests; currently unused.
        """
        super().__init__(llm, memory)
        self._runner: Optional[FunctionAgentRunner] = None
        self._es_index_name = es_index_name
        self._enable_tavily = enable_tavily
        self._enable_es_search = enable_es_search
        self._agent = None  # lazily built FunctionAgentRunner
        self._vector_index = vector_index
        self._tool_scope_signature: Optional[tuple[str, ...]] = None
        self._es_search_tool_wrapper = None
    
    def _default_config(self) -> ModeConfig:
        """Return default Chat mode configuration."""
        return ModeConfig(
            mode_type=ModeType.CHAT,
            has_memory=True,
            system_prompt=load_prompt("chat.md"),
            verbose=False,
        )
    
    def _build_tools(self) -> List[BaseTool]:
        """Build the list of tools for this mode.
        
        Returns:
            List of tools (web search, etc.)
        """
        # Get search tools
        tools = build_tool_registry(
            es_index_name=self._es_index_name,
            allowed_doc_ids=self.allowed_doc_ids,
        )
        self._es_search_tool_wrapper = None
        for tool in tools:
            wrapper = getattr(tool, "_newbee_es_search_wrapper", None)
            if wrapper is not None:
                self._es_search_tool_wrapper = wrapper
                break
        return tools

    def _clear_tool_result_sources(self) -> None:
        if self._es_search_tool_wrapper and hasattr(self._es_search_tool_wrapper, "clear_last_raw_results"):
            self._es_search_tool_wrapper.clear_last_raw_results()

    def _collect_tool_result_sources(self) -> List[dict]:
        if self._es_search_tool_wrapper is None:
            return []
        raw_results = getattr(self._es_search_tool_wrapper, "last_raw_results", []) or []
        sources: List[dict] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            sources.append(
                {
                    "document_id": item.get("document_id", ""),
                    "chunk_id": item.get("chunk_id", "") or "",
                    "text": item.get("text", "") or "",
                    "score": float(item.get("score", 0.0) or 0.0),
                    "title": item.get("title", "") or "",
                }
            )
        return sources

    def _update_last_sources_after_agent(self, had_tool_calls: bool) -> None:
        if not had_tool_calls:
            self._last_sources = []
            return
        self._last_sources = self._collect_tool_result_sources()

    def _current_scope_signature(self) -> Optional[tuple[str, ...]]:
        if self.allowed_doc_ids is None:
            return None
        return tuple(sorted(self.allowed_doc_ids))

    async def _refresh_runner(self) -> None:
        """Rebuild FunctionAgent runner with current notebook scope."""
        tools = self._build_tools()
        system_prompt = self._config.system_prompt or load_prompt("chat.md")
        self._runner = FunctionAgentRunner(
            llm=self._llm,
            tools=tools,
            system_prompt=system_prompt,
            verbose=self._config.verbose,
        )
        self._tool_scope_signature = self._current_scope_signature()
        print(f"[ChatMode] Initialized with {len(tools)} tool(s).")

    async def _ensure_runner_scope(self) -> None:
        """Ensure tool scope follows current notebook allowed_doc_ids."""
        current_scope = self._current_scope_signature()
        if self._runner is None or current_scope != self._tool_scope_signature:
            await self._refresh_runner()
    
    async def _initialize(self) -> None:
        """Initialize the agent."""
        await self._refresh_runner()
        self._initialized = True
    
    async def _process(self, message: str) -> str:
        """Process message using FunctionAgentRunner.
        
        Args:
            message: User message
            
        Returns:
            Agent response
        """
        await self._ensure_runner_scope()

        # Get chat history for context
        chat_history = []
        if self._memory is not None:
            chat_history = self._memory.get_all()
        chat_history = self._augment_chat_history_with_ec_summary(chat_history)
        
        # Run agent through runner (SRP: runner handles LlamaIndex API)
        self._clear_tool_result_sources()
        try:
            response = await self._runner.run(
                message=message,
                chat_history=chat_history,
            )
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            debug_msg = (
                "[ChatMode] Agent run failed.\n"
                f"message={message!r}\n"
                f"history_len={len(chat_history)}\n"
                f"error={exc}\n"
                f"traceback:\n{tb}"
            )
            print(debug_msg)
            raise
        
        # Store in memory if available
        if self._memory is not None:
            self._memory.put(ChatMessage(role=MessageRole.USER, content=message))
            self._memory.put(ChatMessage(role=MessageRole.ASSISTANT, content=response))
        had_tool_calls = bool(getattr(self._runner, "had_tool_calls", False))
        self._update_last_sources_after_agent(had_tool_calls)
        return response
    
    @property
    def tools(self) -> List[BaseTool]:
        """Get the list of available tools."""
        if self._runner and hasattr(self._runner.agent, 'tools'):
            return self._runner.agent.tools
        return []

    async def _stream(self, message: str) -> AsyncGenerator[str, None]:
        """Stream response in two phases to preserve tool-call correctness.

        Phase 1 runs the FunctionAgent (with tools) to resolve intermediate steps.
        Phase 2 streams the final user-facing answer from the LLM using the agent
        result as context.
        """
        await self._ensure_runner_scope()

        chat_history: List[ChatMessage] = []
        if self._memory is not None:
            chat_history = self._memory.get_all()
        chat_history = self._augment_chat_history_with_ec_summary(chat_history)

        yield build_phase_marker("searching")

        self._clear_tool_result_sources()
        agent_response = await self._runner.run(
            message=message,
            chat_history=chat_history,
        )
        had_tool_calls = bool(getattr(self._runner, "had_tool_calls", False))
        looks_like_tool_intent = (
            "<tool_call>" in agent_response
            or "</tool_call>" in agent_response
            or "\"tool_name\"" in agent_response
            or "\"function\"" in agent_response
        )

        yield build_phase_marker("generating")

        # Fast path: agent already produced a direct answer without invoking tools.
        if not had_tool_calls and not looks_like_tool_intent:
            self._update_last_sources_after_agent(False)
            if self._memory is not None and agent_response:
                self._memory.put(ChatMessage(role=MessageRole.USER, content=message))
                self._memory.put(ChatMessage(role=MessageRole.ASSISTANT, content=agent_response))

            chunk_size = 20
            for idx in range(0, len(agent_response), chunk_size):
                yield agent_response[idx: idx + chunk_size]
            return

        # Phase 2: stream a polished final answer grounded in the agent output.
        messages: List[ChatMessage] = []
        system_prompt = self._config.system_prompt or ""
        if system_prompt:
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))

        if self._memory is not None:
            messages.extend(self._memory.get_all())
        messages = self._augment_chat_history_with_ec_summary(messages)

        messages.append(ChatMessage(role=MessageRole.USER, content=message))
        messages.append(ChatMessage(role=MessageRole.ASSISTANT, content=agent_response))
        messages.append(
            ChatMessage(
                role=MessageRole.USER,
                content="Based on the information above, directly answer the user's question.",
            )
        )

        self._update_last_sources_after_agent(had_tool_calls)

        full_response = ""
        stream_response = await self._llm.astream_chat(messages)
        async for chunk in stream_response:
            delta = getattr(chunk, "delta", None)
            if delta:
                full_response += delta
                yield delta
                continue

            content = ""
            if hasattr(chunk, "message"):
                content = getattr(chunk.message, "content", "") or ""
            elif hasattr(chunk, "content"):
                content = chunk.content or ""
            if content and content != full_response:
                new_content = content[len(full_response):]
                if new_content:
                    full_response = content
                    yield new_content

        if self._memory is not None and full_response:
            self._memory.put(ChatMessage(role=MessageRole.USER, content=message))
            self._memory.put(ChatMessage(role=MessageRole.ASSISTANT, content=full_response))

    def _collect_sources(self, message: str) -> List[dict]:
        """Optionally collect RAG sources for citation."""
        if not self._vector_index or not self.allowed_doc_ids:
            return []
        try:
            pg_filters, _, _ = build_document_filters(self.allowed_doc_ids, key="ref_doc_id")
            retriever = self._vector_index.as_retriever(
                similarity_top_k=3,
                filters=pg_filters,
            )
            results = retriever.retrieve(message)
        except Exception:
            return []
        sources = []
        allowed_doc_ids = set(self.allowed_doc_ids or [])
        for node in results:
            meta = getattr(node.node, "metadata", {}) if hasattr(node, "node") else {}
            doc_id = extract_document_id(node)
            if doc_id not in allowed_doc_ids:
                continue
            sources.append(
                {
                    "document_id": doc_id,
                    "chunk_id": getattr(node.node, "node_id", ""),
                    "text": node.node.get_content() if hasattr(node, "node") else "",
                    "score": getattr(node, "score", 0.0),
                    "title": meta.get("title", meta.get("file_name", "")),
                }
            )
        return sources

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
