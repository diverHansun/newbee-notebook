"""Lifecycle management for user-installed config skills."""

from __future__ import annotations

import hashlib
import inspect
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from newbee_notebook.core.skills.config_provider import ConfigSkillProvider
from newbee_notebook.core.skills.content_hasher import ContentHasher
from newbee_notebook.core.skills.errors import (
    InvalidManifestError,
    SkillNameConflictError,
    SkillNotFoundError,
)
from newbee_notebook.core.skills.manifest_parser import ManifestParser, SkillManifestMeta
from newbee_notebook.core.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


class SettingsServiceProtocol(Protocol):
    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str) -> None: ...

    async def delete_prefix(self, prefix: str) -> None: ...


@dataclass(frozen=True)
class SkillFileInfo:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class SkillInstallPreview:
    manifest: SkillManifestMeta
    file_tree: list[SkillFileInfo] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    content_hash: str = ""
    scopes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SkillRecord:
    name: str
    description: str
    enabled: bool
    source: str
    content_hash: str
    path: str


class SkillLifecycle:
    def __init__(
        self,
        *,
        skills_root: str | Path,
        settings_service: SettingsServiceProtocol,
        registry: SkillRegistry,
        permission_gateway: object | None = None,
        manifest_parser: ManifestParser | None = None,
        content_hasher: ContentHasher | None = None,
    ) -> None:
        self._skills_root = Path(skills_root)
        self._settings = settings_service
        self._registry = registry
        self._permission_gateway = permission_gateway
        self._manifest_parser = manifest_parser or ManifestParser()
        self._content_hasher = content_hasher or ContentHasher()

    def preview_local(self, source_dir: str | Path) -> SkillInstallPreview:
        source_path = Path(source_dir)
        self._validate_source_dir(source_path)
        manifest = self._manifest_parser.parse_file(source_path / "SKILL.md")
        file_tree = self._build_file_tree(source_path)
        scripts = [
            item.path
            for item in file_tree
            if item.path == "scripts" or item.path.startswith("scripts/")
        ]
        return SkillInstallPreview(
            manifest=manifest,
            file_tree=file_tree,
            scripts=scripts,
            content_hash=self._content_hasher.calculate(source_path),
            scopes=[f"/{manifest.name}"],
        )

    async def install_from_local(self, source_dir: str | Path) -> SkillRecord:
        preview = self.preview_local(source_dir)
        target_dir = self._skills_root / preview.manifest.name
        self._skills_root.mkdir(parents=True, exist_ok=True)
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(Path(source_dir), target_dir, symlinks=False)

        await self._settings.set(f"skills.{preview.manifest.name}.enabled", "true")
        await self._settings.set(f"skills.{preview.manifest.name}.source", "local")
        await self._settings.set(
            f"skills.{preview.manifest.name}.content_hash",
            preview.content_hash,
        )
        record = SkillRecord(
            name=preview.manifest.name,
            description=preview.manifest.description,
            enabled=True,
            source="local",
            content_hash=preview.content_hash,
            path=str(target_dir),
        )
        self._register_record(record)
        return record

    async def set_enabled(self, skill_name: str, enabled: bool) -> SkillRecord:
        record = await self._load_record(skill_name)
        await self._settings.set(
            f"skills.{record.name}.enabled",
            "true" if enabled else "false",
        )
        updated = SkillRecord(
            name=record.name,
            description=record.description,
            enabled=enabled,
            source=record.source,
            content_hash=record.content_hash,
            path=record.path,
        )
        self._register_record(updated)
        return updated

    async def uninstall(self, skill_name: str) -> None:
        record = await self._load_record(skill_name)
        target_dir = Path(record.path)
        if target_dir.exists():
            shutil.rmtree(target_dir)
        await self._settings.delete_prefix(f"skills.{record.name}.")
        self._registry.unregister(record.name)
        clear = getattr(self._permission_gateway, "clear_skill_permissions", None)
        if callable(clear):
            result = clear(record.name)
            if inspect.isawaitable(result):
                await result

    async def list_skills(self) -> list[SkillRecord]:
        if not self._skills_root.exists():
            return []
        records: list[SkillRecord] = []
        for skill_dir in sorted(path for path in self._skills_root.iterdir() if path.is_dir()):
            try:
                records.append(await self._load_record(skill_dir.name))
            except (InvalidManifestError, SkillNotFoundError):
                continue
        return records

    async def _load_record(self, skill_name: str) -> SkillRecord:
        normalized = str(skill_name or "").strip()
        target_dir = self._skills_root / normalized
        skill_file = target_dir / "SKILL.md"
        if not skill_file.exists():
            raise SkillNotFoundError(f"skill not found: {normalized}")
        manifest = self._manifest_parser.parse_file(skill_file)
        enabled = (await self._settings.get(f"skills.{manifest.name}.enabled")) != "false"
        source = await self._settings.get(f"skills.{manifest.name}.source") or "local"
        content_hash = await self._settings.get(f"skills.{manifest.name}.content_hash")
        if not content_hash:
            content_hash = self._content_hasher.calculate(target_dir)
        return SkillRecord(
            name=manifest.name,
            description=manifest.description,
            enabled=enabled,
            source=source,
            content_hash=content_hash,
            path=str(target_dir),
        )

    def _register_record(self, record: SkillRecord) -> None:
        self._registry.unregister(record.name)
        self._registry.register(
            ConfigSkillProvider(
                meta=SkillManifestMeta(
                    name=record.name,
                    description=record.description,
                ),
                skill_dir=record.path,
                content_hash=record.content_hash,
                enabled=record.enabled,
            )
        )

    @staticmethod
    def _validate_source_dir(source_dir: Path) -> None:
        if not source_dir.is_dir():
            raise SkillNotFoundError(f"skill source directory not found: {source_dir}")
        if not (source_dir / "SKILL.md").is_file():
            raise InvalidManifestError("SKILL.md is required")
        for path in [source_dir, *source_dir.rglob("*")]:
            if path.is_symlink():
                raise InvalidManifestError("symlinks are not allowed in skill sources")

    @staticmethod
    def _build_file_tree(root: Path) -> list[SkillFileInfo]:
        items: list[SkillFileInfo] = []
        for file_path in sorted(path for path in root.rglob("*") if path.is_file()):
            rel_path = file_path.relative_to(root).as_posix()
            items.append(
                SkillFileInfo(
                    path=rel_path,
                    size=file_path.stat().st_size,
                    sha256=hashlib.sha256(file_path.read_bytes()).hexdigest(),
                )
            )
        return items


async def register_installed_config_skills(
    *,
    skills_root: str | Path,
    settings_service: SettingsServiceProtocol,
    registry: SkillRegistry,
) -> SkillRegistry:
    lifecycle = SkillLifecycle(
        skills_root=skills_root,
        settings_service=settings_service,
        registry=registry,
    )
    for record in await lifecycle.list_skills():
        try:
            registry.register(
                ConfigSkillProvider(
                    meta=SkillManifestMeta(
                        name=record.name,
                        description=record.description,
                    ),
                    skill_dir=record.path,
                    content_hash=record.content_hash,
                    enabled=record.enabled,
                )
            )
        except SkillNameConflictError as exc:
            logger.warning("Skipping config skill '%s': %s", record.name, exc)
    return registry
