"""Pydantic models for chat confirmation callbacks."""

from typing import Literal

from pydantic import BaseModel, model_validator


class PermissionResolveRequest(BaseModel):
    request_id: str
    approved: bool | None = None
    response: Literal["once", "always_session", "always_persist", "reject"] | None = None
    suggestion: str | None = None

    @model_validator(mode="after")
    def _validate_choice(self) -> "PermissionResolveRequest":
        if self.approved is None and self.response is None:
            raise ValueError("Either approved or response is required")
        if self.approved is not None and self.response is not None:
            raise ValueError("Use either approved or response, not both")
        return self


ConfirmActionRequest = PermissionResolveRequest
