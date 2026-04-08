"""
Newbee Notebook - Chat Router

Handles chat-related API endpoints including streaming responses.
"""

import asyncio
import json
from contextlib import suppress
from typing import Optional, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from newbee_notebook.api.dependencies import get_session_service, get_chat_service
from newbee_notebook.api.models.confirm_models import ConfirmActionRequest
from newbee_notebook.api.models.requests import ChatRequest
from newbee_notebook.application.services.session_service import (
    SessionLimitExceededError,
    SessionService,
    SessionNotFoundError,
)
from newbee_notebook.application.services.chat_service import ChatService
from newbee_notebook.domain.value_objects.mode_type import ModeType
from newbee_notebook.exceptions import DocumentProcessingError


router = APIRouter(prefix="/chat")
SSE_HEARTBEAT_INTERVAL_SECONDS = 10


def _session_limit_detail(exc: SessionLimitExceededError) -> dict:
    return {
        "error_code": "E3001",
        "message": str(exc),
        "details": {
            "current_count": exc.current_count,
            "max_count": exc.max_count,
            "suggestions": [
                "Delete unused sessions",
                "Create a new notebook",
            ],
        },
    }


class ChatResponse(BaseModel):
    """Response model for non-streaming chat."""
    session_id: str
    message_id: int
    content: str
    mode: str
    sources: list = Field(default_factory=list)
    images: list = Field(default_factory=list)
    warnings: list = Field(default_factory=list)


class ConfirmActionResponse(BaseModel):
    status: str


# =============================================================================
# SSE Event Types
# =============================================================================

class SSEEvent:
    """Server-Sent Event formatter."""
    
    @staticmethod
    def format(event_type: str, data: dict) -> str:
        """Format data as SSE event."""
        return f"data: {json.dumps({'type': event_type, **data}, ensure_ascii=False)}\n\n"
    
    @staticmethod
    def start(message_id: int) -> str:
        return SSEEvent.format("start", {"message_id": message_id})
    
    @staticmethod
    def content(delta: str) -> str:
        return SSEEvent.format("content", {"delta": delta})

    @staticmethod
    def thinking(stage: str = "thinking") -> str:
        return SSEEvent.format("thinking", {"stage": stage})

    @staticmethod
    def phase(stage: str) -> str:
        return SSEEvent.format("phase", {"stage": stage})

    @staticmethod
    def warning(code: str, message: str, details: Optional[dict] = None) -> str:
        payload = {"code": code, "message": message}
        if details:
            payload["details"] = details
        return SSEEvent.format("warning", payload)
    
    @staticmethod
    def sources(sources: list, sources_type: Optional[str] = None) -> str:
        payload = {"sources": sources}
        if sources_type:
            payload["sources_type"] = sources_type
        return SSEEvent.format("sources", payload)
    
    @staticmethod
    def done() -> str:
        return SSEEvent.format("done", {})
    
    @staticmethod
    def error(code: str, message: str) -> str:
        return SSEEvent.format("error", {"error_code": code, "message": message})
    
    @staticmethod
    def heartbeat() -> str:
        return SSEEvent.format("heartbeat", {})


# =============================================================================
# Streaming Generator
# =============================================================================

async def chat_stream_generator(
    session_id: str,
    message: str,
    mode: str,
) -> AsyncGenerator[str, None]:
    """
    Generate streaming chat response.
    
    This is a placeholder implementation that simulates streaming.
    The production path uses the batch-2 runtime session orchestrator.
    
    Args:
        session_id: Session ID.
        message: User message.
        mode: Chat mode.
        
    Yields:
        SSE-formatted events.
    """
    message_id = 1  # Placeholder
    
    # Send start event
    yield SSEEvent.start(message_id)
    
    # Simulate streaming response
    # TODO: Replace with actual LLM streaming
    response_text = f"This is a placeholder response to: {message}"
    
    # Stream response in chunks
    words = response_text.split()
    for i, word in enumerate(words):
        yield SSEEvent.content(word + " ")
        await asyncio.sleep(0.05)  # Simulate streaming delay
    
    # Send sources (placeholder)
    yield SSEEvent.sources([])
    
    # Send done event
    yield SSEEvent.done()


async def heartbeat_generator(
    stream: AsyncGenerator[str, None],
    heartbeat_interval: int = 15,
) -> AsyncGenerator[str, None]:
    """
    Wrap a stream generator with heartbeat events.
    
    Args:
        stream: Original stream generator.
        heartbeat_interval: Seconds between heartbeats.
        
    Yields:
        Events from original stream, with heartbeats interspersed.
    """
    stream_iter = stream.__aiter__()
    next_event_task: Optional[asyncio.Task] = None

    try:
        next_event_task = asyncio.create_task(stream_iter.__anext__())

        while True:
            done, _ = await asyncio.wait(
                {next_event_task},
                timeout=heartbeat_interval,
                return_when=asyncio.FIRST_COMPLETED,
            )

            if not done:
                # Emit heartbeat while waiting for the next business event.
                # This prevents idle SSE connections from being closed by
                # proxies/load balancers during long retrieval/LLM gaps.
                yield SSEEvent.heartbeat()
                continue

            try:
                event = next_event_task.result()
            except StopAsyncIteration:
                break

            yield event
            next_event_task = asyncio.create_task(stream_iter.__anext__())
    finally:
        if next_event_task and not next_event_task.done():
            next_event_task.cancel()
            with suppress(asyncio.CancelledError, StopAsyncIteration):
                await next_event_task

        with suppress(Exception):
            await stream.aclose()


