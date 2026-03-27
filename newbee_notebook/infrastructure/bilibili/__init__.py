"""Bilibili infrastructure adapters for the Video module."""

from newbee_notebook.infrastructure.bilibili.auth import BilibiliAuthManager
from newbee_notebook.infrastructure.bilibili.asr import AsrPipeline
from newbee_notebook.infrastructure.bilibili.client import BilibiliClient, extract_bvid
from newbee_notebook.infrastructure.bilibili.exceptions import (
    AuthenticationError,
    BiliError,
    InvalidBvidError,
    NetworkError,
    NotFoundError,
    RateLimitError,
)

__all__ = [
    "AuthenticationError",
    "AsrPipeline",
    "BiliError",
    "BilibiliClient",
    "BilibiliAuthManager",
    "extract_bvid",
    "InvalidBvidError",
    "NetworkError",
    "NotFoundError",
    "RateLimitError",
]
