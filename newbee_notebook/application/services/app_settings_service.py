"""Application settings CRUD service."""

from __future__ import annotations

from datetime import datetime
from typing import Dict

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from newbee_notebook.infrastructure.persistence.models import AppSettingModel


class AppSettingsService:
    """Service for app_settings key-value overrides."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, key: str) -> str | None:
        result = await self._session.execute(
            select(AppSettingModel).where(AppSettingModel.key == key)
        )
        row = result.scalar_one_or_none()
        return row.value if row else None

    async def get_many(self, prefix: str) -> Dict[str, str]:
        result = await self._session.execute(
            select(AppSettingModel).where(AppSettingModel.key.like(f"{prefix}%"))
        )
        return {row.key: row.value for row in result.scalars()}

    async def set(self, key: str, value: str) -> None:
        now = datetime.now()
        stmt = (
            pg_insert(AppSettingModel)
            .values(key=key, value=value, updated_at=now)
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"value": value, "updated_at": now},
            )
        )
        await self._session.execute(stmt)

    async def set_many(self, settings: Dict[str, str]) -> None:
        for key, value in settings.items():
            await self.set(key, value)

    async def delete(self, key: str) -> None:
        await self._session.execute(
            delete(AppSettingModel).where(AppSettingModel.key == key)
        )

    async def delete_prefix(self, prefix: str) -> None:
        await self._session.execute(
            delete(AppSettingModel).where(AppSettingModel.key.like(f"{prefix}%"))
        )
