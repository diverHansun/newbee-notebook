"""Chat mode implementation using FunctionAgent.

This mode uses the FunctionAgent (Workflow-based) to handle standard
conversation with tool support.
"""

from typing import List, Optional

from llama_index.core.tools import BaseTool
from llama_index.core.memory import BaseMemory
from llama_index.core.llms import LLM, ChatMessage, MessageRole

from src.engine.modes.base import BaseMode, ModeConfig, ModeType
from src.tools.tool_registry import build_tool_registry
from src.agent import FunctionAgentRunner
from src.prompts import load_prompt


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
    ):
        """Initialize ChatMode.
        
        Args:
            llm: LLM instance
            memory: Conversation memory
            es_index_name: Elasticsearch index name (unused in this mode but kept for interface consistency)
        """
        super().__init__(llm, memory)
        self._runner: Optional[FunctionAgentRunner] = None
        self._es_index_name = es_index_name
    
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
        
        return response
    
    @property
    def tools(self) -> List[BaseTool]:
        """Get the list of available tools."""
        if self._runner and hasattr(self._runner.agent, 'tools'):
            return self._runner.agent.tools
        return []
