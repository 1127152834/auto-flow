from __future__ import annotations

import asyncio
import copy
import json
import os
import sys
from collections.abc import Mapping
from contextvars import ContextVar
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any, TextIO
from uuid import uuid4

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import (
    CustomModuleResult,
    ExecutionContext,
    InputPromptRequest,
    NestedWorkflowResult,
)
from autoflow.domain.workflows.runs import WorkflowArtifact
from autoflow.infrastructure.filesystem.workflow_artifacts import WorkflowArtifactStore
from autoflow.infrastructure.filesystem.workflow_table_workbook import (
    OpenpyxlTableWorkbookRenderer,
)
from autoflow.providers.integrations import WorkflowIntegrationGateway
from autoflow.providers.model import WorkflowModelGateway

from .workflow_session import launch_workflow_session

_MAX_INLINE_RESULT_BYTES = 64 * 1024


def run_workflow_worker(
    stopped: Event, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout
) -> int:
    try:
        command = _read_command(stdin)
        return asyncio.run(_run(command, stopped, stdout, stdin))
    except BaseException:  # noqa: BLE001 -- secrets and browser details stay isolated.
        _write(stdout, {"type": "error", "error": "Workflow worker failed"})
        return 1


async def _run(
    command: dict[str, Any],
    stopped: Event,
    stdout: TextIO,
    stdin: TextIO | None = None,
) -> int:
    command_bus = _WorkerCommandBus(
        asyncio.get_running_loop(), stopped, stdout, command
    )
    if stdin is not None:
        Thread(
            target=_watch_stdin,
            args=(stdin, stopped, command_bus.receive, command_bus.close),
            daemon=True,
        ).start()
    requires_browser = command.get("requiresBrowser", True)
    if not isinstance(requires_browser, bool):
        raise TypeError("requiresBrowser must be a boolean")
    _required_string(command, "runId")
    _required_string(command, "profileId")
    if not requires_browser:
        return await _run_in_session(command, stopped, stdout, None, command_bus)
    executable = Path(_required_environment("CLOAKBROWSER_BINARY_PATH"))
    cache = Path(_required_environment("CLOAKBROWSER_CACHE_DIR"))
    if (
        not executable.is_absolute()
        or not executable.is_file()
        or not cache.is_absolute()
    ):
        raise ValueError("workflow worker paths are invalid")
    async with launch_workflow_session(command) as browser:
        return await _run_in_session(command, stopped, stdout, browser, command_bus)


