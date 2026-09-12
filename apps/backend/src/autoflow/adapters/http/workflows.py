from dataclasses import asdict

from fastapi import APIRouter

from autoflow.application.workflows.service import WorkflowService
from autoflow.domain.workflows.catalog import node_catalog
from autoflow.domain.workflows.models import WorkflowRecord
from autoflow.domain.workflows.validation import workflow_issues

from .errors import browser_error_responses
from .workflow_schemas import (
    WorkflowCatalog,
    WorkflowList,
    WorkflowRead,
    WorkflowSummary,
    WorkflowUpdate,
    WorkflowWrite,
)


def workflows_router(service: WorkflowService) -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/workflows",
        tags=["workflows"],
        responses=browser_error_responses(401, 404, 409, 422, 500),
    )

    @router.get("/node-catalog", response_model=WorkflowCatalog)
    def catalog() -> WorkflowCatalog:
        return WorkflowCatalog.model_validate({"items": node_catalog()})

    @router.get("", response_model=WorkflowList)
    def list_workflows() -> WorkflowList:
        return WorkflowList(
            items=[
                WorkflowSummary(
                    id=record.document["id"],
                    name=record.document["name"],
                    revision=record.revision,
                    updated_at=record.updated_at,
                )
                for record in service.list()
            ]
        )

    @router.post("", response_model=WorkflowRead, status_code=201)
    def create(body: WorkflowWrite) -> WorkflowRead:
        return _read(
            service.create(
                body.document.model_dump(by_alias=True),
                body.layout.model_dump(by_alias=True),
            )
        )

    @router.get("/{workflow_id}", response_model=WorkflowRead)
    def get(workflow_id: str) -> WorkflowRead:
        return _read(service.get(workflow_id))

    @router.put("/{workflow_id}", response_model=WorkflowRead)
    def save(workflow_id: str, body: WorkflowUpdate) -> WorkflowRead:
        return _read(
            service.save(
                workflow_id,
                body.document.model_dump(by_alias=True),
                body.layout.model_dump(by_alias=True),
                body.expected_revision,
            )
        )

    return router


def _read(record: WorkflowRecord) -> WorkflowRead:
    return WorkflowRead.model_validate(
        {
            **asdict(record),
            "issues": [asdict(issue) for issue in workflow_issues(record.document)],
        }
    )
