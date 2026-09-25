from __future__ import annotations

import asyncio
import copy
import json
from collections.abc import Coroutine, Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any
from uuid import uuid4

from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.domain.workflows.graph import ExecutionGraph, WorkflowNode, parse_workflow
from autoflow.domain.workflows.scope import WorkflowScopeIssue, validate_workflow_scope

from .executors.base import ModuleExecutor, ModuleResult
from .executors.registry import ExecutorRegistry

# Source: WebRPA workflow_executor.py important_modules/trigger_modules, approved scope only.
IMPORTANT_LOG_NODE_TYPES = frozenset({
    'ai_chat',
    'ai_vision',
    'api_request',
    'download_file',
    'export_log',
    'image_ocr',
    'input_prompt',
    'js_script',
    'list_export',
    'print_log',
    'run_command',
    'send_email',
    'share_file',
    'share_folder',
    'start_screen_share',
    'subflow',
    'system_notification',
    'table_export',
    'text_to_speech',
    'upload_file',
})
SYSTEM_LOG_NODE_TYPES = frozenset({
    'api_trigger',
    'element_change_trigger',
    'email_trigger',
    'face_trigger',
    'file_watcher_trigger',
    'hotkey_trigger',
    'image_trigger',
    'mouse_trigger',
    'sound_trigger',
    'webhook_trigger',
})

MAX_NODE_DISPATCHES = 100_000
_LOOP_NODE_TYPES = frozenset({"loop", "foreach", "infinite_loop", "foreach_dict"})


@dataclass(slots=True)
class _NodeTiming:
    started_at: float = field(default_factory=lambda: perf_counter())
    paused_seconds: float = 0.0
    waiting: int = 0
    pause_started: float = 0.0

    def enter_pause(self) -> None:
        if not self.waiting:
            self.pause_started = perf_counter()
        self.waiting += 1

    def leave_pause(self) -> None:
        self.waiting -= 1
        if not self.waiting:
            self.paused_seconds += perf_counter() - self.pause_started


# Task inheritance binds nested calls to their ancestors, never sibling roots.
# Count overlapping child boundary waits once; retain no per-pause history.
_node_timings: ContextVar[tuple[_NodeTiming, ...]] = ContextVar("node_timings", default=())


@dataclass(frozen=True, slots=True)
class WorkflowRuntimeResult:
    success: bool
    executed_node_ids: tuple[str, ...]
    issues: tuple[WorkflowScopeIssue, ...] = ()
    failed_node_id: str | None = None
    node_result: ModuleResult | None = None


class WorkflowRuntime:
    def __init__(self, executor_registry: ExecutorRegistry) -> None:
        self._registry = executor_registry

    def preflight(self, document: Mapping[str, Any]) -> tuple[WorkflowScopeIssue, ...]:
        nodes = document.get("nodes", [])
        source_nodes = (
            [
                node
                for node in nodes
                if isinstance(node, Mapping)
                and (
                    node.get("data", {}).get("moduleType")
                    if isinstance(node.get("data"), Mapping)
                    else node.get("type")
                )
                not in {"group", "note"}
            ]
            if isinstance(nodes, list)
            else []
        )
        return validate_workflow_scope(
            source_nodes,
            runnable_node_types=self._registry.get_all_types(),
        )

    def requires_browser(self, document: Mapping[str, Any]) -> bool:
        nodes = document.get("nodes", [])
        if not isinstance(nodes, list):
            return False
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            data = node.get("data")
            module_type = (
                data.get("moduleType")
                if isinstance(data, Mapping)
                else node.get("type")
            )
            if isinstance(module_type, str):
                executor = self._registry.get(module_type)
                if executor is not None:
                    raw_config = (
                        data.get("config") if isinstance(data, Mapping) else None
                    )
                    config = dict(raw_config) if isinstance(raw_config, Mapping) else dict(data or {})
                    if executor.requires_browser_for(config):
                        return True
        return False

    async def execute(
        self,
        document: Mapping[str, Any],
        context: ExecutionContext,
        *,
        start_node_id: str | None = None,
        detached: bool = False,
    ) -> WorkflowRuntimeResult:
        issues = self.preflight(document)
        if issues:
            return WorkflowRuntimeResult(False, (), issues)
        _, graph = parse_workflow(document)
        if start_node_id is not None and graph.get_node(start_node_id) is None:
            issue = WorkflowScopeIssue(
                start_node_id,
                "startNodeId",
                "START_NODE_NOT_FOUND",
                "调试起点不存在于运行快照",
                "",
            )
            return WorkflowRuntimeResult(False, (), (issue,))
        # Non-waiting workflow calls keep cancellation/debug ownership, but their
        # background pauses cannot change the caller's action duration.
        token = _node_timings.set(()) if detached else None
        try:
            return await _WorkflowScheduler(self._registry, graph, context).run(
                [start_node_id] if start_node_id is not None else None
            )
        finally:
            if token is not None:
                _node_timings.reset(token)


