from dataclasses import asdict
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from autoflow.application.proxies.facade import ProxyApplication
from autoflow.domain.proxies.errors import ProxyError
from autoflow.domain.proxies.models import Connection, Projection, ProxyGroup

from .proxy_schemas import (
    AccountSummary,
    ActionResult,
    ApiError,
    ApiKeyUpdate,
    ConnectionCreate,
    ConnectionList,
    ConnectionUpdate,
    ConnectionView,
    CredentialView,
    Endpoint,
    ErrorResponse,
    ExpectedRevision,
    GroupCreate,
    GroupPage,
    GroupReferences,
    GroupUpdate,
    GroupView,
    HealthSnapshot,
    IpAllowlist,
    IpAllowlistUpdate,
    LocationList,
    ProbeRequest,
    ProxyPage,
    ProxyReferences,
    ProxyUpdate,
    ProxyView,
    RelocateRequest,
    ResourceReference,
    RotationSchedule,
    RotationScheduleUpdate,
    SyncSnapshot,
    UsageView,
)
from .proxy_schemas import (
    Capability as CapabilitySchema,
)


class EmptyCommand(BaseModel):
    pass


def proxy_router(application: ProxyApplication) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/proxy-panel/connections", response_model=ConnectionList)
    def list_connections():
        return ConnectionList(items=[_connection_view(item) for item in application.list_connections()])

    @router.post(
        "/proxy-panel/connections",
        status_code=201,
        response_model=ConnectionView,
        responses=_error_responses(422, 502, 503),
    )
    async def create_connection(body: ConnectionCreate):
        try:
            connection = await application.create_connection(body.name, body.api_key.get_secret_value())
            return _connection_view(connection)
        except (ProxyError, IntegrityError) as exc:
            return _error_response(exc)

    @router.patch(
        "/proxy-panel/connections/{connection_id}",
        response_model=ConnectionView,
        responses=_error_responses(404, 409, 422),
    )
    def update_connection(connection_id: str, body: ConnectionUpdate):
        try:
            return _connection_view(
                application.update_connection(connection_id, body.expected_revision, body.name or "")
            )
        except (ProxyError, IntegrityError) as exc:
            return _error_response(exc)

    @router.put(
        "/proxy-panel/connections/{connection_id}/api-key",
        response_model=ConnectionView,
        responses=_error_responses(404, 409, 502, 503),
    )
    async def replace_api_key(connection_id: str, body: ApiKeyUpdate):
        try:
            connection = await application.replace_api_key(
                connection_id, body.expected_revision, body.api_key.get_secret_value()
            )
            return _connection_view(connection)
        except ProxyError as exc:
            return _error_response(exc)

    @router.delete(
        "/proxy-panel/connections/{connection_id}",
        status_code=204,
        responses=_error_responses(404, 409, 503),
    )
    def delete_connection(connection_id: str):
        try:
            application.delete_connection(connection_id)
            return Response(status_code=204)
        except ProxyError as exc:
            return _error_response(exc)

    @router.post(
        "/proxy-panel/connections/{connection_id}/verify",
        response_model=ActionResult[ConnectionView],
        responses=_error_responses(404, 502, 503),
    )
    async def verify_connection(connection_id: str, body: EmptyCommand):
        try:
            connection = await application.verify_connection(connection_id)
            return ActionResult[ConnectionView](
                status="completed", resource=_connection_view(connection)
            )
        except ProxyError as exc:
            return _error_response(exc)

    @router.post(
        "/proxy-panel/connections/{connection_id}/sync",
        response_model=ActionResult[SyncSnapshot],
        responses=_error_responses(404, 502, 503),
    )
    async def sync_connection(connection_id: str, body: EmptyCommand):
        try:
            connection, count, missing, completeness, provider_total = await application.sync_connection(
                connection_id
            )
            snapshot = SyncSnapshot(
                last_synced_at=connection.last_synced_at,
                stale=completeness != "complete",
                completeness=completeness,
                synced_count=count,
                provider_total=provider_total,
                remote_missing_count=missing,
                last_error=None,
            )
            return ActionResult[SyncSnapshot](status="completed", resource=snapshot)
        except ProxyError as exc:
            return _error_response(exc)

    @router.get("/proxies", response_model=ProxyPage)
    def list_proxies(
        connection_id: str | None = None,
        q: str | None = None,
        carrier: str | None = None,
        city: str | None = None,
        health: str | None = None,
        enabled: bool | None = None,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=50, ge=1, le=100),
    ):
        items, count = application.list_projections(
            connection_id=connection_id,
            q=q,
            carrier=carrier,
            city=city,
            health=health,
            enabled=enabled,
            offset=offset,
            limit=limit,
        )
        return ProxyPage(
            items=[_proxy_view(item) for item in items],
            offset=offset,
            limit=limit,
            matched_count=count,
        )

    @router.get("/proxies/{projection_id}", response_model=ProxyView, responses=_error_responses(404))
    def get_proxy(projection_id: str):
        try:
            return _proxy_view(application.get_projection(projection_id))
        except ProxyError as exc:
            return _error_response(exc)

    @router.patch(
        "/proxies/{projection_id}",
        response_model=ProxyView,
        responses=_error_responses(404, 409, 422),
    )
    def update_proxy(projection_id: str, body: ProxyUpdate):
        try:
            projection = application.update_projection(
                projection_id,
                expected_revision=body.expected_revision,
                name_override=body.name_override,
                enabled=body.enabled,
                change_name="name_override" in body.model_fields_set,
            )
            return _proxy_view(projection)
        except ProxyError as exc:
            return _error_response(exc)

    @router.get(
        "/proxies/{projection_id}/references",
        response_model=ProxyReferences,
        responses=_error_responses(404),
    )
    def proxy_references(projection_id: str):
        try:
            profiles, groups = application.projection_references(projection_id)
            return ProxyReferences(
                profiles=[ResourceReference(id=item[0], name=item[1]) for item in profiles],
                groups=[ResourceReference(id=item[0], name=item[1]) for item in groups],
            )
        except ProxyError as exc:
            return _error_response(exc)

    @router.post(
        "/proxies/{projection_id}/probe",
        response_model=ActionResult[HealthSnapshot],
        responses=_error_responses(404, 503),
    )
    async def check_proxy_health(projection_id: str, body: ProbeRequest):
        try:
            health = await application.check_health(projection_id, body.protocol)
            resource = HealthSnapshot(
                state=health.state,
                latency_ms=health.latency_ms,
                exit_ip=health.exit_ip,
                checked_at=health.checked_at,
                source=health.source,
                error=_stored_error(health.error),
            )
            return ActionResult[HealthSnapshot](status="completed", resource=resource)
        except ProxyError as exc:
            return _error_response(exc)

    @router.post(
        "/proxies/{projection_id}/change-ip",
        response_model=ActionResult[ProxyView],
        responses=_error_responses(404, 503),
    )
    def unavailable_change_ip(projection_id: str, body: ExpectedRevision):
        return _unavailable_projection(application, projection_id)

    @router.post(
        "/proxies/{projection_id}/relocate",
        response_model=ActionResult[ProxyView],
        responses=_error_responses(404, 503),
    )
    def unavailable_relocate(projection_id: str, body: RelocateRequest):
        return _unavailable_projection(application, projection_id)

    @router.get("/proxies/{projection_id}/rotation-schedule", response_model=RotationSchedule, responses=_error_responses(404, 503))
    def unavailable_get_rotation(projection_id: str):
        return _unavailable_projection(application, projection_id)

    @router.put(
        "/proxies/{projection_id}/rotation-schedule",
        response_model=ActionResult[RotationSchedule],
        responses=_error_responses(404, 503),
    )
    def unavailable_set_rotation(projection_id: str, body: RotationScheduleUpdate):
        return _unavailable_projection(application, projection_id)

    @router.delete(
        "/proxies/{projection_id}/rotation-schedule",
        response_model=ActionResult[RotationSchedule],
        responses=_error_responses(404, 503),
    )
    def unavailable_delete_rotation(projection_id: str):
        return _unavailable_projection(application, projection_id)

    @router.get("/proxies/{projection_id}/ip-auth", response_model=IpAllowlist, responses=_error_responses(404, 503))
    def unavailable_get_ip_auth(projection_id: str):
        return _unavailable_projection(application, projection_id)

    @router.put(
        "/proxies/{projection_id}/ip-auth",
        response_model=ActionResult[IpAllowlist],
        responses=_error_responses(404, 503),
    )
    def unavailable_set_ip_auth(projection_id: str, body: IpAllowlistUpdate):
        return _unavailable_projection(application, projection_id)

    @router.get("/proxies/{projection_id}/credentials", response_model=CredentialView, responses=_error_responses(404, 503))
    def unavailable_credentials(projection_id: str):
        return _unavailable_projection(application, projection_id)

    @router.post(
        "/proxies/{projection_id}/credentials/rotate",
        response_model=ActionResult[CredentialView],
        responses=_error_responses(404, 503),
    )
    def unavailable_rotate_credentials(projection_id: str, body: ExpectedRevision):
        return _unavailable_projection(application, projection_id)

    @router.get("/proxies/{projection_id}/usage", response_model=UsageView, responses=_error_responses(404, 503))
    def unavailable_usage(projection_id: str, since: datetime, until: datetime):
        return _unavailable_projection(application, projection_id)

    @router.get(
        "/proxy-panel/connections/{connection_id}/locations",
        response_model=LocationList,
        responses=_error_responses(404, 503),
    )
    def unavailable_locations(
        connection_id: str, q: str | None = None, carrier: str | None = None, refresh: bool = False
    ):
        return _unavailable_connection(application, connection_id)

    @router.get(
        "/proxy-panel/connections/{connection_id}/account-summary",
        response_model=AccountSummary,
        responses=_error_responses(404, 503),
    )
    def unavailable_account_summary(connection_id: str):
        return _unavailable_connection(application, connection_id)

    @router.get("/proxy-groups", response_model=GroupPage)
    def list_groups(
        q: str | None = None,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=50, ge=1, le=100),
    ):
        groups, count = application.list_groups(q=q, offset=offset, limit=limit)
        return GroupPage(
            items=[_group_view(group) for group in groups],
            offset=offset,
            limit=limit,
            matched_count=count,
        )

    @router.post(
        "/proxy-groups",
        status_code=201,
        response_model=GroupView,
        responses=_error_responses(409, 422),
    )
    def create_group(body: GroupCreate):
        try:
            return _group_view(application.create_group(**body.model_dump()))
        except (ProxyError, IntegrityError) as exc:
            return _error_response(exc)

    @router.get("/proxy-groups/{group_id}", response_model=GroupView, responses=_error_responses(404))
    def get_group(group_id: str):
        try:
            return _group_view(application.get_group(group_id))
        except ProxyError as exc:
            return _error_response(exc)

    @router.put(
        "/proxy-groups/{group_id}",
        response_model=GroupView,
        responses=_error_responses(404, 409, 422),
    )
    def update_group(group_id: str, body: GroupUpdate):
        try:
            return _group_view(application.update_group(group_id, **body.model_dump()))
        except (ProxyError, IntegrityError) as exc:
            return _error_response(exc)

    @router.delete("/proxy-groups/{group_id}", status_code=204, responses=_error_responses(404, 409))
    def delete_group(group_id: str):
        try:
            application.delete_group(group_id)
            return Response(status_code=204)
        except ProxyError as exc:
            return _error_response(exc)

    @router.get(
        "/proxy-groups/{group_id}/references",
        response_model=GroupReferences,
        responses=_error_responses(404),
    )
    def group_references(group_id: str):
        try:
            references = application.group_references(group_id)
            return GroupReferences(
                profiles=[ResourceReference(id=item[0], name=item[1]) for item in references]
            )
        except ProxyError as exc:
            return _error_response(exc)

    return router


