"""
Newbee Notebook - FastAPI Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from newbee_notebook.exceptions import NewbeeNotebookException
from newbee_notebook.api.middleware.error_handler import (
    newbee_notebook_exception_handler,
    generic_exception_handler,
)
from newbee_notebook.core.common.config_db import (
    is_model_switch_enabled,
    sync_runtime_env_from_db,
)

# Import routers
from newbee_notebook.api.routers import config
from newbee_notebook.api.routers import (
    library,
    notebooks,
    notebook_documents,
    sessions,
    health,
    chat,
    documents,
    admin,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    print("Starting Newbee Notebook API...")
    try:
        from newbee_notebook.core.common.config import get_documents_directory
        from newbee_notebook.infrastructure.persistence.database import get_database
        from newbee_notebook.infrastructure.persistence.repositories.document_repo_impl import (
            DocumentRepositoryImpl,
        )
        from newbee_notebook.scripts.detect_orphans import detect_orphan_documents

        db = await get_database()
        async with db.session() as session:
            if is_model_switch_enabled():
                await sync_runtime_env_from_db(session)

            doc_repo = DocumentRepositoryImpl(session)
            await detect_orphan_documents(
                documents_dir=get_documents_directory(),
                document_repo=doc_repo,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Orphan detection skipped due to startup error: %s", exc)
    yield
    # Shutdown
    print("Shutting down Newbee Notebook API...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Newbee Notebook API",
        description="AI-powered document analysis and conversation API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register global exception handlers.
    app.add_exception_handler(NewbeeNotebookException, newbee_notebook_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Include routers
    app.include_router(health.router, prefix="/api/v1", tags=["Health"])
    app.include_router(library.router, prefix="/api/v1", tags=["Library"])
    app.include_router(notebooks.router, prefix="/api/v1", tags=["Notebooks"])
    app.include_router(notebook_documents.router, prefix="/api/v1", tags=["Notebook Documents"])
    app.include_router(sessions.router, prefix="/api/v1", tags=["Sessions"])
    app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
    app.include_router(documents.router, prefix="/api/v1", tags=["Documents"])
    app.include_router(admin.router, prefix="/api/v1", tags=["Admin"])

    if is_model_switch_enabled():
        app.include_router(config.router, prefix="/api/v1", tags=["Config"])

    return app


# Create the application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("newbee_notebook.api.main:app", host="0.0.0.0", port=8000, reload=True)
