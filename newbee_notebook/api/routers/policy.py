"""Agent policy preference endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from newbee_notebook.api.dependencies import (
    get_notebook_service,
    get_permission_session_cache_dep,
    get_policy_preference_service,
    get_session_service,
)
from newbee_notebook.api.models.policy_models import (
    EffectivePolicyResponse,
    PolicyPreferenceUpdateRequest,
)
from newbee_notebook.application.services.policy_preference_service import (
    PolicyPreferenceService,
)
from newbee_notebook.application.services.notebook_service import (
    NotebookNotFoundError,
    NotebookService,
)
from newbee_notebook.application.services.session_service import (
    SessionNotFoundError,
    SessionService,
)
from newbee_notebook.core.permission import SessionAllowCache

router = APIRouter(prefix="/policy")


@router.get("/notebooks/{notebook_id}/effective", response_model=EffectivePolicyResponse)
async def get_effective_policy(
    notebook_id: str = Path(...),
    session_id: str | None = Query(None),
    service: PolicyPreferenceService = Depends(get_policy_preference_service),
    notebook_service: NotebookService = Depends(get_notebook_service),
) -> EffectivePolicyResponse:
    try:
        await notebook_service.get_or_raise(notebook_id)
    except NotebookNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Notebook not found") from exc

    policy = await service.get_effective(
        notebook_id=notebook_id,
        session_id=session_id,
    )
    return EffectivePolicyResponse(**asdict(policy))


@router.put("/notebooks/{notebook_id}", response_model=EffectivePolicyResponse)
async def update_policy(
    request: PolicyPreferenceUpdateRequest,
    notebook_id: str = Path(...),
    policy_service: PolicyPreferenceService = Depends(get_policy_preference_service),
    notebook_service: NotebookService = Depends(get_notebook_service),
    session_service: SessionService = Depends(get_session_service),
    session_cache: SessionAllowCache = Depends(get_permission_session_cache_dep),
) -> EffectivePolicyResponse:
    try:
        await notebook_service.get_or_raise(notebook_id)
    except NotebookNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Notebook not found") from exc

    session_id = request.session_id
    if request.scope == "session":
        try:
            session = await session_service.get_or_raise(str(session_id))
        except SessionNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        if str(session.notebook_id) != str(notebook_id):
            raise HTTPException(
                status_code=400,
                detail="Session does not belong to notebook",
            )
        policy = await policy_service.update_session(
            notebook_id=notebook_id,
            session_id=str(session_id),
            policy=request.policy,
        )
        if request.policy == "default":
            session_cache.clear_session(str(session_id))
    else:
        policy = await policy_service.update_notebook(
            notebook_id=notebook_id,
            session_id=session_id,
            policy=request.policy,
        )
        if request.policy == "default":
            if session_id:
                session_cache.clear_session(str(session_id))
            else:
                sessions, _total = await session_service.list_by_notebook(
                    notebook_id,
                    limit=100,
                    offset=0,
                )
                for session in sessions:
                    session_cache.clear_session(str(session.session_id))
    return EffectivePolicyResponse(**asdict(policy))
