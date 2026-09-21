from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from contextvars import ContextVar
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


@dataclass(frozen=True, slots=True)
class InputPromptRequest:
    variable_name: str
    title: str
    message: str
    default_value: str | float | bool | None
    input_mode: str
    min_value: float | None = None
    max_value: float | None = None
    max_length: int | None = None
    required: bool = True
    select_options: tuple[str, ...] | None = None


class InputPromptGateway(Protocol):
    async def request_input(
        self, request: InputPromptRequest, *, timeout_seconds: float
    ) -> str | None: ...


@dataclass(frozen=True, slots=True)
class NestedWorkflowResult:
    reference: str
    name: str
    success: bool
    variables: Mapping[str, Any]
    executed_nodes: int
    failed_nodes: int
    error: str | None = None
    waited: bool = True
    sensitive_outputs: frozenset[str] = frozenset()


class NestedWorkflowGateway(Protocol):
    async def run_workflow(
        self,
        reference: str,
        *,
        variables: Mapping[str, Any],
        wait_complete: bool,
    ) -> NestedWorkflowResult: ...


class CanvasSubflowGateway(Protocol):
    async def run_subflow(
        self, *, group_id: str, name: str, inputs: Mapping[str, Any] | None = None
    ) -> NestedWorkflowResult: ...


@dataclass(frozen=True, slots=True)
class CustomModuleResult:
    module_id: str
    name: str
    success: bool
    outputs: Mapping[str, Any]
    executed_nodes: int
    failed_nodes: int
    error: str | None = None
    sensitive_outputs: frozenset[str] = frozenset()


class CustomModuleGateway(Protocol):
    def definition(self, module_id: str) -> Mapping[str, Any] | None: ...

    async def run_custom_module(
        self,
        *,
        module_id: str,
        parameter_values: Mapping[str, Any],
    ) -> CustomModuleResult: ...


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
    input_prompts: InputPromptGateway | None = None
    nested_workflows: NestedWorkflowGateway | None = None
    canvas_subflows: CanvasSubflowGateway | None = None
    custom_modules: CustomModuleGateway | None = None
    cancellation: CancellationToken | None = None
    clock: WorkflowClock = field(default_factory=WorkflowClock)
    data_rows: list[dict[str, Any]] = field(default_factory=list)
    sensitive_table_cells: set[tuple[int, Any]] = field(default_factory=set)
    network_monitors: dict[Any, BrowserRequestWatchPort] = field(default_factory=dict)
    current_row: dict[str, Any] = field(default_factory=dict)
    loop_stack: list[dict[str, Any]] = field(default_factory=list)
    execution_scopes: tuple[dict[str, Any], ...] = ()
    progress: Callable[[str, str], Awaitable[None]] | None = None
    node_boundary: Callable[[ExecutionContext, str], AbstractAsyncContextManager[None]] | None = None
    current_node_id: str | None = None
    current_execution_id: str | None = None
    should_break: bool = False
    should_continue: bool = False
    stop_workflow: bool = False
    stop_reason: str = ""
    _node_uses_sensitive_values: bool = field(default=False, repr=False)
    _node_sensitive_context: ContextVar[bool] = field(
        default_factory=lambda: ContextVar("workflow_node_sensitive", default=False),
        repr=False,
    )
    _node_artifact_context: ContextVar[tuple[bool, ArtifactWriter | None]] = field(
        default_factory=lambda: ContextVar(
            "workflow_node_artifacts", default=(False, None)
        ),
        repr=False,
    )

    def begin_node(self) -> None:
        self._node_uses_sensitive_values = False
        self._node_sensitive_context.set(False)

    def bind_node_artifacts(self) -> None:
        """Bind the current writer to this task before parallel node execution."""
        self._node_artifact_context.set((True, self.artifacts))

    def mark_sensitive_use(self) -> None:
        self._node_uses_sensitive_values = True
        self._node_sensitive_context.set(True)

    def resolve_value(self, value: Any, *, preserve_types: bool = False) -> Any:
        if references_sensitive_value(value, self.sensitive_variables):
            self.mark_sensitive_use()
        return resolve_value(value, self.variables, self.credentials, preserve_types=preserve_types)

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
            self.node_uses_sensitive_values if sensitive is None else sensitive
        )
        if effective_sensitive:
            self.sensitive_variables.add(name)
        else:
            self.sensitive_variables.discard(name)

    @property
    def node_uses_sensitive_values(self) -> bool:
        return self._node_sensitive_context.get()

    @property
    def node_artifacts(self) -> ArtifactWriter | None:
        bound, writer = self._node_artifact_context.get()
        return writer if bound else self.artifacts

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
