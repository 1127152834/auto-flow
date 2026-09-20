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
from autoflow.adapters.http.custom_modules import custom_modules_router
from autoflow.adapters.http.workflow_ai import workflow_ai_router
from autoflow.adapters.http.workflow_inspection import workflow_inspection_router
from autoflow.adapters.http.workflow_mcp import workflow_mcp_router
from autoflow.adapters.http.workflow_runs import (
    WorkflowRunCommands,
    workflow_run_command_router,
    workflow_runs_router,
)
from autoflow.adapters.http.workflows import workflows_router
from autoflow.application.workflows.assistant import WorkflowAssistantService
from autoflow.application.workflows.coordinator import WorkflowRunCoordinator
from autoflow.application.workflows.documents import WorkflowDocumentService
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.inspection import WorkflowInspectionService
from autoflow.application.workflows.mcp import WorkflowMcpService
from autoflow.application.workflows.modules import CustomModuleService
from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.runs import WorkflowRunError
from autoflow.infrastructure.database.workflow_assistant import (
    SqlAlchemyWorkflowAssistant,
)
from autoflow.infrastructure.database.workflow_modules import SqlAlchemyWorkflowModules
from autoflow.infrastructure.database.workflow_mcp import SqlAlchemyWorkflowMcp
from autoflow.infrastructure.database.workflow_runs import SqlAlchemyWorkflowRuns
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowDocuments
from autoflow.infrastructure.process.inspection_worker import inspection_worker_command
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

    async def submit_event_command(
        self, command_id: str, event: str, data: Mapping[str, Any]
    ) -> tuple[dict[str, Any], int]:
        del command_id, event, data
        raise WorkflowRunError(
            "WORKFLOW_EXECUTION_NOT_READY", "真实运行协调器尚未完成装配", 503
        )

    def event_command(self, command_id: str) -> tuple[dict[str, Any], int]:
        del command_id
        raise WorkflowRunError(
            "WORKFLOW_EXECUTION_NOT_READY", "真实运行协调器尚未完成装配", 503
        )

    def input_prompt_state(self, request_id: str) -> dict[str, str]:
        del request_id
        raise WorkflowRunError(
            "WORKFLOW_EXECUTION_NOT_READY", "真实运行协调器尚未完成装配", 503
        )


class StudioEventCommandMux:
    def __init__(self, workflows: Any, assistant: WorkflowAssistantService) -> None:
        self._workflows = workflows
        self._assistant = assistant

    async def submit_event_command(
        self, command_id: str, event: str, data: Mapping[str, Any]
    ) -> tuple[dict[str, Any], int]:
        if event in {"ai_client_action_claim", "ai_client_action_ack"}:
            return await self._assistant.submit_event_command(command_id, event, dict(data))
        return await self._workflows.submit_event_command(command_id, event, data)

    def event_command(self, command_id: str) -> tuple[dict[str, Any], int]:
        if self._assistant.has_command(command_id):
            return self._assistant.event_command(command_id)
        return self._workflows.event_command(command_id)

    def input_prompt_state(self, request_id: str) -> dict[str, str]:
        return self._workflows.input_prompt_state(request_id)


@dataclass(slots=True)
class WorkflowServices:
    documents: WorkflowDocumentService
    modules: CustomModuleService
    runs: WorkflowRunService
    commands: WorkflowRunCommands
    events: StudioEventJournal
    workers: WorkflowWorkerManager | None = None
    artifact_root: Path | None = None
    inspection: WorkflowInspectionService | Any | None = None
    assistant: WorkflowAssistantService | Any | None = None
    mcp: WorkflowMcpService | Any | None = None
    event_commands: Any | None = None

    async def shutdown(self) -> None:
        tasks = []
        if self.workers is not None:
            tasks.append(self.workers.shutdown())
        if self.inspection is not None:
            tasks.append(self.inspection.shutdown())
        if self.assistant is not None:
            tasks.append(self.assistant.shutdown())
        if self.mcp is not None:
            tasks.append(self.mcp.shutdown())
        if tasks:
            import asyncio

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, BaseException):
                    raise result

    def blockers(self) -> list[str]:
        if self.workers is not None and self.workers.busy():
            return ["workflow_process_active"]
        if self.inspection is not None and self.inspection.busy():
            return ["workflow_inspection_active"]
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
    models: Any | None = None,
    credential_store: Any | None = None,
) -> WorkflowServices:
    modules = CustomModuleService(SqlAlchemyWorkflowModules(session_factory))
    documents = WorkflowDocumentService(
        SqlAlchemyWorkflowDocuments(session_factory),
        custom_module_exists=modules.exists,
    )
    modules.bind_workflow_dependents(documents.referencing_custom_module_ids)
    run_repository = SqlAlchemyWorkflowRuns(session_factory)
    runs = WorkflowRunService(run_repository)
    events = StudioEventJournal()
    mcp = (
        WorkflowMcpService(
            SqlAlchemyWorkflowMcp(session_factory), credential_store
        )
        if credential_store is not None
        else None
    )
    assistant = (
        WorkflowAssistantService(
            SqlAlchemyWorkflowAssistant(session_factory),
            artifact_root / "assistant" / "checkpoints.sqlite3",
            models,
            events,
            mcp,
        )
        if artifact_root is not None and models is not None
        else None
    )
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
            modules=modules,
            runs=runs,
            commands=PendingWorkflowRunCommands(),
            events=events,
            assistant=assistant,
            mcp=mcp,
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
    inspection_holder: dict[str, WorkflowInspectionService] = {}

    async def on_event(event: dict[str, object]) -> None:
        await holder["coordinator"].on_worker_event(event)

    async def on_exit(run_id: str, return_code: int) -> None:
        await holder["coordinator"].on_worker_exit(run_id, return_code)

    async def on_inspection_event(event: dict[str, object]) -> None:
        await inspection_holder["service"].on_worker_event(event)

    async def on_inspection_exit(session_id: str, return_code: int) -> None:
        await inspection_holder["service"].on_worker_exit(session_id, return_code)

    workers = WorkflowWorkerManager(
        temp_root,
        on_event=on_event,
        on_exit=on_exit,
    )
    resources = WorkflowResourceCoordinator(profile_guard, kernels_root)
    inspection_workers = WorkflowWorkerManager(
        temp_root,
        command=inspection_worker_command(),
        on_event=on_inspection_event,
        on_exit=on_inspection_exit,
    )
    inspection = WorkflowInspectionService(
        profiles=profiles,
        installed_kernels=installed_kernels,
        resolve_proxy=resolve_proxy,
        read_license=read_license,
        resources=resources,
        workers=inspection_workers,
    )
    inspection_holder["service"] = inspection
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
        modules=modules,
        resolve_model=models.execution_binding if models is not None else None,
    )
    holder["coordinator"] = coordinator
    return WorkflowServices(
        documents=documents,
        modules=modules,
        runs=runs,
        commands=coordinator,
        events=events,
        workers=workers,
        artifact_root=artifact_root,
        inspection=inspection,
        assistant=assistant,
        mcp=mcp,
        event_commands=StudioEventCommandMux(coordinator, assistant) if assistant else None,
    )


