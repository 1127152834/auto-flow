from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DashboardSnapshot:
    profiles: int
    enabled_proxies: int
    proxy_groups: int
    installed_kernels: int
    model_providers: int | None
    models: int | None
    generated_at: datetime


@dataclass(frozen=True)
class RuntimeSnapshot:
    api_version: str
    backend_version: str
    python_version: str
    sqlite_version: str
    paths: dict[str, str]
    blockers: tuple[str, ...]
