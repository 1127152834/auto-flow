from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from .browser import BrowserSessionPort
from .variables import CredentialReader, resolve_value


class ArtifactWriter(Protocol):
    async def write_bytes(
        self, *, name: str, content: bytes, mime_type: str
    ) -> str: ...

    async def write_text(
        self,
        *,
        output_path: str,
        content: str,
        separator: str,
        encoding: str,
        append: bool,
        mime_type: str,
    ) -> str: ...


class ModelGateway(Protocol):
    async def invoke(self, model_id: str, payload: Mapping[str, Any]) -> Any: ...


class ExternalIntegrationGateway(Protocol):
    async def call(self, integration: str, payload: Mapping[str, Any]) -> Any: ...


class WorkflowEventSink(Protocol):
    async def publish(self, event: Mapping[str, Any]) -> None: ...


class CancellationToken(Protocol):
    @property
    def cancelled(self) -> bool: ...

    def raise_if_cancelled(self) -> None: ...


@dataclass(frozen=True, slots=True)
class WorkflowClock:
    now: Callable[[], datetime] = lambda: datetime.now(UTC)


@dataclass(slots=True)
class ExecutionContext:
    variables: dict[str, Any] = field(default_factory=dict)
    browser: BrowserSessionPort | None = None
    artifacts: ArtifactWriter | None = None
    credentials: CredentialReader | None = None
    models: ModelGateway | None = None
    external_integrations: ExternalIntegrationGateway | None = None
    events: WorkflowEventSink | None = None
    cancellation: CancellationToken | None = None
    clock: WorkflowClock = field(default_factory=WorkflowClock)
    data_rows: list[dict[str, Any]] = field(default_factory=list)
    current_row: dict[str, Any] = field(default_factory=dict)
    loop_stack: list[dict[str, Any]] = field(default_factory=list)
    progress: Callable[[str, str], Awaitable[None]] | None = None
    current_node_id: str | None = None
    current_execution_id: str | None = None

    def resolve_value(self, value: Any) -> Any:
        return resolve_value(value, self.variables, self.credentials)

    def set_variable(self, name: str, value: Any) -> None:
        if self.cancellation is not None:
            self.cancellation.raise_if_cancelled()
        self.variables[name] = value

    def get_variable(self, name: Any, default: Any = None) -> Any:
        if not isinstance(name, str):
            return self.variables.get(name, default)
        normalized = name.strip()
        if normalized.startswith("${") and normalized.endswith("}"):
            normalized = normalized[2:-1].strip()
        elif normalized.startswith("{") and normalized.endswith("}"):
            normalized = normalized[1:-1].strip()
        return self.variables.get(normalized, default)

    def add_data_value(self, column: str, value: Any) -> None:
        if column in self.current_row:
            self.commit_row()
        self.current_row[column] = value

    def commit_row(self) -> None:
        if self.current_row:
            self.data_rows.append(self.current_row.copy())
            self.current_row.clear()

    async def send_progress(self, message: str, level: str = "info") -> None:
        if self.progress is not None:
            await self.progress(message, level)