@dataclass(slots=True)
class _WorkflowScheduler:
    registry: ExecutorRegistry
    graph: ExecutionGraph
    context: ExecutionContext
    executed_order: list[str] = field(default_factory=list)
    executed: set[str] = field(default_factory=set)
    executing: set[str] = field(default_factory=set)
    pending: dict[str, set[str]] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    event_binding_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    dispatch_count: int = 0
    halted: bool = False
    failed_node_id: str | None = None
    failed_result: ModuleResult | None = None
    loop_local_restores: dict[int, dict[str, tuple[bool, Any, bool]]] = field(
        default_factory=dict
    )

    async def run(self, start_nodes: list[str] | None = None) -> WorkflowRuntimeResult:
        await self._execute_parallel(
            self.graph.get_start_nodes() if start_nodes is None else start_nodes
        )
        return WorkflowRuntimeResult(
            success=self.failed_result is None,
            executed_node_ids=tuple(self.executed_order),
            failed_node_id=self.failed_node_id,
            node_result=self.failed_result,
        )

    async def _execute_parallel(self, node_ids: list[str]) -> None:
        if not node_ids or self.halted:
            return
        self._raise_if_cancelled()
        async with self.lock:
            claimed: list[str] = []
            for node_id in dict.fromkeys(node_ids):
                if node_id in self.executed or node_id in self.executing:
                    continue
                self.executing.add(node_id)
                claimed.append(node_id)
        if not claimed:
            return

        tasks = [
            asyncio.create_task(self._execute_branch(node_id)) for node_id in claimed
        ]
        try:
            await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

    async def _execute_branch(self, node_id: str) -> None:
        token = self.context.bind_branch_loop_stack()
        try:
            await self._execute_claimed(node_id)
        finally:
            self.context.reset_branch_loop_stack(token)

    async def _execute_claimed(self, node_id: str) -> None:
        node = self.graph.get_node(node_id)
        if node is None:
            async with self.lock:
                self.executing.discard(node_id)
            return
        try:
            result = await self._dispatch(node)
        except BaseException:
            async with self.lock:
                self.executing.discard(node_id)
            raise

        async with self.lock:
            self.executed.add(node_id)
            self.executing.discard(node_id)
            self.executed_order.append(node_id)

        if not result.success:
            self._remember_failure(node_id, result)
            error_nodes = self.graph.get_error_nodes(node_id)
            if error_nodes:
                await self._execute_parallel(error_nodes)
            else:
                self.halted = True
            return
        if self.halted or bool(getattr(self.context, "stop_workflow", False)):
            return
        if bool(getattr(self.context, "should_break", False)) or bool(
            getattr(self.context, "should_continue", False)
        ):
            return
        if node.type in _LOOP_NODE_TYPES:
            await self._handle_loop(node)
            return

        next_nodes = (
            self.graph.get_next_nodes(node_id, result.branch)
            if result.branch
            else self.graph.get_next_nodes(node_id)
        )
        await self._notify_successors(next_nodes, node_id)

    async def _dispatch(self, node: WorkflowNode) -> ModuleResult:
        self._raise_if_cancelled()
        if self.dispatch_count >= MAX_NODE_DISPATCHES:
            result = ModuleResult(
                success=False,
                error=f"工作流节点调度次数超过安全上限 {MAX_NODE_DISPATCHES}",
            )
            self._remember_failure(node.id, result)
            self.halted = True
            return result
        self.dispatch_count += 1
        executor = self.registry.get(node.type)
        if executor is None:
            result = ModuleResult(
                success=False, error=f"节点类型 {node.type} 的真实执行器尚未迁入"
            )
            self._remember_failure(node.id, result)
            return result

        parents = _node_timings.get()
        if self.context.debug is not None:
            for parent in parents:
                parent.enter_pause()
            try:
                await self.context.debug.before_node(
                    self.context,
                    node_id=node.id,
                    label=str(node.data.get("label") or node.type),
                )
            finally:
                for parent in parents:
                    parent.leave_pause()

        timing = _NodeTiming()
        token = _node_timings.set((*parents, timing))
        try:
            return await self._execute_node(node, executor, timing)
        finally:
            _node_timings.reset(token)

    async def _execute_node(
        self, node: WorkflowNode, executor: ModuleExecutor, timing: _NodeTiming
    ) -> ModuleResult:
        execution_id = str(uuid4())
        self.context.proxy_visit.set((node.id, execution_id))
        node_label = str(node.data.get("label") or node.type)
        execution_context = execution_context_snapshot(self.context)
        variables_before_loop = (
            dict(self.context.variables)
            if node.type in _LOOP_NODE_TYPES
            else None
        )
        sensitive_before_loop = (
            set(self.context.sensitive_variables)
            if node.type in _LOOP_NODE_TYPES
            else set()
        )
        async with self.event_binding_lock:
            self.context.current_node_id = node.id
            self.context.current_execution_id = execution_id
            await _publish(
                self.context,
                {
                    "type": "execution:node_start",
                    "nodeId": node.id,
                    "executionId": execution_id,
                    "executionContext": execution_context,
                },
            )
            self.context.bind_node_artifacts()
        tracking_token = self.context.begin_variable_tracking(
            node_id=node.id,
            node_name=node_label,
            execution_id=execution_id,
        )
        raw_config = node.data.get("config")
        config = (
            dict(raw_config) if isinstance(raw_config, Mapping) else dict(node.data)
        )
        self.context.begin_node()
        # Frozen source measures dispatch milliseconds; exclude transport setup
        # and the enclosing call's own/nested debug boundary waits.
        timing.started_at = perf_counter()
        result = await _execute_with_cancellation(
            self._execute_network_guarded(node, executor, config), self.context
        )
        if (
            result.success
            and node.type in _LOOP_NODE_TYPES
            and isinstance(result.data, dict)
            and variables_before_loop is not None
        ):
            self.loop_local_restores[id(result.data)] = {
                name: (
                    name in variables_before_loop,
                    copy.deepcopy(variables_before_loop.get(name)),
                    name in sensitive_before_loop,
                )
                for name in _active_loop_variable_names(result.data)
            }
        if (
            node.type == "custom_module"
            and result.success
            and self.context.custom_modules is not None
            and isinstance(result.data, Mapping)
        ):
            module_id = str(result.data.get("module_id") or "")
            raw_parameters = result.data.get("parameter_mappings", {})
            parameters = raw_parameters if isinstance(raw_parameters, Mapping) else {}
            custom_result = await self.context.custom_modules.run_custom_module(
                module_id=module_id,
                parameter_values=parameters,
            )
            if custom_result.success:
                for name, value in custom_result.outputs.items():
                    self.context.set_variable(
                        name, value, sensitive=name in custom_result.sensitive_outputs
                    )
                if custom_result.sensitive_outputs:
                    self.context.mark_sensitive_use()
            result = ModuleResult(
                success=custom_result.success,
                message=(
                    f"自定义模块 '{custom_result.name}' 执行完成"
                    if custom_result.success
                    else ""
                ),
                error=custom_result.error,
                data={
                    "outputs": dict(custom_result.outputs),
                    "executed_nodes": custom_result.executed_nodes,
                    "failed_nodes": custom_result.failed_nodes,
                },
            )
        if (
            node.type == "subflow"
            and result.success
            and self.context.canvas_subflows is not None
            and isinstance(result.data, Mapping)
        ):
            nested_subflow = await self.context.canvas_subflows.run_subflow(
                group_id=str(result.data.get("subflow_group_id") or ""),
                name=str(result.data.get("subflow_name") or ""),
            )
            result = ModuleResult(
                success=nested_subflow.success,
                message=(
                    (
                        f"子流程 [{nested_subflow.name}] 为空"
                        if nested_subflow.executed_nodes == 0
                        else f"子流程 [{nested_subflow.name}] 执行完成"
                    )
                    if nested_subflow.success
                    else ""
                ),
                error=nested_subflow.error,
                data={
                    "subflow": nested_subflow.name,
                    "executed_nodes": nested_subflow.executed_nodes,
                    "failed_nodes": nested_subflow.failed_nodes,
                },
            )
        if not _is_json_value(result.data):
            result = ModuleResult(success=False, error="节点结果包含无法序列化的数据")
        result.duration = max(
            0.0, perf_counter() - timing.started_at - timing.paused_seconds
        ) * 1000
        for change in self.context.end_variable_tracking(tracking_token):
            await _publish(
                self.context,
                {
                    "type": "execution:variable_changed",
                    "nodeId": node.id,
                    "executionId": execution_id,
                    **change,
                },
            )
        reported_result = _reported_result(result, self.context)
        await _publish(
            self.context,
            {
                "type": "execution:node_complete",
                "nodeId": node.id,
                "executionId": execution_id,
                "executionContext": execution_context,
                "success": reported_result.success,
                "message": reported_result.message,
                "error": reported_result.error,
                "isTimeout": reported_result.is_timeout,
                "data": reported_result.data,
                "logLevel": reported_result.log_level,
                "isUserLog": node.type in IMPORTANT_LOG_NODE_TYPES or not reported_result.success,
                "isSystemLog": node.type in SYSTEM_LOG_NODE_TYPES,
                "duration": reported_result.duration,
            },
        )
        return reported_result if self.context.node_uses_sensitive_values else result

    async def _execute_network_guarded(self, node, executor, config):
        if node.type in {"proxy_change_ip", "proxy_change_location", "proxy_query"} or not executor.requires_browser_for(config):
            return await executor.execute(config, self.context)
        active = self.context.proxy_activity
        if "proxy-switch" in active:
            return ModuleResult(False, error="PROXY_BUSY")
        key = str(uuid4())
        active.add(key)
        try:
            return await executor.execute(config, self.context)
        finally:
            active.discard(key)

    async def _handle_loop(self, loop_node: WorkflowNode) -> None:
        body_nodes = self.graph.get_loop_body_nodes(loop_node.id)
        done_nodes = self.graph.get_loop_done_nodes(loop_node.id)
        if not self.context.loop_stack:
            await self._notify_successors(done_nodes, loop_node.id)
            return
        loop_state = self.context.loop_stack[-1]
        loop_state.setdefault("node_id", loop_node.id)
        body_scope = self._collect_loop_body_nodes(loop_node.id, body_nodes, done_nodes)
        while not self.halted and self._loop_should_continue(loop_state):
            self._raise_if_cancelled()
            self.context.should_continue = False
            await self._reset_nodes(body_scope)
            await self._execute_parallel(body_nodes)
            if self.halted:
                break
            if bool(getattr(self.context, "should_break", False)):
                self.context.should_break = False
                break
            self.context.should_continue = False
            await self._advance_loop(loop_node, loop_state)
            await asyncio.sleep(0)

        if self.context.loop_stack and self.context.loop_stack[-1] is loop_state:
            self.context.loop_stack.pop()
        await self._exit_loop_scope(loop_node, loop_state)
        if done_nodes and not self.halted:
            await self._notify_successors(done_nodes, loop_node.id)

    def _loop_should_continue(self, state: Mapping[str, Any]) -> bool:
        loop_type = state.get("type")
        current = int(state.get("current_index", 0))
        if loop_type == "count":
            return current < int(state.get("count", 0))
        if loop_type == "range":
            end = state.get("end_value", 0)
            step = state.get("step_value", 1)
            return current <= end if step > 0 else current >= end
        if loop_type in {"foreach", "foreach_dict"}:
            data = state.get("data", [])
            return isinstance(data, (list, tuple)) and current < len(data)
        if loop_type == "infinite":
            return True
        if loop_type == "while":
            resolved = self.context.resolve_value(state.get("condition"))
            if isinstance(resolved, bool):
                return resolved
            if isinstance(resolved, str):
                try:
                    from .executors.safe_expr import safe_eval

                    return bool(safe_eval(resolved, dict(self.context.variables)))
                except Exception:  # noqa: BLE001 -- frozen boolean fallback.
                    return resolved.strip().lower() in {"true", "1"}
            return bool(resolved)
        return False

    async def _advance_loop(
        self, loop_node: WorkflowNode, state: dict[str, Any]
    ) -> None:
        execution_id = str(uuid4())
        tracking_token = self.context.begin_variable_tracking(
            node_id=loop_node.id,
            node_name=str(loop_node.data.get("label") or loop_node.type),
            execution_id=execution_id,
        )
        loop_type = state.get("type")
        step = state.get("step_value", 1) if loop_type == "range" else 1
        state["current_index"] = state.get("current_index", 0) + step
        current = state["current_index"]
        index_variable = state.get("index_variable")
        if isinstance(index_variable, str) and index_variable:
            self.context.set_variable(index_variable, current)
        data = state.get("data", [])
        if loop_type == "foreach" and current < len(data):
            item_variable = state.get("item_variable")
            if isinstance(item_variable, str) and item_variable:
                self.context.set_variable(item_variable, data[current])
        if loop_type == "foreach_dict" and current < len(data):
            key, value = data[current]
            key_variable = state.get("key_variable")
            value_variable = state.get("value_variable")
            if isinstance(key_variable, str) and key_variable:
                self.context.set_variable(key_variable, key)
            if isinstance(value_variable, str) and value_variable:
                self.context.set_variable(value_variable, value)
        await self._publish_variable_changes(tracking_token)

    async def _exit_loop_scope(
        self, loop_node: WorkflowNode, state: dict[str, Any]
    ) -> None:
        restore = self.loop_local_restores.pop(id(state), {})
        if not restore:
            return
        execution_id = str(uuid4())
        tracking_token = self.context.begin_variable_tracking(
            node_id=loop_node.id,
            node_name=str(loop_node.data.get("label") or loop_node.type),
            execution_id=execution_id,
        )
        for name, (existed, value, sensitive) in restore.items():
            if existed:
                self.context.set_variable(
                    name,
                    copy.deepcopy(value),
                    sensitive=sensitive,
                    operation="scope_exit",
                )
            else:
                self.context.delete_variable(name, operation="scope_exit")
        await self._publish_variable_changes(tracking_token)

    async def _publish_variable_changes(self, tracking_token: Any) -> None:
        for change in self.context.end_variable_tracking(tracking_token):
            await _publish(
                self.context,
                {
                    "type": "execution:variable_changed",
                    "nodeId": change["node_id"],
                    "executionId": change["executionId"],
                    **change,
                },
            )

    def _collect_loop_body_nodes(
        self, loop_id: str, roots: list[str], done_nodes: list[str]
    ) -> set[str]:
        blocked = {loop_id, *done_nodes}
        collected: set[str] = set()
        queue = list(roots)
        while queue:
            current = queue.pop(0)
            if current in blocked or current in collected:
                continue
            collected.add(current)
            queue.extend(self._full_successors(current))
        return collected

    async def _reset_nodes(self, node_ids: set[str]) -> None:
        async with self.lock:
            for node_id in node_ids:
                self.executed.discard(node_id)
                self.executing.discard(node_id)
                self.pending.pop(node_id, None)

    async def _notify_successors(
        self, next_nodes: list[str], completed_node_id: str
    ) -> None:
        if not next_nodes or self.halted:
            return
        ready: list[str] = []
        async with self.lock:
            for next_id in dict.fromkeys(next_nodes):
                if next_id in self.executed or next_id in self.executing:
                    if self._is_back_edge(next_id, completed_node_id):
                        for cycle_id in self._nodes_between(next_id, completed_node_id):
                            self.executed.discard(cycle_id)
                            self.pending.pop(cycle_id, None)
                    else:
                        continue
                prev_nodes = self.graph.get_join_prev_nodes(next_id)
                if len(prev_nodes) <= 1:
                    ready.append(next_id)
                    continue
                waiting = self.pending.setdefault(
                    next_id,
                    {node_id for node_id in prev_nodes if node_id not in self.executed},
                )
                waiting.discard(completed_node_id)
                if not waiting:
                    self.pending.pop(next_id, None)
                    ready.append(next_id)

            for pending_id in list(self.pending):
                waiting = {
                    predecessor
                    for predecessor in self.pending[pending_id]
                    if predecessor not in self.executed
                    and self._is_node_reachable(predecessor, next_nodes)
                }
                if waiting:
                    self.pending[pending_id] = waiting
                else:
                    self.pending.pop(pending_id, None)
                    ready.append(pending_id)
        if ready:
            await self._execute_parallel(list(dict.fromkeys(ready)))

    def _is_node_reachable(self, target_id: str, additional_roots: list[str]) -> bool:
        roots = set(self.executing) | set(additional_roots) | set(self.pending)
        if target_id in roots:
            return True
        seen = set(roots)
        queue = list(roots)
        while queue:
            current = queue.pop(0)
            for successor in self._full_successors(current):
                if successor == target_id:
                    return True
                if successor not in seen:
                    seen.add(successor)
                    queue.append(successor)
        return False

    def _full_successors(self, node_id: str) -> list[str]:
        successors = list(self.graph.adjacency.get(node_id, []))
        for targets in self.graph.condition_branches.get(node_id, {}).values():
            successors.extend(targets)
        for targets in self.graph.loop_branches.get(node_id, {}).values():
            successors.extend(targets)
        successors.extend(self.graph.error_branches.get(node_id, []))
        return successors

    def _is_back_edge(self, target_id: str, source_id: str) -> bool:
        return target_id == source_id or source_id in self._reachable_from(target_id)

    def _reachable_from(self, start: str) -> set[str]:
        seen: set[str] = set()
        queue = [start]
        while queue:
            current = queue.pop(0)
            for successor in self._full_successors(current):
                if successor not in seen:
                    seen.add(successor)
                    queue.append(successor)
        return seen

    def _nodes_between(self, start: str, end: str) -> set[str]:
        forward = {start, *self._reachable_from(start)}
        if end not in forward:
            return {start, end}
        reverse: dict[str, set[str]] = {}
        for source in forward:
            for target in self._full_successors(source):
                if target in forward:
                    reverse.setdefault(target, set()).add(source)
        result = {end}
        queue = [end]
        while queue:
            current = queue.pop(0)
            for predecessor in reverse.get(current, set()):
                if predecessor not in result:
                    result.add(predecessor)
                    queue.append(predecessor)
        result.add(start)
        return result

    def _remember_failure(self, node_id: str, result: ModuleResult) -> None:
        if self.failed_result is None:
            self.failed_node_id = node_id
            self.failed_result = result

    def _raise_if_cancelled(self) -> None:
        if self.context.cancellation is not None:
            self.context.cancellation.raise_if_cancelled()


