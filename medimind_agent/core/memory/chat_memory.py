"""Chat memory management using LlamaIndex ChatSummaryMemoryBuffer.

This module provides functions to build and manage conversation memory
with automatic summarization when token limit is exceeded.
"""

import os
from typing import Optional
from llama_index.core.memory import ChatSummaryMemoryBuffer
from llama_index.core.llms import LLM
from medimind_agent.core.common.config import (
    load_yaml_config,
    get_memory_token_limit,
    get_memory_summarize_prompt,
)


# Default summarization prompt
DEFAULT_SUMMARIZE_PROMPT = (
    "Summarize the following conversation concisely, "
    "preserving key information and important context."
)


def load_memory_config(config_path: str = "configs/memory.yaml") -> dict:
    """Load memory configuration from YAML file.

    Args:
        config_path: Path to memory configuration file

    Returns:
        dict: Memory configuration dictionary

    Example:
        >>> config = load_memory_config("configs/memory.yaml")
        >>> print(config["memory"]["token_limit"])
        64000
    """
    config = load_yaml_config(config_path)
    return config.get("memory", {})


def build_chat_memory(
    llm: LLM,
    token_limit: Optional[int] = None,
    summarize_prompt: Optional[str] = None,
) -> ChatSummaryMemoryBuffer:
    """Build a chat memory buffer for multi-turn conversations.

    Uses ChatSummaryMemoryBuffer to maintain conversation history with
    automatic summarization when token limit is exceeded.

    Configuration priority:
    1. Function parameters (if provided)
    2. configs/memory.yaml (memory section)
    3. Environment variables (MEMORY_TOKEN_LIMIT, MEMORY_SUMMARIZE_PROMPT)
    4. Defaults (64000, default prompt)

    Args:
        llm: LLM instance for generating summaries
        token_limit: Maximum token count for memory buffer.
                    If None, loads from config (default from config: 64000)
        summarize_prompt: Optional custom summarization prompt.
                         If None, loads from config or uses default prompt.

    Returns:
        ChatSummaryMemoryBuffer: Configured memory buffer instance

    Raises:
        ValueError: If token_limit is less than 1000

    Example:
        >>> from medimind_agent.core.llm.zhipu import build_llm
        >>>
        >>> # Use configuration from configs/memory.yaml
        >>> llm = build_llm()
        >>> memory = build_chat_memory(llm=llm)
        >>>
        >>> # Override with custom values
        >>> memory = build_chat_memory(llm=llm, token_limit=32000)
        >>>
        >>> # With custom prompt
        >>> custom_prompt = "Summarize the medical consultation..."
        >>> memory = build_chat_memory(llm=llm, summarize_prompt=custom_prompt)
    """
    # Use provided parameters or fall back to config
    final_token_limit = token_limit if token_limit is not None else get_memory_token_limit()
    final_summarize_prompt = summarize_prompt if summarize_prompt is not None else get_memory_summarize_prompt()
    
    # Validate token limit
    if final_token_limit < 1000:
        raise ValueError(
            f"token_limit must be at least 1000, got {final_token_limit}"
        )

    # Use default prompt if still None after config check
    if final_summarize_prompt is None:
        final_summarize_prompt = DEFAULT_SUMMARIZE_PROMPT

    # Create memory buffer
    memory = ChatSummaryMemoryBuffer.from_defaults(
        llm=llm,
        token_limit=final_token_limit,
        summarize_prompt=final_summarize_prompt,
        count_initial_tokens=False,
    )

    return memory


