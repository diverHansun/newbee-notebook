"""
Newbee Notebook - Sessions Router

Handles Session-related API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import Optional

from newbee_notebook.api.models.requests import CreateSessionRequest
from newbee_notebook.api.models.responses import (
    SessionResponse,
    SessionListResponse,
    PaginationInfo,
)
from newbee_notebook.api.dependencies import get_session_service
from newbee_notebook.application.services.session_service import (
    SessionService,
    NotebookNotFoundError,
    SessionNotFoundError,
    SessionLimitExceededError,
)


router = APIRouter()


def _to_response(session) -> SessionResponse:
    """Convert domain entity to response model."""
    return SessionResponse(
        session_id=session.session_id,
        notebook_id=session.notebook_id,
        title=session.title,
        message_count=session.message_count,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


# =============================================================================
# Sessions under Notebooks
# =============================================================================

@router.post(
    "/notebooks/{notebook_id}/sessions",
    response_model=SessionResponse,
    status_code=201,
)
async def create_session(
    notebook_id: str = Path(..., description="Notebook ID"),
    request: CreateSessionRequest = None,
    service: SessionService = Depends(get_session_service),
):
    """
    Create a new Session in a Notebook.
    
    Each Notebook can have up to 20 sessions. Returns 400 if limit reached.
    
    Args:
        notebook_id: Notebook unique identifier.
        request: Optional session title.
        
    Returns:
        Created session.
        
    Raises:
        404: Notebook not found.
        400: Session limit exceeded (max 20 per notebook).
    """
    try:
        title = request.title if request else None
        session = await service.create(notebook_id, title)
        return _to_response(session)
    except NotebookNotFoundError:
        raise HTTPException(status_code=404, detail="Notebook not found")
    except SessionLimitExceededError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "E3001",
                "message": str(e),
                "details": {
                    "current_count": e.current_count,
                    "max_count": e.max_count,
                    "suggestions": [
                        "Delete unused sessions",
                        "Create a new notebook",
                    ],
                },
            },
        )


@router.get("/notebooks/{notebook_id}/sessions", response_model=SessionListResponse)
async def list_sessions(
    notebook_id: str = Path(..., description="Notebook ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: SessionService = Depends(get_session_service),
):
    """
    List Sessions in a Notebook.
    
    Sessions are ordered by updated_at DESC (most recent first).
    
    Args:
        notebook_id: Notebook unique identifier.
        limit: Maximum number of sessions to return.
        offset: Number of sessions to skip.
        
    Returns:
        List of sessions with pagination info.
        
    Raises:
        404: Notebook not found.
    """
    try:
        sessions, total = await service.list_by_notebook(
            notebook_id, limit=limit, offset=offset
        )
        return SessionListResponse(
            data=[_to_response(s) for s in sessions],
            pagination=PaginationInfo(
                total=total,
                limit=limit,
                offset=offset,
                has_next=offset + limit < total,
                has_prev=offset > 0,
            ),
        )
    except NotebookNotFoundError:
        raise HTTPException(status_code=404, detail="Notebook not found")


@router.get("/notebooks/{notebook_id}/sessions/latest", response_model=SessionResponse)
async def get_latest_session(
    notebook_id: str = Path(..., description="Notebook ID"),
    service: SessionService = Depends(get_session_service),
):
    """
    Get the most recently updated Session in a Notebook.
    
    Useful for resuming the last conversation.
    
    Args:
        notebook_id: Notebook unique identifier.
        
    Returns:
        Latest session.
        
    Raises:
        404: Notebook not found or no sessions exist.
    """
    try:
        session = await service.get_latest(notebook_id)
        if not session:
            raise HTTPException(status_code=404, detail="No sessions found")
        return _to_response(session)
    except NotebookNotFoundError:
        raise HTTPException(status_code=404, detail="Notebook not found")


# =============================================================================
# Session direct access
# =============================================================================

@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str = Path(..., description="Session ID"),
    service: SessionService = Depends(get_session_service),
):
    """
    Get a Session by ID.
    
    Args:
        session_id: Session unique identifier.
        
    Returns:
        Session details.
        
    Raises:
        404: Session not found.
    """
    try:
        session = await service.get_or_raise(session_id)
        return _to_response(session)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str = Path(..., description="Session ID"),
    service: SessionService = Depends(get_session_service),
):
    """
    Delete a Session.
    
    This will also delete all messages and references in the session.
    
    Args:
        session_id: Session unique identifier.
        
    Raises:
        404: Session not found.
    """
    try:
        await service.delete(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")


