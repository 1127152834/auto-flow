from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from autoflow.application.settings.runtime import SettingsRuntimeService

from .errors import error_response


class RuntimePaths(BaseModel):
    workspace: str
    database: str
    profiles: str
    kernels: str
    logs: str


class RuntimeRead(BaseModel):
    apiVersion: str
    backendVersion: str
    pythonVersion: str
    sqliteVersion: str
    paths: RuntimePaths
    blockers: list[str]


class DashboardRead(BaseModel):
    profiles: int
    enabledProxies: int
    proxyGroups: int
    installedKernels: int
    modelProviders: int | None
    models: int | None
    generatedAt: datetime


class PauseRead(BaseModel):
    paused: bool


def settings_dashboard_router(service: SettingsRuntimeService) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/settings/runtime", response_model=RuntimeRead)
    def runtime() -> RuntimeRead:
        value = service.runtime()
        return RuntimeRead(
            apiVersion=value.api_version,
            backendVersion=value.backend_version,
            pythonVersion=value.python_version,
            sqliteVersion=value.sqlite_version,
            paths=RuntimePaths(**value.paths),
            blockers=list(value.blockers),
        )

    @router.get("/api/v1/dashboard", response_model=DashboardRead)
    def dashboard() -> DashboardRead:
        value = service.dashboard()
        return DashboardRead(
            profiles=value.profiles,
            enabledProxies=value.enabled_proxies,
            proxyGroups=value.proxy_groups,
            installedKernels=value.installed_kernels,
            modelProviders=value.model_providers,
            models=value.models,
            generatedAt=value.generated_at,
        )

    @router.post("/internal/settings/quiesce", include_in_schema=False)
    def quiesce():
        blockers = service.quiesce()
        if blockers:
            return error_response(409, "SETTINGS_QUIESCE_BLOCKED", "Service cannot pause while work is active", {"blockers": blockers})
        return PauseRead(paused=True)

    @router.post("/internal/settings/resume", response_model=PauseRead, include_in_schema=False)
    def resume() -> PauseRead:
        service.resume()
        return PauseRead(paused=False)

    return router
