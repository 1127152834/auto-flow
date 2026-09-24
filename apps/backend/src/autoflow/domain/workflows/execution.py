from __future__ import annotations

import copy
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, SupportsIndex

from .browser import BrowserRequestWatchPort, BrowserSessionPort
from .variables import CredentialReader, references_sensitive_value, resolve_value


class _TaskLocalStack(list[dict[str, Any]]):
    def __init__(self, values: list[dict[str, Any]] | None = None) -> None:
        super().__init__(values or [])
        self._branch: ContextVar[list[dict[str, Any]] | None] = ContextVar(
            "workflow_branch_loop_stack", default=None
        )

    def bind_branch(self) -> Token[list[dict[str, Any]] | None]:
        active = self._branch.get()
        source = list.__iter__(self) if active is None else iter(active)
        return self._branch.set([dict(state) for state in source])

    def reset_branch(self, token: Token[list[dict[str, Any]] | None]) -> None:
        self._branch.reset(token)

    def append(self, value: dict[str, Any]) -> None:
        active = self._branch.get()
        (list.append(self, value) if active is None else active.append(value))

    def pop(self, index: SupportsIndex = -1) -> dict[str, Any]:
        active = self._branch.get()
        return list.pop(self, index) if active is None else active.pop(index)

    def __len__(self) -> int:
        active = self._branch.get()
        return list.__len__(self) if active is None else len(active)

    def __iter__(self):  # type: ignore[no-untyped-def]
        active = self._branch.get()
        return list.__iter__(self) if active is None else iter(active)

    def __getitem__(self, index):  # type: ignore[no-untyped-def]
        active = self._branch.get()
        return list.__getitem__(self, index) if active is None else active[index]

    def __eq__(self, other: object) -> bool:
        return list(self) == other


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

    async def invoke_media(
        self,
        model_id: str,
        payload: Mapping[str, Any],
        *,
        check_cancelled: Callable[[], None] | None = None,
    ) -> Mapping[str, Any]: ...


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
class JsScriptResult:
    success: bool
    result: Any = None
    variables: Mapping[str, Any] | None = None
    error: str | None = None


class BrowserScriptGateway(Protocol):
    async def request_script(
        self,
        code: str,
        variables: Mapping[str, Any],
        *,
        timeout_seconds: float,
    ) -> JsScriptResult: ...


@dataclass(frozen=True, slots=True)
class SpeechResult:
    success: bool
    error: str | None = None


class SpeechGateway(Protocol):
    async def speak(
        self,
        text: str,
        *,
        lang: str,
        rate: float,
        pitch: float,
        volume: float,
        timeout_seconds: float,
    ) -> SpeechResult: ...


@dataclass(frozen=True, slots=True)
class DesktopActionResult:
    success: bool
    value: Any = None
    error: str | None = None


class DesktopActionGateway(Protocol):
    async def perform(
        self,
        action: str,
        payload: Mapping[str, Any],
        *,
        timeout_seconds: float,
    ) -> DesktopActionResult: ...


class WebhookTriggerGateway(Protocol):
    async def wait_for_webhook(
        self,
        *,
        webhook_id: str,
        method: str,
        validate_headers: Mapping[str, Any],
        validate_params: Mapping[str, Any],
        response_body: Any,
        response_status: int,
        timeout_seconds: float,
    ) -> Mapping[str, Any]: ...


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


