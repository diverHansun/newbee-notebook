"""Notebook export API router."""

from __future__ import annotations

from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse

from newbee_notebook.api.dependencies import get_export_service, get_notebook_service
from newbee_notebook.application.services.export_service import DEFAULT_EXPORT_TYPES, ExportService
from newbee_notebook.application.services.notebook_service import NotebookNotFoundError, NotebookService


router = APIRouter()


def parse_export_types(raw_types: Optional[str]) -> set[str]:
    if raw_types is None or not raw_types.strip():
        return set(DEFAULT_EXPORT_TYPES)

    parsed = [item.strip() for item in raw_types.split(",") if item.strip()]
    if not parsed:
        return set(DEFAULT_EXPORT_TYPES)

    invalid = sorted({item for item in parsed if item not in DEFAULT_EXPORT_TYPES})
    if invalid:
        raise HTTPException(status_code=422, detail=f"Invalid export type: {invalid[0]}")
    return set(parsed)


def _build_attachment_content_disposition(filename: str) -> str:
    ascii_filename = filename.encode("ascii", "ignore").decode("ascii").strip() or "notebook-export.zip"
    utf8_filename = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{utf8_filename}"


@router.get("/notebooks/{notebook_id}/export")
async def export_notebook(
    notebook_id: str = Path(..., min_length=1, description="Notebook ID"),
    types: Optional[str] = Query(None, description="Comma-separated export types"),
    notebook_service: NotebookService = Depends(get_notebook_service),
    export_service: ExportService = Depends(get_export_service),
):
    requested_types = parse_export_types(types)
    try:
        await notebook_service.get_or_raise(notebook_id)
        zip_buffer, filename = await export_service.export_notebook(notebook_id, requested_types)
    except NotebookNotFoundError:
        raise HTTPException(status_code=404, detail="Notebook not found")

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": _build_attachment_content_disposition(filename),
        },
    )
