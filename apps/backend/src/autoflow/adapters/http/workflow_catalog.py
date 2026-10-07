from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import Field

from autoflow.application.workflows.service import WorkflowService
from autoflow.domain.workflows.models import (
    WorkflowError,
    WorkflowRecord,
    canonical_json,
)
from autoflow.domain.workflows.run_validation import prepare_run
from autoflow.domain.workflows.signature import document_signature, parse_signature

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


class WorkflowSignatureField(ApiModel):
    key: str
    name: str
    type: Literal["string", "number", "boolean", "date", "any"]
    required: bool
    sensitive: bool
    # Remediation M5 5B-A3: optional example value; never returned for sensitive fields.
    sample: str | int | float | bool | None = None


class WorkflowSignatureInput(ApiModel):
    key: str
    name: str
    fields: list[WorkflowSignatureField]


class WorkflowSignature(ApiModel):
    inputs: list[WorkflowSignatureInput]


class WorkflowSignatureIssue(ApiModel):
    path: str
    message: str


class WorkflowCatalogItem(ApiModel):
    workflow_id: str
    name: str
    revision: int
    checksum: str
    browser_environment_version: int | None = None
    # Remediation M2 R2-18: the inputs a workflow needs, for binding automation data; None when undeclared.
    signature: WorkflowSignature | None = None
    # Why ``signature`` is None despite one being stored; empty when it parsed (or none is declared).
    signature_issues: list[WorkflowSignatureIssue] = Field(default_factory=list)
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
    signature, signature_issues = parse_signature(document_signature(record.document))
    return WorkflowCatalogItem(
        workflow_id=record.workflow_id,
        name=record.name,
        revision=record.revision,
        browser_environment_version=record.document.get("content", record.document).get("browserEnvironmentVersion"),
        checksum=hashlib.sha256(canonical_json(record.document).encode()).hexdigest(),
        signature=WorkflowSignature(inputs=[
            WorkflowSignatureInput(key=item.key, name=item.name, fields=[
                WorkflowSignatureField(key=field.key, name=field.name, type=field.type, required=field.required, sensitive=field.sensitive, sample=None if field.sensitive else field.sample)  # type: ignore[arg-type]
                for field in item.fields
            ])
            for item in signature.inputs
        ]) if signature is not None and not signature_issues else None,
        signature_issues=[WorkflowSignatureIssue(path=issue.path, message=issue.message) for issue in signature_issues],
        validation=WorkflowCatalogValidation(
            status="ready" if runnable else "blocked",
            runnable=runnable,
            issues=issues,
        ),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
