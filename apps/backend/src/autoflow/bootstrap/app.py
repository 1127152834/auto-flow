import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from autoflow.adapters.events.kernels import kernels_events_router
from autoflow.adapters.events.workflows import workflow_events_router
from autoflow.adapters.http.errors import error_response, install_error_handlers
from autoflow.adapters.http.health import health_router
from autoflow.adapters.http.inspection import inspection_router
from autoflow.adapters.http.kernels import internal_kernel_paths_router, kernels_router
from autoflow.adapters.http.models import models_router
from autoflow.adapters.http.openapi import configure_openapi
from autoflow.adapters.http.profiles import profiles_router
from autoflow.adapters.http.proxy_options import proxy_options_router
from autoflow.adapters.http.settings_dashboard import settings_dashboard_router
from autoflow.adapters.http.workflow_runs import workflow_runs_router
from autoflow.adapters.http.workflows import workflows_router
from autoflow.adapters.http.workflow_recordings import recording_router
from autoflow.application.workflows.recording import RecordingService
from autoflow.infrastructure.database.workflow_recordings import RecordingRepository
from autoflow.infrastructure.filesystem.recording_values import RecordingValues
from autoflow.application.kernels.service import KernelService
from autoflow.application.models.service import ModelService
from autoflow.application.profiles.service import ProfileService
from autoflow.application.profiles.test_browser import ProfileTestBrowserService
from autoflow.application.settings.runtime import QuiesceGate, SettingsRuntimeService
from autoflow.application.workflows.inspection import InspectionService
from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.application.workflows.service import WorkflowService
from autoflow.bootstrap.config import Settings
from autoflow.bootstrap.proxies import (
    LazySystemCredentialStore,
    configure_proxy_management,
)
from autoflow.domain.credentials import CredentialStore
from autoflow.domain.kernels.errors import KernelBusy
from autoflow.domain.models.ports import ModelGateway
from autoflow.domain.profiles.models import Profile
from autoflow.domain.profiles.ports import (
    InstalledKernelLookup,
    ProfileDataStore,
    ProfileUsageGuard,
)
from autoflow.domain.workflows.runs import WorkflowRunLauncher
from autoflow.infrastructure.credentials.cloakbrowser import CloakBrowserLicenseStore
from autoflow.infrastructure.database.kernel_operations import (
    SqlAlchemyKernelOperationRepository,
)
from autoflow.infrastructure.database.kernel_settings import (
    SqlAlchemyDefaultKernelRepository,
)
from autoflow.infrastructure.database.model_providers import (
    model_repository_transaction,
)
from autoflow.infrastructure.database.profiles import profile_repository_transaction
from autoflow.infrastructure.database.proxy_options import SqlAlchemyProxyOptions
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.settings_runtime import (
    SqlAlchemySettingsRuntimeRepository,
)
from autoflow.infrastructure.database.workflow_runs import (
    SqlAlchemyWorkflowRunRepository,
)
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from autoflow.infrastructure.events.kernel_events import KernelEventBroker
from autoflow.infrastructure.filesystem.kernel_installations import (
    FilesystemKernelInstallationStore,
    kernel_target_lock,
)
from autoflow.infrastructure.filesystem.paths import AppPaths
from autoflow.infrastructure.filesystem.profile_data import (
    FilesystemProfileDataStore,
    FilesystemProfileUsageGuard,
)
from autoflow.infrastructure.filesystem.profile_environment import (
    read_profile_environment_options,
)
from autoflow.infrastructure.filesystem.workflow_artifacts import artifact_path
from autoflow.infrastructure.filesystem.workflow_diagnostics import (
    read_workflow_json,
    result_archive,
)
from autoflow.infrastructure.process.inspection_worker import InspectionWorkerManager
from autoflow.infrastructure.process.kernel_worker import KernelWorkerManager
from autoflow.infrastructure.process.test_browser_worker import TestBrowserWorkerManager
from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager
from autoflow.providers.kernel.cloakbrowser import (
    CloakBrowserCatalogProvider,
    CloakBrowserLicenseProvider,
)
from autoflow.providers.model.http import HttpModelProvider


