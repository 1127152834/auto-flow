from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class ProviderConnection:
    preset_id: str | None
    provider_kind: str
    base_url: str | None


@dataclass(frozen=True, slots=True)
class RemoteModel:
    model_key: str
    display_name: str
    owned_by: str | None = None
    context_window: int | None = None


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    items: tuple[RemoteModel, ...]
    latency_ms: float
    endpoint: str
    message: str


@dataclass(frozen=True, slots=True)
class ModelTestResult:
    latency_ms: float
    endpoint: str
    output_preview: str
    reasoning_preview: str
    message: str


@dataclass(frozen=True, slots=True)
class ModelInvocationResult:
    model_key: str
    content: str
    reasoning: str
    usage: dict[str, Any]
    endpoint: str
    tool_calls: tuple[dict[str, Any], ...] = ()


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    name: str
    preset_id: str | None
    provider_kind: str
    base_url: str | None
    secret_ref: str | None
    enabled: bool
    description: str

    @classmethod
    def from_values(
        cls,
        name: str,
        preset_id: str | None,
        provider_kind: str,
        base_url: str | None,
        secret_ref: str | None,
        enabled: bool,
        description: str,
    ) -> "ProviderProfile":
        return cls(
            name.strip(),
            preset_id,
            provider_kind,
            base_url.strip() if base_url and base_url.strip() else None,
            secret_ref,
            enabled,
            description,
        )


@dataclass(frozen=True, slots=True)
class LocalModelSpec:
    model_key: str
    display_name: str
    tags_json: tuple[str, ...] = ()
    context_window: int | None = None
    enabled: bool = True
    description: str = ""

    @classmethod
    def from_values(
        cls,
        model_key: str,
        display_name: str,
        tags_json: list[str] | tuple[str, ...] = (),
        context_window: int | None = None,
        enabled: bool = True,
        description: str = "",
    ) -> "LocalModelSpec":
        tags = tuple(
            dict.fromkeys(value.strip() for value in tags_json if value.strip())
        )
        return cls(
            model_key.strip(),
            display_name.strip(),
            tags,
            context_window,
            enabled,
            description,
        )


@dataclass(frozen=True, slots=True)
class LocalModel:
    id: str
    provider_id: str
    spec: LocalModelSpec
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(cls, provider_id: str, spec: LocalModelSpec) -> "LocalModel":
        now = utc_now()
        return cls(str(uuid4()), provider_id, spec, now, now)

    @property
    def model_key(self) -> str:
        return self.spec.model_key

    @property
    def display_name(self) -> str:
        return self.spec.display_name

    @property
    def tags_json(self) -> list[str]:
        return list(self.spec.tags_json)

    @property
    def context_window(self) -> int | None:
        return self.spec.context_window

    @property
    def enabled(self) -> bool:
        return self.spec.enabled

    @property
    def description(self) -> str:
        return self.spec.description


@dataclass(frozen=True, slots=True)
class ModelProvider:
    id: str
    profile: ProviderProfile
    models: tuple[LocalModel, ...] = field(default_factory=tuple)
    connection_status: str = "untested"
    last_checked_at: datetime | None = None
    last_check_latency_ms: float | None = None
    last_check_message: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @classmethod
    def create(cls, profile: ProviderProfile) -> "ModelProvider":
        now = utc_now()
        return cls(str(uuid4()), profile, created_at=now, updated_at=now)

    @property
    def name(self) -> str:
        return self.profile.name

    @property
    def preset_id(self) -> str | None:
        return self.profile.preset_id

    @property
    def provider_kind(self) -> str:
        return self.profile.provider_kind

    @property
    def base_url(self) -> str | None:
        return self.profile.base_url

    @property
    def secret_ref(self) -> str | None:
        return self.profile.secret_ref

    @property
    def api_key_configured(self) -> bool:
        return self.profile.secret_ref is not None

    @property
    def enabled(self) -> bool:
        return self.profile.enabled

    @property
    def description(self) -> str:
        return self.profile.description


@dataclass(frozen=True, slots=True)
class ModelOptionRecord:
    id: str
    provider_id: str
    provider_name: str
    model_key: str
    display_name: str
    tags_json: tuple[str, ...]
