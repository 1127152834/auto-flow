"""Google Sheets transport. Ownership, transactions and network calls stay in services."""

import hmac
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, Response
from pydantic import BeforeValidator

from autoflow.application.project_sync.bindings import SheetsBindingService
from autoflow.application.project_sync.connections import SheetsConnectionService
from autoflow.application.project_sync.outbound import SheetsSyncService
from autoflow.domain.projects.models import ProjectError

from .errors import browser_error_responses
from .project_data_impact_schemas import SheetsImpactReport
from .project_schemas import OperationAccepted
from .project_sheets_schemas import (
    GoogleAuthorization,
    GoogleAuthorizationCreate,
    SheetsBinding,
    SheetsBindingDelete,
    SheetsBindingWrite,
    SheetsConnectionCreate,
    SheetsConnectionDelete,
    SheetsConnectionDirectory,
    SheetsIdentityVerification,
    SheetsInspectionCreate,
    SheetsInspectionResult,
    SourceRecordObservations,
    SyncAbandonRequest,
    SyncOperation,
    SyncOperationPage,
    SyncPauseRequest,
    SyncPullRequest,
    SyncPushRequest,
    SyncStateView,
    SyncStatusRevisionRequest,
)


def _canonical_uuid(value: object) -> object:
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError("Must be a canonical lowercase UUID")
    return value


CanonicalId = Annotated[UUID, BeforeValidator(_canonical_uuid)]
Key = Annotated[CanonicalId, Header(alias="Idempotency-Key")]


def internal_google_authorizations_router(
    service: SheetsConnectionService,
) -> APIRouter:
    """Host only handover of Google credentials; never reachable from a page."""

    router = APIRouter(prefix="/internal/google-authorizations", include_in_schema=False)

    @router.post("", status_code=201, response_model=GoogleAuthorization)
    def register_authorization(
        body: GoogleAuthorizationCreate,
        request: Request,
        x_autoflow_host_token: str = Header(alias="x-autoflow-host-token"),
    ):
        expected = getattr(request.app.state.config, "host_token", None)
        if not expected or not hmac.compare_digest(x_autoflow_host_token, expected):
            raise ProjectError("UNAUTHORIZED", "Host authentication failed", 401)
        return service.register_authorization(body.model_dump(by_alias=True))

    return router


def project_sheets_connections_router(service: SheetsConnectionService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}/sheets")

    @router.get(
        "/connections",
        response_model=SheetsConnectionDirectory,
        response_model_exclude_none=True,
        responses=browser_error_responses(401, 404, 422),
    )
    def list_connections(projectId: CanonicalId):
        return service.list_connections(str(projectId))

    @router.post(
        "/connections",
        status_code=202,
        response_model=OperationAccepted,
        responses=browser_error_responses(401, 404, 409, 422),
    )
    def create_connection(
        projectId: CanonicalId, body: SheetsConnectionCreate, idempotency_key: Key
    ):
        return service.create_connection(
            str(projectId), str(idempotency_key), body.model_dump(by_alias=True)
        )

    @router.delete(
        "/connections/{connectionId}",
        status_code=202,
        response_model=OperationAccepted,
        responses=browser_error_responses(401, 404, 409, 412, 422),
    )
    def delete_connection(
        projectId: CanonicalId,
        connectionId: CanonicalId,
        body: SheetsConnectionDelete,
        idempotency_key: Key,
    ):
        return service.delete_connection(
            str(projectId),
            str(connectionId),
            str(idempotency_key),
            body.model_dump(by_alias=True),
        )

    return router


