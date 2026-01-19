"""
MediMind Agent - Notebooks Router

Handles Notebook-related API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import Optional

from medimind_agent.api.models.requests import (
    CreateNotebookRequest,
    UpdateNotebookRequest,
    CreateReferenceRequest,
)
from medimind_agent.api.models.responses import (
    NotebookResponse,
    NotebookListResponse,
    PaginationInfo,
    NotebookDocumentRefResponse,
)
from medimind_agent.api.dependencies import get_notebook_service
from medimind_agent.application.services.notebook_service import (
    NotebookService,
    NotebookNotFoundError,
    DocumentNotFoundError,
    DuplicateReferenceError,
)


router = APIRouter(prefix="/notebooks")


def _to_response(notebook) -> NotebookResponse:
    """Convert domain entity to response model."""
    return NotebookResponse(
        notebook_id=notebook.notebook_id,
        title=notebook.title,
        description=notebook.description,
        session_count=notebook.session_count,
        document_count=notebook.document_count,
        created_at=notebook.created_at,
        updated_at=notebook.updated_at,
    )


@router.post("", response_model=NotebookResponse, status_code=201)
async def create_notebook(
    request: CreateNotebookRequest,
    service: NotebookService = Depends(get_notebook_service),
):
    """
    Create a new Notebook.
    
    Args:
        request: Notebook creation data.
        
    Returns:
        Created notebook.
    """
    notebook = await service.create(request.title, request.description)
    return _to_response(notebook)


@router.get("", response_model=NotebookListResponse)
async def list_notebooks(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: NotebookService = Depends(get_notebook_service),
):
    """
    List all Notebooks.
    
    Returns:
        List of notebooks with pagination info.
    """
    notebooks, total = await service.list(limit=limit, offset=offset)
    
    return NotebookListResponse(
        data=[_to_response(n) for n in notebooks],
        pagination=PaginationInfo(
            total=total,
            limit=limit,
            offset=offset,
            has_next=offset + limit < total,
            has_prev=offset > 0,
        ),
    )


@router.get("/{notebook_id}", response_model=NotebookResponse)
async def get_notebook(
    notebook_id: str = Path(..., description="Notebook ID"),
    service: NotebookService = Depends(get_notebook_service),
):
    """
    Get a Notebook by ID.
    
    Args:
        notebook_id: Notebook unique identifier.
        
    Returns:
        Notebook details.
        
    Raises:
        404: Notebook not found.
    """
    try:
        notebook = await service.get_or_raise(notebook_id)
        return _to_response(notebook)
    except NotebookNotFoundError:
        raise HTTPException(status_code=404, detail="Notebook not found")


@router.patch("/{notebook_id}", response_model=NotebookResponse)
async def update_notebook(
    notebook_id: str = Path(..., description="Notebook ID"),
    request: UpdateNotebookRequest = None,
    service: NotebookService = Depends(get_notebook_service),
):
    """
    Update a Notebook.
    
    Args:
        notebook_id: Notebook unique identifier.
        request: Fields to update.
        
    Returns:
        Updated notebook.
        
    Raises:
        404: Notebook not found.
    """
    try:
        notebook = await service.update(
            notebook_id,
            title=request.title if request else None,
            description=request.description if request else None,
        )
        return _to_response(notebook)
    except NotebookNotFoundError:
        raise HTTPException(status_code=404, detail="Notebook not found")


@router.delete("/{notebook_id}", status_code=204)
async def delete_notebook(
    notebook_id: str = Path(..., description="Notebook ID"),
    service: NotebookService = Depends(get_notebook_service),
):
    """
    Delete a Notebook.
    
    This will also delete:
    - All sessions in the notebook
    - All documents owned by the notebook
    - All references from this notebook
    
    Args:
        notebook_id: Notebook unique identifier.
        
    Raises:
        404: Notebook not found.
    """
    try:
        await service.delete(notebook_id)
    except NotebookNotFoundError:
        raise HTTPException(status_code=404, detail="Notebook not found")


# =============================================================================
# Document References
# =============================================================================

@router.post("/{notebook_id}/references", response_model=NotebookDocumentRefResponse, status_code=201)
async def create_reference(
    notebook_id: str = Path(..., description="Notebook ID"),
    request: CreateReferenceRequest = None,
    service: NotebookService = Depends(get_notebook_service),
):
    """
    Create a reference from a Library document to this Notebook.
    
    Args:
        notebook_id: Notebook unique identifier.
        request: Reference creation data (document_id).
        
    Returns:
        Created reference.
        
    Raises:
        404: Notebook or document not found.
        400: Document already referenced or not in Library.
    """
    try:
        ref = await service.create_reference(notebook_id, request.document_id)
        return NotebookDocumentRefResponse(
            reference_id=ref.reference_id,
            notebook_id=ref.notebook_id,
            document_id=ref.document_id,
            created_at=ref.created_at,
        )
    except NotebookNotFoundError:
        raise HTTPException(status_code=404, detail="Notebook not found")
    except DocumentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DuplicateReferenceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{notebook_id}/references")
async def list_references(
    notebook_id: str = Path(..., description="Notebook ID"),
    service: NotebookService = Depends(get_notebook_service),
):
    """
    List all document references for a Notebook.
    
    Args:
        notebook_id: Notebook unique identifier.
        
    Returns:
        List of references.
        
    Raises:
        404: Notebook not found.
    """
    try:
        refs = await service.list_references(notebook_id)
        return {
            "data": [
                {
                    "reference_id": ref.reference_id,
                    "notebook_id": ref.notebook_id,
                    "document_id": ref.document_id,
                    "created_at": ref.created_at,
                }
                for ref in refs
            ]
        }
    except NotebookNotFoundError:
        raise HTTPException(status_code=404, detail="Notebook not found")


@router.delete("/{notebook_id}/references/{reference_id}", status_code=204)
async def delete_reference(
    notebook_id: str = Path(..., description="Notebook ID"),
    reference_id: str = Path(..., description="Reference ID"),
    service: NotebookService = Depends(get_notebook_service),
):
    """
    Remove a document reference from a Notebook.
    
    This does not delete the Library document, only the reference.
    
    Args:
        notebook_id: Notebook unique identifier.
        reference_id: Reference unique identifier.
        
    Raises:
        404: Notebook or reference not found.
    """
    try:
        await service.delete_reference(notebook_id, reference_id)
    except NotebookNotFoundError:
        raise HTTPException(status_code=404, detail="Notebook not found")
    except ValueError:
        raise HTTPException(status_code=404, detail="Reference not found")


