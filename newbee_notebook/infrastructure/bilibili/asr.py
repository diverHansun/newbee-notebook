"""Composable ASR pipeline scaffold for video transcription."""

from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable, Sequence


class AsrPipeline:
    """Audio-to-text pipeline with pluggable steps."""

    def __init__(
        self,
        *,
        audio_fetcher: Callable[[Any], Awaitable[Any] | Any] | None = None,
        segmenter: Callable[[Any], Awaitable[Sequence[Any]] | Sequence[Any]] | None = None,
        transcriber: Callable[[Any], Awaitable[str] | str] | None = None,
    ) -> None:
        self._audio_fetcher = audio_fetcher
        self._segmenter = segmenter
        self._transcriber = transcriber

    async def transcribe(self, source: Any) -> str:
        if self._audio_fetcher is None or self._segmenter is None or self._transcriber is None:
            raise RuntimeError("ASR pipeline is not fully configured")

        audio_input = await self._resolve(self._audio_fetcher(source))
        segments = await self._resolve(self._segmenter(audio_input))
        results: list[str] = []
        for segment in segments:
            results.append(await self._resolve(self._transcriber(segment)))
        return await self._merge_results(results)

    async def _merge_results(self, parts: Sequence[str]) -> str:
        return " ".join(part.strip() for part in parts if str(part or "").strip())

    async def _resolve(self, value):
        if inspect.isawaitable(value):
            return await value
        return value
