"""Export route schemas without databases, workers, credentials or a listening app."""
import json
from dataclasses import fields
from typing import Any

from fastapi import FastAPI

from autoflow.adapters.http.openapi import configure_openapi
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
    projects = ProjectHttpServices(**{field.name: unavailable for field in fields(ProjectHttpServices)})
    register_project_routes(app, projects)
    workflows = WorkflowServices(
        documents=unavailable,
        modules=unavailable,
        runs=unavailable,
        commands=unavailable,
        events=unavailable,
    )
    register_workflow_routes(app, workflows)
    return app.openapi()


if __name__ == '__main__':
    print(json.dumps(export_schema(), ensure_ascii=False))
