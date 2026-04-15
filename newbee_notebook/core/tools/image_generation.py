"""Runtime image generation tool for ask/agent modes."""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Awaitable, Callable

import requests

from newbee_notebook.core.tools.contracts import (
    ImageResult,
    ToolCallResult,
    ToolDefinition,
)
from newbee_notebook.domain.entities.base import generate_uuid
from newbee_notebook.infrastructure.storage.base import StorageBackend

DEFAULT_ZHIPU_IMAGE_MODEL = "glm-image"
DEFAULT_QWEN_IMAGE_MODEL = "qwen-image-2.0-pro"

DEFAULT_ZHIPU_IMAGE_API_URL = "https://open.bigmodel.cn/api/paas/v4/images/generations"
DEFAULT_QWEN_IMAGE_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

DEFAULT_ZHIPU_IMAGE_SIZE = "1280x1280"
DEFAULT_QWEN_IMAGE_SIZE = "1024*1024"

DEFAULT_ZHIPU_WATERMARK_ENABLED = True
DEFAULT_QWEN_WATERMARK_ENABLED = False

DEFAULT_REQUEST_TIMEOUT_SECONDS = 90.0
IMAGE_MAX_RETRIES = 1
IMAGE_RETRY_DELAY_SECONDS = 0.5

ImageRecordSaver = Callable[..., Awaitable[object | None]]


@dataclass(frozen=True)
class ImageAPIResult:
    image_urls: list[str]
    model: str
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class ImageToolContext:
    session_id: str
    notebook_id: str
    provider: str
    api_key: str
    storage: StorageBackend
    save_record: ImageRecordSaver
    zhipu_model: str = DEFAULT_ZHIPU_IMAGE_MODEL
    qwen_model: str = DEFAULT_QWEN_IMAGE_MODEL
    zhipu_watermark_enabled: bool | None = None
    qwen_watermark_enabled: bool | None = None


class ImageHTTPStatusError(RuntimeError):
    def __init__(self, status_code: int, text: str):
        super().__init__(f"request failed: HTTP {status_code} - {text}")
        self.status_code = status_code


def _is_retryable_exception(exc: Exception) -> bool:
    if isinstance(
        exc,
        (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            TimeoutError,
        ),
    ):
        return True
    status_code = getattr(exc, "status_code", None)
    return isinstance(status_code, int) and 500 <= status_code < 600


def _parse_size_parts(value: str) -> tuple[int, int] | None:
    normalized = str(value or "").strip().lower().replace(" ", "")
    if not normalized:
        return None
    match = re.fullmatch(r"(\d{2,5})[x\*](\d{2,5})", normalized)
    if not match:
        return None
    width = int(match.group(1))
    height = int(match.group(2))
    if width <= 0 or height <= 0:
        return None
    return width, height


def _normalize_size(
    size: str | None,
    *,
    provider: str,
) -> tuple[str, int | None, int | None]:
    if provider == "qwen":
        default_size = DEFAULT_QWEN_IMAGE_SIZE
        separator = "*"
    else:
        default_size = DEFAULT_ZHIPU_IMAGE_SIZE
        separator = "x"

    parts = _parse_size_parts(size or "")
    if parts is None:
        parts = _parse_size_parts(default_size)
    assert parts is not None
    width, height = parts
    return f"{width}{separator}{height}", width, height


def _coerce_positive_int(value: object) -> int | None:
    try:
        normalized = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if normalized <= 0:
        return None
    return normalized


def _normalize_requested_dimensions(
    *,
    provider: str,
    size: str | None,
    width: object = None,
    height: object = None,
) -> tuple[str, int | None, int | None]:
    normalized_width = _coerce_positive_int(width)
    normalized_height = _coerce_positive_int(height)
    if normalized_width is not None and normalized_height is not None:
        separator = "*" if provider == "qwen" else "x"
        return (
            f"{normalized_width}{separator}{normalized_height}",
            normalized_width,
            normalized_height,
        )
    return _normalize_size(size, provider=provider)


def _resolve_zhipu_url() -> str:
    return str(
        os.getenv("ZHIPU_IMAGE_API_BASE")
        or os.getenv("ZHIPU_IMAGE_API_URL")
        or DEFAULT_ZHIPU_IMAGE_API_URL
    ).strip()


def _resolve_qwen_url() -> str:
    # Keep Beijing endpoint as default to satisfy the deployment requirement.
    raw = str(
        os.getenv("QWEN_IMAGE_API_BASE")
        or os.getenv("DASHSCOPE_IMAGE_API_BASE")
        or DEFAULT_QWEN_IMAGE_API_URL
    ).strip()
    if not raw:
        return DEFAULT_QWEN_IMAGE_API_URL
    normalized = raw.rstrip("/")
    if normalized.endswith("/generation"):
        return normalized
    if normalized.endswith("/api/v1"):
        return f"{normalized}/services/aigc/multimodal-generation/generation"
    if normalized.endswith(".aliyuncs.com"):
        return f"{normalized}/api/v1/services/aigc/multimodal-generation/generation"
    return normalized


