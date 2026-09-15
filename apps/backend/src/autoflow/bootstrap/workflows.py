from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from autoflow.adapters.events.workflows import (
    StudioEventJournal,
    workflow_events_router,
)
from autoflow.adapters.http.workflow_runs import (
    WorkflowRunCommands,
    workflow_run_command_router,
    workflow_runs_router,
)
from autoflow.adapters.http.workflows import workflows_router
from autoflow.application.workflows.coordinator import WorkflowRunCoordinator
from autoflow.application.workflows.documents import WorkflowDocumentService
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.runs import WorkflowRunError
from autoflow.infrastructure.database.workflow_runs import SqlAlchemyWorkflowRuns
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowDocuments
from autoflow.infrastructure.process.workflow_worker import (
    WorkflowResourceCoordinator,
    WorkflowWorkerManager,
)


class PendingWorkflowRunCommands:
    async def start(
        self, workflow_id: str, request: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        raise WorkflowRunError(
            "WORKFLOW_EXECUTION_NOT_READY", "真实运行协调器尚未完成装配", 503
        )

    async def stop(self, workflow_id: str, run_id: str) -> Mapping[str, Any]:
        raise WorkflowRunError(
            "WORKFLOW_EXECUTION_NOT_READY", "真实运行协调器尚未完成装配", 503
        )


@dataclass(slots=True)
class WorkflowServices:
    documents: WorkflowDocumentService
    runs: WorkflowRunService
    commands: WorkflowRunCommands
    events: StudioEventJournal
    workers: WorkflowWorkerManager | None = None
    artifact_root: Path | None = None

    async def shutdown(self) -> None:
        if self.workers is not None:
            await self.workers.shutdown()

    def blockers(self) -> list[str]:
        if self.workers is not None and self.workers.busy():
            return ["workflow_process_active"]
        return []


def build_workflow_services(
    session_factory: Any,
    *,
    profiles: Any | None = None,
    installed_kernels: Any | None = None,
    resolve_proxy: Any | None = None,
    read_license: Any | None = None,
    profile_guard: Any | None = None,
    kernels_root: Path | None = None,
    temp_root: Path | None = None,
    artifact_root: Path | None = None,
) -> WorkflowServices:
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(session_factory))
    run_repository = SqlAlchemyWorkflowRuns(session_factory)
    runs = WorkflowRunService(run_repository)
    events = StudioEventJournal()
    if any(
        value is None
        for value in (
            profiles,
            installed_kernels,
            resolve_proxy,
            read_license,
            profile_guard,
            kernels_root,
            temp_root,
            artifact_root,
        )
    ):
        return WorkflowServices(
            documents=documents,
            runs=runs,
            commands=PendingWorkflowRunCommands(),
            events=events,
        )
    assert profiles is not None
    assert installed_kernels is not None
    assert resolve_proxy is not None
    assert read_license is not None
    assert profile_guard is not None
    assert kernels_root is not None
    assert temp_root is not None
    assert artifact_root is not None

    holder: dict[str, WorkflowRunCoordinator] = {}

    async def on_event(event: dict[str, object]) -> None:
        await holder["coordinator"].on_worker_event(event)

    async def on_exit(run_id: str, return_code: int) -> None:
        await holder["coordinator"].on_worker_exit(run_id, return_code)

    workers = WorkflowWorkerManager(
        temp_root,
        on_event=on_event,
        on_exit=on_exit,
    )
    resources = WorkflowResourceCoordinator(profile_guard, kernels_root)
    registry = build_production_executor_registry()
    coordinator = WorkflowRunCoordinator(
        documents=documents,
        runs=runs,
        run_repository=run_repository,
        runtime=WorkflowRuntime(registry),
        profiles=profiles,
        installed_kernels=installed_kernels,
        resolve_proxy=resolve_proxy,
        read_license=read_license,
        workers=workers,
        resources=resources,
        events=events,
        artifact_root=artifact_root,
    )
    holder["coordinator"] = coordinator
    return WorkflowServices(documents, runs, coordinator, events, workers, artifact_root)


def register_workflow_routes(app: FastAPI, services: WorkflowServices) -> None:
    # Static workflow commands must be registered before the dynamic document ID.
    app.include_router(workflow_run_command_router(services.commands))
    app.include_router(workflows_router(services.documents))
    app.include_router(workflow_runs_router(services.runs, services.artifact_root))
    app.include_router(workflow_events_router(services.events))
