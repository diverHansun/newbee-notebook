"""In-process background bash task manager."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, replace
from pathlib import Path

from newbee_notebook.core.sandbox import SandboxExecutor
from newbee_notebook.core.shell.environment import ShellEnvironment
from newbee_notebook.core.shell.executor import ShellExecutor


@dataclass(frozen=True)
class BackgroundBashTaskRecord:
    task_id: str
    command: str
    description: str
    status: str
    log_path: Path
    created_at: float
    updated_at: float
    exit_code: int | None = None
    error_code: str | None = None
    timed_out: bool = False


@dataclass(frozen=True)
class BackgroundBashTaskOutput:
    task_id: str
    status: str
    log_path: Path
    content: str
    truncated: bool = False


class BackgroundBashTaskManager:
    """Manage notebook-scoped background bash tasks."""

    def __init__(
        self,
        *,
        tasks_root: Path | str,
        clock=time.time,
    ) -> None:
        self._tasks_root = Path(tasks_root).expanduser().resolve(strict=False)
        self._clock = clock
        self._records: dict[str, BackgroundBashTaskRecord] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    @property
    def tasks_root(self) -> Path:
        return self._tasks_root

    async def start(
        self,
        *,
        command: str,
        description: str,
        environment: ShellEnvironment,
        sandbox_executor: SandboxExecutor | None,
        timeout_seconds: float | None = None,
    ) -> BackgroundBashTaskRecord:
        normalized_command = str(command or "").strip()
        normalized_description = str(description or "").strip()
        if not normalized_command:
            raise ValueError("command is required")
        if not normalized_description:
            raise ValueError("description is required for background bash tasks")

        task_id = uuid.uuid4().hex
        record = self._make_record(
            task_id=task_id,
            command=normalized_command,
            description=normalized_description,
        )
        record.log_path.parent.mkdir(parents=True, exist_ok=True)
        record.log_path.write_text(
            f"Task {task_id} started\nDescription: {normalized_description}\nCommand: {normalized_command}\n\n",
            encoding="utf-8",
        )
        self._records[task_id] = record
        task = asyncio.create_task(
            self._run_task(
                task_id=task_id,
                environment=environment,
                sandbox_executor=sandbox_executor,
                timeout_seconds=timeout_seconds,
            )
        )
        self._tasks[task_id] = task
        return record

    def get(self, task_id: str) -> BackgroundBashTaskRecord:
        normalized = _normalize_task_id(task_id)
        try:
            return self._records[normalized]
        except KeyError as exc:
            raise KeyError(f"background task not found: {normalized}") from exc

    def list_tasks(self, *, limit: int = 20) -> list[BackgroundBashTaskRecord]:
        records = sorted(
            self._records.values(),
            key=lambda item: item.created_at,
            reverse=True,
        )
        return records[: max(1, int(limit))]

    def output(
        self,
        task_id: str,
        *,
        max_bytes: int = 16_000,
    ) -> BackgroundBashTaskOutput:
        record = self.get(task_id)
        data = record.log_path.read_bytes() if record.log_path.exists() else b""
        truncated = len(data) > max_bytes
        if truncated:
            data = data[-max_bytes:]
        return BackgroundBashTaskOutput(
            task_id=record.task_id,
            status=record.status,
            log_path=record.log_path,
            content=data.decode("utf-8", errors="replace"),
            truncated=truncated,
        )

    async def stop(self, task_id: str) -> BackgroundBashTaskRecord:
        record = self.get(task_id)
        task = self._tasks.get(record.task_id)
        if task is None or task.done():
            return record
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        current = self.get(record.task_id)
        if current.status in {"pending", "running"}:
            self._append_log(current, "\nTask stopped by request.\n")
            self._set_record(current, status="stopped")
        return self.get(record.task_id)

    async def wait(
        self,
        task_id: str,
        *,
        timeout_seconds: float | None = None,
    ) -> BackgroundBashTaskRecord:
        task = self._tasks.get(_normalize_task_id(task_id))
        if task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=timeout_seconds)
            except TimeoutError:
                return self.get(task_id)
        return self.get(task_id)

    def _make_record(
        self,
        *,
        task_id: str,
        command: str,
        description: str,
    ) -> BackgroundBashTaskRecord:
        now = self._clock()
        return BackgroundBashTaskRecord(
            task_id=task_id,
            command=command,
            description=description,
            status="pending",
            log_path=self._tasks_root / task_id / "output.log",
            created_at=now,
            updated_at=now,
        )

    async def _run_task(
        self,
        *,
        task_id: str,
        environment: ShellEnvironment,
        sandbox_executor: SandboxExecutor | None,
        timeout_seconds: float | None,
    ) -> None:
        record = self.get(task_id)
        self._set_record(record, status="running")
        executor = ShellExecutor(
            environment=environment,
            sandbox_executor=sandbox_executor,
        )
        try:
            result = await executor.execute_bash(
                record.command,
                timeout_seconds=timeout_seconds,
            )
        except asyncio.CancelledError:
            self._append_log(record, "\nTask stopped by request.\n")
            self._set_record(record, status="stopped")
            raise

        self._append_log(record, _format_result_log(result))
        status = "completed" if result.error_code is None and result.exit_code == 0 else "failed"
        self._set_record(
            record,
            status=status,
            exit_code=result.exit_code,
            error_code=result.error_code,
            timed_out=result.timed_out,
        )

    def _append_log(self, record: BackgroundBashTaskRecord, text: str) -> None:
        with record.log_path.open("a", encoding="utf-8", newline="") as handle:
            handle.write(text)

    def _set_record(
        self,
        record: BackgroundBashTaskRecord,
        *,
        status: str,
        exit_code: int | None = None,
        error_code: str | None = None,
        timed_out: bool = False,
    ) -> None:
        self._records[record.task_id] = replace(
            self._records[record.task_id],
            status=status,
            updated_at=self._clock(),
            exit_code=exit_code,
            error_code=error_code,
            timed_out=timed_out,
        )


def _format_result_log(result) -> str:
    lines = [f"\nExit code: {'timeout' if result.timed_out else result.exit_code}\n"]
    if result.truncated:
        lines.append("Output truncated: true\n")
    if result.stdout:
        lines.extend(["STDOUT:\n", result.stdout.rstrip(), "\n"])
    if result.stderr:
        lines.extend(["STDERR:\n", result.stderr.rstrip(), "\n"])
    if not result.stdout and not result.stderr:
        lines.append("(no output)\n")
    return "".join(lines)


def _normalize_task_id(task_id: str) -> str:
    normalized = str(task_id or "").strip()
    if not normalized:
        raise KeyError("task_id is required")
    return normalized
