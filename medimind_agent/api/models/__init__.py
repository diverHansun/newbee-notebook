"""
MediMind Agent - API Models Package
"""

from medimind_agent.api.models.requests import (
    CreateNotebookRequest,
    UpdateNotebookRequest,
    CreateSessionRequest,
    CreateReferenceRequest,
)
from medimind_agent.api.models.responses import (
    NotebookResponse,
    NotebookListResponse,
    SessionResponse,
    SessionListResponse,
    LibraryResponse,
    DocumentResponse,
    PaginationInfo,
    ErrorResponse,
)

__all__ = [
    # Requests
    "CreateNotebookRequest",
    "UpdateNotebookRequest",
    "CreateSessionRequest",
    "CreateReferenceRequest",
    # Responses
    "NotebookResponse",
    "NotebookListResponse",
    "SessionResponse",
    "SessionListResponse",
    "LibraryResponse",
    "DocumentResponse",
    "PaginationInfo",
    "ErrorResponse",
]


