from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_core import PydanticCustomError

from .schemas import ApiModel

ProviderKind = Literal["openai", "anthropic", "gemini", "openai-compatible", "custom"]
ConnectionStatus = Literal["untested", "connected", "failed"]
ContextWindow = Annotated[int, Field(strict=True, ge=1, le=9_007_199_254_740_991)]
LatencyMs = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=0)]
ApiKey = Annotated[SecretStr, Field(json_schema_extra={"writeOnly": True})]
OPTIONAL_API_KEY_PRESETS = {"ollama", "custom-openai-compatible"}


def _requires_api_key(preset_id: str | None, provider_kind: ProviderKind) -> bool:
    return provider_kind in {"anthropic", "gemini"} or preset_id not in OPTIONAL_API_KEY_PRESETS


class _NamedModel(ApiModel):
    @field_validator("name", "model_key", "display_name", mode="before", check_fields=False)
    @classmethod
    def strip_identifier(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ModelProviderCreateInput(_NamedModel):
    name: str = Field(min_length=1, max_length=120)
    preset_id: str | None = Field(default=None, max_length=80)
    provider_kind: ProviderKind = "openai-compatible"
    base_url: str | None = None
    api_key: ApiKey = Field(default_factory=lambda: SecretStr(""))
    enabled: bool = True
    description: str = ""

    @model_validator(mode="after")
    def require_api_key(self) -> "ModelProviderCreateInput":
        if _requires_api_key(self.preset_id, self.provider_kind) and not self.api_key.get_secret_value().strip():
            raise PydanticCustomError(
                "model_provider_api_key_required", "API key is required for this provider"
            )
        return self


class ModelInput(_NamedModel):
    model_key: str = Field(min_length=1, max_length=160)
    display_name: str = Field(min_length=1, max_length=160)
    tags_json: list[str] = Field(default_factory=list)
    context_window: ContextWindow | None = None
    enabled: bool = True
    description: str = ""

    @field_validator("tags_json")
    @classmethod
    def normalize_tags(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class ModelProviderConnectInput(ApiModel):
    provider: ModelProviderCreateInput
    selected_models: list[ModelInput] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def reject_duplicate_models(self) -> "ModelProviderConnectInput":
        keys = [model.model_key for model in self.selected_models]
        if len(keys) != len(set(keys)):
            raise ValueError("selectedModels contains duplicate modelKey values")
        return self


class ModelProviderMetadataUpdateInput(_NamedModel):
    name: str = Field(min_length=1, max_length=120)
    description: str
    enabled: bool


class ModelProviderConnectionUpdateInput(_NamedModel):
    name: str = Field(min_length=1, max_length=120)
    preset_id: str | None = Field(max_length=80)
    provider_kind: ProviderKind
    base_url: str | None
    api_key: ApiKey = Field(default_factory=lambda: SecretStr(""))
    enabled: bool
    description: str

    @model_validator(mode="after")
    def validate_explicit_api_key(self) -> "ModelProviderConnectionUpdateInput":
        if (
            "api_key" in self.model_fields_set
            and _requires_api_key(self.preset_id, self.provider_kind)
            and not self.api_key.get_secret_value().strip()
        ):
            raise PydanticCustomError(
                "model_provider_api_key_required", "API key is required for this provider"
            )
        return self


class ModelTestInput(_NamedModel):
    model_key: str = Field(min_length=1, max_length=160)


class ModelRead(ApiModel):
    id: UUID
    provider_id: UUID
    model_key: str
    display_name: str
    tags_json: list[str]
    context_window: ContextWindow | None
    enabled: bool
    description: str
    created_at: datetime
    updated_at: datetime


class ModelProviderRead(ApiModel):
    id: UUID
    name: str
    preset_id: str | None
    provider_kind: ProviderKind
    base_url: str | None
    api_key_configured: bool
    enabled: bool
    description: str
    models: list[ModelRead]
    connection_status: ConnectionStatus
    last_checked_at: datetime | None
    last_check_latency_ms: LatencyMs | None
    last_check_message: str | None
    created_at: datetime
    updated_at: datetime


class ModelProviderListRead(ApiModel):
    items: list[ModelProviderRead]
    total: int


class RemoteModel(_NamedModel):
    model_key: str
    display_name: str
    owned_by: str | None = None
    context_window: ContextWindow | None = None


class ModelDiscoveryRead(ApiModel):
    ok: Literal[True] = True
    items: list[RemoteModel]
    total: int
    latency_ms: LatencyMs
    endpoint: str
    message: str


class ModelTestRead(_NamedModel):
    ok: Literal[True] = True
    model_key: str
    latency_ms: LatencyMs
    output_preview: str
    reasoning_preview: str
    message: str


class ModelOption(_NamedModel):
    id: UUID
    provider_id: UUID
    provider_name: str
    model_key: str
    display_name: str
    tags_json: list[str]


class ModelOptionListRead(ApiModel):
    items: list[ModelOption]
    total: int