def project_sheets_binding_router(service: SheetsBindingService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}/tables/{tableId}")

    @router.post(
        "/sheets/inspect",
        response_model=SheetsInspectionResult | OperationAccepted,
        responses={202: {"model": OperationAccepted}},
    )
    def inspect(
        projectId: CanonicalId,
        tableId: CanonicalId,
        body: SheetsInspectionCreate,
        response: Response,
        idempotency_key: Key,
    ):
        result = service.inspect(
            str(projectId),
            str(tableId),
            str(idempotency_key),
            body.model_dump(by_alias=True),
        )
        if "inspection" not in result:
            response.status_code = 202
        return result

    @router.put(
        "/sheets/binding",
        status_code=202,
        response_model=OperationAccepted,
        responses=browser_error_responses(401, 404, 409, 412, 422),
    )
    def put_binding(
        projectId: CanonicalId,
        tableId: CanonicalId,
        body: SheetsBindingWrite,
        idempotency_key: Key,
    ):
        return service.put_binding(
            str(projectId),
            str(tableId),
            str(idempotency_key),
            body.model_dump(by_alias=True),
        )

    @router.post("/sheets/system-identity", status_code=202, response_model=OperationAccepted,
                 responses=browser_error_responses(401, 404, 409, 412, 422))
    def initialize_identity(projectId: CanonicalId, tableId: CanonicalId, body: SheetsBindingWrite, idempotency_key: Key):
        return service.initialize_identity(str(projectId), str(tableId), str(idempotency_key), body.model_dump(by_alias=True))

    @router.post("/sheets/system-identity/{operationId}/preview", response_model=SheetsImpactReport)
    def preview_identity(projectId: CanonicalId, tableId: CanonicalId, operationId: CanonicalId):
        return service.preview_identity(str(projectId), str(tableId), str(operationId))

    @router.post("/sheets/system-identity/{operationId}/retry", status_code=202, response_model=OperationAccepted)
    def retry_identity(projectId: CanonicalId, tableId: CanonicalId, operationId: CanonicalId, body: SheetsIdentityVerification | None = None):
        return service.retry_identity(str(projectId), str(tableId), str(operationId), body.model_dump(by_alias=True) if body else None)

    @router.post("/sheets/system-identity/{operationId}/verify", status_code=202, response_model=OperationAccepted,
                 responses=browser_error_responses(401, 404, 409, 412, 422))
    def verify_identity(projectId: CanonicalId, tableId: CanonicalId, operationId: CanonicalId, body: SheetsIdentityVerification | None = None):
        return service.verify_identity(str(projectId), str(tableId), str(operationId), body.model_dump(by_alias=True) if body else None)

    @router.delete(
        "/sheets/binding",
        status_code=202,
        response_model=OperationAccepted,
        responses=browser_error_responses(401, 404, 409, 412, 422),
    )
    def delete_binding(
        projectId: CanonicalId,
        tableId: CanonicalId,
        body: SheetsBindingDelete,
        idempotency_key: Key,
    ):
        return service.delete_binding(
            str(projectId),
            str(tableId),
            str(idempotency_key),
            body.model_dump(by_alias=True),
        )

    @router.get(
        "/sheets/binding",
        response_model=SheetsBinding | None,
        response_model_exclude_none=True,
        responses=browser_error_responses(401, 404, 422),
    )
    def read_binding(projectId: CanonicalId, tableId: CanonicalId):
        return service.read_binding(str(projectId), str(tableId))

    return router


