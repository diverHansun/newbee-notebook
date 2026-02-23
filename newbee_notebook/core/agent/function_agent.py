"""FunctionAgent runner implementation.

This module provides a wrapper for LlamaIndex FunctionAgent Workflow,
adapting the new Workflow-based API to the AgentRunner interface.
"""

from typing import Optional, List, Sequence

from llama_index.core.llms import LLM, ChatMessage
from llama_index.core.tools import BaseTool
from llama_index.core.agent.workflow import FunctionAgent

from newbee_notebook.core.agent.base import AgentRunner, SupportsWorkflowAgent


class FunctionAgentRunner(AgentRunner):
    """Runner for LlamaIndex FunctionAgent Workflow.
    
    This class wraps the FunctionAgent Workflow API, providing a simple
    run() interface that hides the Workflow execution details.
    
    Attributes:
        _agent: The underlying FunctionAgent instance
    """
    
    def __init__(
        self,
        llm: LLM,
        tools: Optional[Sequence[BaseTool]] = None,
        system_prompt: Optional[str] = None,
        verbose: bool = False,
        initial_tool_choice: Optional[str] = None,
    ):
        """Initialize FunctionAgentRunner.
        
        Args:
            llm: Language model for the agent
            tools: Optional list of tools the agent can use
            system_prompt: Optional system prompt for the agent
            initial_tool_choice: Optional tool name to force on first turn
        """
        self._agent = FunctionAgent(
            llm=llm,
            tools=list(tools) if tools else [],
            system_prompt=system_prompt,
            verbose=verbose,
        )
        self._had_tool_calls = False
        self._last_tool_calls: List[str] = []
    
    async def run(
        self,
        message: str,
        chat_history: Optional[List[ChatMessage]] = None,
    ) -> str:
        """Execute the FunctionAgent Workflow.
        
        Args:
            message: User message to process
            chat_history: Optional conversation history
            
        Returns:
            Agent response as string
        """
        self._had_tool_calls = False
        self._last_tool_calls = []
        try:
            # Run the workflow and await the handler
            handler = self._agent.run(
                user_msg=message,
                chat_history=chat_history or [],
            )
            
            # Await the workflow result
            # Note: FunctionAgent workflow returns an AgentRunResult or similar, 
            # but the handler resolves to the final state.
            result = await handler
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            debug_msg = (
                "[FunctionAgentRunner] Execution failed.\n"
                f"message={message!r}\n"
                f"chat_history_len={len(chat_history) if chat_history is not None else 0}\n"
                f"error={exc}\n"
                f"traceback:\n{tb}"
            )
            print(debug_msg)
            raise
        
        # Extract response content
        # The result typically has a 'response' attribute which is a ChatResponse
        tool_calls = getattr(result, "tool_calls", None)
        if tool_calls:
            tool_names = [getattr(tc, "tool_name", "unknown") for tc in tool_calls]
            self._had_tool_calls = len(tool_names) > 0
            self._last_tool_calls = tool_names
            print(f"[FunctionAgentRunner] tools used: {', '.join(tool_names)}")

        if hasattr(result, "response"):
            resp = result.response
            content = getattr(resp, "content", None)
            if content:
                return str(content)
            # Fallback to message.content if main content is empty
            if hasattr(resp, "message") and getattr(resp.message, "content", None):
                return str(resp.message.content)
        
        # Last-resort fallback
        fallback = str(result)
        return fallback if fallback else "No response generated."
    
    @property
    def agent(self) -> SupportsWorkflowAgent:
        """Get the underlying FunctionAgent instance."""
        return self._agent

    @property
    def had_tool_calls(self) -> bool:
        return self._had_tool_calls

    @property
    def last_tool_calls(self) -> List[str]:
        return list(self._last_tool_calls)


