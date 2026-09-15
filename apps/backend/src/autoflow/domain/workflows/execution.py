from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from .browser import BrowserRequestWatchPort, BrowserSessionPort
from .variables import CredentialReader, references_sensitive_value, resolve_value


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

    async def write_binary_output(
        self,
        *,
        output_path: str,
        content: bytes,
        mime_type: str,
        expected_identity: str | None = None,
    ) -> str: ...

    async def read_binary_output(
        self,
        *,
        output_path: str,
        max_bytes: int,
    ) -> BinaryOutputSnapshot: ...


@dataclass(frozen=True, slots=True)
class BinaryOutputSnapshot:
    content: bytes | None
    identity: str


class TableWorkbookRenderer(Protocol):
    async def render(
        self,
        *,
        rows: Sequence[Mapping[str, Any]],
        sheet_name: str,
        existing_content: bytes | None,
        cancellation: CancellationToken | None,
    ) -> bytes: ...

    async def render_grid(
        self,
        *,
        rows: Sequence[Sequence[str]],
        sheet_name: str,
        header_row: int,
        include_header: bool,
        cancellation: CancellationToken | None,
    ) -> bytes: ...


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
    sensitive_variables: set[str] = field(default_factory=set)
    browser: BrowserSessionPort | None = None
    artifacts: ArtifactWriter | None = None
    table_workbooks: TableWorkbookRenderer | None = None
    credentials: CredentialReader | None = None
    models: ModelGateway | None = None
    external_integrations: ExternalIntegrationGateway | None = None
    events: WorkflowEventSink | None = None
    cancellation: CancellationToken | None = None
    clock: WorkflowClock = field(default_factory=WorkflowClock)
    data_rows: list[dict[str, Any]] = field(default_factory=list)
    sensitive_table_cells: set[tuple[int, Any]] = field(default_factory=set)
    network_monitors: dict[Any, BrowserRequestWatchPort] = field(default_factory=dict)
    current_row: dict[str, Any] = field(default_factory=dict)
    loop_stack: list[dict[str, Any]] = field(default_factory=list)
    progress: Callable[[str, str], Awaitable[None]] | None = None
    current_node_id: str | None = None
    current_execution_id: str | None = None
    _node_uses_sensitive_values: bool = field(default=False, repr=False)

    def begin_node(self) -> None:
        self._node_uses_sensitive_values = False

    def resolve_value(self, value: Any) -> Any:
        if references_sensitive_value(value, self.sensitive_variables):
            self._node_uses_sensitive_values = True
        return resolve_value(value, self.variables, self.credentials)

    def resolve_value_with_sensitivity(self, value: Any) -> tuple[Any, bool]:
        sensitive = references_sensitive_value(value, self.sensitive_variables)
        return self.resolve_value(value), sensitive

    def set_variable(
        self, name: str, value: Any, *, sensitive: bool | None = None
    ) -> None:
        if self.cancellation is not None:
            self.cancellation.raise_if_cancelled()
        self.variables[name] = value
        effective_sensitive = (
            self._node_uses_sensitive_values if sensitive is None else sensitive
        )
        if effective_sensitive:
            self.sensitive_variables.add(name)
        else:
            self.sensitive_variables.discard(name)

    @property
    def node_uses_sensitive_values(self) -> bool:
        return self._node_uses_sensitive_values

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
