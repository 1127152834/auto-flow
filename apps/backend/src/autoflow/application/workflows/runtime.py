from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import Coroutine, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.domain.workflows.graph import parse_workflow
from autoflow.domain.workflows.scope import WorkflowScopeIssue, validate_workflow_scope

from .executors.base import ModuleResult
from .executors.registry import ExecutorRegistry


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
                if executor is not None and executor.requires_browser:
                    return True
        return False

    async def execute(
        self, document: Mapping[str, Any], context: ExecutionContext
    ) -> WorkflowRuntimeResult:
        issues = self.preflight(document)
        if issues:
            return WorkflowRuntimeResult(False, (), issues)
        _, graph = parse_workflow(document)
        queue = deque(graph.get_start_nodes())
        executed: list[str] = []
        visited: set[str] = set()
        while queue:
            if context.cancellation is not None:
                context.cancellation.raise_if_cancelled()
            node_id = queue.popleft()
            if node_id in visited:
                continue
            visited.add(node_id)
            node = graph.get_node(node_id)
            if node is None:
                continue
            executor = self._registry.get(node.type)
            if executor is None:
                return WorkflowRuntimeResult(
                    False,
                    tuple(executed),
                    (
                        WorkflowScopeIssue(
                            node_id=node.id,
                            path=f"nodes.{node.id}.data.moduleType",
                            code="UNSUPPORTED_NODE_TYPE",
                            message=f"节点类型 {node.type} 的真实执行器尚未迁入",
                            node_type=node.type,
                        ),
                    ),
                )
            execution_id = str(uuid4())
            context.current_node_id = node.id
            context.current_execution_id = execution_id
            await _publish(
                context,
                {
                    "type": "execution:node_start",
                    "nodeId": node.id,
                    "executionId": execution_id,
                },
            )
            raw_config = node.data.get("config")
            config = (
                dict(raw_config) if isinstance(raw_config, Mapping) else dict(node.data)
            )
            result = await _execute_with_cancellation(
                executor.execute(config, context), context
            )
            if not _is_json_value(result.data):
                result = ModuleResult(
                    success=False,
                    error="节点结果包含无法序列化的数据",
                )
            executed.append(node_id)
            await _publish(
                context,
                {
                    "type": "execution:node_complete",
                    "nodeId": node.id,
                    "executionId": execution_id,
                    "success": result.success,
                    "message": result.message,
                    "error": result.error,
                    "data": result.data,
                },
            )
            if not result.success:
                return WorkflowRuntimeResult(
                    False,
                    tuple(executed),
                    failed_node_id=node_id,
                    node_result=result,
                )
            queue.extend(
                graph.get_next_nodes(node_id, result.branch)
                if result.branch
                else graph.get_next_nodes(node_id)
            )
        return WorkflowRuntimeResult(True, tuple(executed))


def _is_json_value(value: Any) -> bool:
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        return False
    return True


async def _publish(context: ExecutionContext, event: dict[str, Any]) -> None:
    if context.events is not None:
        await context.events.publish(event)


async def _execute_with_cancellation(
    operation: Coroutine[Any, Any, ModuleResult], context: ExecutionContext
) -> ModuleResult:
    token = context.cancellation
    if token is None:
        return await operation
    operation_task = asyncio.create_task(operation)
    cancellation_task = asyncio.create_task(_wait_until_cancelled(context))
    try:
        done, _ = await asyncio.wait(
            {operation_task, cancellation_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if operation_task in done:
            return operation_task.result()
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
