"""Shared route registration for the runtime and schema-only export."""
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import FastAPI

from autoflow.adapters.events.kernels import kernels_events_router
from autoflow.adapters.http.health import health_router
from autoflow.adapters.http.internal_proxy_credentials import (
    CopyCredentialRequest,
    internal_proxy_credentials_router,
)
from autoflow.adapters.http.kernels import internal_kernel_paths_router, kernels_router
from autoflow.adapters.http.models import models_router
from autoflow.adapters.http.profiles import profiles_router
from autoflow.adapters.http.proxies import proxy_router
from autoflow.adapters.http.proxy_options import proxy_options_router
from autoflow.adapters.http.proxy_remote import proxy_remote_router
from autoflow.adapters.http.settings_dashboard import settings_dashboard_router
from autoflow.application.kernels.operations import KernelOperation
from autoflow.application.kernels.service import KernelService
from autoflow.application.models.service import ModelService
from autoflow.application.profiles.service import ProfileService
from autoflow.application.profiles.test_browser import ProfileTestBrowserService
from autoflow.application.proxies.facade import ProxyApplication
from autoflow.application.proxies.remote_controls import ProxyRemoteControls
from autoflow.application.settings.runtime import SettingsRuntimeService
from autoflow.domain.profiles.ports import ProfileEnvironmentOptions, ProxyOptionsLookup
from autoflow.infrastructure.events.kernel_events import KernelEventBroker


@dataclass(frozen=True)
class ManagementHttpServices:
    profiles: ProfileService
    environment_options: Callable[[], ProfileEnvironmentOptions]
    test_browsers: ProfileTestBrowserService
    proxy_options: ProxyOptionsLookup
    models: ModelService
    kernels: KernelService
    settings: SettingsRuntimeService
    kernel_events: KernelEventBroker
    kernel_snapshot: Callable[[], list[KernelOperation]]


@dataclass(frozen=True)
class ProxyHttpServices:
    application: ProxyApplication
    remote: ProxyRemoteControls
    credential_copy: Callable[[CopyCredentialRequest], str | Awaitable[str]]


def register_proxy_routes(app: FastAPI, services: ProxyHttpServices) -> None:
    app.include_router(proxy_router(services.application))
    app.include_router(proxy_remote_router(services.remote))
    app.include_router(internal_proxy_credentials_router(services.credential_copy))


def register_management_routes(
    app: FastAPI, services: ManagementHttpServices, *, api_version: str, instance_id: str
) -> None:
    app.include_router(health_router(api_version=api_version, instance_id=instance_id))
    app.include_router(profiles_router(services.profiles, services.environment_options, services.test_browsers))
    app.include_router(proxy_options_router(services.proxy_options))
    app.include_router(models_router(services.models))
    app.include_router(kernels_router(services.kernels))
    app.include_router(internal_kernel_paths_router(services.kernels))
    app.include_router(settings_dashboard_router(services.settings))
    app.include_router(kernels_events_router(services.kernel_events, services.kernel_snapshot))
