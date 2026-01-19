"""Unit tests for Memory module.

Tests for:
- build_chat_memory() function
- load_memory_config() function
- ChatSummaryMemoryBuffer integration
"""

import pytest
from pathlib import Path

from medimind_agent.core.memory import build_chat_memory, load_memory_config


class TestMemoryConfig:
    """Tests for memory configuration loading."""

    def test_load_memory_config_default(self, configs_dir):
        """Test loading default memory configuration."""
        config_path = configs_dir / "memory.yaml"
        config = load_memory_config(str(config_path))

        assert config is not None
        assert "token_limit" in config
        assert config["token_limit"] == 64000

    def test_load_memory_config_missing_file(self):
        """Test loading non-existent config file returns empty dict."""
        config = load_memory_config("non_existent_config.yaml")
        assert config == {}


class TestBuildChatMemory:
    """Tests for build_chat_memory() function."""

    @pytest.mark.requires_api
    def test_build_chat_memory_with_defaults(self):
        """Test building memory buffer with default parameters."""
        from medimind_agent.core.llm.zhipu import build_llm

        llm = build_llm()
        memory = build_chat_memory(llm=llm)

        assert memory is not None
        assert memory.token_limit == 64000

    @pytest.mark.requires_api
    def test_build_chat_memory_with_custom_token_limit(self):
        """Test building memory buffer with custom token limit."""
        from medimind_agent.core.llm.zhipu import build_llm

        llm = build_llm()
        custom_limit = 32000
        memory = build_chat_memory(llm=llm, token_limit=custom_limit)

        assert memory.token_limit == custom_limit

    @pytest.mark.requires_api
    def test_build_chat_memory_with_custom_prompt(self):
        """Test building memory buffer with custom summarize prompt."""
        from medimind_agent.core.llm.zhipu import build_llm

        llm = build_llm()
        custom_prompt = "Custom summarization prompt"
        memory = build_chat_memory(llm=llm, summarize_prompt=custom_prompt)

        assert memory.summarize_prompt == custom_prompt

    def test_build_chat_memory_invalid_token_limit(self):
        """Test that invalid token limit raises ValueError."""
        from medimind_agent.core.llm.zhipu import build_llm

        with pytest.raises(ValueError):
            llm = build_llm()
            build_chat_memory(llm=llm, token_limit=500)  # Too small


