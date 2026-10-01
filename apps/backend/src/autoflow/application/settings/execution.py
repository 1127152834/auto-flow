"""Execution-capacity setting applied in revision order (remediation M1, R1-07).

One service instance owns one asyncio.Lock. Validate, persist (in a worker thread) and apply
(on the owning loop) happen under that lock, so a reader never sees a revision that the
dispatcher has not applied yet, and two writers can never apply out of order. Updates run as
tasks owned by the service: a cancelled request or dropped client does not abandon a half
finished persist-and-apply sequence, and shutdown waits for it.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from autoflow.domain.settings.execution_capacity import (
    ExecutionCapacity,
    HardwareProfile,
    resolve_capacity,
    validate_configured,
)
from autoflow.infrastructure.database.app_settings import AppSettingConflict

KEY = "execution.maxRunningBrowsers"
APPLY_FAILED_MESSAGE = "并发设置应用失败，已暂停派发新任务，正在按已保存的值核验"
log = logging.getLogger(__name__)


class SettingsStore(Protocol):
    def get(self, key: str) -> tuple[Any | None, int]: ...
    def put(self, key: str, value: Any, expected_revision: int) -> int: ...


@dataclass(frozen=True)
class ExecutionSettingsView:
    capacity: ExecutionCapacity
    memory_pressure: bool
    hardware: HardwareProfile
    revision: int


def _stored(value: Any) -> int | None:
    candidate = value.get("maxRunningBrowsers") if isinstance(value, dict) else None
    try:
        return validate_configured(candidate)
    except ValueError:
        log.warning("Ignoring invalid stored execution capacity %r", candidate)
        return None


class ExecutionSettingsService:
    def __init__(
        self,
        store: SettingsStore,
        hardware: Callable[[], HardwareProfile],
        memory_pressure: Callable[[], bool],
    ) -> None:
        self._store = store
        self._hardware = hardware
        self._memory_pressure = memory_pressure
        self._lock = asyncio.Lock()
        self._dispatcher: Any = None
        self._worker: Any = None
        self._initialized = False
        self._unverified = False
        self._revision = 0
        self._configured: int | None = None
        self._operations: set[asyncio.Task[Any]] = set()

    def bind(self, dispatcher: Any, worker: Any) -> None:
        self._dispatcher = dispatcher
        self._worker = worker

    async def initialize(self) -> None:
        async with self._lock:
            await self._load_and_apply_locked()

    async def read(self) -> ExecutionSettingsView:
        return await self._owned(self._read())

    async def update(self, configured: int | None, expected_revision: int) -> ExecutionSettingsView:
        validate_configured(configured)
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expectedRevision must be a non-negative integer")
        return await self._owned(self._update(configured, expected_revision))

    async def shutdown(self) -> None:
        while self._operations:
            await asyncio.gather(*tuple(self._operations), return_exceptions=True)

    async def _owned(self, coroutine: Any) -> Any:
        task = asyncio.ensure_future(coroutine)
        self._operations.add(task)
        task.add_done_callback(self._operations.discard)
        task.add_done_callback(lambda done: done.cancelled() or done.exception())  # consumed by the awaiting request
        return await asyncio.shield(task)

    async def _read(self) -> ExecutionSettingsView:
        async with self._lock:
            await self._ensure_ready_locked()
            return self._view_locked()

    async def _update(self, configured: int | None, expected_revision: int) -> ExecutionSettingsView:
        async with self._lock:
            await self._ensure_ready_locked()
            revision = await asyncio.to_thread(
                self._store.put, KEY, {"maxRunningBrowsers": configured}, expected_revision
            )
            self._revision, self._configured = revision, configured
            self._apply_locked()
            return self._view_locked()

    async def _ensure_ready_locked(self) -> None:
        if not self._initialized or self._unverified:
            await self._load_and_apply_locked()

    async def _load_and_apply_locked(self) -> None:
        value, revision = await asyncio.to_thread(self._store.get, KEY)
        self._configured, self._revision = _stored(value), revision
        self._apply_locked()
        self._initialized = True

    def _apply_locked(self) -> None:
        capacity = resolve_capacity(self._configured, self._hardware())
        try:
            self._dispatcher.set_capacity(capacity.effective, capacity.live)
            self._worker.set_capacity(capacity.live)
        except Exception:
            # The value is already persisted; do not dispatch against an unknown limit.
            self._unverified = True
            try:
                self._dispatcher.pause_dispatch(APPLY_FAILED_MESSAGE)
            finally:
                log.exception("Could not apply execution capacity revision %s", self._revision)
            raise
        self._unverified = False
        self._dispatcher.pause_dispatch(None)

    def _view_locked(self) -> ExecutionSettingsView:
        hardware = self._hardware()
        return ExecutionSettingsView(
            resolve_capacity(self._configured, hardware), self._memory_pressure(), hardware, self._revision
        )


__all__ = ["AppSettingConflict", "ExecutionSettingsService", "ExecutionSettingsView"]
