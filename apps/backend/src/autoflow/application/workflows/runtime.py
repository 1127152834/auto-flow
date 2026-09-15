from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

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
            raw_config = node.data.get("config")
            config = dict(raw_config) if isinstance(raw_config, Mapping) else dict(node.data)
            result = await executor.execute(config, context)
            executed.append(node_id)
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
