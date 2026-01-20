"""Chat mode implementation using FunctionAgent.

This mode uses the FunctionAgent (Workflow-based) to handle standard
conversation with tool support.
"""

from typing import List, Optional, AsyncGenerator

from llama_index.core.tools import BaseTool
from llama_index.core.memory import BaseMemory
from llama_index.core.llms import LLM, ChatMessage, MessageRole

from medimind_agent.core.engine.modes.base import BaseMode, ModeConfig, ModeType
from medimind_agent.core.tools.tool_registry import build_tool_registry
from medimind_agent.core.agent import FunctionAgentRunner
from medimind_agent.core.prompts import load_prompt
from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator

# Backward-compatible exported prompt constant for tests
DEFAULT_CHAT_SYSTEM_PROMPT = load_prompt("chat.md")


class ChatMode(BaseMode):
    """Chat mode implementation.
    
    This mode uses a FunctionAgent to handle conversational interactions
    with support for tools (web search, etc.).
    """
    
    def __init__(
        self,
        llm: LLM,
        memory: Optional[BaseMemory] = None,
        es_index_name: str = "medimind_docs",
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
        return build_tool_registry(es_index_name=self._es_index_name)
    
    async def _initialize(self) -> None:
        """Initialize the agent."""
        # 1. Get tools
        tools = self._build_tools()
        
        # 2. Get system prompt
        system_prompt = self._config.system_prompt or load_prompt("chat.md")
        
        # 3. Create FunctionAgentRunner (no forced tool)
        self._runner = FunctionAgentRunner(
            llm=self._llm,
            tools=tools,
            system_prompt=system_prompt,
            verbose=self._config.verbose,
        )
        print(f"[ChatMode] Initialized with {len(tools)} tool(s).")
        
        self._initialized = True
    
    async def _process(self, message: str) -> str:
        """Process message using FunctionAgentRunner.
        
        Args:
            message: User message
            
        Returns:
            Agent response
        """
        # Get chat history for context
        chat_history = []
        if self._memory is not None:
            chat_history = self._memory.get_all()
        
        # Run agent through runner (SRP: runner handles LlamaIndex API)
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
        self._last_sources = self._collect_sources(message)
        return response
    
    @property
    def tools(self) -> List[BaseTool]:
        """Get the list of available tools."""
        if self._runner and hasattr(self._runner.agent, 'tools'):
            return self._runner.agent.tools
        return []

    async def _stream(self, message: str) -> AsyncGenerator[str, None]:
        """Stream response directly from LLM.

        This bypasses the FunctionAgent to provide true token-by-token streaming.
        Tool calling is not supported in streaming mode; use _process() for that.

        Args:
            message: User message

        Yields:
            Response text chunks
        """
        # Build messages list with history
        messages: List[ChatMessage] = []

        # Add system prompt
        system_prompt = self._config.system_prompt or ""
        if system_prompt:
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=system_prompt))

        # Add chat history
        if self._memory is not None:
            history = self._memory.get_all()
            messages.extend(history)

        # Add current user message
        messages.append(ChatMessage(role=MessageRole.USER, content=message))

        # Collect sources before streaming (non-blocking retrieval)
        self._last_sources = self._collect_sources(message)

        # Stream response from LLM
        full_response = ""
        try:
            # Use astream_chat for true streaming
            stream_response = await self._llm.astream_chat(messages)
            async for chunk in stream_response:
                # Extract delta content from chunk
                delta = getattr(chunk, "delta", None)
                if delta:
                    full_response += delta
                    yield delta
                else:
                    # Fallback: try message.content for final chunk
                    content = ""
                    if hasattr(chunk, "message"):
                        content = getattr(chunk.message, "content", "") or ""
                    elif hasattr(chunk, "content"):
                        content = chunk.content or ""
                    if content and content != full_response:
                        # Only yield new content
                        new_content = content[len(full_response):]
                        if new_content:
                            full_response = content
                            yield new_content
        except Exception as exc:
            raise
            return

        # Store in memory
        if self._memory is not None and full_response:
            self._memory.put(ChatMessage(role=MessageRole.USER, content=message))
            self._memory.put(ChatMessage(role=MessageRole.ASSISTANT, content=full_response))

    def _collect_sources(self, message: str) -> List[dict]:
        """Optionally collect RAG sources for citation."""
        if not self._vector_index or not self.allowed_doc_ids:
            return []
        try:
            filters = MetadataFilters(
                filters=[
                    MetadataFilter(
                        key="document_id",
                        value=self.allowed_doc_ids,
                        operator=FilterOperator.IN,
                    )
                ]
            )
            retriever = self._vector_index.as_retriever(
                similarity_top_k=3,
                filters=filters,
            )
            results = retriever.retrieve(message)
        except Exception:
            return []
        sources = []
        for node in results:
            meta = getattr(node.node, "metadata", {}) if hasattr(node, "node") else {}
            sources.append(
                {
                    "document_id": meta.get("document_id"),
                    "chunk_id": getattr(node.node, "node_id", ""),
                    "text": node.node.get_content() if hasattr(node, "node") else "",
                    "score": getattr(node, "score", 0.0),
                    "title": meta.get("title", meta.get("file_name", "")),
                }
            )
        return sources


