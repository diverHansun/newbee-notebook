"""Runtime settings endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from newbee_notebook.api.dependencies import (
    get_app_settings_service,
    get_mcp_client_manager_dep,
)
from newbee_notebook.api.models.requests import UpdateSettingRequest
from newbee_notebook.api.models.responses import (
    MCPServerStatusResponse,
    MCPServersStatusResponse,
    UpdateSettingResponse,
)
from newbee_notebook.application.services.app_settings_service import AppSettingsService


router = APIRouter(prefix="/settings", tags=["Settings"])


def _status_value(status, key: str):
    if isinstance(status, dict):
        return status.get(key)
    return getattr(status, key)


@router.get("/mcp/servers", response_model=MCPServersStatusResponse)
async def get_mcp_server_statuses(
    settings_service: AppSettingsService = Depends(get_app_settings_service),
    manager=Depends(get_mcp_client_manager_dep),
):
    statuses = await manager.get_server_statuses()
    mcp_enabled = (await settings_service.get("mcp.enabled")) == "true"
    return MCPServersStatusResponse(
        mcp_enabled=mcp_enabled,
        servers=[
            MCPServerStatusResponse(
                name=_status_value(status, "name"),
                transport=_status_value(status, "transport"),
                enabled=_status_value(status, "enabled"),
                connection_status=_status_value(status, "connection_status"),
                tool_count=_status_value(status, "tool_count"),
                error_message=_status_value(status, "error_message"),
            )
            for status in statuses
        ],
    )


@router.put("", response_model=UpdateSettingResponse)
async def update_setting(
    request: UpdateSettingRequest,
    settings_service: AppSettingsService = Depends(get_app_settings_service),
    manager=Depends(get_mcp_client_manager_dep),
):
    key = request.key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="key must not be empty")

    await settings_service.set(key, request.value)

    if key == "mcp.enabled":
        enabled = request.value == "true"
        manager.set_enabled(enabled)
        if not enabled:
            await manager.shutdown()
    elif key.startswith("mcp.servers.") and key.endswith(".enabled"):
        server_name = key[len("mcp.servers.") : -len(".enabled")]
        if server_name:
            enabled = request.value == "true"
            manager.set_server_enabled(server_name, enabled)
            if enabled and (await settings_service.get("mcp.enabled")) == "true":
                await manager.enable_server(server_name)
            else:
                await manager.disable_server(server_name)

    return UpdateSettingResponse(key=key, value=request.value)