async def _run_in_session(
    command: dict[str, Any],
    stopped: Event,
    stdout: TextIO,
    browser: Any,
    command_bus: _WorkerCommandBus,
) -> int:
    run_id = _required_string(command, "runId")
    profile_id = _required_string(command, "profileId")
    ready: dict[str, Any] = {
        "type": "ready",
        "runId": run_id,
        "profileId": profile_id,
    }
    child_pid = getattr(browser, "browser_pid", None)
    if isinstance(child_pid, int):
        ready["childPid"] = child_pid
    _write(stdout, ready)
    document = command.get("document")
    if isinstance(document, dict):
        workflow_id = _required_string(command, "workflowId")
        artifact_root = Path(_required_string(command, "artifactRoot"))
        if not artifact_root.is_absolute():
            raise ValueError("artifactRoot must be absolute")
        artifacts = _WorkerArtifactRepository(stdout)
        integrations = WorkflowIntegrationGateway()
        context = ExecutionContext(
            variables=_initial_variables(document),
            browser=browser,
            cancellation=_ThreadCancellation(stopped),
            table_workbooks=OpenpyxlTableWorkbookRenderer(),
            models=WorkflowModelGateway(_model_bindings(command)),
            external_integrations=integrations,
        )
        sink = _WorkerEventSink(
            stdout,
            run_id=run_id,
            workflow_id=workflow_id,
            context=context,
            artifacts=artifacts,
            artifact_root=artifact_root,
        )
        context.events = sink
        context.input_prompts = command_bus.for_context(context)
        registry = build_production_executor_registry()
        nested = _WorkerNestedWorkflows(
            command.get("workflowDependencies"),
            registry=registry,
            parent=context,
            sink=sink,
            command_bus=command_bus,
        )
        context.nested_workflows = nested
        custom_modules = _WorkerCustomModules(
            command.get("customModuleDependencies"),
            registry=registry,
            parent=context,
            sink=sink,
            command_bus=command_bus,
            nested_workflows=nested,
        )
        context.custom_modules = custom_modules
        nested.custom_modules = custom_modules
        canvas_subflows = _WorkerCanvasSubflows(
            document,
            registry=registry,
            parent=context,
            sink=sink,
            command_bus=command_bus,
            nested_workflows=nested,
        )
        context.canvas_subflows = canvas_subflows
        try:
            result = await WorkflowRuntime(registry).execute(
                canvas_subflows.top_level_document(), context
            )
            await nested.drain()
        finally:
            await integrations.close()
        terminal = "execution:completed" if result.success else "execution:failed"
        _write(
            stdout,
            {
                "type": terminal,
                "runId": run_id,
                "workflowId": workflow_id,
                "executedNodes": len(result.executed_node_ids),
                "failedNodeId": result.failed_node_id,
                "issues": [
                    {
                        "nodeId": issue.node_id,
                        "path": issue.path,
                        "code": issue.code,
                        "message": issue.message,
                    }
                    for issue in result.issues
                ],
                "error": result.node_result.error if result.node_result else None,
            },
        )
        return 0 if result.success else 2
    while not stopped.is_set():
        await asyncio.sleep(0.05)
    return 0


def _model_bindings(command: dict[str, Any]) -> list[Mapping[str, Any]]:
    raw = command.pop("modelBindings", [])
    if not isinstance(raw, list) or not all(isinstance(item, Mapping) for item in raw):
        raise ValueError("modelBindings must be a list")
    return raw


class _ThreadCancellation:
    def __init__(self, stopped: Event) -> None:
        self._stopped = stopped

    @property
    def cancelled(self) -> bool:
        return self._stopped.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise asyncio.CancelledError


class _WorkerArtifactRepository:
    def __init__(self, stdout: TextIO) -> None:
        self._stdout = stdout
        self._lock = Lock()
        self._ordinal = 0
        self._by_execution: dict[str, list[str]] = {}

    def register_artifact(
        self,
        *,
        run_id: str,
        artifact_id: str,
        node_id: str,
        execution_id: str | None,
        relative_path: str,
        size: int,
        sha256: str,
        mime_type: str,
        purpose: str,
    ) -> WorkflowArtifact:
        with self._lock:
            self._ordinal += 1
            if execution_id:
                self._by_execution.setdefault(execution_id, []).append(artifact_id)
            _write(
                self._stdout,
                {
                    "type": "artifact:registered",
                    "runId": run_id,
                    "artifactId": artifact_id,
                    "nodeId": node_id,
                    "executionId": execution_id,
                    "relativePath": relative_path,
                    "size": size,
                    "sha256": sha256,
                    "mimeType": mime_type,
                    "purpose": purpose,
                },
            )
            return WorkflowArtifact(
                run_id=run_id,
                artifact_id=artifact_id,
                ordinal=self._ordinal,
                node_id=node_id,
                execution_id=execution_id,
                relative_path=relative_path,
                size=size,
                sha256=sha256,
                mime_type=mime_type,
                purpose=purpose,
                event_sequence=0,
            )

    def take(self, execution_id: str) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._by_execution.pop(execution_id, ()))


