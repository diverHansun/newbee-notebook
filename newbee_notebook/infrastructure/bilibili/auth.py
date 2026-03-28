"""Credential persistence helpers for Bilibili login state."""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from typing import Any

from bilibili_api.login_v2 import QrCodeLogin, QrCodeLoginEvents
from bilibili_api.utils.network import Credential
from sqlalchemy.ext.asyncio import AsyncSession

from newbee_notebook.core.common.config_db import (
    delete_bilibili_credential_async,
    get_bilibili_credential_async,
    save_bilibili_credential_async,
)


class BilibiliAuthManager:
    """Persist and load Bilibili credential payloads from app_settings."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        base_dir: str | Path,
        qr_login_factory=QrCodeLogin,
        poll_interval_seconds: float = 2.0,
    ) -> None:
        self._session = session
        self._base_dir = Path(base_dir)
        self._credential_path = self._base_dir / "bilibili" / "credential.json"
        self._qr_login_factory = qr_login_factory
        self._poll_interval_seconds = poll_interval_seconds

    @property
    def credential_path(self) -> Path:
        return self._credential_path

    async def save_credential(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = await save_bilibili_credential_async(self._session, payload)
        await self._commit_session()
        self._remove_legacy_file()
        return normalized

    async def load_credential(self) -> dict[str, Any] | None:
        payload = await get_bilibili_credential_async(self._session)
        if payload is not None:
            return payload
        return await self._migrate_legacy_file_if_needed()

    async def clear_credential(self) -> None:
        await delete_bilibili_credential_async(self._session)
        await self._commit_session()
        self._remove_legacy_file()

    async def get_credential(self) -> Credential | None:
        payload = await self.load_credential()
        if payload is None:
            return None
        return Credential(
            sessdata=payload.get("sessdata"),
            bili_jct=payload.get("bili_jct"),
            buvid3=payload.get("buvid3"),
            buvid4=payload.get("buvid4"),
            dedeuserid=payload.get("dedeuserid"),
            ac_time_value=payload.get("ac_time_value"),
        )

    async def stream_qr_login(self):
        login = self._qr_login_factory()
        try:
            await login.generate_qrcode()
            payload: dict[str, Any] = {}
            qr_url = getattr(login, "_QrCodeLogin__qr_link", None)
            if qr_url:
                payload["qr_url"] = qr_url
            try:
                picture = login.get_qrcode_picture()
                image_content = getattr(picture, "content", None)
                if isinstance(image_content, (bytes, bytearray)):
                    payload["image_base64"] = base64.b64encode(image_content).decode("ascii")
            except Exception:
                pass
            yield ("qr_generated", payload)

            last_state = None
            while True:
                state = await login.check_state()
                if state == last_state and state != QrCodeLoginEvents.DONE:
                    await asyncio.sleep(self._poll_interval_seconds)
                    continue
                last_state = state

                if state == QrCodeLoginEvents.CONF:
                    yield ("scanned", {})
                elif state == QrCodeLoginEvents.DONE:
                    await self.save_credential(login.get_credential())
                    yield ("done", {})
                    break
                elif state == QrCodeLoginEvents.TIMEOUT:
                    yield ("timeout", {})
                    break
                await asyncio.sleep(self._poll_interval_seconds)
        except Exception as exc:  # noqa: BLE001
            yield ("error", {"message": str(exc)})

    @staticmethod
    def _normalize_payload(payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            return {
                "sessdata": payload.get("sessdata", ""),
                "bili_jct": payload.get("bili_jct", ""),
                "buvid3": payload.get("buvid3", ""),
                "buvid4": payload.get("buvid4", ""),
                "dedeuserid": payload.get("dedeuserid", ""),
                "ac_time_value": payload.get("ac_time_value", ""),
            }
        return {
            "sessdata": getattr(payload, "sessdata", "") or "",
            "bili_jct": getattr(payload, "bili_jct", "") or "",
            "buvid3": getattr(payload, "buvid3", "") or "",
            "buvid4": getattr(payload, "buvid4", "") or "",
            "dedeuserid": getattr(payload, "dedeuserid", "") or "",
            "ac_time_value": getattr(payload, "ac_time_value", "") or "",
        }

    async def _migrate_legacy_file_if_needed(self) -> dict[str, Any] | None:
        if not self._credential_path.exists():
            return None

        try:
            payload = json.loads(self._credential_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

        if not isinstance(payload, dict):
            return None

        normalized = await self.save_credential(payload)
        return normalized if any(normalized.values()) else None

    async def _commit_session(self) -> None:
        commit = getattr(self._session, "commit", None)
        if callable(commit):
            await commit()

    def _remove_legacy_file(self) -> None:
        if self._credential_path.exists():
            self._credential_path.unlink()
