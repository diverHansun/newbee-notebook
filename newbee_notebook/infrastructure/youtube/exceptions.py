"""YouTube-specific infrastructure errors."""

from __future__ import annotations


class YouTubeError(RuntimeError):
    """Base error for YouTube infrastructure operations."""


class InvalidYouTubeInputError(YouTubeError):
    """Raised when a value cannot be recognized as a valid YouTube input."""


class InvalidYouTubeVideoIdError(YouTubeError):
    """Raised when a parsed YouTube video id is invalid."""


class YouTubeVideoUnavailableError(YouTubeError):
    """Raised when the target video is unavailable."""


class YouTubeNetworkError(YouTubeError):
    """Raised when a YouTube network request fails."""
