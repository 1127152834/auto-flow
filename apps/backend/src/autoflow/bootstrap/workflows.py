from collections.abc import Awaitable, Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from autoflow.application.profiles.service import ProfileService
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.browser_resources import WorkflowBrowserResources
from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
from autoflow.application.workflows.runtime import WorkflowRuntimeService
from autoflow.domain.kernels.errors import KernelBusy, KernelNotFound
from autoflow.domain.kernels.models import InstalledKernel, KernelRef
from autoflow.domain.profiles.models import Profile, ProfileBrowserProxy
from autoflow.domain.profiles.ports import ProfileUsageGuard
from autoflow.domain.workflows.runtime import CoreRun
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from autoflow.infrastructure.filesystem.kernel_installations import (
    FilesystemKernelInstallationStore,
    kernel_target_lock,
)
from autoflow.infrastructure.process.workflow_recovery import recover_worker_directories
from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager


def configure_workflow_runtime(
    app: FastAPI, *, session_factory: sessionmaker[Session],
    profiles: ProfileService, installed: Callable[[], Sequence[InstalledKernel]],
    resolve_proxy: Callable[[Profile, str], Awaitable[ProfileBrowserProxy | None]],
    read_license: Callable[[], str | None], usage_guard: ProfileUsageGuard,
    installations: FilesystemKernelInstallationStore, temp_dir: Path,
    gate: QuiesceGate,
    environment_directory: Callable[[str], Path | None] | None = None,
) -> WorkflowRunDispatcher:
    @contextmanager
    def guard(kernel: KernelRef) -> Iterator[None]:
        lock = kernel_target_lock(installations.root, kernel.edition, kernel.version)
        try:
            if not lock.acquire():
                raise KernelBusy()
            if kernel.edition == 'licensed':
                with installations.license_guard():
                    yield
            else:
                yield
        finally:
            lock.release()

    resources = WorkflowBrowserResources(
        profiles, installed, resolve_proxy, read_license, usage_guard, guard,
        environment_directory=environment_directory,
    )
    worker = WorkflowWorkerManager(temp_dir)

    async def recover(run: CoreRun) -> None:
        for kernel in installed():
            if f'{kernel.edition}:{kernel.version}' == run.resource_request.get('kernelId'):
                with usage_guard.guard(str(run.resource_request['profileId'])), guard(KernelRef(kernel.edition, kernel.version)):
                    await recover_worker_directories(temp_dir, run.run_id, kernel.executable_path)
                return
        # Missing installed resources cannot justify deleting old ownership evidence.
        raise KernelNotFound()

    dispatcher = WorkflowRunDispatcher(session_factory, worker, resources, gate, recover)
    runtime = WorkflowRuntimeService(session_factory, SqlAlchemyWorkflowRepository(session_factory))
    app.state.workflow_runtime = runtime
    app.state.workflow_resources = resources
    app.state.workflow_worker_manager = worker
    app.state.workflow_dispatcher = dispatcher
    app.router.add_event_handler('startup', dispatcher.startup)
    return dispatcher
