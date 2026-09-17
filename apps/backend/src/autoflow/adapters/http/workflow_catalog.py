from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter

from autoflow.application.workflows.service import WorkflowService
from autoflow.domain.workflows.models import (
    WorkflowError,
    WorkflowRecord,
    canonical_json,
)
from autoflow.domain.workflows.run_validation import prepare_run

from .errors import browser_error_responses
from .schemas import ApiModel


class WorkflowCatalogIssue(ApiModel):
    node_id: str | None
    path: list[str]
    code: str
    message: str


class WorkflowCatalogValidation(ApiModel):
    status: Literal["ready", "blocked"]
    runnable: bool
    issues: list[WorkflowCatalogIssue]


class WorkflowCatalogItem(ApiModel):
    workflow_id: str
    name: str
    revision: int
    checksum: str
    validation: WorkflowCatalogValidation
    created_at: datetime
    updated_at: datetime


class WorkflowCatalogList(ApiModel):
    items: list[WorkflowCatalogItem]


class WorkflowCatalogDetail(WorkflowCatalogItem):
    pass


def workflow_catalog_router(service: WorkflowService) -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/workflows",
        tags=["workflow-catalog"],
        responses=browser_error_responses(401, 404, 422),
    )

    @router.get("", response_model=WorkflowCatalogList)
    def list_workflows() -> WorkflowCatalogList:
        return WorkflowCatalogList(items=[_item(record) for record in service.list()])

    @router.get("/{workflowId}", response_model=WorkflowCatalogDetail)
    def get_workflow(workflowId: UUID) -> WorkflowCatalogDetail:
        return WorkflowCatalogDetail.model_validate(
            _item(service.get(str(workflowId))).model_dump()
        )

    return router


def _item(record: WorkflowRecord) -> WorkflowCatalogItem:
    issues = []
    try:
        prepare_run(record.document)
    except WorkflowError as error:
        issues = [
            WorkflowCatalogIssue(
                node_id=issue.node_id,
                path=issue.path,
                code=issue.code,
                message=issue.message,
            )
            for issue in error.issues
        ] or [
            WorkflowCatalogIssue(
                node_id=None,
                path=[],
                code=error.code,
                message=error.message,
            )
        ]
    runnable = not issues
    return WorkflowCatalogItem(
        workflow_id=record.workflow_id,
        name=record.name,
        revision=record.revision,
        checksum=hashlib.sha256(canonical_json(record.document).encode()).hexdigest(),
        validation=WorkflowCatalogValidation(
            status="ready" if runnable else "blocked",
            runnable=runnable,
            issues=issues,
        ),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
