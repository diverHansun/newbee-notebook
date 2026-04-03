"""Shared concurrency controls for video summarization."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class VideoConcurrencyController:
    """Coordinates shared admission and model concurrency for video jobs."""

    def __init__(
        self,
        *,
        max_processing_videos: int = 5,
        max_llm_concurrency: int = 2,
        max_asr_concurrency: int = 2,
    ) -> None:
        self._max_processing_videos = max_processing_videos
        self._admission_lock = asyncio.Lock()
        self._llm_semaphore = asyncio.Semaphore(max_llm_concurrency)
        self._asr_semaphore = asyncio.Semaphore(max_asr_concurrency)

    @property
    def max_processing_videos(self) -> int:
        return self._max_processing_videos

    @asynccontextmanager
    async def admission(self) -> AsyncIterator[None]:
        async with self._admission_lock:
            yield

    @asynccontextmanager
    async def llm_slot(self) -> AsyncIterator[None]:
        async with self._llm_semaphore:
            yield

    @asynccontextmanager
    async def asr_slot(self) -> AsyncIterator[None]:
        async with self._asr_semaphore:
            yield