def _connection_view(connection: Connection) -> ConnectionView:
    return ConnectionView(
        id=connection.id,
        name=connection.name,
        has_secret=bool(connection.secret_ref),
        status=connection.status,
        revision=connection.revision,
        last_verified_at=connection.last_verified_at,
        last_synced_at=connection.last_synced_at,
        last_error=_stored_error(connection.last_error),
        capabilities=[CapabilitySchema(**asdict(capability)) for capability in connection.capabilities],
    )


def _proxy_view(projection: Projection) -> ProxyView:
    health_error = _stored_error(projection.health.error)
    return ProxyView(
        id=projection.id,
        connection_id=projection.connection_id,
        name=projection.display_name,
        name_override=projection.name_override,
        enabled=projection.enabled,
        remote_status=projection.remote_status,
        remote_missing=projection.remote_missing,
        carrier=projection.carrier,
        city=projection.city,
        region=projection.region,
        exit_ip=projection.exit_ip,
        http_endpoint=Endpoint(**asdict(projection.http_endpoint)) if projection.http_endpoint else None,
        socks5_endpoint=Endpoint(**asdict(projection.socks5_endpoint)) if projection.socks5_endpoint else None,
        credential_available=projection.credential_available,
        health=HealthSnapshot(
            state=projection.health.state,
            latency_ms=projection.health.latency_ms,
            exit_ip=projection.health.exit_ip,
            checked_at=projection.health.checked_at,
            source=projection.health.source,
            error=health_error,
        ),
        subscription_expires_at=projection.subscription_expires_at,
        last_synced_at=projection.last_synced_at,
        stale=projection.stale,
        revision=projection.revision,
        reference_count=projection.reference_count,
        capabilities=[CapabilitySchema(**asdict(capability)) for capability in projection.capabilities],
    )