def create_app(
    settings: Settings,
    *,
    installed_kernel_lookup: InstalledKernelLookup | None = None,
    profile_data_store: ProfileDataStore | None = None,
    profile_usage_guard: ProfileUsageGuard | None = None,
    kernel_service: KernelService | None = None,
    credential_store: CredentialStore | None = None,
    model_gateway: ModelGateway | None = None,
    workflow_run_launcher: WorkflowRunLauncher | None = None,
) -> FastAPI:
    paths = AppPaths.from_data_dir(Path(settings.data_dir))
    for directory in (paths.database.parent, paths.logs, paths.workspace, paths.cache, paths.temp, paths.profiles, paths.kernels):
        directory.mkdir(parents=True, exist_ok=True)
    migrate_database(paths.database)
    session_factory = create_session_factory(paths.database)
    kernel_events = KernelEventBroker()
    kernel_worker_manager = KernelWorkerManager(
        kernels_dir=paths.kernels,
        repository=SqlAlchemyKernelOperationRepository(session_factory),
        events=kernel_events,
    )
    kernel_worker_manager.recover_interrupted()
    credentials = LazySystemCredentialStore()
    catalog_provider = CloakBrowserCatalogProvider(
        paths.kernels, licensed_catalog=kernel_worker_manager.licensed_catalog
    )
    license_store = CloakBrowserLicenseStore(credentials)
    installations = FilesystemKernelInstallationStore(paths.kernels)
    with installations.guard():
        installations.retry_pending()
    kernel_service = kernel_service or KernelService(
        catalog_provider,
        CloakBrowserLicenseProvider(license_store, kernel_worker_manager.validate_license),
        license_store,
        SqlAlchemyDefaultKernelRepository(session_factory),
        installations,
        kernel_worker_manager,
    )
    transaction = partial(profile_repository_transaction, session_factory)
    proxy_options = SqlAlchemyProxyOptions(session_factory)
    data_store = profile_data_store or FilesystemProfileDataStore(paths.profiles)
    usage_guard = profile_usage_guard or FilesystemProfileUsageGuard(paths.profiles)
    data_store.retry_pending(lambda profile_id: _profile_exists(transaction, profile_id))
    profile_service = ProfileService(
        transaction,
        installed_kernel_lookup or catalog_provider,
        proxy_options,
        usage_guard,
        data_store,
    )
    test_browser_workers = TestBrowserWorkerManager(paths.temp)

    model_service = ModelService(
        partial(model_repository_transaction, session_factory),
        credential_store if credential_store is not None else credentials,
        model_gateway or HttpModelProvider(),
    )
    model_service.recover_credentials()

    app = FastAPI()
    configure_openapi(app, api_version=settings.api_version)
    install_error_handlers(app)
    quiesce_gate = QuiesceGate()
    proxy_runtime = configure_proxy_management(app, paths.database)
    profile_test_browser = ProfileTestBrowserService(
        profile_service,
        catalog_provider.installed,
        proxy_runtime.resolve_profile,
        license_store.read,
        test_browser_workers,
    )

    @contextmanager
    def workflow_kernel_guard(profile: Profile) -> Iterator[None]:
        lock = kernel_target_lock(paths.kernels, profile.spec.browser_edition, profile.spec.browser_version)
        try:
            if not lock.acquire():
                raise KernelBusy()
            yield
        finally:
            lock.release()

    workflow_workers = workflow_run_launcher or WorkflowWorkerManager(paths.temp, paths.workspace / "runs")
    run_repository = SqlAlchemyWorkflowRunRepository(session_factory)
    run_repository.recover_interrupted()
    workflow_runs = WorkflowRunService(
        run_repository, profile_service, catalog_provider.installed, workflow_kernel_guard,
        proxy_runtime.resolve_profile, license_store.read, workflow_workers,
        partial(artifact_path, paths.workspace / "runs"),
        read_json=read_workflow_json, archive=result_archive,
    )

    inspection_workers = InspectionWorkerManager(paths.temp)
    inspection = InspectionService(profile_service, catalog_provider.installed, workflow_kernel_guard,
                                   proxy_runtime.resolve_profile, license_store.read, inspection_workers,
                                   workflow_runs.busy)
    recording_repository = RecordingRepository(session_factory)
    recording_repository.recover()
    recording_values = RecordingValues(paths.workspace / 'recordings')
    recording = RecordingService(recording_repository, profile_service, catalog_provider.installed, workflow_kernel_guard,
                                 proxy_runtime.resolve_profile, license_store.read, InspectionWorkerManager(paths.temp, recording=True),
                                 lambda: workflow_runs.busy() or inspection.busy(),
                                 recording_values.write, recording_values.read, recording_values.remove)
    inspection._run_busy = lambda: workflow_runs.busy() or recording.busy()
    workflow_runs.inspection_busy = lambda: inspection.busy() or recording.busy()

    settings_runtime = SettingsRuntimeService(
        SqlAlchemySettingsRuntimeRepository(session_factory, paths.profiles),
        {
            "workspace": str(paths.data_dir),
            "database": str(paths.database),
            "profiles": str(paths.profiles),
            "kernels": str(paths.kernels),
            "logs": str(paths.logs),
        },
        settings.api_version,
        lambda: len(catalog_provider.installed()),
        lambda: [
            *(["kernel_process_active"] if kernel_worker_manager.active_processes() else []),
            *(["test_browser_process_active"] if test_browser_workers.busy() else []),
            *(["workflow_run_active"] if workflow_runs.busy() else []),
            *(["workflow_inspection_active"] if inspection.busy() else []),
            *(["workflow_recording_active"] if recording.busy() else []),
        ],
        quiesce_gate,
    )

    app.state.paths = paths
    app.state.session_factory = session_factory
    app.state.profile_service = profile_service
    app.state.profile_test_browser = profile_test_browser
    app.state.test_browser_worker_manager = test_browser_workers
    app.state.model_service = model_service
    app.state.kernel_worker_manager = kernel_worker_manager
    app.state.kernel_service = kernel_service
    app.state.settings_runtime = settings_runtime
    app.state.workflow_recording_service = recording
    app.state.workflow_inspection_service = inspection
    app.state.inspection_worker_manager = inspection_workers
    app.state.workflow_run_service = workflow_runs
    app.state.workflow_worker_manager = workflow_workers

    async def shutdown() -> None:
        try:
            import asyncio

            await asyncio.gather(
                test_browser_workers.shutdown(), kernel_worker_manager.shutdown(),
                workflow_runs.shutdown(), inspection.shutdown(), recording.shutdown()
            )
        finally:
            try:
                from inspect import isawaitable

                closing = proxy_runtime.close()
                if isawaitable(closing):
                    await closing
            finally:
                session_factory.dispose()

    app.router.add_event_handler("shutdown", shutdown)
    app.include_router(health_router(api_version=settings.api_version, instance_id=settings.instance_id))
    app.include_router(
        profiles_router(
            profile_service, read_profile_environment_options, profile_test_browser
        )
    )
    app.include_router(proxy_options_router(proxy_options))
    app.include_router(models_router(model_service))
    app.include_router(kernels_router(kernel_service))
    app.include_router(internal_kernel_paths_router(kernel_service))
    app.include_router(settings_dashboard_router(settings_runtime))
    app.include_router(recording_router(recording))
    app.include_router(inspection_router(inspection))
    app.include_router(workflow_runs_router(workflow_runs))
    app.include_router(workflow_events_router(workflow_runs))
    app.include_router(workflows_router(WorkflowService(SqlAlchemyWorkflowRepository(session_factory))))
    app.include_router(
        kernels_events_router(kernel_events, kernel_worker_manager.snapshot)
    )

    @app.middleware("http")
    async def authenticate_api(request: Request, call_next):
        if request.url.path.startswith("/internal/"):
            supplied = request.headers.get("x-autoflow-host-token", "")
            if (
                not settings.host_token
                or request.headers.get("origin") is not None
                or not secrets.compare_digest(supplied, settings.host_token)
            ):
                return JSONResponse(
                    {"detail": "Unauthorized"},
                    status_code=401,
                    headers={"Cache-Control": "no-store"},
                )
        if request.url.path.startswith("/api/v1/") and (
            settings.instance_token is None or request.headers.get("x-autoflow-token") != settings.instance_token
        ):
            return error_response(401, "SIDECAR_UNAUTHORIZED", "本地服务认证失效，请重新连接")
        guarded_get = (
            request.method == "GET"
            and (
                request.url.path in {"/api/v1/kernels/catalog", "/api/v1/kernels/license"}
                or request.url.path.endswith("/models/discover")
            )
        )
        guarded_request = request.url.path.startswith("/api/v1/") and (
            request.method not in {"GET", "HEAD", "OPTIONS"} or guarded_get
        )
        if not guarded_request:
            return await call_next(request)
        with quiesce_gate.mutation() as admitted:
            if not admitted:
                return error_response(
                    409,
                    "SERVICE_QUIESCED",
                    "Service is paused for a desktop operation",
                )
            return await call_next(request)

    if settings.renderer_origin:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[settings.renderer_origin],
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["x-autoflow-token", "content-type", "Idempotency-Key"],
        )
    return app


def _profile_exists(transaction, profile_id: str) -> bool:
    with transaction() as repository:
        return repository.get(profile_id) is not None