def register_workflow_routes(app: FastAPI, services: WorkflowServices) -> None:
    # Static workflow commands must be registered before the dynamic document ID.
    app.include_router(workflow_run_command_router(services.commands))
    if services.inspection is not None:
        app.include_router(workflow_inspection_router(services.inspection))
    if services.assistant is not None:
        app.include_router(workflow_ai_router(services.assistant))
    if services.mcp is not None:
        app.include_router(workflow_mcp_router(services.mcp))
        app.router.add_event_handler("startup", services.mcp.startup)
    app.include_router(custom_modules_router(services.modules))
    app.include_router(workflows_router(services.documents))
    app.include_router(workflow_runs_router(services.runs, services.artifact_root))
    app.include_router(
        workflow_events_router(
            services.events, services.event_commands or services.commands
        )
    )


def configure_project_workflow_runtime(
    app: FastAPI,
    *,
    session_factory: Any,
    profiles: Any,
    installed: Any,
    resolve_proxy: Any,
    read_license: Any,
    usage_guard: Any,
    installations: Any,
    temp_dir: Path,
    gate: Any,
    environment_directory: Any | None = None,
) -> Any:
    """Compose the PM4 durable runtime beside the current Studio runtime."""
    from contextlib import contextmanager

    from autoflow.application.workflows.browser_resources import (
        WorkflowBrowserResources,
    )
    from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
    from autoflow.application.workflows.runtime import WorkflowRuntimeService
    from autoflow.domain.kernels.errors import KernelBusy, KernelNotFound
    from autoflow.domain.kernels.models import KernelRef
    from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
    from autoflow.infrastructure.filesystem.kernel_installations import (
        kernel_target_lock,
    )
    from autoflow.infrastructure.filesystem.locking import ExclusiveFileLock
    from autoflow.infrastructure.process.project_workflow_worker import (
        ProjectWorkflowWorkerManager,
    )
    from autoflow.infrastructure.process.workflow_recovery import (
        recover_worker_directories,
    )

    @contextmanager
    def guard(kernel: KernelRef):
        workspace_lock = ExclusiveFileLock(
            installations.root / ".studio-browser-session.lock"
        )
        if not workspace_lock.acquire():
            raise KernelBusy()
        lock = kernel_target_lock(installations.root, kernel.edition, kernel.version)
        try:
            if not lock.acquire():
                raise KernelBusy()
            if kernel.edition == "licensed":
                with installations.license_guard():
                    yield
            else:
                yield
        finally:
            lock.release()
            workspace_lock.release()

    resources = WorkflowBrowserResources(
        profiles, installed, resolve_proxy, read_license, usage_guard, guard,
        environment_directory=environment_directory,
    )
    worker = ProjectWorkflowWorkerManager(temp_dir)

    async def recover(run: Any) -> None:
        for kernel in installed():
            if f"{kernel.edition}:{kernel.version}" == run.resource_request.get(
                "kernelId"
            ):
                with usage_guard.guard(str(run.resource_request["profileId"])), guard(
                    KernelRef(kernel.edition, kernel.version)
                ):
                    await recover_worker_directories(
                        temp_dir, run.run_id, kernel.executable_path
                    )
                return
        raise KernelNotFound()

    dispatcher = WorkflowRunDispatcher(
        session_factory, worker, resources, gate, recover
    )
    runtime = WorkflowRuntimeService(
        session_factory, SqlAlchemyWorkflowRepository(session_factory)
    )
    app.state.project_workflow_runtime = runtime
    app.state.project_workflow_resources = resources
    app.state.project_workflow_worker_manager = worker
    app.state.project_workflow_dispatcher = dispatcher
    app.router.add_event_handler("startup", dispatcher.startup)
    return dispatcher
