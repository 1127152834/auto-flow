from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, Query

from autoflow.application.environments.service import EnvironmentService

from .errors import browser_error_responses
from .project_environment_schemas import (
    EnvironmentDeleteRequest,
    EnvironmentDetailView,
    EnvironmentEndRequest,
    EnvironmentImpactView,
    EnvironmentInstancePage,
    EnvironmentInstanceView,
    EnvironmentOpenRequest,
    EnvironmentOperationView,
    EnvironmentPage,
    EnvironmentPatch,
    EnvironmentRepairRequest,
    EnvironmentSaveRequest,
    EnvironmentView,
    MaintenanceDiscardRequest,
    MaintenanceStartRequest,
    ManualFinishRequest,
    ManualItemPage,
    ManualItemView,
    ManualResumeRequest,
)
from .projects import _op

Key = Annotated[UUID, Header(alias="Idempotency-Key")]


def project_environments_router(service: EnvironmentService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}")

    @router.get(
        "/environments",
        response_model=EnvironmentPage,
        responses=browser_error_responses(401, 404, 422),
    )
    def list_environments(
        projectId: UUID,
        state: str | None = None,
        q: str | None = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(50, alias="pageSize", ge=1, le=200),
        sort: str = "-updatedAt",
    ):
        items, total, linked = service.list_with_counts(
            str(projectId), state=state, q=q, page=page, page_size=page_size, sort=sort
        )
        return {
            "items": [
                {
                    **item.to_dict(),
                    "linkedRecordCount": linked.get(item.ref.environment_id, 0),
                }
                for item in items
            ],
            "page": page,
            "pageSize": page_size,
            "total": total,
            "sort": sort,
        }

    @router.get(
        "/environments/{environmentId}",
        response_model=EnvironmentDetailView,
        responses=browser_error_responses(401, 404, 422),
    )
    def get_environment(projectId: UUID, environmentId: UUID):
        environment, instance, linked = service.get(str(projectId), str(environmentId))
        return {
            "environment": environment.to_dict(),
            "activeInstance": instance.to_dict() if instance else None,
            "linkedRecordCount": linked,
        }

    @router.get(
        "/environments/{environmentId}/impact",
        response_model=EnvironmentImpactView,
        responses=browser_error_responses(401, 404, 422),
    )
    def environment_impact(projectId: UUID, environmentId: UUID, action: str = "delete"):
        return service.impact(str(projectId), str(environmentId), action)

    @router.delete(
        "/environments/{environmentId}",
        status_code=202,
        response_model=EnvironmentOperationView,
        responses=browser_error_responses(401, 404, 409, 412, 422, 423),
    )
    def delete_environment(
        projectId: UUID,
        environmentId: UUID,
        body: EnvironmentDeleteRequest,
        idempotency_key: Key,
    ):
        _result, operation = service.delete(
            str(projectId), str(environmentId), str(idempotency_key), body.payload()
        )
        return {"operation": _op(operation), "outcome": None}

    @router.patch(
        "/environments/{environmentId}",
        response_model=EnvironmentView,
        responses=browser_error_responses(401, 404, 409, 422, 423),
    )
    def patch_environment(
        projectId: UUID,
        environmentId: UUID,
        body: EnvironmentPatch,
        idempotency_key: Key,
    ):
        environment, _operation, _replayed = service.patch(
            str(projectId), str(environmentId), str(idempotency_key), body.payload()
        )
        return environment.to_dict()

    @router.get(
        "/environment-instances",
        response_model=EnvironmentInstancePage,
        responses=browser_error_responses(401, 404, 422),
    )
    def list_instances(
        projectId: UUID,
        state: str | None = None,
        task_id: Annotated[str | None, Query(alias="taskId")] = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(50, alias="pageSize", ge=1, le=200),
        sort: str = "-updatedAt",
    ):
        items, total = service.list_instances(
            str(projectId), state=state, task_id=task_id, page=page, page_size=page_size
        )
        return {
            "items": [item.to_dict() for item in items],
            "page": page,
            "pageSize": page_size,
            "total": total,
            "sort": sort,
        }

    @router.get(
        "/environment-instances/{instanceId}",
        response_model=EnvironmentInstanceView,
        responses=browser_error_responses(401, 404, 422),
    )
    def get_instance(projectId: UUID, instanceId: UUID):
        return service.get_instance(str(projectId), str(instanceId)).to_dict()

    @router.post(
        "/environment-instances/{instanceId}/open",
        status_code=202,
        response_model=EnvironmentOperationView,
        responses=browser_error_responses(401, 404, 409, 422, 423, 429),
    )
    def open_instance(
        projectId: UUID,
        instanceId: UUID,
        body: EnvironmentOpenRequest,
        idempotency_key: Key,
    ):
        outcome, operation, _replayed = service.open_instance(
            str(projectId), str(instanceId), str(idempotency_key), body.payload()
        )
        return {"operation": _op(operation), "outcome": outcome}

    @router.post(
        "/environment-saves",
        status_code=202,
        response_model=EnvironmentOperationView,
        responses=browser_error_responses(401, 404, 409, 410, 422, 423),
    )
    def save_environment(
        projectId: UUID, body: EnvironmentSaveRequest, idempotency_key: Key
    ):
        outcome, operation, _replayed = service.save(
            str(projectId), str(idempotency_key), body.payload()
        )
        return {"operation": _op(operation), "outcome": outcome}

    @router.post(
        "/tasks/{taskId}/end",
        status_code=202,
        response_model=EnvironmentOperationView,
        responses=browser_error_responses(401, 404, 409, 410, 422, 423),
    )
    def end_task(
        projectId: UUID,
        taskId: UUID,
        body: EnvironmentEndRequest,
        idempotency_key: Key,
    ):
        payload = body.payload()
        payload["taskId"] = str(taskId)
        outcome, operation, _replayed = service.end(
            str(projectId), str(idempotency_key), payload
        )
        return {"operation": _op(operation), "outcome": outcome}

    @router.post(
        "/environments/{environmentId}/maintenance",
        status_code=202,
        response_model=EnvironmentOperationView,
        responses=browser_error_responses(401, 404, 409, 422, 423),
    )
    def start_maintenance(
        projectId: UUID,
        environmentId: UUID,
        body: MaintenanceStartRequest,
        idempotency_key: Key,
    ):
        outcome, operation, _replayed = service.start_maintenance(
            str(projectId),
            str(environmentId),
            str(idempotency_key),
            body.expected_content_generation,
        )
        return {"operation": _op(operation), "outcome": outcome}

    @router.post(
        "/environments/{environmentId}/maintenance/discard",
        status_code=202,
        response_model=EnvironmentOperationView,
        responses=browser_error_responses(401, 404, 409, 422),
    )
    def discard_maintenance(
        projectId: UUID,
        environmentId: UUID,
        body: MaintenanceDiscardRequest,
        idempotency_key: Key,
    ):
        outcome, operation, _replayed = service.discard_maintenance(
            str(projectId),
            str(idempotency_key),
            body.instance_id,
            body.maintenance_operation_id,
        )
        return {"operation": _op(operation), "outcome": outcome}

    @router.post(
        "/environment-operations/{operationId}/repair",
        status_code=202,
        response_model=EnvironmentOperationView,
        responses=browser_error_responses(401, 404, 409, 422),
    )
    def repair_end(
        projectId: UUID,
        operationId: UUID,
        body: EnvironmentRepairRequest,
        idempotency_key: Key,
    ):
        outcome, operation, _replayed = service.repair(
            str(projectId), str(idempotency_key), str(operationId), body.payload()
        )
        return {"operation": _op(operation), "outcome": outcome}

    @router.get(
        "/environment-operations/{operationId}",
        response_model=EnvironmentOperationView,
        responses=browser_error_responses(401, 404, 422),
    )
    def get_environment_operation(projectId: UUID, operationId: UUID):
        operation = service.projects.operation(
            operation_id=str(operationId), project_id=str(projectId)
        )
        return {"operation": _op(operation), "outcome": operation.result}

    @router.get(
        "/manual-items",
        response_model=ManualItemPage,
        responses=browser_error_responses(401, 404, 422),
    )
    def list_manual_items(
        projectId: UUID,
        status: str | None = None,
        q: str | None = Query(None, max_length=120),
        sort: Literal["-updatedAt", "expiresAt"] = "-updatedAt",
        page: int = Query(1, ge=1),
        page_size: int = Query(50, alias="pageSize", ge=1, le=200),
    ):
        items, total = service.list_manual(
            str(projectId),
            status=status,
            q=q,
            sort=sort,
            page=page,
            page_size=page_size,
        )
        return {
            "items": items,
            "page": page,
            "pageSize": page_size,
            "total": total,
        }

    @router.get(
        "/manual-items/{manualItemId}",
        response_model=ManualItemView,
        responses=browser_error_responses(401, 404, 422),
    )
    def get_manual_item(projectId: UUID, manualItemId: UUID):
        return service.get_manual(str(projectId), str(manualItemId))

    @router.post(
        "/manual-items/{manualItemId}/resume",
        status_code=202,
        response_model=EnvironmentOperationView,
        responses=browser_error_responses(401, 404, 409, 422),
    )
    def resume_manual_item(
        projectId: UUID,
        manualItemId: UUID,
        body: ManualResumeRequest,
        idempotency_key: Key,
    ):
        outcome, operation, _replayed = service.resume_manual(
            str(projectId),
            str(idempotency_key),
            str(manualItemId),
            {
                "checkpointRevision": body.checkpoint_revision,
                "expectedStatusRevision": body.expected_status_revision,
                "targetNodeId": body.target_node_id,
                "inputs": body.inputs,
            },
        )
        return {"operation": _op(operation), "outcome": outcome}

    @router.post(
        "/manual-items/{manualItemId}/finish",
        status_code=202,
        response_model=EnvironmentOperationView,
        responses=browser_error_responses(401, 404, 409, 422),
    )
    def finish_manual_item(
        projectId: UUID,
        manualItemId: UUID,
        body: ManualFinishRequest,
        idempotency_key: Key,
    ):
        outcome, operation, _replayed = service.finish_manual(
            str(projectId),
            str(idempotency_key),
            str(manualItemId),
            {
                "expectedCheckpointRevision": body.expected_checkpoint_revision,
                "expectedStatusRevision": body.expected_status_revision,
                "outcome": body.outcome,
                "reason": body.reason,
                "retainEnvironment": body.retain_environment,
            },
        )
        return {"operation": _op(operation), "outcome": outcome}

    return router