class _WorkerEventSink:
    def __init__(
        self,
        stdout: TextIO,
        *,
        run_id: str,
        workflow_id: str,
        context: ExecutionContext,
        artifacts: _WorkerArtifactRepository,
        artifact_root: Path,
    ) -> None:
        self._stdout = stdout
        self._run_id = run_id
        self._workflow_id = workflow_id
        self._context = context
        self._artifacts = artifacts
        self._artifact_root = artifact_root

    def for_context(self, context: ExecutionContext) -> _WorkerEventSink:
        return _WorkerEventSink(
            self._stdout,
            run_id=self._run_id,
            workflow_id=self._workflow_id,
            context=context,
            artifacts=self._artifacts,
            artifact_root=self._artifact_root,
        )

    async def publish(self, event: Mapping[str, Any]) -> None:
        event = dict(event)
        node_id = event.get("nodeId")
        execution_id = event.get("executionId")
        if isinstance(node_id, str) and isinstance(execution_id, str):
            self._context.current_node_id = node_id
            self._context.current_execution_id = execution_id
            if event.get("type") == "execution:node_start":
                self._context.artifacts = WorkflowArtifactStore(
                    self._artifact_root,
                    self._artifacts,
                ).writer(
                    run_id=self._run_id,
                    node_id=node_id,
                    execution_id=execution_id,
                    purpose="result",
                    cancellation=self._context.cancellation,
                )
            elif event.get("type") == "execution:node_complete":
                await self._externalize_large_result(event, execution_id)
                event["artifactIds"] = list(self._artifacts.take(execution_id))
                self._context.log_records.append(
                    {
                        "timestamp": self._context.clock.now().isoformat(),
                        "level": event.get("logLevel") or ("error" if not event.get("success") else "info"),
                        "message": event.get("message") or event.get("error") or "",
                        "duration": event.get("duration") or 0,
                        "nodeId": node_id,
                    }
                )
        for key in ("message", "error"):
            value = event.get(key)
            if isinstance(value, str) and len(value.encode("utf-8")) > 4096:
                event[key] = value[:1000] + "…"
        _write(
            self._stdout,
            {
                **event,
                "runId": self._run_id,
                "workflowId": self._workflow_id,
            },
        )

    async def _externalize_large_result(
        self, event: dict[str, Any], execution_id: str
    ) -> None:
        value = event.get("data")
        if value is None:
            return
        encoded = json.dumps(
            value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode("utf-8")
        if len(encoded) <= _MAX_INLINE_RESULT_BYTES:
            return
        writer = self._context.artifacts
        if writer is None:
            raise RuntimeError("节点大结果缺少产物写入器")
        await writer.write_bytes(
            name=f"node-results/{execution_id}.json",
            content=encoded,
            mime_type="application/json",
        )
        event["data"] = {
            "externalized": True,
            "mimeType": "application/json",
            "size": len(encoded),
        }


def _initial_variables(document: dict[str, Any]) -> dict[str, Any]:
    variables = document.get("variables", [])
    if not isinstance(variables, list):
        return {}
    return {
        item["name"]: item.get("value")
        for item in variables
        if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"]
    }


class _WorkerNestedWorkflows:
    def __init__(
        self,
        snapshots: Any,
        *,
        registry: Any,
        parent: ExecutionContext,
        sink: _WorkerEventSink,
        command_bus: _WorkerCommandBus,
    ) -> None:
        self._snapshots = (
            {str(key): copy.deepcopy(value) for key, value in snapshots.items()}
            if isinstance(snapshots, Mapping)
            else {}
        )
        self._registry = registry
        self._parent = parent
        self._sink = sink
        self._command_bus = command_bus
        self._stack: ContextVar[tuple[str, ...]] = ContextVar(
            "workflow_chain_stack", default=()
        )
        self._background: set[asyncio.Task[NestedWorkflowResult]] = set()
        self.custom_modules: _WorkerCustomModules | None = None

    async def run_workflow(
        self,
        reference: str,
        *,
        variables: Mapping[str, Any],
        wait_complete: bool,
    ) -> NestedWorkflowResult:
        snapshot, canonical = self._resolve(reference)
        name = str(snapshot.get("name") or canonical)
        if not wait_complete:
            task = asyncio.create_task(
                self._execute(snapshot, canonical, variables),
                name=f"nested-workflow:{canonical}",
            )
            self._background.add(task)
            task.add_done_callback(self._background.discard)
            return NestedWorkflowResult(
                reference, name, True, {}, 0, 0, waited=False
            )
        return await self._execute(snapshot, canonical, variables)

    async def drain(self) -> None:
        while self._background:
            await asyncio.gather(*tuple(self._background), return_exceptions=True)

    def _resolve(self, reference: str) -> tuple[dict[str, Any], str]:
        normalized = reference.strip().strip('"')
        candidates = [normalized]
        if normalized.lower().endswith(".json"):
            candidates.append(normalized[:-5])
        else:
            candidates.append(f"{normalized}.json")
        for candidate in candidates:
            snapshot = self._snapshots.get(candidate)
            if isinstance(snapshot, dict):
                canonical = str(snapshot.get("id") or candidate)
                return copy.deepcopy(snapshot), canonical
        raise RuntimeError(
            f"找不到工作流「{reference}」。请确认它存在于当前工作区。"
        )

    async def _execute(
        self,
        snapshot: dict[str, Any],
        canonical: str,
        variables: Mapping[str, Any],
    ) -> NestedWorkflowResult:
        stack = self._stack.get()
        name = str(snapshot.get("name") or canonical)
        reference = f"{name}.json"
        if canonical in stack:
            return NestedWorkflowResult(
                reference,
                name,
                False,
                {},
                0,
                1,
                f"检测到工作流循环调用：{' -> '.join(stack)} -> {canonical}。请检查工作流之间的相互调用关系。",
            )
        if len(stack) >= 16:
            return NestedWorkflowResult(
                reference,
                name,
                False,
                {},
                0,
                1,
                "工作流嵌套调用层数过深（>16），已终止以避免无限递归。",
            )
        token = self._stack.set((*stack, canonical))
        child = ExecutionContext(
            variables={**_initial_variables(snapshot), **copy.deepcopy(dict(variables))},
            sensitive_variables=set(self._parent.sensitive_variables),
            execution_scopes=(
                *self._parent.execution_scopes,
                {"kind": "workflow", "id": canonical, "name": name},
            ),
            browser=self._parent.browser,
            table_workbooks=self._parent.table_workbooks,
            credentials=self._parent.credentials,
            models=self._parent.models,
            external_integrations=self._parent.external_integrations,
            log_records=self._parent.log_records,
            cancellation=self._parent.cancellation,
            clock=self._parent.clock,
        )
        child_sink = self._sink.for_context(child)
        child.events = child_sink
        child.input_prompts = self._command_bus.for_context(child)
        child.nested_workflows = self
        if self.custom_modules is not None:
            child.custom_modules = self.custom_modules.for_context(child, child_sink)
        canvas_subflows = _WorkerCanvasSubflows(
            snapshot,
            registry=self._registry,
            parent=child,
            sink=child_sink,
            command_bus=self._command_bus,
            nested_workflows=self,
        )
        child.canvas_subflows = canvas_subflows
        await child_sink.publish(
            {
                "type": "subflow:started",
                "subflowId": str(uuid4()),
                "name": name,
                "file": reference,
                "depth": len(stack),
            }
        )
        try:
            result = await WorkflowRuntime(self._registry).execute(
                canvas_subflows.top_level_document(), child
            )
            nested = NestedWorkflowResult(
                reference=reference,
                name=name,
                success=result.success,
                variables=copy.deepcopy(child.variables),
                executed_nodes=len(result.executed_node_ids),
                failed_nodes=0 if result.success else 1,
                error=result.node_result.error if result.node_result else None,
            )
            await child_sink.publish(
                {
                    "type": "subflow:completed",
                    "name": name,
                    "success": nested.success,
                    "executedNodes": nested.executed_nodes,
                    "failedNodes": nested.failed_nodes,
                    "error": nested.error,
                }
            )
            return nested
        finally:
            self._stack.reset(token)


class _WorkerCustomModules:
    def __init__(
        self,
        snapshots: Any,
        *,
        registry: Any,
        parent: ExecutionContext,
        sink: _WorkerEventSink,
        command_bus: _WorkerCommandBus,
        nested_workflows: _WorkerNestedWorkflows,
        stack: ContextVar[tuple[str, ...]] | None = None,
    ) -> None:
        self._snapshots = (
            {str(key): copy.deepcopy(value) for key, value in snapshots.items()}
            if isinstance(snapshots, Mapping)
            else {}
        )
        self._registry = registry
        self._parent = parent
        self._sink = sink
        self._command_bus = command_bus
        self._nested_workflows = nested_workflows
        self._stack = stack or ContextVar("custom_module_stack", default=())

    def for_context(
        self, context: ExecutionContext, sink: _WorkerEventSink
    ) -> _WorkerCustomModules:
        return _WorkerCustomModules(
            self._snapshots,
            registry=self._registry,
            parent=context,
            sink=sink,
            command_bus=self._command_bus,
            nested_workflows=self._nested_workflows,
            stack=self._stack,
        )

    def definition(self, module_id: str) -> Mapping[str, Any] | None:
        value = self._snapshots.get(module_id)
        return copy.deepcopy(value) if isinstance(value, Mapping) else None

    async def run_custom_module(
        self,
        *,
        module_id: str,
        parameter_values: Mapping[str, Any],
    ) -> CustomModuleResult:
        definition = self._snapshots.get(module_id)
        if not isinstance(definition, Mapping):
            return CustomModuleResult(
                module_id,
                module_id,
                False,
                {},
                0,
                1,
                f"自定义模块不存在: {module_id}",
            )
        name = str(definition.get("display_name") or definition.get("name") or module_id)
        stack = self._stack.get()
        if module_id in stack:
            return CustomModuleResult(
                module_id,
                name,
                False,
                {},
                0,
                1,
                f"检测到自定义模块循环引用: {' -> '.join(stack)} -> {module_id}",
            )
        if len(stack) >= 16:
            return CustomModuleResult(
                module_id,
                name,
                False,
                {},
                0,
                1,
                f"自定义模块嵌套层数过深(>16): {' -> '.join(stack)}",
            )
        workflow = definition.get("workflow")
        if not isinstance(workflow, Mapping):
            return CustomModuleResult(
                module_id,
                name,
                False,
                {},
                0,
                1,
                f"自定义模块 '{name}' 缺少工作流定义",
            )
        document = copy.deepcopy(dict(workflow))
        token = self._stack.set((*stack, module_id))
        variables = _initial_variables(document)
        sensitive_parameters: set[str] = set()
        for key, value in parameter_values.items():
            resolved, sensitive = self._parent.resolve_value_with_sensitivity(value)
            variables[str(key)] = copy.deepcopy(resolved)
            if sensitive:
                sensitive_parameters.add(str(key))
        child = ExecutionContext(
            variables=variables,
            sensitive_variables=sensitive_parameters,
            execution_scopes=(
                *self._parent.execution_scopes,
                {"kind": "customModule", "id": module_id, "name": name},
            ),
            browser=self._parent.browser,
            table_workbooks=self._parent.table_workbooks,
            credentials=self._parent.credentials,
            models=self._parent.models,
            external_integrations=self._parent.external_integrations,
            log_records=self._parent.log_records,
            cancellation=self._parent.cancellation,
            clock=self._parent.clock,
        )
        child_sink = self._sink.for_context(child)
        child.events = child_sink
        child.input_prompts = self._command_bus.for_context(child)
        child.nested_workflows = self._nested_workflows
        child.custom_modules = self.for_context(child, child_sink)
        canvas_subflows = _WorkerCanvasSubflows(
            document,
            registry=self._registry,
            parent=child,
            sink=child_sink,
            command_bus=self._command_bus,
            nested_workflows=self._nested_workflows,
        )
        child.canvas_subflows = canvas_subflows
        try:
            result = await WorkflowRuntime(self._registry).execute(
                canvas_subflows.top_level_document(), child
            )
            output_values: dict[str, Any] = {}
            outputs = definition.get("outputs", [])
            if isinstance(outputs, list):
                for output in outputs:
                    if not isinstance(output, Mapping):
                        continue
                    output_name = output.get("name")
                    if isinstance(output_name, str) and output_name:
                        output_values[output_name] = copy.deepcopy(
                            child.variables.get(output_name)
                        )
            return CustomModuleResult(
                module_id,
                name,
                result.success,
                output_values if result.success else {},
                len(result.executed_node_ids),
                0 if result.success else 1,
                result.node_result.error if result.node_result else None,
                frozenset(output_values) & child.sensitive_variables,
            )
        finally:
            self._stack.reset(token)


class _WorkerCanvasSubflows:
    def __init__(
        self,
        document: dict[str, Any],
        *,
        registry: Any,
        parent: ExecutionContext,
        sink: _WorkerEventSink,
        command_bus: _WorkerCommandBus,
        nested_workflows: _WorkerNestedWorkflows,
        stack: ContextVar[tuple[str, ...]] | None = None,
    ) -> None:
        self._document = copy.deepcopy(document)
        self._registry = registry
        self._parent = parent
        self._sink = sink
        self._command_bus = command_bus
        self._nested_workflows = nested_workflows
        self._stack = stack or ContextVar("canvas_subflow_stack", default=())

    def for_context(
        self, parent: ExecutionContext, sink: _WorkerEventSink
    ) -> _WorkerCanvasSubflows:
        return _WorkerCanvasSubflows(
            self._document,
            registry=self._registry,
            parent=parent,
            sink=sink,
            command_bus=self._command_bus,
            nested_workflows=self._nested_workflows,
            stack=self._stack,
        )

    def top_level_document(self) -> dict[str, Any]:
        excluded: set[str] = set()
        for node in self._nodes():
            if self._is_definition(node):
                excluded.add(str(node.get("id") or ""))
                excluded.update(self._members(node))
        return self._subset(excluded, invert=True)

    async def run_subflow(
        self, *, group_id: str, name: str
    ) -> NestedWorkflowResult:
        definition = self._find_definition(group_id, name)
        if definition is None:
            target = name or group_id
            return NestedWorkflowResult(
                target, target, False, {}, 0, 1, f"找不到子流程: {target}"
            )
        identity = str(definition.get("id") or name or group_id)
        display_name = str(_node_data(definition).get("subflowName") or "子流程")
        stack = self._stack.get()
        if identity in stack:
            return NestedWorkflowResult(
                identity,
                display_name,
                False,
                {},
                0,
                1,
                f"检测到子流程循环引用: {' -> '.join(stack)} -> {identity}",
            )
        if len(stack) >= 32:
            return NestedWorkflowResult(
                identity,
                display_name,
                False,
                {},
                0,
                1,
                f"子流程嵌套层数过深(>32): {' -> '.join(stack)}",
            )
        members = self._members(definition)
        if not members:
            return NestedWorkflowResult(
                identity, display_name, True, self._parent.variables, 0, 0
            )
        token = self._stack.set((*stack, identity))
        child = ExecutionContext(
            variables=self._parent.variables,
            sensitive_variables=self._parent.sensitive_variables,
            execution_scopes=(
                *self._parent.execution_scopes,
                {"kind": "subflow", "id": identity, "name": display_name},
            ),
            browser=self._parent.browser,
            table_workbooks=self._parent.table_workbooks,
            credentials=self._parent.credentials,
            models=self._parent.models,
            external_integrations=self._parent.external_integrations,
            log_records=self._parent.log_records,
            cancellation=self._parent.cancellation,
            clock=self._parent.clock,
        )
        child_sink = self._sink.for_context(child)
        child.events = child_sink
        child.input_prompts = self._command_bus.for_context(child)
        child.nested_workflows = self._nested_workflows
        if isinstance(self._parent.custom_modules, _WorkerCustomModules):
            child.custom_modules = self._parent.custom_modules.for_context(
                child, child_sink
            )
        child.canvas_subflows = self.for_context(child, child_sink)
        try:
            result = await WorkflowRuntime(self._registry).execute(
                self._subset(members), child
            )
            return NestedWorkflowResult(
                identity,
                display_name,
                result.success,
                child.variables,
                len(result.executed_node_ids),
                0 if result.success else 1,
                result.node_result.error if result.node_result else None,
            )
        finally:
            self._stack.reset(token)

    def _nodes(self) -> list[dict[str, Any]]:
        nodes = self._document.get("nodes", [])
        return [dict(node) for node in nodes if isinstance(node, Mapping)] if isinstance(nodes, list) else []

    def _edges(self) -> list[dict[str, Any]]:
        edges = self._document.get("edges", [])
        return [dict(edge) for edge in edges if isinstance(edge, Mapping)] if isinstance(edges, list) else []

    def _is_definition(self, node: Mapping[str, Any]) -> bool:
        node_type = _node_type(node)
        data = _node_data(node)
        return node_type == "subflow_header" or (
            node_type == "group" and data.get("isSubflow") is True
        )

    def _find_definition(
        self, group_id: str, name: str
    ) -> dict[str, Any] | None:
        definitions = [node for node in self._nodes() if self._is_definition(node)]
        if name:
            match = next(
                (
                    node
                    for node in definitions
                    if _node_data(node).get("subflowName") == name
                ),
                None,
            )
            if match is not None:
                return match
        return next(
            (node for node in definitions if node.get("id") == group_id), None
        )

    def _members(self, definition: Mapping[str, Any]) -> set[str]:
        if _node_type(definition) == "subflow_header":
            return self._header_members(str(definition.get("id") or ""))
        position = definition.get("position")
        position = position if isinstance(position, Mapping) else {}
        data = _node_data(definition)
        style = definition.get("style")
        style = style if isinstance(style, Mapping) else {}
        left = _dimension(position.get("x"), 0)
        top = _dimension(position.get("y"), 0)
        width = _dimension(
            data.get("width", definition.get("width", style.get("width"))), 300
        )
        height = _dimension(
            data.get("height", definition.get("height", style.get("height"))), 200
        )
        members: set[str] = set()
        for node in self._nodes():
            node_id = str(node.get("id") or "")
            if node_id == definition.get("id") or _node_type(node) in {"group", "note"}:
                continue
            node_position = node.get("position")
            node_position = node_position if isinstance(node_position, Mapping) else {}
            x = _dimension(node_position.get("x"), 0)
            y = _dimension(node_position.get("y"), 0)
            if left <= x <= left + width and top <= y <= top + height:
                members.add(node_id)
        return members

    def _header_members(self, header_id: str) -> set[str]:
        nodes = {str(node.get("id") or ""): node for node in self._nodes()}
        members: set[str] = set()
        queue = [header_id]
        visited: set[str] = set()
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for edge in self._edges():
                if edge.get("source") != current:
                    continue
                target = str(edge.get("target") or "")
                target_node = nodes.get(target)
                if target_node is None or target in visited:
                    continue
                if _node_type(target_node) not in {"group", "note", "subflow_header"}:
                    members.add(target)
                    queue.append(target)
        return members

    def _subset(self, node_ids: set[str], *, invert: bool = False) -> dict[str, Any]:
        selected = {
            str(node.get("id") or "")
            for node in self._nodes()
            if (str(node.get("id") or "") not in node_ids) == invert
        }
        result = copy.deepcopy(self._document)
        result["nodes"] = [
            node for node in self._nodes() if str(node.get("id") or "") in selected
        ]
        result["edges"] = [
            edge
            for edge in self._edges()
            if edge.get("source") in selected and edge.get("target") in selected
        ]
        return result


def _node_data(node: Mapping[str, Any]) -> Mapping[str, Any]:
    data = node.get("data")
    return data if isinstance(data, Mapping) else {}


def _node_type(node: Mapping[str, Any]) -> str:
    data = _node_data(node)
    value = data.get("moduleType") or node.get("type") or ""
    return str(value)


def _dimension(value: Any, default: float) -> float:
    if isinstance(value, str):
        value = value.removesuffix("px")
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_command(stdin: TextIO) -> dict[str, Any]:
    raw = stdin.readline()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise TypeError("workflow worker command must be an object")
    return value


class _WorkerCommandBus:
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        stopped: Event,
        stdout: TextIO,
        command: dict[str, Any],
    ) -> None:
        self._loop = loop
        self._stopped = stopped
        self._stdout = stdout
        self._run_id = _required_string(command, "runId")
        workflow_id = command.get("workflowId")
        self._workflow_id = workflow_id if isinstance(workflow_id, str) else ""
        self._pending: dict[str, asyncio.Future[str | None]] = {}

    def for_context(self, context: ExecutionContext) -> _BoundInputPrompts:
        return _BoundInputPrompts(self, context)

    def receive(self, command: dict[str, Any]) -> None:
        if not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._apply, command)

    def close(self) -> None:
        if not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._cancel_pending)

    async def request_input(
        self,
        context: ExecutionContext,
        request: InputPromptRequest,
        *,
        timeout_seconds: float,
    ) -> str | None:
        request_id = str(uuid4())
        future: asyncio.Future[str | None] = self._loop.create_future()
        self._pending[request_id] = future
        await _publish_prompt(context, request_id, request)
        status = "expired"
        try:
            value = (
                await asyncio.wait_for(future, timeout_seconds)
                if timeout_seconds > 0
                else await future
            )
            status = "cancelled" if value is None else "answered"
            return value
        finally:
            self._pending.pop(request_id, None)
            if context.events is not None:
                await context.events.publish(
                    {
                        "type": "execution:input_prompt_closed",
                        "requestId": request_id,
                        "nodeId": context.current_node_id,
                        "executionId": context.current_execution_id,
                        "status": status,
                    }
                )

    def _apply(self, command: dict[str, Any]) -> None:
        if command.get("type") != "input_prompt_result":
            return
        request_id = command.get("requestId")
        command_id = command.get("commandId")
        value = command.get("value")
        future = self._pending.get(request_id) if isinstance(request_id, str) else None
        if future is None or future.done() or not isinstance(command_id, str):
            return
        if value is not None and not isinstance(value, str):
            return
        future.set_result(value)
        _write(
            self._stdout,
            {
                "type": "execution:command_applied",
                "runId": self._run_id,
                "workflowId": self._workflow_id,
                "commandId": command_id,
                "requestId": request_id,
            },
        )

    def _cancel_pending(self) -> None:
        for future in self._pending.values():
            if not future.done():
                future.cancel()