def _reported_result(result: ModuleResult, context: ExecutionContext) -> ModuleResult:
    if not context.node_uses_sensitive_values:
        return result
    return ModuleResult(
        success=result.success,
        message="节点执行成功（结果包含凭据派生值）" if result.success else "",
        data=None,
        error="节点执行失败（错误包含凭据派生值）" if not result.success else None,
        branch=result.branch,
        duration=result.duration,
        log_level=result.log_level,
        skipped=result.skipped,
        is_timeout=result.is_timeout,
    )


def execution_context_snapshot(context: ExecutionContext) -> dict[str, Any]:
    loops: list[dict[str, Any]] = []
    for state in context.loop_stack:
        current = _integer(state.get("current_index"))
        loop_type = str(state.get("type") or "")
        if loop_type == "range":
            start = _integer(state.get("start_value"))
            step = _integer(state.get("step_value")) or 1
            iteration = abs(current - start) // abs(step) + 1
        else:
            iteration = current + 1
        loops.append(
            {
                "nodeId": str(state.get("node_id") or ""),
                "type": loop_type,
                "currentIndex": current,
                "iteration": iteration,
            }
        )
    return {
        "scopes": [copy.deepcopy(scope) for scope in context.execution_scopes],
        "loops": loops,
    }


def _integer(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _is_json_value(value: Any) -> bool:
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        return False
    return True


async def _publish(context: ExecutionContext, event: dict[str, Any]) -> None:
    if context.events is not None:
        await context.events.publish(event)


def _active_loop_variable_names(state: Mapping[str, Any]) -> tuple[str, ...]:
    if state.get("type") in {"foreach", "foreach_dict"} and not state.get("data"):
        return ()
    return tuple(
        dict.fromkeys(
            name
            for key in (
                "index_variable",
                "item_variable",
                "key_variable",
                "value_variable",
            )
            if isinstance((name := state.get(key)), str) and name
        )
    )


async def _execute_with_cancellation(
    operation: Coroutine[Any, Any, ModuleResult], context: ExecutionContext
) -> ModuleResult:
    token = context.cancellation
    if token is None:
        return await operation
    async def run_operation() -> tuple[ModuleResult, bool]:
        result = await operation
        return result, context.node_uses_sensitive_values

    operation_task = asyncio.create_task(run_operation())
    cancellation_task = asyncio.create_task(_wait_until_cancelled(context))
    try:
        done, _ = await asyncio.wait(
            {operation_task, cancellation_task}, return_when=asyncio.FIRST_COMPLETED
        )
        if operation_task in done:
            result, used_sensitive_values = operation_task.result()
            if used_sensitive_values:
                context.mark_sensitive_use()
            return result
        operation_task.cancel()
        await asyncio.gather(operation_task, return_exceptions=True)
        token.raise_if_cancelled()
        raise RuntimeError("workflow cancellation token did not raise")
    finally:
        cancellation_task.cancel()
        await asyncio.gather(cancellation_task, return_exceptions=True)


async def _wait_until_cancelled(context: ExecutionContext) -> None:
    assert context.cancellation is not None
    while not context.cancellation.cancelled:
        await asyncio.sleep(0.02)


from .core_runtime import WorkflowRuntimeService  # noqa: F401
