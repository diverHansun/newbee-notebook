"""
MediMind Agent - API Models Package
"""

from medimind_agent.api.models.requests import (
    CreateNotebookRequest,
    UpdateNotebookRequest,
    CreateSessionRequest,
    CreateReferenceRequest,
    AddNotebookDocumentsRequest,
)
from medimind_agent.api.models.responses import (
    NotebookResponse,
    NotebookListResponse,
    SessionResponse,
    SessionListResponse,
    LibraryResponse,
    DocumentResponse,
    UploadDocumentsResponse,
    NotebookDocumentsAddResponse,
    NotebookDocumentListResponse,
    PaginationInfo,
    ErrorResponse,
)

__all__ = [
    # Requests
    "CreateNotebookRequest",
    "UpdateNotebookRequest",
    "CreateSessionRequest",
    "CreateReferenceRequest",
    "AddNotebookDocumentsRequest",
    # Responses
    "NotebookResponse",
    "NotebookListResponse",
    "SessionResponse",
    "SessionListResponse",
    "LibraryResponse",
    "DocumentResponse",
    "UploadDocumentsResponse",
    "NotebookDocumentsAddResponse",
    "NotebookDocumentListResponse",
    "PaginationInfo",
    "ErrorResponse",
]


