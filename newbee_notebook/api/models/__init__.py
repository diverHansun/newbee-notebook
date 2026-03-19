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
from newbee_notebook.api.models.diagram_models import (
    DiagramResponse,
    DiagramListResponse,
    UpdateDiagramPositionsRequest,
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
    "DiagramResponse",
    "DiagramListResponse",
    "UpdateDiagramPositionsRequest",
]


