"""OpenAI-compatible async runtime LLM client."""

from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from newbee_notebook.core.llm.config import LLMRuntimeConfig


class LLMClient:
    def __init__(self, runtime_config: LLMRuntimeConfig, transport: Any | None = None):
        self.runtime_config = runtime_config
        self._transport = transport or AsyncOpenAI(
            api_key=runtime_config.api_key,
            base_url=runtime_config.base_url,
        )

    def _build_params(
        self,
        *,
        messages: list,
        tools: list | None = None,
        tool_choice: Any = None,
        stream: bool | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self.runtime_config.model,
            "messages": messages,
            "temperature": self.runtime_config.temperature,
        }
        if self.runtime_config.max_tokens is not None:
            params["max_tokens"] = self.runtime_config.max_tokens
        if self.runtime_config.top_p is not None:
            params["top_p"] = self.runtime_config.top_p
        if tools is not None:
            params["tools"] = tools
        if tool_choice is not None:
            params["tool_choice"] = tool_choice
        if stream is not None:
            params["stream"] = stream
        params.update(kwargs)
        return params

    async def chat(self, *, messages: list, tools: list | None = None, tool_choice=None, **kwargs: Any):
        params = self._build_params(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            **kwargs,
        )
        return await self._transport.chat.completions.create(**params)

    async def chat_stream(self, *, messages: list, tools: list | None = None, tool_choice=None, **kwargs: Any):
        params = self._build_params(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            stream=True,
            **kwargs,
        )
        return await self._transport.chat.completions.create(**params)