class DebugControlPort(Protocol):
    async def before_node(
        self, context: ExecutionContext, *, node_id: str, label: str
    ) -> None: ...


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
    process_cleanup: Callable[[Any], Awaitable[None]] | None = None
    events: WorkflowEventSink | None = None
    input_prompts: InputPromptGateway | None = None
    browser_scripts: BrowserScriptGateway | None = None
    speech: SpeechGateway | None = None
    desktop_actions: DesktopActionGateway | None = None
    webhook_triggers: WebhookTriggerGateway | None = None
    nested_workflows: NestedWorkflowGateway | None = None
    canvas_subflows: CanvasSubflowGateway | None = None
    custom_modules: CustomModuleGateway | None = None
    cancellation: CancellationToken | None = None
    debug: DebugControlPort | None = None
    clock: WorkflowClock = field(default_factory=WorkflowClock)
    data_rows: list[dict[str, Any]] = field(default_factory=list)
    log_records: list[dict[str, Any]] = field(default_factory=list)
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
    variable_tracking_enabled: bool = False
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
    _variable_tracking_context: ContextVar[dict[str, Any] | None] = field(
        default_factory=lambda: ContextVar("workflow_variable_tracking", default=None),
        repr=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.loop_stack, _TaskLocalStack):
            self.loop_stack = _TaskLocalStack(self.loop_stack)

    def begin_node(self) -> None:
        self._node_uses_sensitive_values = False
        self._node_sensitive_context.set(False)

    def bind_node_artifacts(self) -> None:
        """Bind the current writer to this task before parallel node execution."""
        self._node_artifact_context.set((True, self.artifacts))

    def bind_branch_loop_stack(self) -> Token[list[dict[str, Any]] | None]:
        assert isinstance(self.loop_stack, _TaskLocalStack)
        return self.loop_stack.bind_branch()

    def reset_branch_loop_stack(
        self, token: Token[list[dict[str, Any]] | None]
    ) -> None:
        assert isinstance(self.loop_stack, _TaskLocalStack)
        self.loop_stack.reset_branch(token)

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
        self,
        name: str,
        value: Any,
        *,
        sensitive: bool | None = None,
        operation: Literal["create", "update", "scope_exit"] | None = None,
    ) -> None:
        if self.cancellation is not None:
            self.cancellation.raise_if_cancelled()
        tracking = self._variable_tracking_context.get()
        previous_values = tracking["values"] if tracking is not None else None
        existed = isinstance(previous_values, dict) and name in previous_values
        old_value = (
            copy.deepcopy(previous_values.get(name))
            if isinstance(previous_values, dict)
            else None
        )
        self.variables[name] = value
        effective_sensitive = (
            self.node_uses_sensitive_values if sensitive is None else sensitive
        )
        if effective_sensitive:
            self.sensitive_variables.add(name)
        else:
            self.sensitive_variables.discard(name)
        if tracking is not None and isinstance(previous_values, dict):
            old_sensitive = name in tracking["sensitive"]
            new_sensitive = name in self.sensitive_variables
            if (
                operation == "scope_exit"
                or not existed
                or old_value != value
                or old_sensitive != new_sensitive
            ):
                tracking["changes"].append(
                    {
                        "variable_name": name,
                        "old_value": "***" if old_sensitive else old_value,
                        "new_value": "***" if new_sensitive else copy.deepcopy(value),
                        "node_id": tracking["nodeId"],
                        "node_name": tracking["nodeName"],
                        "executionId": tracking["executionId"],
                        "operation": operation or ("update" if existed else "create"),
                        "value_type": _variable_value_type(value),
                    }
                )
            previous_values[name] = copy.deepcopy(value)
            if new_sensitive:
                tracking["sensitive"].add(name)
            else:
                tracking["sensitive"].discard(name)

    def delete_variable(
        self,
        name: str,
        *,
        operation: Literal["update", "scope_exit"] = "update",
    ) -> None:
        tracking = self._variable_tracking_context.get()
        previous_values = tracking["values"] if tracking is not None else None
        existed = isinstance(previous_values, dict) and name in previous_values
        old_value = (
            copy.deepcopy(previous_values.get(name))
            if isinstance(previous_values, dict)
            else None
        )
        old_sensitive = bool(tracking is not None and name in tracking["sensitive"])
        self.variables.pop(name, None)
        self.sensitive_variables.discard(name)
        if tracking is not None and isinstance(previous_values, dict) and existed:
            tracking["changes"].append(
                {
                    "variable_name": name,
                    "old_value": "***" if old_sensitive else old_value,
                    "new_value": None,
                    "node_id": tracking["nodeId"],
                    "node_name": tracking["nodeName"],
                    "executionId": tracking["executionId"],
                    "operation": operation,
                    "value_type": "null",
                }
            )
            previous_values.pop(name, None)
            tracking["sensitive"].discard(name)

    def begin_variable_tracking(
        self, *, node_id: str, node_name: str, execution_id: str
    ) -> Token[dict[str, Any] | None] | None:
        if not self.variable_tracking_enabled:
            return None
        return self._variable_tracking_context.set(
            {
                "nodeId": node_id,
                "nodeName": node_name,
                "executionId": execution_id,
                "values": copy.deepcopy(self.variables),
                "sensitive": set(self.sensitive_variables),
                "changes": [],
            }
        )

    def end_variable_tracking(
        self, token: Token[dict[str, Any] | None] | None
    ) -> list[dict[str, Any]]:
        if token is None:
            return []
        tracking = self._variable_tracking_context.get()
        changes = copy.deepcopy(tracking["changes"]) if tracking is not None else []
        self._variable_tracking_context.reset(token)
        return changes

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


def _variable_value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"
