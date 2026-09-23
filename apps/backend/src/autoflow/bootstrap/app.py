import secrets
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from autoflow.adapters.http.android import android_router
from autoflow.adapters.http.android_fleet import android_fleet_router
from autoflow.adapters.http.errors import error_response, install_error_handlers
from autoflow.adapters.http.image_assets import image_assets_router
from autoflow.adapters.http.laya_lab import laya_lab_router
from autoflow.adapters.http.local_workflows import local_workflows_router
from autoflow.adapters.http.openapi import configure_openapi
from autoflow.adapters.http.studio_credentials import studio_credentials_router
from autoflow.adapters.http.studio_retention import studio_retention_router
from autoflow.adapters.http.workflow_bundles import workflow_bundles_router
from autoflow.adapters.http.workflow_catalog import workflow_catalog_router
from autoflow.adapters.http.workflow_schedules import workflow_schedules_router
from autoflow.application.android.console import AndroidConsole
from autoflow.application.android.fleet import AndroidFleet
from autoflow.application.environments.service import EnvironmentService
from autoflow.application.kernels.service import KernelService
from autoflow.application.lab.service import LayaService
from autoflow.application.models.service import ModelService
from autoflow.application.profiles.service import ProfileService
from autoflow.application.profiles.test_browser import ProfileTestBrowserService
from autoflow.application.project_automations.resource_query import (
    ProjectAutomationResourceQuery,
)
from autoflow.application.project_automations.service import ProjectAutomationService
from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.deletions import DataDeletionService
from autoflow.application.project_data.excel import ProjectExcelService
from autoflow.application.project_data.excel_export import ProjectExcelExportService
from autoflow.application.project_data.excel_import import ExcelImportService
from autoflow.application.project_data.queries import DataRecordQueryService
from autoflow.application.project_data.records import DataRecordService
from autoflow.application.project_data.schema import DataSchemaService
from autoflow.application.project_data.status_batches import (
    RecordStatusBatchCoordinator,
    RecordStatusBatchService,
)
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.project_runs.coordinator import ProjectRunCoordinator
from autoflow.application.project_runs.events import ProjectRunEvents
from autoflow.application.project_runs.evidence import ProjectRunEvidence
from autoflow.application.project_runs.queries import ProjectRunQueries
from autoflow.application.project_runs.resources import ProjectRunResourceResolver
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.project_sync.access import GoogleAccess, TransportFactory
from autoflow.application.project_sync.bindings import SheetsBindingService
from autoflow.application.project_sync.connections import (
    AuthorizationRegistry,
    SheetsConnectionService,
)
from autoflow.application.project_sync.impacts import SheetsImpactService
from autoflow.application.project_sync.outbound import SheetsSyncService
from autoflow.application.project_sync.runs import SheetsRun
from autoflow.application.projects.lifecycle import (
    ProjectLifecycleCoordinator,
    ProjectLifecycleService,
)
from autoflow.application.projects.overview import ProjectOverviewService
from autoflow.application.projects.service import ProjectService
from autoflow.application.projects.statistics import ProjectStatisticsService
from autoflow.application.settings.runtime import QuiesceGate, SettingsRuntimeService
from autoflow.application.workflows.bundles import WorkflowBundleService
from autoflow.application.workflows.credentials import StudioCredentialService
from autoflow.application.workflows.image_assets import ImageAssetStore
from autoflow.application.workflows.local_files import LocalWorkflowFiles
from autoflow.application.workflows.retention import StudioRetentionService
from autoflow.application.workflows.schedule_notifications import (
    WorkflowScheduleNotifier,
)
from autoflow.application.workflows.schedules import WorkflowScheduleService
from autoflow.application.workflows.service import WorkflowService
from autoflow.application.workflows.webdav import WebDavWorkflowService
from autoflow.bootstrap.android import CurrentAndroidRunBoundary, android_service
from autoflow.bootstrap.config import Settings
from autoflow.bootstrap.http_routes import (
    ManagementHttpServices,
    register_management_routes,
)
from autoflow.bootstrap.project_http_routes import (
    ProjectHttpServices,
    register_project_routes,
)
from autoflow.bootstrap.proxies import (
    LazySystemCredentialStore,
    configure_proxy_management,
)
from autoflow.bootstrap.workflows import (
    build_workflow_services,
    configure_project_workflow_runtime,
    register_workflow_routes,
)
from autoflow.domain.credentials import CredentialStore
from autoflow.domain.models.ports import ModelGateway
from autoflow.domain.profiles.ports import (
    InstalledKernelLookup,
    ProfileDataStore,
    ProfileUsageGuard,
)
from autoflow.infrastructure.credentials.cloakbrowser import CloakBrowserLicenseStore
from autoflow.infrastructure.database.android_resources import AndroidResourceRepository
from autoflow.infrastructure.database.environments import SqlAlchemyEnvironments
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
from autoflow.infrastructure.database.project_automations import (
    SqlAlchemyProjectAutomations,
)
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_deletions import (
    SqlAlchemyProjectDataDeletions,
)
from autoflow.infrastructure.database.project_data_queries import (
    SqlAlchemyProjectDataQueries,
)
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.project_data_schema import (
    SqlAlchemyProjectDataSchema,
)
from autoflow.infrastructure.database.project_data_status_batches import (
    SqlAlchemyRecordStatusBatches,
)
from autoflow.infrastructure.database.project_excel_exports import (
    SqlAlchemyProjectExcelExports,
)
from autoflow.infrastructure.database.project_excel_imports import (
    SqlAlchemyExcelImports,
)
from autoflow.infrastructure.database.project_lifecycle import (
    SqlAlchemyProjectLifecycle,
)
from autoflow.infrastructure.database.project_pending import (
    SqlAlchemyProjectPendingWork,
)
from autoflow.infrastructure.database.project_resource_references import (
    SqlAlchemyProjectResourceReferences,
)
from autoflow.infrastructure.database.project_sync import SqlAlchemyProjectSync
from autoflow.infrastructure.database.project_sync_impacts import (
    SqlAlchemySheetsImpacts,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.proxy_options import SqlAlchemyProxyOptions
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.settings_runtime import (
    SqlAlchemySettingsRuntimeRepository,
)
from autoflow.infrastructure.database.studio_credentials import (
    SqlAlchemyStudioCredentials,
)
from autoflow.infrastructure.database.studio_retention import SqlAlchemyStudioRetention
from autoflow.infrastructure.database.workflow_schedules import (
    SqlAlchemyWorkflowSchedules,
)
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from autoflow.infrastructure.events.kernel_events import KernelEventBroker
from autoflow.infrastructure.filesystem.environment_store import EnvironmentStore
from autoflow.infrastructure.filesystem.kernel_installations import (
    FilesystemKernelInstallationStore,
)
from autoflow.infrastructure.filesystem.paths import AppPaths
from autoflow.infrastructure.filesystem.profile_data import (
    FilesystemProfileDataStore,
    FilesystemProfileUsageGuard,
)
from autoflow.infrastructure.filesystem.profile_environment import (
    read_profile_environment_options,
)
from autoflow.infrastructure.process.kernel_worker import KernelWorkerManager
from autoflow.infrastructure.process.test_browser_worker import TestBrowserWorkerManager
from autoflow.providers.android.stream import AndroidStream
from autoflow.providers.browser.environment_browser import EnvironmentBrowserLauncher
from autoflow.providers.data import google_auth
from autoflow.providers.data.google_auth import HttpxTokenTransport
from autoflow.providers.data.google_sheets import HttpxSheetsTransport
from autoflow.providers.kernel.cloakbrowser import (
    CloakBrowserCatalogProvider,
    CloakBrowserLicenseProvider,
)
from autoflow.providers.laya.runtime import LayaRuntime
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
    google_tokens: google_auth.TokenTransport | None = None,
    google_transports: TransportFactory | None = None,
) -> FastAPI:
    paths = AppPaths.from_data_dir(Path(settings.data_dir))
    for directory in (
        paths.database.parent,
        paths.logs,
        paths.workspace,
        paths.cache,
        paths.temp,
        paths.profiles,
        paths.kernels,
        paths.workspace / "environments",
    ):
        directory.mkdir(parents=True, exist_ok=True)
    migrate_database(paths.database)
    session_factory = create_session_factory(paths.database)
    resource_references = SqlAlchemyProjectResourceReferences(session_factory)
    kernel_events = KernelEventBroker()
    kernel_worker_manager = KernelWorkerManager(
        kernels_dir=paths.kernels,
        repository=SqlAlchemyKernelOperationRepository(session_factory),
        events=kernel_events,
    )
    kernel_worker_manager.recover_interrupted()
    credentials = LazySystemCredentialStore()
    active_credentials = credential_store or credentials
    catalog_provider = CloakBrowserCatalogProvider(
        paths.kernels, licensed_catalog=kernel_worker_manager.licensed_catalog
    )
    license_store = CloakBrowserLicenseStore(credentials)
    installations = FilesystemKernelInstallationStore(paths.kernels)
    with installations.guard():
        installations.retry_pending()
    kernel_service = kernel_service or KernelService(
        catalog_provider,
        CloakBrowserLicenseProvider(
            license_store, kernel_worker_manager.validate_license
        ),
        license_store,
        SqlAlchemyDefaultKernelRepository(session_factory),
        installations,
        kernel_worker_manager,
        resource_references,
    )
    transaction = partial(profile_repository_transaction, session_factory)
    proxy_options = SqlAlchemyProxyOptions(session_factory)
    data_store = profile_data_store or FilesystemProfileDataStore(paths.profiles)
    usage_guard = profile_usage_guard or FilesystemProfileUsageGuard(paths.profiles)
    data_store.retry_pending(
        lambda profile_id: _profile_exists(transaction, profile_id)
    )
    profile_service = ProfileService(
        transaction,
        installed_kernel_lookup or catalog_provider,
        proxy_options,
        usage_guard,
        data_store,
        resource_references,
    )
    test_browser_workers = TestBrowserWorkerManager(paths.temp)

    model_service = ModelService(
        partial(model_repository_transaction, session_factory),
        active_credentials,
        model_gateway or HttpModelProvider(),
        resource_references,
    )
    model_service.recover_credentials()

    app = FastAPI()
    app.state.config = settings
    configure_openapi(app, api_version=settings.api_version)
    install_error_handlers(app)
    quiesce_gate = QuiesceGate()
    project_excel = ProjectExcelService(
        session_factory,
        workspace_id=str(paths.data_dir),
        instance_id=settings.instance_id,
        gate=quiesce_gate,
    )
    excel_imports = ExcelImportService(
        SqlAlchemyExcelImports(
            session_factory, str(paths.data_dir), settings.instance_id
        ),
        quiesce_gate,
    )
    excel_export_executor = ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="project-export"
    )
    excel_exports = ProjectExcelExportService(
        SqlAlchemyProjectExcelExports(
            session_factory, str(paths.data_dir), settings.instance_id
        ),
        quiesce_gate,
        excel_export_executor,
    )
    app.state.excel_exports = excel_exports
    app.router.add_event_handler("startup", excel_exports.startup)
    app.state.excel_imports = excel_imports
    app.router.add_event_handler("startup", excel_imports.startup)
    app.state.project_excel_service = project_excel
    app.router.add_event_handler("startup", project_excel.startup)
    status_batch_repository = SqlAlchemyRecordStatusBatches(session_factory)
    status_batch_executor = ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="project-status"
    )
    status_batch_coordinator = RecordStatusBatchCoordinator(
        status_batch_repository, quiesce_gate, status_batch_executor
    )
    status_batch_service = RecordStatusBatchService(
        status_batch_repository, status_batch_coordinator
    )
    app.state.status_batch_service = status_batch_service
    app.state.status_batch_coordinator = status_batch_coordinator
    app.router.add_event_handler("startup", status_batch_coordinator.resume)
    proxy_runtime = configure_proxy_management(app, paths.database, resource_references)
    profile_test_browser = ProfileTestBrowserService(
        profile_service,
        catalog_provider.installed,
        proxy_runtime.resolve_profile,
        license_store.read,
        test_browser_workers,
    )
    studio_credentials = StudioCredentialService(
        SqlAlchemyStudioCredentials(session_factory), active_credentials
    )
    app.state.studio_credentials = studio_credentials
    workflow_services = build_workflow_services(
        session_factory,
        profiles=profile_service,
        installed_kernels=catalog_provider.installed,
        resolve_proxy=proxy_runtime.resolve_profile,
        read_license=license_store.read,
        profile_guard=usage_guard,
        kernels_root=paths.kernels,
        temp_root=paths.temp,
        artifact_root=paths.workspace,
        models=model_service,
        credential_store=active_credentials,
        resolve_credential=studio_credentials.resolve,
    )
    workflow_services.runs.recover_interrupted()
    webdav_workflows = WebDavWorkflowService(paths.workspace, active_credentials)
    app.state.webdav_workflows = webdav_workflows
    schedule_repository = SqlAlchemyWorkflowSchedules(session_factory)
    local_workflows = LocalWorkflowFiles(
        paths.workspace,
        webdav_workflows,
        schedule_repository.ensure_workflow_unreferenced,
    )
    app.state.local_workflows = local_workflows
    image_assets = ImageAssetStore(paths.workspace)
    app.state.image_assets = image_assets
    workflow_bundles = WorkflowBundleService(workflow_services.modules, image_assets)
    app.state.workflow_bundles = workflow_bundles
    studio_retention = StudioRetentionService(
        SqlAlchemyStudioRetention(session_factory), paths.workspace
    )
    app.state.studio_retention = studio_retention
    workflow_schedules = WorkflowScheduleService(
        schedule_repository,
        local_workflows,
        workflow_services.commands,
        workflow_services.runs,
        gate=quiesce_gate,
        notifier=WorkflowScheduleNotifier(studio_credentials),
    )
    app.state.workflow_schedules = workflow_schedules
    app.router.add_event_handler("startup", studio_retention.startup)
    app.router.add_event_handler("startup", workflow_schedules.startup)
    android = android_service(session_factory, paths.workspace)
    android_resources = AndroidResourceRepository(session_factory)
    android_runs = CurrentAndroidRunBoundary()
    android_fleet = AndroidFleet(android, android_resources, None, android_runs)
    android_console = AndroidConsole(
        android, android_runs, android_resources, AndroidStream
    )
    app.state.android_service = android
    app.state.android_fleet = android_fleet
    app.state.android_console = android_console
    app.router.add_event_handler("startup", android.recover)
    app.router.add_event_handler("startup", android_fleet.start)
    app.router.add_event_handler("startup", android_console.start)

    environment_store = EnvironmentStore(paths.workspace / "environments")

    def _run_execution_generation(run_id: str):
        """The stored run generation outranks whatever a request claims for itself."""

        runtime = getattr(app.state, "project_workflow_runtime", None)
        if runtime is None:
            return None
        query_run = getattr(runtime, "query_run", None)
        if query_run is not None:
            return query_run(run_id=run_id)
        get_run = getattr(runtime, "get_run", None)
        return get_run(run_id=run_id) if get_run is not None else None

    # Headed work copies for saved/running instances: opener + closer share one owner,
    # so End and save can confirm the browser is really gone before copying files.
    # The injected lookup decides what is installed everywhere else, so the
    # launcher must read the same inventory; a bare lookup without an
    # ``installed()`` list still falls back to the real catalog.
    kernel_inventory = getattr(
        installed_kernel_lookup or catalog_provider, "installed", None
    ) or catalog_provider.installed
    environment_browser = EnvironmentBrowserLauncher(
        profile_service, kernel_inventory, environment_store
    )
    environment_service = EnvironmentService(
        ProjectService(SqlAlchemyProjects(session_factory)),
        SqlAlchemyEnvironments(session_factory),
        environment_store,
        opener=environment_browser.opener,
        closer=environment_browser.closer,
        execution_generation_lookup=_run_execution_generation,
    )
    app.state.environment_browser = environment_browser
    app.state.environment_service = environment_service
    sheets_impacts = SqlAlchemySheetsImpacts(session_factory)
    sheets_repository = SqlAlchemyProjectSync(session_factory, sheets_impacts)
    sheets_tokens = google_tokens or HttpxTokenTransport()
    google_credentials = active_credentials
    sheets_access = GoogleAccess(
        sheets_repository,
        google_credentials,
        sheets_tokens,
        transports=google_transports or HttpxSheetsTransport,
    )
    sheets_runs = SheetsRun(sheets_repository)
    sheets_connections = SheetsConnectionService(
        sheets_repository, google_credentials, sheets_tokens, AuthorizationRegistry()
    )
    sheets_bindings = SheetsBindingService(
        session_factory,
        sheets_runs,
        sheets_access,
        DataTableService(SqlAlchemyProjectData(session_factory)),
    )
    sheets_impacts_service = SheetsImpactService(sheets_impacts)
    sheets_sync = SheetsSyncService(
        session_factory, sheets_runs, sheets_repository, sheets_access
    )
    app.state.sheets_connections = sheets_connections
    app.state.sheets_bindings = sheets_bindings
    app.state.sheets_sync = sheets_sync

    project_workflow_dispatcher = configure_project_workflow_runtime(
        app,
        session_factory=session_factory,
        profiles=profile_service,
        installed=catalog_provider.installed,
        resolve_proxy=proxy_runtime.resolve_profile,
        read_license=license_store.read,
        usage_guard=usage_guard,
        installations=installations,
        temp_dir=paths.temp,
        gate=quiesce_gate,
        environment_directory=environment_service.run_work_directory,
    )
    automation_resources = ProjectAutomationResourceQuery(
        SqlAlchemyProjects(session_factory),
        profile_service,
        installed_kernel_lookup or catalog_provider,
        proxy_options,
        model_service,
        environment_service,
        workflow_runtime=app.state.project_workflow_runtime,
    )
    project_run_coordinator = ProjectRunCoordinator(
        session_factory,
        app.state.project_workflow_runtime,
        resolve_resources=ProjectRunResourceResolver(
            automation_resources,
            app.state.project_workflow_resources,
            environment_service,
        ),
        available_capabilities=["browser.cloakbrowser", "project.data"],
        environments=environment_service,
    )
    project_run_scheduler = ProjectBatchScheduler(
        session_factory, project_workflow_dispatcher, quiesce_gate, environment_service
    )
    project_pending_work = SqlAlchemyProjectPendingWork(session_factory)
    app.state.project_run_coordinator = project_run_coordinator
    app.state.project_run_scheduler = project_run_scheduler
    app.router.add_event_handler("startup", project_run_scheduler.startup)

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
            *project_pending_work.blockers(),
            *project_workflow_dispatcher.blockers(),
            *project_run_scheduler.blockers(),
            *project_lifecycle_coordinator.blockers(),
            *(
                ["project_excel_operation_active"]
                if project_excel.pending_operations()
                or excel_imports.pending_operations()
                or excel_exports.pending_operations()
                else []
            ),
            *(
                ["project_data_status_batch_active"]
                if status_batch_repository.pending_operation_ids()
                else []
            ),
            *(
                ["kernel_process_active"]
                if kernel_worker_manager.active_processes()
                else []
            ),
            *(["test_browser_process_active"] if test_browser_workers.busy() else []),
            *workflow_services.blockers(),
            *workflow_schedules.blockers(),
            *(["android_management_active"] if android.management.busy() else []),
            *(["android_console_active"] if android_console.busy() else []),
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
    app.state.workflow_services = workflow_services
    app.state.project_workflow_dispatcher = project_workflow_dispatcher
    app.state.workflow_dispatcher = project_workflow_dispatcher

    async def shutdown() -> None:
        try:
            import asyncio

            excel_exports.shutdown()
            await asyncio.to_thread(excel_export_executor.shutdown, wait=True)
            excel_imports.shutdown()
            project_excel.shutdown()
            status_batch_coordinator.shutdown()
            await asyncio.to_thread(status_batch_executor.shutdown, wait=True)
            await workflow_schedules.shutdown()

            async def close_project_workflows() -> None:
                try:
                    await project_run_scheduler.shutdown()
                    await project_lifecycle_coordinator.shutdown()
                finally:
                    await project_workflow_dispatcher.shutdown()

            results = await asyncio.gather(
                studio_retention.shutdown(),
                workflow_services.shutdown(),
                android.management.shutdown(),
                android_fleet.shutdown(),
                android_console.shutdown(),
                close_project_workflows(),
                test_browser_workers.shutdown(),
                kernel_worker_manager.shutdown(),
                return_exceptions=True,
            )
            environment_browser.shutdown()
            for result in results:
                if isinstance(result, BaseException):
                    raise result
        finally:
            try:
                from inspect import isawaitable

                closing = proxy_runtime.close()
                if isawaitable(closing):
                    await closing
            finally:
                session_factory.dispose()

    app.router.add_event_handler("shutdown", shutdown)
    register_management_routes(
        app,
        ManagementHttpServices(
            profiles=profile_service,
            environment_options=read_profile_environment_options,
            test_browsers=profile_test_browser,
            proxy_options=proxy_options,
            models=model_service,
            kernels=kernel_service,
            settings=settings_runtime,
            kernel_events=kernel_events,
            kernel_snapshot=kernel_worker_manager.snapshot,
        ),
        api_version=settings.api_version,
        instance_id=settings.instance_id,
    )
    laya_runtime = LayaRuntime(paths.cache)
    app.include_router(laya_lab_router(LayaService(laya_runtime)))
    app.router.add_event_handler("shutdown", laya_runtime.close)
    register_workflow_routes(app, workflow_services)
    app.include_router(local_workflows_router(local_workflows, webdav_workflows))
    app.include_router(image_assets_router(image_assets))
    app.include_router(workflow_bundles_router(workflow_bundles))
    app.include_router(studio_credentials_router(studio_credentials))
    app.include_router(studio_retention_router(studio_retention))
    app.include_router(workflow_schedules_router(workflow_schedules))
    app.include_router(android_router(android))
    app.include_router(android_fleet_router(android_fleet, android_console))
    project_workflow_service = WorkflowService(
        SqlAlchemyWorkflowRepository(session_factory)
    )
    app.include_router(workflow_catalog_router(project_workflow_service))
    project_lifecycle_repository = SqlAlchemyProjectLifecycle(
        session_factory, environment_root=environment_store.root, workflow_artifact_root=paths.workspace,
        inspection_blockers=workflow_services.inspection.project_blockers if workflow_services.inspection is not None else None
    )
    project_lifecycle_coordinator = ProjectLifecycleCoordinator(
        project_lifecycle_repository, quiesce_gate
    )
    project_lifecycle = ProjectLifecycleService(
        SqlAlchemyProjects(session_factory),
        project_lifecycle_repository,
        project_lifecycle_coordinator,
    )
    app.state.project_lifecycle = project_lifecycle
    app.state.project_lifecycle_coordinator = project_lifecycle_coordinator
    app.router.add_event_handler("startup", project_lifecycle_coordinator.startup)
    register_project_routes(app, ProjectHttpServices(
        run_coordinator=project_run_coordinator,
        run_queries=ProjectRunQueries(session_factory),
        run_evidence=ProjectRunEvidence(session_factory, paths.workspace),
        run_events=ProjectRunEvents(session_factory),
        run_scheduler=project_run_scheduler,
        gate=quiesce_gate,
        projects=ProjectService(SqlAlchemyProjects(session_factory)),
        lifecycle=project_lifecycle,
        overview=ProjectOverviewService(session_factory),
        statistics=ProjectStatisticsService(session_factory),
        automations=ProjectAutomationService(
            SqlAlchemyProjects(session_factory),
            SqlAlchemyProjectAutomations(session_factory),
            workflow_service=project_workflow_service,
            resource_query=automation_resources,
            capability_query=project_run_coordinator,
        ),
        tables=DataTableService(SqlAlchemyProjectData(session_factory)),
        catalog=DataCatalogService(SqlAlchemyProjectDataCatalog(session_factory)),
        records=DataRecordService(SqlAlchemyProjectDataRecords(session_factory)),
        queries=DataRecordQueryService(SqlAlchemyProjectDataQueries(session_factory)),
        deletions=DataDeletionService(SqlAlchemyProjectDataDeletions(session_factory)),
        schema=DataSchemaService(SqlAlchemyProjectDataSchema(session_factory)),
        status_batches=status_batch_service,
        excel=project_excel, imports=excel_imports, exports=excel_exports,
        environments=environment_service,
        sheets_connections=sheets_connections,
        sheets_bindings=sheets_bindings,
        sheets_impacts=sheets_impacts_service,
        sync=sheets_sync,
    ))

    @app.middleware("http")
    async def authenticate_api(request: Request, call_next):
        external_webhook = request.url.path.startswith("/api/triggers/webhook/")
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
        if request.url.path.startswith("/api/") and not external_webhook and (
            settings.instance_token is None
            or request.headers.get("x-autoflow-token") != settings.instance_token
        ):
            return error_response(
                401, "SIDECAR_UNAUTHORIZED", "本地服务认证失效，请重新连接"
            )
        guarded_get = request.method == "GET" and (
            request.url.path in {"/api/v1/kernels/catalog", "/api/v1/kernels/license"}
            or request.url.path.endswith("/models/discover")
        )
        guarded_request = request.url.path.startswith("/api/") and (
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
