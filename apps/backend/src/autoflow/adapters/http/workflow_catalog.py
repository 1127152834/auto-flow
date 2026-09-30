from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Query

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
    browser_environment_version: int | None = None
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
    def list_workflows(projectId: str | None = Query(default=None, min_length=1, max_length=200)) -> WorkflowCatalogList:
        records = service.list()
        if projectId is not None:
            records = [record for record in records if record.project_id == projectId]
        return WorkflowCatalogList(items=[_item(record) for record in records])

    @router.get("/{workflowId}", response_model=WorkflowCatalogDetail)
    def get_workflow(workflowId: str, projectId: str | None = Query(default=None, min_length=1, max_length=200)) -> WorkflowCatalogDetail:
        record = service.get(workflowId)
        if projectId is not None and record.project_id != projectId:
            raise WorkflowError("WORKFLOW_NOT_FOUND", "工作流不存在", 404)
        return WorkflowCatalogDetail.model_validate(_item(record).model_dump())

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
        browser_environment_version=record.document.get("content", record.document).get("browserEnvironmentVersion"),
        checksum=hashlib.sha256(canonical_json(record.document).encode()).hexdigest(),
        validation=WorkflowCatalogValidation(
            status="ready" if runnable else "blocked",
            runnable=runnable,
            issues=issues,
        ),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
