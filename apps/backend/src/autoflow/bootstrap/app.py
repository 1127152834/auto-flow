import secrets
from functools import partial
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from autoflow.adapters.events.kernels import kernels_events_router
from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.health import health_router
from autoflow.adapters.http.openapi import configure_openapi
from autoflow.adapters.http.profiles import profiles_router
from autoflow.adapters.http.proxy_options import proxy_options_router
from autoflow.application.profiles.service import ProfileService
from autoflow.bootstrap.config import Settings
from autoflow.bootstrap.proxies import configure_proxy_management
from autoflow.domain.profiles.ports import (
    InstalledKernelLookup,
    ProfileDataStore,
    ProfileUsageGuard,
)
from autoflow.infrastructure.database.kernel_operations import (
    SqlAlchemyKernelOperationRepository,
)
from autoflow.infrastructure.database.profiles import profile_repository_transaction
from autoflow.infrastructure.database.proxy_options import SqlAlchemyProxyOptions
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.events.kernel_events import KernelEventBroker
from autoflow.infrastructure.filesystem.paths import AppPaths
from autoflow.infrastructure.filesystem.profile_data import (
    FilesystemProfileDataStore,
    FilesystemProfileUsageGuard,
)
from autoflow.infrastructure.process.kernel_worker import KernelWorkerManager


class _NoInstalledKernels:
    def is_installed(self, edition: str, version: str) -> bool:
        return False


def create_app(
    settings: Settings,
    *,
    installed_kernel_lookup: InstalledKernelLookup | None = None,
    profile_data_store: ProfileDataStore | None = None,
    profile_usage_guard: ProfileUsageGuard | None = None,
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
    transaction = partial(profile_repository_transaction, session_factory)
    proxy_options = SqlAlchemyProxyOptions(session_factory)
    data_store = profile_data_store or FilesystemProfileDataStore(paths.profiles)
    usage_guard = profile_usage_guard or FilesystemProfileUsageGuard(paths.profiles)
    data_store.retry_pending(lambda profile_id: _profile_exists(transaction, profile_id))
    profile_service = ProfileService(
        transaction,
        installed_kernel_lookup or _NoInstalledKernels(),
        proxy_options,
        usage_guard,
        data_store,
    )

    app = FastAPI()
    configure_openapi(app, api_version=settings.api_version)
    install_error_handlers(app)
    app.state.paths = paths
    app.state.session_factory = session_factory
    app.state.profile_service = profile_service
    app.state.kernel_worker_manager = kernel_worker_manager
    close_proxies = configure_proxy_management(app, paths.database)

    async def shutdown() -> None:
        try:
            await kernel_worker_manager.shutdown()
        finally:
            try:
                close_proxies()
            finally:
                session_factory.dispose()

    app.router.add_event_handler("shutdown", shutdown)
    app.include_router(health_router(api_version=settings.api_version, instance_id=settings.instance_id))
    app.include_router(profiles_router(profile_service))
    app.include_router(proxy_options_router(proxy_options))
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
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
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
