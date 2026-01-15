"""Tests for OpenAI adapter tool_choice handling.

Ensures tool_choice is preserved so FunctionAgent can force first-turn tool use.
"""

from llama_index.llms.openai import OpenAI
from llama_index.core.tools import FunctionTool


def dummy_tool_fn(query: str) -> str:  # pragma: no cover - trivial helper
    return f"echo:{query}"


def test_openai_llm_keeps_tool_choice():
    """OpenAI adapter should carry tool_choice through the prepared kwargs."""
    llm = OpenAI(
        model="gpt-4o-mini",
        api_key="test-key",
        api_base="http://example.com",  # avoid real calls
    )
    tool = FunctionTool.from_defaults(fn=dummy_tool_fn, name="web_search")

    chat_kwargs = llm._prepare_chat_with_tools_compat(  # type: ignore[attr-defined]
        tools=[tool],
        user_msg="测试工具调用",
        tool_choice="web_search",
    )

    tool_choice = chat_kwargs.get("tool_choice")
    assert tool_choice is not None
    assert tool_choice.get("function", {}).get("name") == "web_search"
    assert chat_kwargs.get("tools") is not None
    assert chat_kwargs.get("messages") is not None
