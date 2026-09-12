from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header
from pydantic import BaseModel

from autoflow.application.proxies.remote_controls import ProxyRemoteControls
from autoflow.domain.proxies.errors import ProxyError

from .proxies import _error_response, _stored_error
from .proxy_schemas import (
    ActionResult,
    Capability,
    ExpectedRevision,
    LocationList,
    LocationView,
    OperationView,
    RelocateRequest,
    RotationSchedule,
    RotationScheduleUpdate,
)


class RemoteStateView(BaseModel):
    status: str | None
    city: str | None
    region: str | None
    carrier: str | None
    current_ip: str | None
    bound: bool | None
    capabilities: list[Capability]
    operation: OperationView | None
    fetched_at: datetime


def operation_view(value) -> OperationView:
    return OperationView(
        id=value.id,
        kind=value.kind,
        target_id=value.target_id,
        status=value.status,
        resource_revision=value.resource_revision,
        error=_stored_error(value.error),
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def proxy_remote_router(service: ProxyRemoteControls) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/proxies/{projection_id}/remote-state", response_model=RemoteStateView)
    async def remote_state(projection_id: str):
        try:
            value, active = await service.state(projection_id)
            return RemoteStateView(
                status=value.proxy.remote_status,
                city=value.proxy.city,
                region=value.proxy.region,
                carrier=value.proxy.carrier,
                current_ip=value.current_ip,
                bound=value.bound,
                capabilities=[Capability(**asdict(c)) for c in value.capabilities],
                operation=operation_view(active) if active else None,
                fetched_at=datetime.now(UTC),
            )
        except ProxyError as exc:
            return _error_response(exc)

    @router.get(
        "/proxy-panel/connections/{connection_id}/locations",
        response_model=LocationList,
    )
    async def locations(connection_id: str, q: str = "", carrier: str = ""):
        try:
            values = await service.locations(connection_id)
            items = [
                LocationView(
                    id=v.id,
                    city=v.city,
                    country=v.country,
                    carrier=v.carrier,
                    cities=list(v.cities),
                    available_slots=v.available_slots,
                    availability="available" if v.available_slots else "unavailable",
                )
                for v in values
                if (
                    not q
                    or q.casefold()
                    in f"{v.country} {' '.join(v.cities)} {v.carrier or ''}".casefold()
                )
                and (not carrier or carrier == v.carrier)
            ]
            return LocationList(items=items, fetched_at=datetime.now(UTC), stale=False)
        except ProxyError as exc:
            return _error_response(exc)

    @router.get(
        "/proxies/{projection_id}/rotation-schedule", response_model=RotationSchedule
    )
    async def schedule(projection_id: str):
        try:
            return RotationSchedule(**asdict(await service.schedule(projection_id)))
        except ProxyError as exc:
            return _error_response(exc)

    def submit(projection_id, kind, payload, revision, key):
        try:
            value = service.submit(projection_id, kind, payload, revision, str(key))
            return ActionResult(
                status="completed"
                if value.status == "succeeded"
                else "failed"
                if value.status == "failed"
                else "accepted",
                operation_id=value.id,
                error=_stored_error(value.error),
            )
        except ProxyError as exc:
            return _error_response(exc)

    @router.post(
        "/proxies/{projection_id}/change-ip",
        response_model=ActionResult,
        status_code=202,
    )
    async def change_ip(
        projection_id: str,
        body: ExpectedRevision,
        idempotency_key: Annotated[UUID, Header()],
    ):
        return submit(
            projection_id, "change_ip", {}, body.expected_revision, idempotency_key
        )

    @router.post(
        "/proxies/{projection_id}/relocate",
        response_model=ActionResult,
        status_code=202,
    )
    async def relocate(
        projection_id: str,
        body: RelocateRequest,
        idempotency_key: Annotated[UUID, Header()],
    ):
        return submit(
            projection_id,
            "relocate",
            {"location_id": body.location_id},
            body.expected_revision,
            idempotency_key,
        )

    @router.put(
        "/proxies/{projection_id}/rotation-schedule",
        response_model=ActionResult,
        status_code=202,
    )
    async def save_rotation(
        projection_id: str,
        body: RotationScheduleUpdate,
        idempotency_key: Annotated[UUID, Header()],
    ):
        return submit(
            projection_id,
            "save_rotation",
            {"mode": body.mode, "interval_minutes": body.interval_minutes},
            body.expected_revision,
            idempotency_key,
        )

    @router.delete(
        "/proxies/{projection_id}/rotation-schedule",
        response_model=ActionResult,
        status_code=202,
    )
    async def clear_rotation(
        projection_id: str,
        body: ExpectedRevision,
        idempotency_key: Annotated[UUID, Header()],
    ):
        return submit(
            projection_id, "clear_rotation", {}, body.expected_revision, idempotency_key
        )

    @router.get(
        "/proxies/{projection_id}/operation", response_model=OperationView | None
    )
    async def latest_operation(projection_id: str):
        value = service.operations.active(projection_id) or service.operations.latest(
            projection_id
        )
        return operation_view(value) if value else None

    @router.get("/proxy-operations/{operation_id}", response_model=OperationView)
    async def get_operation(operation_id: str):
        try:
            return operation_view(service.operations.get(operation_id))
        except ProxyError as exc:
            return _error_response(exc)

    @router.post(
        "/proxy-operations/{operation_id}/reconcile", response_model=OperationView
    )
    async def reconcile_operation(operation_id: str):
        try:
            return operation_view(service.reconcile(operation_id))
        except ProxyError as exc:
            return _error_response(exc)

    @router.post(
        "/proxy-operations/{operation_id}/acknowledge", response_model=OperationView
    )
    async def acknowledge_unknown(operation_id: str):
        try:
            return operation_view(service.acknowledge(operation_id))
        except ProxyError as exc:
            return _error_response(exc)

    return router
