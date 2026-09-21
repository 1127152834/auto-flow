from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from autoflow.adapters.http.workflow_studio_schemas import (
    StudioCredentialConfirmed,
    StudioCredentialFieldsCommand,
    StudioCredentialFieldsConfirmed,
    StudioCredentialList,
    StudioCredentialNames,
    StudioCredentialRenameRequest,
    StudioCredentialSaved,
    StudioCredentialUpsertRequest,
)
from autoflow.application.workflows.credentials import StudioCredentialService


def studio_credentials_router(service: StudioCredentialService) -> APIRouter:
    router = APIRouter(prefix="/api/credentials", tags=["studio-credentials"])

    @router.get("", response_model=StudioCredentialList, response_model_exclude_none=True)
    def list_credentials() -> dict[str, Any]:
        return {"success": True, "credentials": service.list_items()}

    @router.get("/names", response_model=StudioCredentialNames)
    def credential_names() -> dict[str, Any]:
        return {"success": True, "names": service.names()}

    @router.post("", response_model=StudioCredentialSaved, response_model_exclude_none=True)
    def upsert_credential(request: StudioCredentialUpsertRequest) -> dict[str, Any]:
        return service.upsert(request.name, request.fields, request.description)

    @router.post("/rename", response_model=StudioCredentialConfirmed)
    def rename_credential(request: StudioCredentialRenameRequest) -> dict[str, bool]:
        return service.rename(request.old_name, request.new_name)

    @router.post(
        "/fields",
        response_model=StudioCredentialFieldsConfirmed,
        response_model_exclude_none=True,
    )
    def mutate_fields(request: StudioCredentialFieldsCommand) -> dict[str, Any]:
        return service.mutate_fields(request.model_dump(by_alias=True))

    @router.delete("/{name:path}", response_model=StudioCredentialConfirmed)
    def delete_credential(name: str) -> dict[str, bool]:
        return service.delete(name)

    return router
