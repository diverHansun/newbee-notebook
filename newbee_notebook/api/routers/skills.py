"""Configurable skill management endpoints."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException

from newbee_notebook.api.dependencies import get_app_settings_service, get_permission_gateway_dep
from newbee_notebook.application.services.app_settings_service import AppSettingsService
from newbee_notebook.core.common.project_paths import get_configs_directory
from newbee_notebook.core.permission import PermissionGateway
from newbee_notebook.core.skills.errors import SkillNotFoundError
from newbee_notebook.core.skills.lifecycle import SkillLifecycle, SkillRecord
from newbee_notebook.core.skills.registry import SkillRegistry

router = APIRouter(prefix="/skills", tags=["Skills"])


class SkillResponse(BaseModel):
    name: str
    command: str
    description: str
    enabled: bool
    kind: str
    source: str
    content_hash: str
    path: str
    scopes: list[str]
    manageable: bool
    deletable: bool
    readonly_reason: str | None = None


class SkillsListResponse(BaseModel):
    skills: list[SkillResponse]


class ToggleSkillRequest(BaseModel):
    enabled: bool


class DeleteSkillResponse(BaseModel):
    deleted: bool
    name: str


BUILTIN_SKILLS: tuple[SkillResponse, ...] = (
    SkillResponse(
        name="note",
        command="/note",
        description="Note and mark management skill",
        enabled=True,
        kind="builtin",
        source="studio",
        content_hash="",
        path="",
        scopes=["/note"],
        manageable=False,
        deletable=False,
        readonly_reason="builtin",
    ),
    SkillResponse(
        name="diagram",
        command="/diagram",
        description="Diagram generation and management skill",
        enabled=True,
        kind="builtin",
        source="studio",
        content_hash="",
        path="",
        scopes=["/diagram"],
        manageable=False,
        deletable=False,
        readonly_reason="builtin",
    ),
    SkillResponse(
        name="video",
        command="/video",
        description="Video metadata lookup and summarization skill",
        enabled=True,
        kind="builtin",
        source="studio",
        content_hash="",
        path="",
        scopes=["/video"],
        manageable=False,
        deletable=False,
        readonly_reason="builtin",
    ),
)


def _is_builtin_skill(skill_name: str) -> bool:
    normalized = str(skill_name or "").strip().lstrip("/")
    return any(skill.name == normalized for skill in BUILTIN_SKILLS)


def get_skill_lifecycle_dep(
    settings_service: AppSettingsService = Depends(get_app_settings_service),
    permission_gateway: PermissionGateway = Depends(get_permission_gateway_dep),
) -> SkillLifecycle:
    return SkillLifecycle(
        skills_root=get_configs_directory() / "skills",
        settings_service=settings_service,
        registry=SkillRegistry(),
        permission_gateway=permission_gateway,
    )


def _to_response(record: SkillRecord) -> SkillResponse:
    return SkillResponse(
        name=record.name,
        command=f"/{record.name}",
        description=record.description,
        enabled=record.enabled,
        kind="installed",
        source=record.source,
        content_hash=record.content_hash,
        path=record.path,
        scopes=[f"/{record.name}"],
        manageable=True,
        deletable=True,
        readonly_reason=None,
    )


@router.get("", response_model=SkillsListResponse)
async def list_skills(
    lifecycle: SkillLifecycle = Depends(get_skill_lifecycle_dep),
) -> SkillsListResponse:
    records = await lifecycle.list_skills()
    installed = [record for record in records if not _is_builtin_skill(record.name)]
    return SkillsListResponse(
        skills=[*BUILTIN_SKILLS, *[_to_response(record) for record in installed]]
    )


@router.post("/{skill_name}/toggle", response_model=SkillResponse)
async def toggle_skill(
    skill_name: str,
    request: ToggleSkillRequest,
    lifecycle: SkillLifecycle = Depends(get_skill_lifecycle_dep),
) -> SkillResponse:
    if _is_builtin_skill(skill_name):
        raise HTTPException(status_code=400, detail="builtin skills are read-only")
    try:
        record = await lifecycle.set_enabled(skill_name, request.enabled)
    except SkillNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_response(record)


@router.delete("/{skill_name}", response_model=DeleteSkillResponse)
async def delete_skill(
    skill_name: str,
    lifecycle: SkillLifecycle = Depends(get_skill_lifecycle_dep),
) -> DeleteSkillResponse:
    if _is_builtin_skill(skill_name):
        raise HTTPException(status_code=400, detail="builtin skills are read-only")
    try:
        await lifecycle.uninstall(skill_name)
    except SkillNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DeleteSkillResponse(deleted=True, name=skill_name)