def _parse_env_bool(value: str | None) -> bool | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _resolve_watermark_enabled(*, provider: str, override: bool | None) -> bool:
    if override is not None:
        return bool(override)
    if provider == "zhipu":
        env_value = _parse_env_bool(os.getenv("ZHIPU_IMAGE_WATERMARK_ENABLED"))
        if env_value is not None:
            return env_value
        return DEFAULT_ZHIPU_WATERMARK_ENABLED
    env_value = _parse_env_bool(os.getenv("QWEN_IMAGE_WATERMARK_ENABLED"))
    if env_value is not None:
        return env_value
    return DEFAULT_QWEN_WATERMARK_ENABLED


def _post_json(
    url: str, *, headers: dict[str, str], payload: dict, timeout: float
) -> dict:
    response = requests.post(url, json=payload, headers=headers, timeout=timeout)
    if not response.ok:
        raise ImageHTTPStatusError(response.status_code, response.text)
    return response.json()


def _download_image(url: str, timeout: float) -> bytes:
    response = requests.get(url, timeout=timeout)
    if not response.ok:
        raise RuntimeError(f"image download failed: HTTP {response.status_code}")
    return response.content


def _extract_zhipu_result(
    payload: dict, *, requested_size: tuple[int | None, int | None]
) -> ImageAPIResult:
    data = payload.get("data") or []
    urls = [
        str(item.get("url") or "").strip()
        for item in data
        if str(item.get("url") or "").strip()
    ]
    if not urls:
        raise RuntimeError("zhipu image API returned no image URL")
    return ImageAPIResult(
        image_urls=urls,
        model=str(payload.get("model") or DEFAULT_ZHIPU_IMAGE_MODEL),
        width=requested_size[0],
        height=requested_size[1],
    )


def _extract_qwen_result(payload: dict, *, fallback_model: str) -> ImageAPIResult:
    output = payload.get("output") or {}
    choices = output.get("choices") or []
    urls: list[str] = []
    for choice in choices:
        message = (choice or {}).get("message") or {}
        content = message.get("content") or []
        if isinstance(content, list):
            for item in content:
                url = str((item or {}).get("image") or "").strip()
                if url:
                    urls.append(url)

    if not urls:
        raise RuntimeError("qwen image API returned no image URL")

    usage = payload.get("usage") or {}
    width = usage.get("width")
    height = usage.get("height")
    return ImageAPIResult(
        image_urls=urls,
        model=str(payload.get("model") or fallback_model),
        width=int(width) if isinstance(width, int) else None,
        height=int(height) if isinstance(height, int) else None,
    )


async def zhipu_generate_image(
    *,
    api_key: str,
    prompt: str,
    model: str = DEFAULT_ZHIPU_IMAGE_MODEL,
    size: str | None = None,
    watermark_enabled: bool = DEFAULT_ZHIPU_WATERMARK_ENABLED,
) -> ImageAPIResult:
    normalized_size, req_width, req_height = _normalize_size(size, provider="zhipu")
    payload = {
        "model": model,
        "prompt": prompt,
        "size": normalized_size,
        "watermark_enabled": bool(watermark_enabled),
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    response_json = await asyncio.to_thread(
        _post_json,
        _resolve_zhipu_url(),
        headers=headers,
        payload=payload,
        timeout=DEFAULT_REQUEST_TIMEOUT_SECONDS,
    )
    return _extract_zhipu_result(
        response_json,
        requested_size=(req_width, req_height),
    )


async def qwen_generate_image(
    *,
    api_key: str,
    prompt: str,
    model: str = DEFAULT_QWEN_IMAGE_MODEL,
    size: str | None = None,
    watermark_enabled: bool = DEFAULT_QWEN_WATERMARK_ENABLED,
) -> ImageAPIResult:
    normalized_size, _, _ = _normalize_size(size, provider="qwen")
    payload = {
        "model": model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"text": prompt},
                    ],
                }
            ]
        },
        "parameters": {
            "n": 1,
            "size": normalized_size,
            "watermark": bool(watermark_enabled),
        },
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    response_json = await asyncio.to_thread(
        _post_json,
        _resolve_qwen_url(),
        headers=headers,
        payload=payload,
        timeout=DEFAULT_REQUEST_TIMEOUT_SECONDS,
    )
    return _extract_qwen_result(response_json, fallback_model=model)


async def _download_image_bytes(url: str) -> bytes:
    return await asyncio.to_thread(
        _download_image,
        url,
        DEFAULT_REQUEST_TIMEOUT_SECONDS,
    )


def _safe_preview(prompt: str, max_len: int = 64) -> str:
    normalized = str(prompt or "").strip()
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max_len - 3] + "..."


def _resolve_provider(provider: str) -> str:
    normalized = str(provider or "").strip().lower()
    if normalized in {"qwen", "zhipu"}:
        return normalized
    raise ValueError(f"Unsupported image provider: {provider}")


def _format_storage_key(notebook_id: str, session_id: str, image_id: str) -> str:
    return f"generated-images/{notebook_id}/{session_id}/{image_id}.png"


