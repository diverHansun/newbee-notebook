"""
Domain-aware exceptions with stable API error semantics.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class NewbeeNotebookException(Exception):
    """Base exception for consistent API error responses."""

    error_code: str = "E1000"
    message: str = "Internal error"
    http_status: int = 500

    def __init__(self, message: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.message = message or self.__class__.message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "error_code": self.error_code,
            "message": self.message,
        }
        if self.details:
            payload["details"] = self.details
        return payload


class ValidationError(NewbeeNotebookException):
    error_code = "E1001"
    message = "Validation error"
    http_status = 400


class NotFoundError(NewbeeNotebookException):
    error_code = "E1002"
    message = "Resource not found"
    http_status = 404


class DocumentNotFoundError(NotFoundError):
    error_code = "E4000"
    message = "Document not found"


class DocumentProcessingError(NewbeeNotebookException):
    """Document is not ready for retrieval-dependent chat modes."""

    error_code = "E4001"
    message = "Document is still processing"
    http_status = 409

