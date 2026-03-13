from __future__ import annotations

import asyncio
from types import SimpleNamespace

from newbee_notebook.core.llm.client import LLMClient
from newbee_notebook.core.llm.config import LLMRuntimeConfig
from newbee_notebook.core.llm.factory import LLMClientFactory


class _FakeCompletions:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return {"ok": True, "kwargs": kwargs}


class _FakeTransport:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def _runtime_config(provider: str = "qwen", model: str = "qwen3.5-plus") -> LLMRuntimeConfig:
    return LLMRuntimeConfig(
        provider=provider,
        model=model,
        api_key=f"{provider}-key",
        base_url=f"https://{provider}.example.test/v1",
        temperature=0.35,
        max_tokens=8192,
        top_p=0.8,
    )


def test_llm_client_chat_maps_openai_compatible_parameters():
    transport = _FakeTransport()
    client = LLMClient(runtime_config=_runtime_config(), transport=transport)

    response = asyncio.run(
        client.chat(
            messages=[{"role": "user", "content": "hello"}],
            tools=[{"type": "function", "function": {"name": "knowledge_base"}}],
            tool_choice="auto",
            extra_body={"reasoning": {"effort": "medium"}},
        )
    )

    assert response["ok"] is True
    call = transport.chat.completions.calls[0]
    assert call["model"] == "qwen3.5-plus"
    assert call["messages"] == [{"role": "user", "content": "hello"}]
    assert call["tools"] == [{"type": "function", "function": {"name": "knowledge_base"}}]
    assert call["tool_choice"] == "auto"
    assert call["temperature"] == 0.35
    assert call["max_tokens"] == 8192
    assert call["top_p"] == 0.8
    assert call["extra_body"] == {"reasoning": {"effort": "medium"}}
    assert "stream" not in call


def test_llm_client_chat_stream_sets_stream_flag_and_passthrough():
    transport = _FakeTransport()
    client = LLMClient(runtime_config=_runtime_config(provider="zhipu", model="glm-4.7-flash"), transport=transport)

    response = asyncio.run(
        client.chat_stream(
            messages=[{"role": "user", "content": "hello"}],
            tool_choice="none",
        )
    )

    assert response["ok"] is True
    call = transport.chat.completions.calls[0]
    assert call["model"] == "glm-4.7-flash"
    assert call["stream"] is True
    assert call["tool_choice"] == "none"


def test_llm_client_factory_refreshes_cached_client_when_provider_or_model_changes():
    built = []

    def _builder(config: LLMRuntimeConfig):
        built.append((config.provider, config.model))
        return object()

    factory = LLMClientFactory(client_builder=_builder)

    config_a = _runtime_config(provider="qwen", model="qwen3.5-plus")
    config_b = _runtime_config(provider="zhipu", model="glm-4.7-flash")

    client_a1 = factory.get_client(config_a)
    client_a2 = factory.get_client(config_a)
    client_b = factory.get_client(config_b)

    assert client_a1 is client_a2
    assert client_b is not client_a1
    assert built == [("qwen", "qwen3.5-plus"), ("zhipu", "glm-4.7-flash")]
