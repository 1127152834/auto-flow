"""Batch progress and draft input matching (remediation M5 5B-A4, B7/B4). Both are read-only."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import JsonValue

from autoflow.application.project_runs.input_match import InputMatchService
from autoflow.application.project_runs.progress import BatchProgressService

from .errors import browser_error_responses
from .project_automation_schemas import InputPlan
from .schemas import ApiModel

FailureCode = Literal[
    "input_invalid", "business_failed", "page_error", "environment_error", "outcome_unknown", "cancelled", "unknown"
]


class LedgerCounts(ApiModel):
    total: int
    pending: int
    running: int
    succeeded: int
    failed_retryable: int
    quarantined: int
    needs_review: int
    skipped: int


class Throughput(ApiModel):
    window_minutes: int
    recent_per_minute: float
    average_per_minute: float
    eta_seconds: int | None


class RunningTaskSummary(ApiModel):
    task_id: str
    display_name: str | None
    identity_name: str | None
    current_node_name: str | None
    started_at: datetime | None
    elapsed_seconds: int | None


class FailureGroup(ApiModel):
    error_code: FailureCode
    count: int
    sample_message: str | None
    sample_unit_ids: list[str]


class BatchProgress(ApiModel):
    ledger: LedgerCounts
    throughput: Throughput
    running_tasks: list[RunningTaskSummary]
    failure_groups: list[FailureGroup]
    updated_at: datetime


class InputMatchRequest(ApiModel):
    input_plan: InputPlan


class InputMatchItem(ApiModel):
    input_id: str
    alias: str
    outcome: Literal["counted", "dependsOnOtherInput", "tableUnavailable", "filterInvalid"]
    matched_count: int | None
    unprocessed_count: int | None
    sample: list[dict[str, JsonValue]]


class InputMatchResponse(ApiModel):
    inputs: list[InputMatchItem]


def project_run_progress_router(progress: BatchProgressService, matching: InputMatchService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}")

    @router.get(
        "/batches/{batchId}/progress",
        response_model=BatchProgress,
        responses=browser_error_responses(401, 404),
    )
    async def batch_progress(projectId: UUID, batchId: UUID) -> dict[str, Any]:
        return await asyncio.to_thread(progress.progress, str(projectId), str(batchId))

    @router.post(
        "/automations/{automationId}/input-match",
        response_model=InputMatchResponse,
        responses=browser_error_responses(401, 404, 422),
    )
    async def input_match(projectId: UUID, automationId: UUID, body: InputMatchRequest) -> dict[str, Any]:
        plan = body.input_plan.model_dump(by_alias=True, exclude_unset=True)
        return await asyncio.to_thread(matching.match, str(projectId), str(automationId), plan)

    return router
