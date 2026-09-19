from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header, Query

from autoflow.application.project_runs.coordinator import ProjectRunCoordinator
from autoflow.application.project_runs.queries import ProjectRunQueries
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.settings.runtime import QuiesceGate
from autoflow.domain.project_runs.models import ProjectRunError

from .errors import browser_error_responses
from .project_run_schemas import (
    BatchDetail,
    BatchPage,
    BatchStartRequest,
    BatchStopRequest,
    FollowUpBatchRequest,
    InputPreviewRequest,
    InputPreviewResponse,
    ProjectRunOperationAccepted,
    TaskDetail,
    TaskPage,
)

Key = Annotated[UUID, Header(alias="Idempotency-Key")]


def project_runs_router(
    coordinator: ProjectRunCoordinator,
    queries: ProjectRunQueries,
    scheduler: ProjectBatchScheduler,
    gate: QuiesceGate,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}")

    @router.post(
        "/automations/{automationId}/batches",
        status_code=202,
        response_model=ProjectRunOperationAccepted,
        responses=browser_error_responses(401, 404, 409, 422, 423, 429, 503),
    )
    async def start_batch(
        projectId: UUID,
        automationId: UUID,
        body: BatchStartRequest,
        idempotency_key: Key,
    ):
        with gate.mutation() as admitted:
            if not admitted:
                raise ProjectRunError(
                    "SERVICE_UNAVAILABLE", "系统正在暂停写入，请稍后重试", 503
                )
            _batch, operation, _replayed = coordinator.start(
                str(projectId),
                str(automationId),
                str(idempotency_key),
                body.payload(),
            )
        scheduler.wake()
        return {"operation": _operation(operation)}

    @router.post(
        "/tasks/{taskId}/follow-up-batches",
        status_code=202,
        response_model=ProjectRunOperationAccepted,
        responses=browser_error_responses(401, 404, 409, 422, 423, 503),
    )
    async def follow_up_batch(
        projectId: UUID, taskId: UUID, body: FollowUpBatchRequest, idempotency_key: Key
    ):
        with gate.mutation() as admitted:
            if not admitted:
                raise ProjectRunError(
                    "SERVICE_UNAVAILABLE", "系统正在暂停写入，请稍后重试", 503
                )
            _batch, operation, _replayed = coordinator.follow_up(
                str(projectId),
                str(taskId),
                str(idempotency_key),
                body.payload(),
            )
        scheduler.wake()
        return {"operation": _operation(operation)}

    @router.post(
        "/automations/{automationId}/input-preview",
        response_model=InputPreviewResponse,
        responses=browser_error_responses(401, 404, 409, 422),
    )
    def preview_inputs(
        projectId: UUID, automationId: UUID, body: InputPreviewRequest
    ):
        return coordinator.preview_inputs(
            str(projectId),
            str(automationId),
            body.expected_automation_revision,
        )

    @router.post(
        "/batches/{batchId}/stop",
        status_code=202,
        response_model=ProjectRunOperationAccepted,
        responses=browser_error_responses(401, 404, 409, 422),
    )
    async def stop_batch(
        projectId: UUID, batchId: UUID, body: BatchStopRequest, idempotency_key: Key
    ):
        operation = await scheduler.stop(
            str(projectId),
            str(batchId),
            str(idempotency_key),
            body.model_dump(by_alias=True),
        )
        return {"operation": _operation(operation)}

    @router.post(
        "/batches/{batchId}/force-stop",
        status_code=202,
        response_model=ProjectRunOperationAccepted,
        responses=browser_error_responses(401, 404, 409, 422),
    )
    async def force_stop_batch(
        projectId: UUID, batchId: UUID, body: BatchStopRequest, idempotency_key: Key
    ):
        operation = await scheduler.stop(
            str(projectId),
            str(batchId),
            str(idempotency_key),
            body.model_dump(by_alias=True),
            force=True,
        )
        return {"operation": _operation(operation)}

    @router.get("/batches", response_model=BatchPage)
    def list_batches(
        projectId: UUID,
        q: Annotated[str | None, Query(max_length=120)] = None,
        automation_id: Annotated[UUID | None, Query(alias="automationId")] = None,
        status: str | None = None,
        started_from: Annotated[datetime | None, Query(alias="startedFrom")] = None,
        started_to: Annotated[datetime | None, Query(alias="startedTo")] = None,
        page: int = Query(1, ge=1, le=2_147_483_647),
        page_size: int = Query(50, alias="pageSize", ge=1, le=200),
        sort: str = "-createdAt",
    ):
        items, total = queries.list_batches(
            str(projectId),
            query_text=q,
            automation_id=str(automation_id) if automation_id else None,
            status=status,
            started_from=started_from,
            started_to=started_to,
            page=page,
            page_size=page_size,
            sort=sort,
        )
        return {
            "items": items,
            "page": page,
            "pageSize": page_size,
            "total": total,
            "sort": sort,
        }

    @router.get("/batches/{batchId}", response_model=BatchDetail)
    def get_batch(projectId: UUID, batchId: UUID):
        result = queries.batch_detail(str(projectId), str(batchId))
        allowed, available_at = scheduler.force_stop_availability(
            str(projectId), str(batchId)
        )
        return {
            **result,
            "forceStopAllowed": allowed,
            "forceStopAvailableAt": available_at,
        }

    @router.get("/tasks", response_model=TaskPage)
    def list_tasks(
        projectId: UUID,
        q: Annotated[str | None, Query(max_length=120)] = None,
        batch_id: Annotated[UUID | None, Query(alias="batchId")] = None,
        automation_id: Annotated[UUID | None, Query(alias="automationId")] = None,
        status: str | None = None,
        ended_from: Annotated[datetime | None, Query(alias="endedFrom")] = None,
        ended_to: Annotated[datetime | None, Query(alias="endedTo")] = None,
        page: int = Query(1, ge=1, le=2_147_483_647),
        page_size: int = Query(50, alias="pageSize", ge=1, le=200),
        sort: str = "-createdAt",
    ):
        items, total = queries.list_tasks(
            str(projectId),
            query_text=q,
            batch_id=str(batch_id) if batch_id else None,
            automation_id=str(automation_id) if automation_id else None,
            status=status,
            ended_from=ended_from,
            ended_to=ended_to,
            page=page,
            page_size=page_size,
            sort=sort,
        )
        return {
            "items": items,
            "page": page,
            "pageSize": page_size,
            "total": total,
            "sort": sort,
        }

    @router.get("/tasks/{taskId}", response_model=TaskDetail)
    def get_task(projectId: UUID, taskId: UUID):
        return queries.task_detail(str(projectId), str(taskId))

    return router


def _operation(value: Any) -> dict[str, Any]:
    return {
        "operationId": value.operation_id,
        "projectId": value.project_id,
        "idempotencyKey": value.idempotency_key,
        "kind": value.kind,
        "status": value.status,
        "statusRevision": value.status_revision,
        "resource": value.resource,
        "result": value.result,
        "error": value.error,
        "createdAt": value.created_at,
        "updatedAt": value.updated_at,
        "completedAt": value.completed_at,
    }
