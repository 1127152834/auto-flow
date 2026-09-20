from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, status
from pydantic import ConfigDict, Field

from autoflow.adapters.http.schemas import ApiModel
from autoflow.application.workflows.modules import CustomModuleService


class CustomModuleWrite(ApiModel):
    model_config = ConfigDict(
        alias_generator=None,
        populate_by_name=True,
        extra="allow",
    )

    client_request_id: str = Field(alias="clientRequestId", min_length=1, max_length=128)


class CustomModuleCreate(CustomModuleWrite):
    name: str = Field(min_length=1, max_length=50)
    display_name: str
    description: str = ""
    icon: str = "📦"
    color: str = "#8B5CF6"
    category: str = "custom"
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    outputs: list[dict[str, Any]] = Field(default_factory=list)
    workflow: dict[str, Any]
    tags: list[str] = Field(default_factory=list)


class CustomModuleUpdate(CustomModuleWrite):
    expected_revision: int = Field(alias="expectedRevision", ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=50)
    display_name: str | None = None
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    category: str | None = None
    parameters: list[dict[str, Any]] | None = None
    outputs: list[dict[str, Any]] | None = None
    workflow: dict[str, Any] | None = None
    tags: list[str] | None = None
    is_favorite: bool | None = None
    sort_order: int | None = None


class CustomModuleDuplicate(CustomModuleWrite):
    new_name: str | None = Field(default=None, alias="new_name", max_length=50)


class CustomModuleResponse(ApiModel):
    model_config = ConfigDict(alias_generator=None, populate_by_name=True)

    id: str
    revision: int
    name: str
    display_name: str
    description: str
    icon: str
    color: str
    category: str
    parameters: list[dict[str, Any]]
    outputs: list[dict[str, Any]]
    workflow: dict[str, Any]
    author: str
    version: str
    tags: list[str]
    usage_count: int
    download_count: int
    created_at: str
    updated_at: str
    is_published: bool
    is_builtin: bool
    is_favorite: bool
    sort_order: int


class CustomModuleListResponse(ApiModel):
    model_config = ConfigDict(alias_generator=None, populate_by_name=True)

    modules: list[CustomModuleResponse]
    total: int


class CustomModuleDeleteResponse(ApiModel):
    success: bool


class CustomModuleUsageResponse(ApiModel):
    model_config = ConfigDict(alias_generator=None, populate_by_name=True)

    success: bool
    usage_count: int


def _payload(value: CustomModuleWrite) -> dict[str, Any]:
    return value.model_dump(
        by_alias=False,
        exclude={"client_request_id", "expected_revision"},
        exclude_unset=True,
    )


def custom_modules_router(service: CustomModuleService) -> APIRouter:
    router = APIRouter(prefix="/api/custom-modules", tags=["studio-custom-modules"])

    @router.get("", response_model=CustomModuleListResponse)
    def list_modules(
        category: str | None = None, search: str | None = None
    ) -> dict[str, Any]:
        modules = service.list(category=category, search=search)
        return {
            "modules": [module.to_payload() for module in modules],
            "total": len(modules),
        }

    @router.post(
        "", status_code=status.HTTP_201_CREATED, response_model=CustomModuleResponse
    )
    def create_module(request: CustomModuleCreate) -> dict[str, Any]:
        return service.create(
            _payload(request), client_request_id=request.client_request_id
        ).to_payload()

    @router.post(
        "/import",
        status_code=status.HTTP_201_CREATED,
        response_model=CustomModuleResponse,
    )
    def import_module(request: CustomModuleCreate) -> dict[str, Any]:
        return service.import_module(
            _payload(request), client_request_id=request.client_request_id
        ).to_payload()

    @router.get("/{module_id}", response_model=CustomModuleResponse)
    def get_module(module_id: str) -> dict[str, Any]:
        return service.get(module_id).to_payload()

    @router.put("/{module_id}", response_model=CustomModuleResponse)
    def update_module(
        module_id: str, request: CustomModuleUpdate
    ) -> dict[str, Any]:
        return service.update(
            module_id,
            _payload(request),
            expected_revision=request.expected_revision,
            client_request_id=request.client_request_id,
        ).to_payload()

    @router.delete("/{module_id}", response_model=CustomModuleDeleteResponse)
    def delete_module(
        module_id: str,
        expected_revision: int = Query(alias="expectedRevision", ge=1),
        client_request_id: str = Query(alias="clientRequestId", min_length=1, max_length=128),
    ) -> dict[str, Any]:
        service.delete(
            module_id,
            expected_revision=expected_revision,
            client_request_id=client_request_id,
        )
        return {"success": True}

    @router.post(
        "/{module_id}/duplicate",
        status_code=status.HTTP_201_CREATED,
        response_model=CustomModuleResponse,
    )
    def duplicate_module(
        module_id: str, request: CustomModuleDuplicate
    ) -> dict[str, Any]:
        return service.duplicate(
            module_id,
            new_name=request.new_name,
            client_request_id=request.client_request_id,
        ).to_payload()

    @router.post(
        "/{module_id}/increment-usage", response_model=CustomModuleUsageResponse
    )
    def increment_usage(module_id: str) -> dict[str, Any]:
        saved = service.increment_usage(module_id)
        return {"success": True, "usage_count": saved.usage_count}

    return router
