"""Tests for Zhipu OpenAI-compatible adapter tool_choice handling."""

from llama_index.core.tools import FunctionTool
from medimind_agent.core.llm.zhipu import ZhipuOpenAI


def dummy_tool_fn(query: str) -> str:  # pragma: no cover - trivial helper
    return f"echo:{query}"


def test_zhipu_llm_keeps_tool_choice():
    """ZhipuOpenAI should preserve tool_choice (OpenAI-compatible stack)."""
    llm = ZhipuOpenAI(model="glm-4", api_key="dummy-key")
    tool = FunctionTool.from_defaults(fn=dummy_tool_fn, name="web_search")

    chat_kwargs = llm._prepare_chat_with_tools_compat(  # type: ignore[attr-defined]
        tools=[tool],
        user_msg="浠婂ぉ澶╂皵鎬庝箞鏍凤紵",
        tool_choice="web_search",
    )

    tool_choice = chat_kwargs.get("tool_choice")
    assert tool_choice is not None
    assert tool_choice.get("function", {}).get("name") == "web_search"
    assert chat_kwargs.get("tools") is not None
    assert chat_kwargs.get("messages") is not None


