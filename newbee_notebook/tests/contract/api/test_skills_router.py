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
            ),
            "note": SkillRecord(
                name="note",
                description="Conflicting installed skill.",
                enabled=True,
                source="local",
                content_hash="hash-note",
                path="configs/skills/note",
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
    skills = response.json()["skills"]
    assert [item["name"] for item in skills] == ["note", "diagram", "video", "demo"]
    assert skills[0] == {
        "name": "note",
        "command": "/note",
        "description": "Note and mark management skill",
        "enabled": True,
        "kind": "builtin",
        "source": "studio",
        "content_hash": "",
        "path": "",
        "scopes": ["/note"],
        "manageable": False,
        "deletable": False,
        "readonly_reason": "builtin",
    }
    assert skills[-1] == {
        "name": "demo",
        "command": "/demo",
        "description": "Prepare a concise notebook brief.",
        "enabled": True,
        "kind": "installed",
        "source": "local",
        "content_hash": "hash123",
        "path": "configs/skills/demo",
        "scopes": ["/demo"],
        "manageable": True,
        "deletable": True,
        "readonly_reason": None,
    }


def test_toggle_skill_updates_enabled_status():
    client, _lifecycle = _build_client()

    response = client.post("/api/v1/skills/demo/toggle", json={"enabled": False})

    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert response.json()["name"] == "demo"
    assert response.json()["manageable"] is True


def test_toggle_builtin_skill_returns_readonly_error():
    client, _lifecycle = _build_client()

    response = client.post("/api/v1/skills/note/toggle", json={"enabled": False})

    assert response.status_code == 400
    assert "builtin" in response.json()["detail"]


def test_delete_skill_uninstalls_and_returns_status():
    client, lifecycle = _build_client()

    response = client.delete("/api/v1/skills/demo")

    assert response.status_code == 200
    assert response.json() == {"deleted": True, "name": "demo"}
    assert lifecycle.deleted == ["demo"]


def test_delete_builtin_skill_returns_readonly_error():
    client, lifecycle = _build_client()

    response = client.delete("/api/v1/skills/video")

    assert response.status_code == 400
    assert "builtin" in response.json()["detail"]
    assert lifecycle.deleted == []
