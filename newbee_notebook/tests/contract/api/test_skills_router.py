from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from newbee_notebook.api.routers import skills as skills_router
from newbee_notebook.core.skills.lifecycle import SkillRecord

pytestmark = pytest.mark.contract


class _FakeSkillLifecycle:
    def __init__(self) -> None:
        self.records = {
            "demo": SkillRecord(
                name="demo",
                description="Prepare a concise notebook brief.",
                enabled=True,
                source="local",
                content_hash="hash123",
                path="configs/skills/demo",
            )
        }
        self.deleted: list[str] = []

    async def list_skills(self):
        return list(self.records.values())

    async def set_enabled(self, skill_name: str, enabled: bool):
        record = self.records[skill_name]
        updated = SkillRecord(
            name=record.name,
            description=record.description,
            enabled=enabled,
            source=record.source,
            content_hash=record.content_hash,
            path=record.path,
        )
        self.records[skill_name] = updated
        return updated

    async def uninstall(self, skill_name: str):
        self.deleted.append(skill_name)
        self.records.pop(skill_name, None)


def _build_client():
    lifecycle = _FakeSkillLifecycle()
    app = FastAPI()
    app.include_router(skills_router.router, prefix="/api/v1")
    app.dependency_overrides[skills_router.get_skill_lifecycle_dep] = lambda: lifecycle
    return TestClient(app), lifecycle


def test_get_skills_returns_list_contract():
    client, _lifecycle = _build_client()

    response = client.get("/api/v1/skills")

    assert response.status_code == 200
    assert response.json() == {
        "skills": [
            {
                "name": "demo",
                "description": "Prepare a concise notebook brief.",
                "enabled": True,
                "source": "local",
                "content_hash": "hash123",
                "path": "configs/skills/demo",
                "scopes": ["/demo"],
            }
        ]
    }


def test_toggle_skill_updates_enabled_status():
    client, _lifecycle = _build_client()

    response = client.post("/api/v1/skills/demo/toggle", json={"enabled": False})

    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert response.json()["name"] == "demo"


def test_delete_skill_uninstalls_and_returns_status():
    client, lifecycle = _build_client()

    response = client.delete("/api/v1/skills/demo")

    assert response.status_code == 200
    assert response.json() == {"deleted": True, "name": "demo"}
    assert lifecycle.deleted == ["demo"]
