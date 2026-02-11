"""
Newbee Notebook - API Models Package
"""

from newbee_notebook.api.models.requests import (
    CreateNotebookRequest,
    UpdateNotebookRequest,
    CreateSessionRequest,
    CreateReferenceRequest,
    AddNotebookDocumentsRequest,
)
from newbee_notebook.api.models.responses import (
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


