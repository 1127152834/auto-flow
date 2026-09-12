"""Record commands use the same project operation authority as table commands."""

from typing import Annotated

from fastapi import APIRouter, Query, Response

from autoflow.application.project_data.records import DataRecordService

from .errors import browser_error_responses
from .project_data import CanonicalId, Key
from .project_data_record_schemas import (
    DataRecordCreate,
    DataRecordPatch,
    DataRecordStatusWrite,
    DataRecordView,
    RecordKeyType,
)


def project_records_router(service: DataRecordService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}/tables/{tableId}/records")

    @router.post(
        "",
        response_model=DataRecordView,
        status_code=201,
        responses={
            200: {"model": DataRecordView},
            **browser_error_responses(401, 404, 409, 410, 412, 422, 423),
        },
    )
    def create(
        projectId: CanonicalId,
        tableId: CanonicalId,
        body: DataRecordCreate,
        response: Response,
        idempotency_key: Key,
    ):
        snapshot, _, replay = service.create(
            str(projectId),
            str(tableId),
            str(idempotency_key),
            body.model_dump(by_alias=True),
        )
        if replay:
            response.status_code = 200
        return snapshot

    @router.get(
        "/{recordKey}",
        response_model=DataRecordView,
        responses=browser_error_responses(401, 404, 410, 422),
    )
    def get(
        projectId: CanonicalId,
        tableId: CanonicalId,
        recordKey: str,
        dataset_generation: Annotated[str, Query(alias="datasetGeneration")],
        record_key_type: Annotated[RecordKeyType, Query(alias="recordKeyType")],
    ):
        return service.get(
            str(projectId), str(tableId), dataset_generation, recordKey, record_key_type
        )

    @router.patch(
        "/{recordKey}",
        response_model=DataRecordView,
        responses=browser_error_responses(401, 404, 409, 410, 412, 422, 423),
    )
    def update(
        projectId: CanonicalId,
        tableId: CanonicalId,
        recordKey: str,
        body: DataRecordPatch,
        idempotency_key: Key,
    ):
        snapshot, _, _ = service.update(
            str(projectId),
            str(tableId),
            recordKey,
            str(idempotency_key),
            body.model_dump(by_alias=True),
        )
        return snapshot

    @router.put(
        "/{recordKey}/status",
        response_model=DataRecordView,
        responses=browser_error_responses(401, 404, 409, 410, 412, 422, 423),
    )
    def status(
        projectId: CanonicalId,
        tableId: CanonicalId,
        recordKey: str,
        body: DataRecordStatusWrite,
        idempotency_key: Key,
    ):
        snapshot, _, _ = service.set_status(
            str(projectId),
            str(tableId),
            recordKey,
            str(idempotency_key),
            body.model_dump(by_alias=True, exclude_unset=True),
        )
        return snapshot

    return router
