"""
Global error handlers for consistent API error responses.
"""

from __future__ import annotations

import logging
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse

from medimind_agent.exceptions import MediMindException

logger = logging.getLogger(__name__)


async def medimind_exception_handler(request: Request, exc: MediMindException) -> JSONResponse:
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

