"""
Global error handlers for consistent API error responses.
"""

from __future__ import annotations

import logging
import traceback

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from newbee_notebook.api.models.mark_models import MARK_ANCHOR_TEXT_MAX_LENGTH
from newbee_notebook.exceptions import NewbeeNotebookException

logger = logging.getLogger(__name__)


async def newbee_notebook_exception_handler(request: Request, exc: NewbeeNotebookException) -> JSONResponse:
    """Render known business exceptions using the standardized response schema."""
    logger.warning(
        "Business error on %s %s: %s (%s)",
        request.method,
        request.url.path,
        exc.message,
        exc.error_code,
    )
    return JSONResponse(status_code=exc.http_status, content=exc.to_dict())


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render unhandled errors in a stable shape without leaking internals."""
    logger.error(
        "Unexpected error on %s %s: %s\n%s",
        request.method,
        request.url.path,
        exc,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "E1000",
            "message": "An unexpected error occurred",
        },
    )


async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Render selected request validation failures with stable API error codes."""
    errors = exc.errors()
    is_mark_create = (
        request.method == "POST"
        and request.url.path.endswith("/marks")
        and "/documents/" in request.url.path
    )
    has_anchor_too_long_error = any(
        error.get("type") == "string_too_long"
        and tuple(error.get("loc", ())) == ("body", "anchor_text")
        for error in errors
    )

    if is_mark_create and has_anchor_too_long_error:
        return JSONResponse(
            status_code=422,
            content={
                "error_code": "E_MARK_ANCHOR_TOO_LONG",
                "message": "Selected text is too long to create a bookmark. Please select a shorter passage.",
                "details": {
                    "field": "anchor_text",
                    "max_length": MARK_ANCHOR_TEXT_MAX_LENGTH,
                },
            },
        )

    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})