class _BoundInputPrompts:
    def __init__(self, bus: _WorkerCommandBus, context: ExecutionContext) -> None:
        self._bus = bus
        self._context = context

    async def request_input(
        self, request: InputPromptRequest, *, timeout_seconds: float
    ) -> str | None:
        return await self._bus.request_input(
            self._context, request, timeout_seconds=timeout_seconds
        )


async def _publish_prompt(
    context: ExecutionContext, request_id: str, request: InputPromptRequest
) -> None:
    if context.events is None:
        raise RuntimeError("输入请求事件服务不可用")
    await context.events.publish(
        {
            "type": "execution:input_prompt",
            "requestId": request_id,
            "nodeId": context.current_node_id,
            "executionId": context.current_execution_id,
            "variableName": request.variable_name,
            "title": request.title,
            "message": request.message,
            "defaultValue": request.default_value,
            "inputMode": request.input_mode,
            "minValue": request.min_value,
            "maxValue": request.max_value,
            "maxLength": request.max_length,
            "required": request.required,
            "selectOptions": list(request.select_options)
            if request.select_options is not None
            else None,
        }
    )


def _watch_stdin(
    stdin: TextIO,
    stopped: Event,
    receive: Any,
    close: Any,
) -> None:
    try:
        while raw := stdin.readline():
            try:
                command = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(command, dict):
                receive(command)
    finally:
        stopped.set()
        close()


def _required_string(values: dict[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{key} must be a string")
    return value


def _required_environment(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise TypeError(f"{key} must be a string")
    return value


def _write(stdout: TextIO, event: dict[str, object]) -> None:
    stdout.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    stdout.flush()
