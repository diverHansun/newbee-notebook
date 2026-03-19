"""Pydantic models for chat confirmation callbacks."""

from pydantic import BaseModel


class ConfirmActionRequest(BaseModel):
    request_id: str
    approved: bool
