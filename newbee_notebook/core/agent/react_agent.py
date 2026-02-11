"""ReActAgent runner implementation.

Wraps the LlamaIndex ReActAgent Workflow behind a simple async interface.
"""

from typing import Optional, Sequence, List

from llama_index.core.agent.workflow import ReActAgent
from llama_index.core.llms import LLM, ChatMessage
from llama_index.core.tools import BaseTool

from newbee_notebook.core.agent.base import AgentRunner, SupportsWorkflowAgent


class ReActAgentRunner(AgentRunner):
    """Runner for LlamaIndex ReActAgent Workflow."""

    def __init__(
        self,
        llm: LLM,
        tools: Optional[Sequence[BaseTool]] = None,
        system_prompt: Optional[str] = None,
        verbose: bool = False,
    ):
        self._agent = ReActAgent(
            llm=llm,
            tools=list(tools) if tools else [],
            system_prompt=system_prompt,
            verbose=verbose,
        )

    async def run(
        self,
        message: str,
        chat_history: Optional[List[ChatMessage]] = None,
        max_iterations: Optional[int] = None,
    ) -> str:
        """Execute the ReActAgent Workflow and return final content."""
        handler = self._agent.run(
            user_msg=message,
            chat_history=chat_history or [],
            max_iterations=max_iterations,
        )
        result = await handler

        # Log tool usage if available
        tool_calls = getattr(result, "tool_calls", None)
        if tool_calls:
            tool_names = [getattr(tc, "tool_name", "unknown") for tc in tool_calls]
            print(f"[ReActAgentRunner] tools used: {', '.join(tool_names)}")

        if hasattr(result, "response") and hasattr(result.response, "content"):
            return str(result.response.content or "")

        return str(result)

    @property
    def agent(self) -> SupportsWorkflowAgent:
        return self._agent


