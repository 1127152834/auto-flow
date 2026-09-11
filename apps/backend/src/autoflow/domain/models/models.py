from dataclasses import dataclass


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