async def _generate_image_with_retry(
    *,
    provider: str,
    context: ImageToolContext,
    prompt: str,
    normalized_size: str,
    watermark_enabled: bool,
) -> ImageAPIResult:
    for attempt in range(IMAGE_MAX_RETRIES + 1):
        try:
            if provider == "zhipu":
                return await zhipu_generate_image(
                    api_key=context.api_key,
                    prompt=prompt,
                    model=context.zhipu_model,
                    size=normalized_size,
                    watermark_enabled=watermark_enabled,
                )
            return await qwen_generate_image(
                api_key=context.api_key,
                prompt=prompt,
                model=context.qwen_model,
                size=normalized_size,
                watermark_enabled=watermark_enabled,
            )
        except Exception as exc:
            if not _is_retryable_exception(exc) or attempt >= IMAGE_MAX_RETRIES:
                raise
            await asyncio.sleep(IMAGE_RETRY_DELAY_SECONDS)
    raise RuntimeError("unreachable image retry state")


async def _save_images(
    *,
    context: ImageToolContext,
    prompt: str,
    tool_call_id: str,
    requested_size: str | None,
    requested_width: int | None,
    requested_height: int | None,
    result: ImageAPIResult,
) -> list[ImageResult]:
    images: list[ImageResult] = []
    width = result.width if result.width is not None else requested_width
    height = result.height if result.height is not None else requested_height
    for image_url in result.image_urls:
        image_bytes = await _download_image_bytes(image_url)
        image_id = generate_uuid()
        storage_key = _format_storage_key(
            context.notebook_id, context.session_id, image_id
        )
        await context.storage.save_file(
            object_key=storage_key,
            data=BytesIO(image_bytes),
            content_type="image/png",
        )
        await context.save_record(
            image_id=image_id,
            session_id=context.session_id,
            notebook_id=context.notebook_id,
            message_id=None,
            tool_call_id=tool_call_id,
            prompt=prompt,
            provider=context.provider,
            model=result.model,
            size=requested_size,
            width=width,
            height=height,
            storage_key=storage_key,
            file_size=len(image_bytes),
        )
        images.append(
            ImageResult(
                image_id=image_id,
                storage_key=storage_key,
                prompt=prompt,
                provider=context.provider,
                model=result.model,
                width=width,
                height=height,
            )
        )
    return images


def build_image_generation_tool(context: ImageToolContext) -> ToolDefinition:
    """Build runtime image generation tool according to the active provider."""

    provider = _resolve_provider(context.provider)
    default_size, default_width, default_height = _normalize_size(
        None, provider=provider
    )

    async def _execute(payload: dict) -> ToolCallResult:
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            return ToolCallResult(content="", error="prompt is required")

        requested_size_raw = str(payload.get("size") or "").strip() or None
        normalized_size, requested_width, requested_height = (
            _normalize_requested_dimensions(
                provider=provider,
                size=requested_size_raw,
                width=payload.get("width"),
                height=payload.get("height"),
            )
        )
        tool_call_id = str(payload.get("tool_call_id") or "").strip()
        watermark_enabled = _resolve_watermark_enabled(
            provider=provider,
            override=(
                context.zhipu_watermark_enabled
                if provider == "zhipu"
                else context.qwen_watermark_enabled
            ),
        )

        try:
            api_result = await _generate_image_with_retry(
                provider=provider,
                context=context,
                prompt=prompt,
                normalized_size=normalized_size,
                watermark_enabled=watermark_enabled,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolCallResult(content="", error=f"image generation failed: {exc}")

        try:
            images = await _save_images(
                context=context,
                prompt=prompt,
                tool_call_id=tool_call_id,
                requested_size=normalized_size,
                requested_width=requested_width,
                requested_height=requested_height,
                result=api_result,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolCallResult(content="", error=f"image save failed: {exc}")

        return ToolCallResult(
            content=f"Generated {len(images)} image(s) for prompt: {_safe_preview(prompt)}",
            images=images,
            metadata={
                "provider": provider,
                "model": api_result.model,
                "image_count": len(images),
                "watermark_enabled": watermark_enabled,
            },
        )

    return ToolDefinition(
        name="image_generate",
        description=(
            "Generate one or more images from a text prompt. "
            "Use this when the user explicitly requests an illustration, diagram image, poster, or visual output. "
            f"If width/height are omitted, the default output size is {default_size}."
        ),
        parameters={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Detailed visual description of what to generate.",
                },
                "size": {
                    "type": "string",
                    "description": (
                        "Optional output resolution. Accepts 'widthxheight' or 'width*height', "
                        "for example '1024x1024' or '1280*1280'."
                    ),
                    "default": default_size,
                },
                "width": {
                    "type": "integer",
                    "description": (
                        "Optional output width in pixels. Use together with height when a specific aspect ratio is needed."
                    ),
                    "minimum": 1,
                    "default": default_width,
                },
                "height": {
                    "type": "integer",
                    "description": (
                        "Optional output height in pixels. Use together with width when a specific aspect ratio is needed."
                    ),
                    "minimum": 1,
                    "default": default_height,
                },
            },
            "required": ["prompt"],
        },
        execute=_execute,
    )
