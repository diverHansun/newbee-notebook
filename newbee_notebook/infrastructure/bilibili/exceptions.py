"""Exceptions raised by the Bilibili infrastructure layer."""


class BiliError(RuntimeError):
    """Base error for all Bilibili integration failures."""


class InvalidBvidError(BiliError):
    """Raised when a BV identifier is missing or malformed."""


class NetworkError(BiliError):
    """Raised when the Bilibili upstream request fails."""


class AuthenticationError(BiliError):
    """Raised when a Bilibili credential is missing or expired."""


class RateLimitError(BiliError):
    """Raised when Bilibili returns a rate-limiting error."""


class NotFoundError(BiliError):
    """Raised when a Bilibili resource cannot be found."""
