"""
Newbee Notebook - Chat Router

Handles chat-related API endpoints including streaming responses.
"""

import asyncio
import json
from typing import Optional, AsyncGenerator, Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from newbee_notebook.api.dependencies import get_session_service, get_chat_service
from newbee_notebook.api.models.requests import ChatContext
from newbee_notebook.application.services.session_service import SessionService, SessionNotFoundError
from newbee_notebook.application.services.chat_service import ChatService
from newbee_notebook.domain.value_objects.mode_type import ModeType


router = APIRouter(prefix="/chat")


# =============================================================================
# Request/Response Models
# =============================================================================

class ChatRequest(BaseModel):
    """Request model for chat."""
    message: str = Field(..., min_length=1, description="User message")
    mode: Literal["chat", "ask", "explain", "conclude"] = Field(
        "chat", description="Chat mode"
    )
    session_id: Optional[str] = Field(None, description="Session ID (optional)")
    context: Optional[ChatContext] = Field(None, description="Selected text context")


class ChatResponse(BaseModel):
    """Response model for non-streaming chat."""
    session_id: str
    message_id: int
    content: str
    mode: str
    sources: list = Field(default_factory=list)


# =============================================================================
# SSE Event Types
# =============================================================================

class SSEEvent:
    """Server-Sent Event formatter."""
    
    @staticmethod
    def format(event_type: str, data: dict) -> str:
        """Format data as SSE event."""
        return f"data: {json.dumps({'type': event_type, **data})}\n\n"
    
    @staticmethod
    def start(message_id: int) -> str:
        return SSEEvent.format("start", {"message_id": message_id})
    
    @staticmethod
    def content(delta: str) -> str:
        return SSEEvent.format("content", {"delta": delta})
    
    @staticmethod
    def sources(sources: list) -> str:
        return SSEEvent.format("sources", {"sources": sources})
    
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
    The actual implementation will integrate with SessionManager and ModeSelector.
    
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
    import time
    last_heartbeat = time.time()
    
    async for event in stream:
        yield event
        
        # Check if heartbeat needed
        current_time = time.time()
        if current_time - last_heartbeat >= heartbeat_interval:
            yield SSEEvent.heartbeat()
            last_heartbeat = current_time


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
        session = await session_service.create(notebook_id)
        request.session_id = session.session_id
    
    try:
        result = await chat_service.chat(
            session_id=request.session_id,
            message=request.message,
            mode=request.mode,
            context=request.context.dict() if request.context else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return ChatResponse(
        session_id=result.session_id,
        message_id=result.message_id,
        content=result.content,
        mode=result.mode.value,
        sources=[s.__dict__ for s in result.sources],
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
        session = await session_service.create(notebook_id)
        request.session_id = session.session_id

    try:
        # Pre-validate to fail fast for conclude/explain
        await chat_service.prevalidate_mode_requirements(
            session_id=request.session_id,
            mode=request.mode,
            context=request.context.dict() if request.context else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Create streaming response
    business_stream = chat_service.chat_stream(
        session_id=request.session_id,
        message=request.message,
        mode=request.mode,
        context=request.context.dict() if request.context else None,
    )
    stream = sse_adapter(business_stream)
    
    # Add heartbeat
    stream_with_heartbeat = heartbeat_generator(stream, heartbeat_interval=15)
    
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
        yield SSEEvent.format(event_type, payload)


