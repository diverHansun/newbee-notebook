"""
MediMind Agent - FastAPI Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager


# Import routers
from medimind_agent.api.routers import library, notebooks, sessions, health, chat, documents, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    print("Starting MediMind Agent API...")
    yield
    # Shutdown
    print("Shutting down MediMind Agent API...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="MediMind Agent API",
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
    
    # Include routers
    app.include_router(health.router, prefix="/api/v1", tags=["Health"])
    app.include_router(library.router, prefix="/api/v1", tags=["Library"])
    app.include_router(notebooks.router, prefix="/api/v1", tags=["Notebooks"])
    app.include_router(sessions.router, prefix="/api/v1", tags=["Sessions"])
    app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
    app.include_router(documents.router, prefix="/api/v1", tags=["Documents"])
    app.include_router(admin.router, prefix="/api/v1", tags=["Admin"])
    
    return app


# Create the application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("medimind_agent.api.main:app", host="0.0.0.0", port=8000, reload=True)


