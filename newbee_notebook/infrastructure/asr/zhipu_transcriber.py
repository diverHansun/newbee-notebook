"""Zhipu GLM-ASR adapter."""

from __future__ import annotations

import asyncio
from pathlib import Path

import aiohttp

from newbee_notebook.infrastructure.asr.exceptions import AsrTranscriptionError

_ZHIPU_ASR_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/audio/transcriptions"


class ZhipuTranscriber:
    """Segment transcriber backed by Zhipu's GLM-ASR endpoint."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "glm-asr-2512",
        max_concurrency: int = 5,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def transcribe_segments(self, segment_paths: list[str]) -> str:
        tasks = [
            self._transcribe_one(path, index)
            for index, path in enumerate(segment_paths)
        ]
        results = await asyncio.gather(*tasks)
        return " ".join(part.strip() for part in results if str(part or "").strip())

    async def _transcribe_one(self, path: str, index: int) -> str:
        del index
        async with self._semaphore:
            timeout = aiohttp.ClientTimeout(total=120)
            headers = {"Authorization": f"Bearer {self._api_key}"}

            form = aiohttp.FormData()
            form.add_field("model", self._model)
            with open(path, "rb") as handle:
                form.add_field(
                    "file",
                    handle,
                    filename=Path(path).name,
                    content_type="audio/wav",
                )
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(_ZHIPU_ASR_ENDPOINT, data=form, headers=headers) as response:
                        if response.status != 200:
                            raise AsrTranscriptionError(
                                f"Zhipu ASR request failed: HTTP {response.status} - {await response.text()}"
                            )
                        payload = await response.json()
            text = payload.get("text") if isinstance(payload, dict) else None
            if not isinstance(text, str):
                raise AsrTranscriptionError("Zhipu ASR response did not include transcript text")
            return text.strip()
