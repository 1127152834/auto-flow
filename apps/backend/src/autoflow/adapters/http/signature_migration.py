"""Workflow signature migration report and apply (remediation M2 R2-22)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Query

from autoflow.application.workflows.signature_migration import SignatureMigration

from .errors import browser_error_responses
from .schemas import ApiModel


class SignatureMigrationItem(ApiModel):
    workflow_id: str
    workflow_name: str
    automation_ids: list[str]
    status: Literal["migrated", "notNeeded", "ambiguous", "migratable", "partial"]
    reason: str
    legacy_references: int
    rewritten: int | None = None
    remaining: int | None = None


def signature_migration_router(service: SignatureMigration) -> APIRouter:
    router = APIRouter(prefix="/api/v1/migrations")
    responses = browser_error_responses(401, 409)

    @router.get("/signature-report", response_model=list[SignatureMigrationItem], response_model_exclude_unset=True, responses=responses)
    def signature_report() -> list[dict[str, Any]]:
        return service.report()

    @router.post("/signature", response_model=list[SignatureMigrationItem], response_model_exclude_unset=True, responses=responses)
    def apply_signature_migration(workflowId: str | None = Query(default=None, min_length=1, max_length=200)) -> list[dict[str, Any]]:
        # Re-entrant: a second call finds nothing left to change. workflowId limits it to one workflow.
        return service.apply(workflowId)

    return router
