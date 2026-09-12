from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from autoflow.domain.profiles.models import Profile, ProfileBrowserProxy
from autoflow.domain.workflows.run_validation import PreparedWorkflow

ACTIVE_RUN_STATES = frozenset({"starting", "running", "finishing", "stopping"})


@dataclass(frozen=True)
class RunRecord:
    request_hash: str
    data: dict[str, Any]


class WorkflowRunRepository(Protocol):
    def get(self, run_id: str) -> RunRecord | None: ...
    def create(self, record: RunRecord) -> RunRecord: ...
    def active_id(self) -> str | None: ...
    def list_runs(self, workflow_id: str | None, offset: int, limit: int) -> list[RunRecord]: ...
    def append(
        self, run_id: str, event: dict[str, Any], changes: dict[str, Any]
    ) -> dict[str, Any]: ...
    def events(self, run_id: str, after_seq: int, limit: int) -> list[dict[str, Any]]: ...
    def recover_interrupted(self) -> None: ...


class WorkflowRunLauncher(Protocol):
    async def execute(
        self, run_id: str, prepared: PreparedWorkflow, profile: Profile,
        executable: Path, proxy: ProfileBrowserProxy | None, license_key: str | None,
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> dict[str, Any]: ...
    async def stop(self, run_id: str) -> None: ...
    async def shutdown(self) -> None: ...
    def busy(self) -> bool: ...
