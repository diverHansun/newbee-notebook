from __future__ import annotations

import json

import pytest

from newbee_notebook.infrastructure.bilibili.auth import BilibiliAuthManager


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_auth_manager_reads_saved_credential_from_db(tmp_path, monkeypatch):
    from newbee_notebook.infrastructure.bilibili import auth as auth_module

    async def _fake_get(_session):
        return {
            "sessdata": "abc",
            "bili_jct": "def",
            "buvid3": "",
            "buvid4": "",
            "dedeuserid": "",
            "ac_time_value": "ghi",
        }

    monkeypatch.setattr(auth_module, "get_bilibili_credential_async", _fake_get)
    manager = BilibiliAuthManager(session=object(), base_dir=tmp_path)

    payload = await manager.load_credential()

    assert payload is not None
    assert payload["sessdata"] == "abc"
    assert payload["bili_jct"] == "def"
    credential = await manager.get_credential()
    assert credential is not None
    assert credential.sessdata == "abc"
    assert credential.ac_time_value == "ghi"


@pytest.mark.anyio
async def test_auth_manager_migrates_legacy_file_to_db(tmp_path, monkeypatch):
    from newbee_notebook.infrastructure.bilibili import auth as auth_module

    saved_payloads: list[dict] = []
    store: dict[str, dict] = {}
    legacy_path = tmp_path / "bilibili" / "credential.json"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text(
        json.dumps(
            {
                "sessdata": "legacy",
                "bili_jct": "csrf",
                "buvid3": "buvid3",
                "buvid4": "buvid4",
                "dedeuserid": "42",
                "ac_time_value": "token",
            }
        ),
        encoding="utf-8",
    )

    async def _fake_get(_session):
        return store.get("payload")

    async def _fake_save(_session, payload):
        normalized = dict(payload)
        store["payload"] = normalized
        saved_payloads.append(normalized)
        return normalized

    monkeypatch.setattr(auth_module, "get_bilibili_credential_async", _fake_get)
    monkeypatch.setattr(auth_module, "save_bilibili_credential_async", _fake_save)

    manager = BilibiliAuthManager(session=object(), base_dir=tmp_path)
    payload = await manager.load_credential()

    assert payload is not None
    assert payload["sessdata"] == "legacy"
    assert saved_payloads[-1]["dedeuserid"] == "42"
    assert not legacy_path.exists()
