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
        disable_thinking: bool = False,
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
        if disable_thinking:
            self._apply_disable_thinking(params)
        return params

    def _apply_disable_thinking(self, params: dict[str, Any]) -> None:
        provider = str(self.runtime_config.provider or "").strip().lower()
        if provider in {"qwen", "zhipu"}:
            extra_body = dict(params.get("extra_body") or {})
            if provider == "qwen":
                extra_body.setdefault("enable_thinking", False)
            else:
                extra_body.setdefault("thinking", {"type": "disabled"})
            params["extra_body"] = extra_body

    async def chat(
        self,
        *,
        messages: list,
        tools: list | None = None,
        tool_choice=None,
        disable_thinking: bool = False,
        **kwargs: Any,
    ):
        params = self._build_params(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            disable_thinking=disable_thinking,
            **kwargs,
        )
        return await self._transport.chat.completions.create(**params)

    async def chat_stream(
        self,
        *,
        messages: list,
        tools: list | None = None,
        tool_choice=None,
        disable_thinking: bool = False,
        **kwargs: Any,
    ):
        params = self._build_params(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            stream=True,
            disable_thinking=disable_thinking,
            **kwargs,
        )
        return await self._transport.chat.completions.create(**params)
