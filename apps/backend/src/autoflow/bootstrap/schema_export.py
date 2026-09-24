"""Export route schemas without databases, workers, credentials or a listening app."""
import json
from dataclasses import fields
from typing import Any

from fastapi import FastAPI

from autoflow.adapters.http.android import android_router
from autoflow.adapters.http.android_fleet import android_fleet_router
from autoflow.adapters.http.android_management import android_management_router
from autoflow.adapters.http.image_assets import image_assets_router
from autoflow.adapters.http.laya_lab import laya_lab_router
from autoflow.adapters.http.local_workflows import local_workflows_router
from autoflow.adapters.http.openapi import configure_openapi
from autoflow.adapters.http.studio_credentials import studio_credentials_router
from autoflow.adapters.http.studio_retention import studio_retention_router
from autoflow.adapters.http.workflow_bundles import workflow_bundles_router
from autoflow.adapters.http.workflow_catalog import workflow_catalog_router
from autoflow.adapters.http.workflow_schedules import workflow_schedules_router
from autoflow.application.lab.service import LayaService
from autoflow.bootstrap.http_routes import (
    ManagementHttpServices,
    ProxyHttpServices,
    register_management_routes,
    register_proxy_routes,
)
from autoflow.bootstrap.project_http_routes import (
    ProjectHttpServices,
    register_project_routes,
)
from autoflow.bootstrap.workflows import WorkflowServices, register_workflow_routes


class _UnavailableService:
    async def startup(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    def __getattr__(self, name: str) -> Any:
        raise RuntimeError(f'Schema registration attempted a business operation: {name}')

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError('Schema registration attempted a business callback')


def export_schema(*, api_version: str = 'v1') -> dict[str, Any]:
    # These dependencies only bind route closures. Any attempt to call them fails;
    # the schema-only app is never served and no fake business data is returned.
    unavailable: Any = _UnavailableService()
    proxies = ProxyHttpServices(**{field.name: unavailable for field in fields(ProxyHttpServices)})
    management = ManagementHttpServices(**{field.name: unavailable for field in fields(ManagementHttpServices)})
    app = FastAPI()
    configure_openapi(app, api_version=api_version)
    register_proxy_routes(app, proxies)
    register_management_routes(app, management, api_version=api_version, instance_id='schema-export')
    app.include_router(laya_lab_router(LayaService(unavailable)))
    app.include_router(workflow_catalog_router(unavailable))
    projects = ProjectHttpServices(**{field.name: unavailable for field in fields(ProjectHttpServices)})
    register_project_routes(app, projects)
    workflows = WorkflowServices(
        documents=unavailable,
        modules=unavailable,
        runs=unavailable,
        commands=unavailable,
        events=unavailable,
        inspection=unavailable,
        assistant=unavailable,
        mcp=unavailable,
        gestures=unavailable,
        event_commands=unavailable,
    )
    register_workflow_routes(app, workflows)
    app.include_router(android_router(unavailable))
    app.include_router(android_management_router(unavailable, unavailable, unavailable, unavailable, unavailable, unavailable, unavailable, unavailable, unavailable))
    app.include_router(android_fleet_router(unavailable, unavailable))
    app.include_router(local_workflows_router(unavailable, unavailable))
    app.include_router(image_assets_router(unavailable))
    app.include_router(workflow_bundles_router(unavailable))
    app.include_router(studio_credentials_router(unavailable))
    app.include_router(studio_retention_router(unavailable))
    app.include_router(workflow_schedules_router(unavailable))
    return app.openapi()


if __name__ == '__main__':
    print(json.dumps(export_schema()))