def _group_view(group: ProxyGroup) -> GroupView:
    return GroupView(
        id=group.id,
        name=group.name,
        description=group.description,
        member_ids=list(group.member_ids),
        revision=group.revision,
        reference_count=group.reference_count,
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


def _stored_error(value: dict[str, Any] | None) -> ApiError | None:
    if value is None:
        return None
    return ApiError(
        code=str(value.get("code", "PROXY_ERROR")),
        message=str(value.get("message", "Proxy operation failed")),
        request_id=str(value.get("request_id", "unavailable")),
        field_errors=value.get("field_errors", {}),
        retry_after_seconds=value.get("retry_after_seconds"),
        outcome_unknown=bool(value.get("outcome_unknown", False)),
    )


def _error_response(exc: Exception) -> JSONResponse:
    request_id = str(uuid4())
    if isinstance(exc, ProxyError):
        code = exc.code
        status = _status_for(code)
        retry = getattr(exc, "retry_after_seconds", None)
        outcome_unknown = getattr(exc, "outcome_unknown", False)
        details = exc.details
        message = str(exc)
    else:
        code, status, retry, outcome_unknown, details = "VALIDATION_ERROR", 409, None, False, {}
        message = "A resource with the same value already exists"
    error = ApiError(
        code=code,
        message=message,
        request_id=request_id,
        field_errors=details,
        retry_after_seconds=retry,
        outcome_unknown=outcome_unknown,
    )
    headers = {"Retry-After": str(retry)} if retry is not None else None
    return JSONResponse(
        status_code=status,
        content={"error": error.model_dump(mode="json")},
        headers=headers,
    )


def _unavailable_projection(application: ProxyApplication, projection_id: str) -> JSONResponse:
    try:
        application.get_projection(projection_id)
    except ProxyError as exc:
        return _error_response(exc)
    from autoflow.domain.proxies.errors import CapabilityUnavailableError

    return _error_response(
        CapabilityUnavailableError("This ProxyPanel capability has not been verified")
    )


def _unavailable_connection(application: ProxyApplication, connection_id: str) -> JSONResponse:
    if not any(connection.id == connection_id for connection in application.list_connections()):
        from autoflow.domain.proxies.errors import ProxyNotFoundError

        return _error_response(ProxyNotFoundError("ProxyPanel connection was not found"))
    from autoflow.domain.proxies.errors import CapabilityUnavailableError

    return _error_response(
        CapabilityUnavailableError("This ProxyPanel capability has not been verified")
    )


def _status_for(code: str) -> int:
    if code == "RESOURCE_NOT_FOUND":
        return 404
    if code == "VALIDATION_ERROR":
        return 422
    if code in {"PROXYPANEL_AUTH_FAILED", "PROXYPANEL_NOT_FOUND", "PROXYPANEL_CONFLICT", "PROXYPANEL_SCHEMA_UNSUPPORTED"}:
        return 502
    if code in {"PROXYPANEL_UNAVAILABLE", "CREDENTIAL_STORE_UNAVAILABLE", "CAPABILITY_UNAVAILABLE"}:
        return 503
    if code == "PROXYPANEL_RATE_LIMITED":
        return 429
    if code == "PROXYPANEL_OUTCOME_UNKNOWN":
        return 504
    return 409


def _error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    return {status: {"model": ErrorResponse} for status in statuses}
