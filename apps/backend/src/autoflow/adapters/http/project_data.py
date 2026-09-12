"""Project table transport. Ownership and transactions stay in the data service."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, Query, Response
from pydantic import BeforeValidator

from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.tables import DataTableService

from .errors import browser_error_responses
from .project_data_catalog_schemas import (
    DataFieldCreate,
    DataFieldDirectory,
    DataFieldMutationView,
    DataFieldPatch,
    DataStatusCreate,
    DataStatusDirectory,
    DataStatusPatch,
    DataStatusView,
)
from .project_data_schemas import (
    DataTableCreate,
    DataTablePage,
    DataTablePatch,
    DataTableView,
)


def _canonical_uuid(value: object) -> object:
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError("Must be a canonical lowercase UUID")
    return value


CanonicalId = Annotated[UUID, BeforeValidator(_canonical_uuid)]
Key = Annotated[CanonicalId, Header(alias="Idempotency-Key")]


def project_data_router(
    service: DataTableService, catalog: DataCatalogService
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}/tables")

    @router.get(
        "",
        response_model=DataTablePage,
        response_model_exclude_none=True,
        responses=browser_error_responses(401, 404, 422),
    )
    def list_tables(
        projectId: CanonicalId,
        q: str | None = None,
        source_kind: Literal["local", "excel", "sheets", "unconfigured"] | None = Query(
            None, alias="sourceKind"
        ),
        page: int = Query(1, ge=1, le=2_147_483_647),
        page_size: int = Query(50, alias="pageSize", ge=1, le=200),
        sort: Literal["name", "-name", "updatedAt", "-updatedAt"] = "-updatedAt",
    ):
        items, total = service.list(
            str(projectId),
            q=q,
            source_kind=source_kind,
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

    @router.post(
        "",
        response_model=DataTableView,
        status_code=201,
        response_model_exclude_none=True,
        responses={
            200: {"model": DataTableView},
            **browser_error_responses(401, 404, 409, 422, 423),
        },
    )
    def create_table(
        projectId: CanonicalId,
        body: DataTableCreate,
        response: Response,
        idempotency_key: Key,
    ):
        table, _operation, replayed = service.create(
            str(projectId), str(idempotency_key), body.model_dump(by_alias=True)
        )
        if replayed:
            response.status_code = 200
        return table

    @router.get(
        "/{tableId}",
        response_model=DataTableView,
        response_model_exclude_none=True,
        responses=browser_error_responses(401, 404, 410, 422),
    )
    def get_table(projectId: CanonicalId, tableId: CanonicalId):
        return service.get(str(projectId), str(tableId))

    @router.patch(
        "/{tableId}",
        response_model=DataTableView,
        response_model_exclude_none=True,
        responses=browser_error_responses(401, 404, 409, 422, 423),
    )
    def update_table(
        projectId: CanonicalId,
        tableId: CanonicalId,
        body: DataTablePatch,
        idempotency_key: Key,
    ):
        table, _operation, _replayed = service.update(
            str(projectId),
            str(tableId),
            str(idempotency_key),
            body.model_dump(by_alias=True, exclude_unset=True),
        )
        return table

    @router.get(
        "/{tableId}/fields",
        response_model=DataFieldDirectory,
        responses=browser_error_responses(401, 404, 422),
    )
    def list_fields(projectId: CanonicalId, tableId: CanonicalId):
        return catalog.fields(str(projectId), str(tableId))

    @router.post(
        "/{tableId}/fields",
        response_model=DataFieldMutationView,
        responses=browser_error_responses(401, 404, 409, 412, 422, 423),
    )
    def create_field(
        projectId: CanonicalId,
        tableId: CanonicalId,
        body: DataFieldCreate,
        idempotency_key: Key,
    ):
        result, _, _ = catalog.create_field(
            str(projectId),
            str(tableId),
            str(idempotency_key),
            body.model_dump(by_alias=True, exclude_unset=True),
        )
        return {"field": result["field"], "tableRevision": result["tableRevision"]}

    @router.get(
        "/{tableId}/statuses",
        response_model=DataStatusDirectory,
        responses=browser_error_responses(401, 404, 422),
    )
    def list_statuses(projectId: CanonicalId, tableId: CanonicalId):
        return catalog.statuses(str(projectId), str(tableId))

    @router.post(
        "/{tableId}/statuses",
        response_model=DataStatusView,
        status_code=201,
        responses={
            200: {"model": DataStatusView},
            **browser_error_responses(401, 404, 409, 422, 423),
        },
    )
    def create_status(
        projectId: CanonicalId,
        tableId: CanonicalId,
        body: DataStatusCreate,
        response: Response,
        idempotency_key: Key,
    ):
        result, _, replayed = catalog.create_status(
            str(projectId),
            str(tableId),
            str(idempotency_key),
            body.model_dump(by_alias=True),
        )
        if replayed:
            response.status_code = 200
        return result["status"]

    @router.patch(
        "/{tableId}/statuses/{statusId}",
        response_model=DataStatusView,
        responses=browser_error_responses(401, 404, 409, 422, 423),
    )
    def update_status(
        projectId: CanonicalId,
        tableId: CanonicalId,
        statusId: CanonicalId,
        body: DataStatusPatch,
        idempotency_key: Key,
    ):
        result, _, _ = catalog.update_status(
            str(projectId),
            str(tableId),
            str(statusId),
            str(idempotency_key),
            body.model_dump(by_alias=True, exclude_unset=True),
        )
        return result["status"]

    @router.patch(
        "/{tableId}/fields/{fieldId}",
        response_model=DataFieldMutationView,
        responses=browser_error_responses(401, 404, 409, 410, 412, 422, 423),
    )
    def update_field(
        projectId: CanonicalId,
        tableId: CanonicalId,
        fieldId: CanonicalId,
        body: DataFieldPatch,
        idempotency_key: Key,
    ):
        result, _, _ = catalog.update_field(
            str(projectId),
            str(tableId),
            str(fieldId),
            str(idempotency_key),
            body.model_dump(by_alias=True),
        )
        return {"field": result["field"], "tableRevision": result["tableRevision"]}

    return router
