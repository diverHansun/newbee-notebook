"""Qwen ASR adapter using DashScope's OpenAI-compatible endpoint."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import Any

import aiohttp

from newbee_notebook.infrastructure.asr.exceptions import AsrTranscriptionError

_DEFAULT_QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_QWEN_ASR_MAX_DATA_URI_BYTES = 10 * 1024 * 1024


class QwenTranscriber:
    """Segment transcriber backed by Qwen's OpenAI-compatible ASR endpoint."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "qwen3-asr-flash",
        base_url: str = _DEFAULT_QWEN_BASE_URL,
        max_concurrency: int = 3,
        enable_itn: bool = False,
        language: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._enable_itn = enable_itn
        self._language = language
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
            timeout = aiohttp.ClientTimeout(total=180)
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
            payload = self._build_payload(path)

            last_error: str | None = None
            for attempt in range(3):
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(self._endpoint, json=payload, headers=headers) as response:
                        if response.status == 200:
                            body = await response.json()
                            return self._extract_text(body)
                        last_error = f"HTTP {response.status} - {await response.text()}"
                if attempt < 2:
                    await asyncio.sleep(2**attempt)

            raise AsrTranscriptionError(f"Qwen ASR request failed: {last_error}")

    @property
    def _endpoint(self) -> str:
        return f"{self._base_url}/chat/completions"

    def _build_payload(self, path: str) -> dict[str, Any]:
        data_uri = self._audio_to_data_uri(path)
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": data_uri,
                            },
                        }
                    ],
                }
            ],
            "stream": False,
            "asr_options": {
                "enable_itn": self._enable_itn,
            },
        }
        if self._language:
            payload["asr_options"]["language"] = self._language
        return payload

    def _audio_to_data_uri(self, path: str) -> str:
        encoded = base64.b64encode(Path(path).read_bytes()).decode("ascii")
        data_uri = f"data:audio/wav;base64,{encoded}"
        if len(data_uri.encode("utf-8")) > _QWEN_ASR_MAX_DATA_URI_BYTES:
            raise AsrTranscriptionError(
                "Qwen ASR segment exceeds the 10MB input limit after base64 encoding"
            )
        return data_uri

    def _extract_text(self, payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AsrTranscriptionError("Qwen ASR response did not include choices")

        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None

        if isinstance(content, str):
            text = content.strip()
            if text:
                return text

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"].strip())
                elif isinstance(item, str):
                    parts.append(item.strip())
            text = " ".join(part for part in parts if part)
            if text:
                return text

        raise AsrTranscriptionError("Qwen ASR response did not include transcript text")