def project_sync_router(service: SheetsSyncService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}/tables/{tableId}")

    @router.get(
        "/sync",
        response_model=SyncStateView,
        response_model_exclude_none=True,
        responses=browser_error_responses(401, 404, 422),
    )
    def sync_state(projectId: CanonicalId, tableId: CanonicalId):
        return service.state(str(projectId), str(tableId))

    @router.get(
        "/records/{recordKey}/source-observations",
        response_model=SourceRecordObservations,
        responses=browser_error_responses(401, 404, 410, 422),
    )
    def source_observations(
        projectId: CanonicalId, tableId: CanonicalId, recordKey: str,
        dataset_generation: Annotated[CanonicalId, Query(alias="datasetGeneration")],
        record_key_type: Annotated[Literal["text", "integer", "uuid"], Query(alias="recordKeyType")],
    ):
        return service.source_observations(str(projectId), str(tableId), str(dataset_generation), recordKey, record_key_type)

    @router.post(
        "/sync/pull",
        status_code=202,
        response_model=OperationAccepted,
        responses=browser_error_responses(401, 404, 409, 412, 422),
    )
    def pull(
        projectId: CanonicalId,
        tableId: CanonicalId,
        body: SyncPullRequest,
        idempotency_key: Key,
    ):
        return service.pull(
            str(projectId),
            str(tableId),
            str(idempotency_key),
            body.model_dump(by_alias=True),
        )

    @router.post(
        "/sync/push",
        status_code=202,
        response_model=OperationAccepted,
        responses=browser_error_responses(401, 404, 409, 412, 422),
    )
    def push(
        projectId: CanonicalId,
        tableId: CanonicalId,
        body: SyncPushRequest,
        idempotency_key: Key,
    ):
        return service.push(
            str(projectId),
            str(tableId),
            str(idempotency_key),
            body.model_dump(by_alias=True),
        )

    @router.post(
        "/sync/pause",
        response_model=SyncStateView,
        response_model_exclude_none=True,
        responses=browser_error_responses(401, 404, 409, 412, 422),
    )
    def pause(
        projectId: CanonicalId,
        tableId: CanonicalId,
        body: SyncPauseRequest,
        idempotency_key: Key,
    ):
        return service.pause(
            str(projectId),
            str(tableId),
            str(idempotency_key),
            body.model_dump(by_alias=True),
        )

    @router.post(
        "/sync/resume",
        response_model=SyncStateView,
        response_model_exclude_none=True,
        responses=browser_error_responses(401, 404, 409, 412, 422),
    )
    def resume(
        projectId: CanonicalId,
        tableId: CanonicalId,
        body: SyncPauseRequest,
        idempotency_key: Key,
    ):
        return service.resume(
            str(projectId),
            str(tableId),
            str(idempotency_key),
            body.model_dump(by_alias=True),
        )

    @router.get(
        "/sync-operations",
        response_model=SyncOperationPage,
        response_model_exclude_none=True,
        responses=browser_error_responses(401, 404, 422),
    )
    def list_operations(
        projectId: CanonicalId,
        tableId: CanonicalId,
        status: Literal[
            "pending",
            "sending",
            "verifying",
            "confirmed",
            "failed",
            "unknown",
            "paused",
        ]
        | None = None,
        page: int = Query(1, ge=1, le=2_147_483_647),
        page_size: int = Query(50, alias="pageSize", ge=1, le=200),
    ):
        return service.list_operations(
            str(projectId), str(tableId), status, page, page_size
        )

    @router.get(
        "/sync-operations/{syncOperationId}",
        response_model=SyncOperation,
        response_model_exclude_none=True,
        responses=browser_error_responses(401, 404, 422),
    )
    def read_operation(
        projectId: CanonicalId, tableId: CanonicalId, syncOperationId: CanonicalId
    ):
        return service.read_operation(
            str(projectId), str(tableId), str(syncOperationId)
        )

    @router.post(
        "/sync-operations/{syncOperationId}/reconcile",
        status_code=202,
        response_model=OperationAccepted,
        responses=browser_error_responses(401, 404, 409, 412, 422),
    )
    def reconcile(
        projectId: CanonicalId,
        tableId: CanonicalId,
        syncOperationId: CanonicalId,
        body: SyncStatusRevisionRequest,
        idempotency_key: Key,
    ):
        return service.reconcile(
            str(projectId),
            str(tableId),
            str(syncOperationId),
            str(idempotency_key),
            body.model_dump(by_alias=True),
        )

    @router.post(
        "/sync-operations/{syncOperationId}/abandon",
        response_model=SyncOperation,
        response_model_exclude_none=True,
        responses=browser_error_responses(401, 404, 409, 412, 422),
    )
    def abandon(
        projectId: CanonicalId,
        tableId: CanonicalId,
        syncOperationId: CanonicalId,
        body: SyncAbandonRequest,
        idempotency_key: Key,
    ):
        return service.abandon(
            str(projectId),
            str(tableId),
            str(syncOperationId),
            str(idempotency_key),
            body.model_dump(by_alias=True),
        )

    return router
