"""Project identities (remediation M4 R4-09)."""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header, Response
from pydantic import Field, StrictBool, StrictStr

from autoflow.application.identities.service import IdentityService

from .errors import browser_error_responses
from .schemas import ApiModel

Key = Annotated[UUID, Header(alias="Idempotency-Key")]


class IdentityHealthView(ApiModel):
    last_login_success_at: str | None = None
    consecutive_failures: int = 0
    banned: bool = False


class IdentityView(ApiModel):
    identity_id: str
    project_id: str
    name: str
    seed_fingerprint: str
    legacy_shared_seed: bool
    template_profile_id: str | None
    environment_id: str | None
    region: dict[str, Any]
    health: IdentityHealthView
    created_at: datetime
    updated_at: datetime


class IdentityPage(ApiModel):
    items: list[IdentityView]


class IdentityCreate(ApiModel):
    name: StrictStr
    template_profile_id: StrictStr | None = None


class IdentityRename(ApiModel):
    name: StrictStr


class IdentityRegenerate(ApiModel):
    confirm_regenerate: StrictBool


class IdentityRowRequest(ApiModel):
    record_key: StrictStr
    name: StrictStr


class IdentityBatchCreate(ApiModel):
    table_id: StrictStr
    template_profile_id: StrictStr | None = None
    rows: list[IdentityRowRequest] = Field(min_length=1, max_length=1000)


class IdentityBatchLink(ApiModel):
    record_key: str
    identity_id: str


class IdentityBatchResult(ApiModel):
    created: int
    kept: int
    identities: list[IdentityBatchLink]


def identities_router(service: IdentityService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects/{projectId}/identities", tags=["identities"])

    @router.get("", response_model=IdentityPage, responses=browser_error_responses(401, 404))
    def list_identities(projectId: UUID) -> dict[str, Any]:
        return {"items": service.list(str(projectId))}

    @router.post("", response_model=IdentityView, status_code=201,
                 responses={200: {"model": IdentityView}, **browser_error_responses(401, 404, 409, 422, 423)})
    def create_identity(projectId: UUID, body: IdentityCreate, response: Response, idempotency_key: Key) -> dict[str, Any]:
        value, replayed = service.create(str(projectId), str(idempotency_key), body.model_dump(by_alias=True))
        if replayed:
            response.status_code = 200
        return value

    @router.post("/from-records", response_model=IdentityBatchResult, responses=browser_error_responses(401, 404, 409, 422, 423))
    def create_from_records(projectId: UUID, body: IdentityBatchCreate) -> dict[str, Any]:
        return service.create_from_records(str(projectId), body.model_dump(by_alias=True))

    @router.patch("/{identityId}", response_model=IdentityView, responses=browser_error_responses(401, 404, 409, 422, 423))
    def rename_identity(projectId: UUID, identityId: UUID, body: IdentityRename) -> dict[str, Any]:
        return service.rename(str(projectId), str(identityId), body.model_dump(by_alias=True))

    @router.post("/{identityId}/regenerate-seed", response_model=IdentityView,
                 responses=browser_error_responses(401, 404, 409, 422, 423))
    def regenerate_seed(projectId: UUID, identityId: UUID, body: IdentityRegenerate) -> dict[str, Any]:
        return service.regenerate_seed(str(projectId), str(identityId), body.model_dump(by_alias=True))

    @router.post("/{identityId}/reset-health", response_model=IdentityView,
                 responses=browser_error_responses(401, 404, 409, 423))
    def reset_health(projectId: UUID, identityId: UUID) -> dict[str, Any]:
        return service.reset_health(str(projectId), str(identityId))

    @router.delete("/{identityId}", status_code=204, responses=browser_error_responses(401, 404, 409, 423))
    def delete_identity(projectId: UUID, identityId: UUID) -> Response:
        service.delete(str(projectId), str(identityId))
        return Response(status_code=204)

    return router
