from fastapi import APIRouter, Response

from autoflow.application.models.service import ModelService
from autoflow.domain.models.models import LocalModelSpec, ProviderProfile

from .model_schemas import (
    ModelDiscoveryRead,
    ModelInput,
    ModelOption,
    ModelOptionListRead,
    ModelProviderConnectInput,
    ModelProviderConnectionUpdateInput,
    ModelProviderCreateInput,
    ModelProviderListRead,
    ModelProviderMetadataUpdateInput,
    ModelProviderRead,
    ModelRead,
    ModelTestInput,
    ModelTestRead,
    RemoteModel,
)


def _profile(body, secret_ref=None) -> ProviderProfile:
    return ProviderProfile.from_values(
        body.name,
        body.preset_id,
        body.provider_kind,
        body.base_url,
        secret_ref,
        body.enabled,
        body.description,
    )


def _spec(body: ModelInput) -> LocalModelSpec:
    return LocalModelSpec.from_values(
        body.model_key,
        body.display_name,
        body.tags_json,
        body.context_window,
        body.enabled,
        body.description,
    )


def _provider(value) -> ModelProviderRead:
    return ModelProviderRead.model_validate(value, from_attributes=True)


def _model(value) -> ModelRead:
    return ModelRead.model_validate(value, from_attributes=True)


def _discovery(value) -> ModelDiscoveryRead:
    items = [
        RemoteModel.model_validate(item, from_attributes=True) for item in value.items
    ]
    return ModelDiscoveryRead(
        items=items,
        total=len(items),
        latency_ms=float(value.latency_ms),
        endpoint=value.endpoint,
        message=value.message,
    )


def models_router(service: ModelService) -> APIRouter:
    router = APIRouter(tags=["models"])

    @router.get("/api/v1/model-providers", response_model=ModelProviderListRead)
    def list_providers():
        items = [_provider(item) for item in service.list_providers()]
        return ModelProviderListRead(items=items, total=len(items))

    @router.post(
        "/api/v1/model-providers/connection-preview", response_model=ModelDiscoveryRead
    )
    async def preview(body: ModelProviderCreateInput):
        return _discovery(
            await service.preview(_profile(body), body.api_key.get_secret_value())
        )

    @router.post(
        "/api/v1/model-providers/connect",
        response_model=ModelProviderRead,
        status_code=201,
    )
    async def connect(body: ModelProviderConnectInput):
        return _provider(
            await service.connect(
                _profile(body.provider),
                body.provider.api_key.get_secret_value(),
                [_spec(item) for item in body.selected_models],
            )
        )

    @router.get(
        "/api/v1/model-providers/{provider_id}", response_model=ModelProviderRead
    )
    def get_provider(provider_id: str):
        return _provider(service.get_provider(provider_id))

    @router.post(
        "/api/v1/model-providers/{provider_id}/test", response_model=ModelDiscoveryRead
    )
    async def test_provider(provider_id: str):
        return _discovery(await service.test_provider(provider_id))

    @router.get(
        "/api/v1/model-providers/{provider_id}/models/discover",
        response_model=ModelDiscoveryRead,
    )
    async def discover(provider_id: str):
        return _discovery(await service.discover(provider_id))

    @router.post(
        "/api/v1/model-providers/{provider_id}/models/test",
        response_model=ModelTestRead,
    )
    async def test_model(provider_id: str, body: ModelTestInput):
        result = await service.test_model(provider_id, body.model_key)
        return ModelTestRead(
            model_key=body.model_key,
            latency_ms=float(result.latency_ms),
            output_preview=result.output_preview,
            reasoning_preview=result.reasoning_preview,
            message=result.message,
        )

    @router.put(
        "/api/v1/model-providers/{provider_id}", response_model=ModelProviderRead
    )
    def update_metadata(provider_id: str, body: ModelProviderMetadataUpdateInput):
        return _provider(
            service.update_metadata(
                provider_id, body.name, body.description, body.enabled
            )
        )

    @router.put(
        "/api/v1/model-providers/{provider_id}/connection",
        response_model=ModelProviderRead,
    )
    async def update_connection(
        provider_id: str, body: ModelProviderConnectionUpdateInput
    ):
        key = (
            body.api_key.get_secret_value()
            if "api_key" in body.model_fields_set
            else None
        )
        return _provider(
            await service.update_connection(provider_id, _profile(body), key)
        )

    @router.delete("/api/v1/model-providers/{provider_id}", status_code=204)
    def delete_provider(provider_id: str):
        service.delete_provider(provider_id)
        return Response(status_code=204)

    @router.post(
        "/api/v1/model-providers/{provider_id}/models",
        response_model=ModelRead,
        status_code=201,
    )
    def create_model(provider_id: str, body: ModelInput):
        return _model(service.create_model(provider_id, _spec(body)))

    @router.put("/api/v1/models/{model_id}", response_model=ModelRead)
    def update_model(model_id: str, body: ModelInput):
        return _model(service.update_model(model_id, _spec(body)))

    @router.delete("/api/v1/models/{model_id}", status_code=204)
    def delete_model(model_id: str):
        service.delete_model(model_id)
        return Response(status_code=204)

    @router.get("/api/v1/models/options", response_model=ModelOptionListRead)
    def options():
        items = [
            ModelOption.model_validate(item, from_attributes=True)
            for item in service.list_options()
        ]
        return ModelOptionListRead(items=items, total=len(items))

    return router
