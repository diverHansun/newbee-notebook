"""YouTube infrastructure adapters for the Video module."""

from newbee_notebook.infrastructure.youtube.client import YouTubeClient
from newbee_notebook.infrastructure.youtube.exceptions import (
    InvalidYouTubeInputError,
    InvalidYouTubeVideoIdError,
    YouTubeError,
    YouTubeNetworkError,
    YouTubeVideoUnavailableError,
)

__all__ = [
    "InvalidYouTubeInputError",
    "InvalidYouTubeVideoIdError",
    "YouTubeClient",
    "YouTubeError",
    "YouTubeNetworkError",
    "YouTubeVideoUnavailableError",
]