# =============================================================================
# Chat Endpoints
# =============================================================================

@router.post("/notebooks/{notebook_id}/chat", response_model=ChatResponse)
async def chat(
    notebook_id: str = Path(..., description="Notebook ID"),
    request: ChatRequest = None,
    session_service: SessionService = Depends(get_session_service),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Send a message and get a complete response (non-streaming).
    
    Args:
        notebook_id: Notebook unique identifier.
        request: Chat request with message and optional mode.
        
    Returns:
        Complete chat response.
    """
    # Validate or create session
    if request.session_id:
        try:
            await session_service.get_or_raise(request.session_id)
        except SessionNotFoundError:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        # Create a new session
        try:
            session = await session_service.create(notebook_id)
            request.session_id = session.session_id
        except SessionLimitExceededError as exc:
            raise HTTPException(status_code=400, detail=_session_limit_detail(exc))
    
    try:
        result = await chat_service.chat(
            session_id=request.session_id,
            message=request.message,
            mode=request.mode,
            context=request.context.model_dump() if request.context else None,
            include_ec_context=request.include_ec_context,
            source_document_ids=request.source_document_ids,
            lang=request.lang,
        )
    except DocumentProcessingError as e:
        raise HTTPException(status_code=e.http_status, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        # Surface upstream OpenAI-compatible API status errors (e.g. 429) as
        # explicit HTTP responses instead of generic 500s.
        module_name = e.__class__.__module__
        status_code = getattr(e, "status_code", None)
        if module_name.startswith("openai") and isinstance(status_code, int):
            raise HTTPException(status_code=status_code, detail=str(e))
        raise

    return ChatResponse(
        session_id=result.session_id,
        message_id=result.message_id,
        content=result.content,
        mode=result.mode.value,
        sources=[s.__dict__ for s in result.sources],
        images=getattr(result, "images", []),
        warnings=result.warnings,
    )


@router.post("/notebooks/{notebook_id}/chat/stream")
async def chat_stream(
    notebook_id: str = Path(..., description="Notebook ID"),
    request: ChatRequest = None,
    session_service: SessionService = Depends(get_session_service),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Send a message and get a streaming response (SSE).
    
    Args:
        notebook_id: Notebook unique identifier.
        request: Chat request with message and optional mode.
        
    Returns:
        Server-Sent Events stream.
    """
    # Validate or create session
    if request.session_id:
        try:
            await session_service.get_or_raise(request.session_id)
        except SessionNotFoundError:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        try:
            session = await session_service.create(notebook_id)
            request.session_id = session.session_id
        except SessionLimitExceededError as exc:
            raise HTTPException(status_code=400, detail=_session_limit_detail(exc))

    try:
        # Pre-validate to fail fast for conclude/explain
        await chat_service.prevalidate_mode_requirements(
            session_id=request.session_id,
            mode=request.mode,
            context=request.context.model_dump() if request.context else None,
        )
    except DocumentProcessingError as e:
        raise HTTPException(status_code=e.http_status, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Create streaming response
    business_stream = chat_service.chat_stream(
        session_id=request.session_id,
        message=request.message,
        mode=request.mode,
        context=request.context.model_dump() if request.context else None,
        include_ec_context=request.include_ec_context,
        source_document_ids=request.source_document_ids,
        lang=request.lang,
    )
    stream = sse_adapter(business_stream)
    
    # Add heartbeat
    stream_with_heartbeat = heartbeat_generator(
        stream,
        heartbeat_interval=SSE_HEARTBEAT_INTERVAL_SECONDS,
    )
    
    return StreamingResponse(
        stream_with_heartbeat,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/stream/{message_id}/cancel")
async def cancel_stream(
    message_id: int = Path(..., description="Message ID to cancel"),
):
    """
    Cancel an ongoing stream.
    
    Args:
        message_id: Message ID to cancel.
        
    Returns:
        Cancellation confirmation.
    """
    # TODO: Implement stream cancellation
    return {
        "message_id": message_id,
        "status": "cancelled",
    }


@router.post("/{session_id}/confirm", response_model=ConfirmActionResponse)
async def confirm_action(
    session_id: str,
    request: ConfirmActionRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    try:
        resolved = await chat_service.confirm_action(
            session_id=session_id,
            request_id=request.request_id,
            approved=request.approved,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if not resolved:
        raise HTTPException(status_code=404, detail="Confirmation request not found")
    return ConfirmActionResponse(status="resolved")


# =============================================================================
# SSE Adapter to consume ChatService stream
# =============================================================================

async def sse_adapter(
    stream: AsyncGenerator[dict, None],
) -> AsyncGenerator[str, None]:
    """
    Adapt internal event dicts to SSE formatted strings.
    """
    async for event in stream:
        event_type = event.get("type")
        payload = {k: v for k, v in event.items() if k != "type"}
        if event_type == "phase":
            stage = str(payload.get("stage") or "thinking")
            yield SSEEvent.phase(stage)
            yield SSEEvent.thinking(stage)
            continue
        yield SSEEvent.format(event_type, payload)


