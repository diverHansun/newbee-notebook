"""
Newbee Notebook - Health Check Router
"""

from typing import Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy import text

from newbee_notebook.infrastructure.persistence.database import get_database, Database
from newbee_notebook.core.common.config_db import is_model_switch_enabled


router = APIRouter()


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Basic health check endpoint.
    
    Returns:
        Status indicating the service is running.
    """
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness_check(db: Database = Depends(get_database)) -> Dict[str, Any]:
    """
    Readiness check - verify all dependencies are available.
    
    Returns:
        Status and individual check results.
    """
    checks = {}
    all_ready = True
    
    # PostgreSQL
    try:
        async with db.session() as session:
            await session.execute(text("SELECT 1"))
        checks["postgresql"] = "ok"
    except Exception as exc:  # pragma: no cover - defensive
        checks["postgresql"] = f"error: {exc}"
        all_ready = False

    # Redis / Elasticsearch not wired in this phase; mark as skipped
    checks["redis"] = "skipped"
    checks["elasticsearch"] = "skipped"
    
    return {
        "status": "ready" if all_ready else "not_ready",
        "checks": checks
    }


@router.get("/health/live")
async def liveness_check() -> Dict[str, str]:
    """
    Liveness check - verify the service process is running.
    
    Returns:
        Status indicating the service is alive.
    """
    return {"status": "alive"}


@router.get("/info")
async def system_info() -> Dict[str, Any]:
    """
    Get system information.
    
    Returns:
        Version and feature information.
    """
    return {
        "name": "Newbee Notebook",
        "version": "1.0.0",
        "features": {
            "library": True,
            "notebooks": True,
            "sessions": True,
            "chat_modes": ["agent", "ask", "explain", "conclude"],
            "model_switch": is_model_switch_enabled(),
        }
    }

