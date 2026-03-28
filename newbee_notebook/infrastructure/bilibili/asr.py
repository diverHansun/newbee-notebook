"""Composable ASR pipeline scaffold for video transcription."""

from __future__ import annotations

import inspect
import shutil
from pathlib import Path
from typing import Any, Awaitable, Callable, Sequence


class AsrPipeline:
    """Audio-to-text pipeline with pluggable steps."""

    def __init__(
        self,
        *,
        audio_fetcher: Callable[[Any], Awaitable[Any] | Any] | None = None,
        segmenter: Callable[[Any], Awaitable[Sequence[Any]] | Sequence[Any]] | None = None,
        transcriber: Any | None = None,
    ) -> None:
        self._audio_fetcher = audio_fetcher
        self._segmenter = segmenter
        self._transcriber = transcriber

    async def transcribe(self, source: Any) -> str:
        if self._audio_fetcher is None or self._segmenter is None or self._transcriber is None:
            raise RuntimeError("ASR pipeline is not fully configured")

        audio_input = None
        try:
            audio_input = await self._resolve(self._audio_fetcher(source))
            segments = await self._resolve(self._segmenter(audio_input))
            return await self._transcribe_segments(segments)
        finally:
            self._cleanup_workspace(audio_input)

    async def _transcribe_segments(self, segments: Sequence[Any]) -> str:
        transcriber = self._transcriber
        if hasattr(transcriber, "transcribe_segments"):
            return str(await self._resolve(transcriber.transcribe_segments(list(segments)))).strip()
        return str(await self._resolve(transcriber(segments))).strip()

    async def _merge_results(self, parts: Sequence[str]) -> str:
        return " ".join(part.strip() for part in parts if str(part or "").strip())

    async def _resolve(self, value):
        if inspect.isawaitable(value):
            return await value
        return value

    @staticmethod
    def _cleanup_workspace(audio_input: Any) -> None:
        if not isinstance(audio_input, (str, Path)):
            return
        path = Path(audio_input)
        workspace = path.parent
        if workspace.exists() and workspace.name.startswith("video-asr-"):
            shutil.rmtree(workspace, ignore_errors=True)
