from __future__ import annotations

import copy
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

_VISUAL_NODE_TYPES = frozenset({"group", "note"})
_CONDITION_NODE_TYPES = frozenset(
    {
        "condition",
        "face_recognition",
        "element_exists",
        "element_visible",
        "image_exists",
        "phone_image_exists",
        "probability_trigger",
    }
)
_LOOP_NODE_TYPES = frozenset({"loop", "foreach", "infinite_loop", "foreach_dict"})


def _business_type(raw: Mapping[str, Any]) -> str:
    data = raw.get("data")
    if isinstance(data, Mapping) and isinstance(data.get("moduleType"), str):
        return data["moduleType"]
    value = raw.get("moduleType", raw.get("type", ""))
    return value if isinstance(value, str) else ""


@dataclass(frozen=True, slots=True)
class WorkflowNode:
    id: str
    type: str
    data: Mapping[str, Any]
    raw: Mapping[str, Any]

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any]) -> WorkflowNode:
        node_id = raw.get("id")
        data = raw.get("data")
        return cls(
            id=node_id if isinstance(node_id, str) else "",
            type=_business_type(raw),
            data=copy.deepcopy(data) if isinstance(data, Mapping) else {},
            raw=copy.deepcopy(dict(raw)),
        )


@dataclass(frozen=True, slots=True)
class WorkflowEdge:
    id: str
    source: str
    target: str
    source_handle: str | None
    target_handle: str | None
    raw: Mapping[str, Any]

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any]) -> WorkflowEdge:
        def text(key: str) -> str:
            value = raw.get(key)
            return value if isinstance(value, str) else ""

        source_handle = raw.get("sourceHandle")
        target_handle = raw.get("targetHandle")
        return cls(
            id=text("id"),
            source=text("source"),
            target=text("target"),
            source_handle=source_handle if isinstance(source_handle, str) else None,
            target_handle=target_handle if isinstance(target_handle, str) else None,
            raw=copy.deepcopy(dict(raw)),
        )


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    id: str
    name: str
    nodes: tuple[WorkflowNode, ...]
    edges: tuple[WorkflowEdge, ...]
    variables: tuple[Mapping[str, Any], ...]
    raw: Mapping[str, Any]

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any]) -> WorkflowDefinition:
        raw_nodes = raw.get("nodes", [])
        raw_edges = raw.get("edges", [])
        raw_variables = raw.get("variables", [])
        nodes = tuple(
            WorkflowNode.from_raw(node)
            for node in raw_nodes
            if isinstance(node, Mapping)
        ) if isinstance(raw_nodes, list) else ()
        edges = tuple(
            WorkflowEdge.from_raw(edge)
            for edge in raw_edges
            if isinstance(edge, Mapping)
        ) if isinstance(raw_edges, list) else ()
        variables = tuple(
            copy.deepcopy(dict(variable))
            for variable in raw_variables
            if isinstance(variable, Mapping)
        ) if isinstance(raw_variables, list) else ()
        workflow_id = raw.get("id")
        name = raw.get("name")
        return cls(
            id=workflow_id if isinstance(workflow_id, str) else "",
            name=name if isinstance(name, str) else "",
            nodes=nodes,
            edges=edges,
            variables=variables,
            raw=copy.deepcopy(dict(raw)),
        )

    def validate(self) -> tuple[bool, tuple[str, ...]]:
        errors: list[str] = []
        if not self.nodes:
            return False, ("工作流没有任何节点",)

        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            errors.append("存在重复的节点ID")
        node_id_set = set(node_ids)
        for edge in self.edges:
            if edge.source not in node_id_set:
                errors.append(f"边的源节点不存在: {edge.source}")
            if edge.target not in node_id_set:
                errors.append(f"边的目标节点不存在: {edge.target}")

        graph = WorkflowParser().parse(self)
        if not graph.start_nodes:
            errors.append("工作流没有起始节点（所有节点都有入边，可能存在循环）")
        for node in self.nodes:
            if node.type in _CONDITION_NODE_TYPES:
                branches = graph.condition_branches.get(node.id, {})
                has_true = bool(branches.get("true") or branches.get("path1"))
                if not has_true and not branches:
                    errors.append(f"条件节点 '{node.id}' ({node.type}) 没有任何输出分支")
            if node.type in _LOOP_NODE_TYPES:
                branches = graph.loop_branches.get(node.id, {})
                if not branches.get("loop"):
                    errors.append(f"循环节点 '{node.id}' ({node.type}) 缺少循环体（loop 出边）")
        return not errors, tuple(errors)


@dataclass(slots=True)
class ExecutionGraph:
    nodes: dict[str, WorkflowNode] = field(default_factory=dict)
    edges: list[WorkflowEdge] = field(default_factory=list)
    adjacency: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    reverse_adjacency: dict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    start_nodes: list[str] = field(default_factory=list)
    isolated_nodes: list[str] = field(default_factory=list)
    condition_branches: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    loop_branches: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    error_branches: dict[str, list[str]] = field(default_factory=dict)
    error_pred: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    def get_node(self, node_id: str) -> WorkflowNode | None:
        return self.nodes.get(node_id)

    def get_next_nodes(self, node_id: str, handle: str | None = None) -> list[str]:
        if handle and node_id in self.condition_branches:
            return list(self.condition_branches[node_id].get(handle, []))
        if handle and node_id in self.loop_branches:
            return list(self.loop_branches[node_id].get(handle, []))
        return list(self.adjacency.get(node_id, []))

    def get_loop_body_nodes(self, node_id: str) -> list[str]:
        return list(self.loop_branches.get(node_id, {}).get("loop", []))

    def get_loop_done_nodes(self, node_id: str) -> list[str]:
        return list(self.loop_branches.get(node_id, {}).get("done", []))

    def get_error_nodes(self, node_id: str) -> list[str]:
        return list(self.error_branches.get(node_id, []))

    def get_prev_nodes(self, node_id: str) -> list[str]:
        return list(self.reverse_adjacency.get(node_id, []))

    def full_successors(self, node_id: str) -> list[str]:
        successors = list(self.adjacency.get(node_id, []))
        for targets in self.condition_branches.get(node_id, {}).values():
            successors.extend(targets)
        for targets in self.loop_branches.get(node_id, {}).values():
            successors.extend(targets)
        successors.extend(self.error_branches.get(node_id, []))
        return successors

    def loop_body_scope(self, loop_id: str) -> set[str]:
        blocked = {loop_id, *self.get_loop_done_nodes(loop_id)}
        collected: set[str] = set()
        queue = self.get_loop_body_nodes(loop_id)
        while queue:
            current = queue.pop()
            if current in blocked or current in collected:
                continue
            collected.add(current)
            queue.extend(self.full_successors(current))
        return collected

    def _forward_reachable(self, node_id: str) -> set[str]:
        seen: set[str] = set()
        stack = [node_id]
        while stack:
            current = stack.pop()
            successors = list(self.adjacency.get(current, []))
            for targets in self.condition_branches.get(current, {}).values():
                successors.extend(targets)
            for targets in self.loop_branches.get(current, {}).values():
                successors.extend(targets)
            for successor in successors:
                if successor not in seen:
                    seen.add(successor)
                    stack.append(successor)
        return seen

    def get_join_prev_nodes(self, node_id: str) -> list[str]:
        previous = list(self.reverse_adjacency.get(node_id, []))
        error_sources = self.error_pred.get(node_id)
        if error_sources:
            previous = [node for node in previous if node not in error_sources]
        if len(previous) <= 1:
            return previous
        reachable = self._forward_reachable(node_id)
        return [node for node in previous if node not in reachable]

    def get_start_nodes(self) -> list[str]:
        return self.start_nodes.copy()


class WorkflowParser:
    def parse(self, workflow: WorkflowDefinition) -> ExecutionGraph:
        graph = ExecutionGraph()
        graph.nodes = {
            node.id: node for node in workflow.nodes if node.type not in _VISUAL_NODE_TYPES
        }
        visual_node_ids = {
            node.id for node in workflow.nodes if node.type in _VISUAL_NODE_TYPES
        }
        graph.edges = [
            edge
            for edge in workflow.edges
            if edge.source not in visual_node_ids and edge.target not in visual_node_ids
        ]

        incoming: set[str] = set()
        normal_incoming: set[str] = set()
        outgoing: set[str] = set()
        seen_adjacency: dict[str, set[str]] = defaultdict(set)
        seen_reverse: dict[str, set[str]] = defaultdict(set)
        seen_condition: dict[tuple[str, str], set[str]] = defaultdict(set)
        seen_loop: dict[tuple[str, str], set[str]] = defaultdict(set)
        seen_error: dict[str, set[str]] = defaultdict(set)

        for edge in graph.edges:
            source_id, target_id = edge.source, edge.target
            source_node = graph.nodes.get(source_id)
            outgoing.add(source_id)
            handle = edge.source_handle
            if handle == "error":
                if target_id not in seen_error[source_id]:
                    seen_error[source_id].add(target_id)
                    graph.error_branches.setdefault(source_id, []).append(target_id)
                graph.error_pred[target_id].add(source_id)
            elif handle and source_node and source_node.type in _CONDITION_NODE_TYPES:
                if target_id not in seen_condition[(source_id, handle)]:
                    seen_condition[(source_id, handle)].add(target_id)
                    graph.condition_branches.setdefault(source_id, {}).setdefault(
                        handle, []
                    ).append(target_id)
            elif handle and source_node and source_node.type in _LOOP_NODE_TYPES:
                normalized_handle = {
                    "loop-body": "loop",
                    "loop-done": "done",
                }.get(handle, handle)
                graph.loop_branches.setdefault(source_id, {"loop": [], "done": []})
                if (
                    normalized_handle in graph.loop_branches[source_id]
                    and target_id not in seen_loop[(source_id, normalized_handle)]
                ):
                    seen_loop[(source_id, normalized_handle)].add(target_id)
                    graph.loop_branches[source_id][normalized_handle].append(target_id)
            elif target_id not in seen_adjacency[source_id]:
                seen_adjacency[source_id].add(target_id)
                graph.adjacency[source_id].append(target_id)

            if source_id not in seen_reverse[target_id]:
                seen_reverse[target_id].add(source_id)
                graph.reverse_adjacency[target_id].append(source_id)
            incoming.add(target_id)
            if handle != "error":
                normal_incoming.add(target_id)

        has_any_edge = bool(graph.edges)
        for node_id in graph.nodes:
            if node_id in incoming:
                continue
            if has_any_edge and node_id not in outgoing:
                graph.isolated_nodes.append(node_id)
            else:
                graph.start_nodes.append(node_id)
        if not graph.start_nodes and graph.isolated_nodes:
            graph.start_nodes.extend(graph.isolated_nodes)
            graph.isolated_nodes = []
        if not graph.start_nodes:
            graph.start_nodes.extend(
                node_id for node_id in graph.nodes if node_id not in normal_incoming
            )
        return graph


def parse_workflow(
    workflow: Mapping[str, Any],
) -> tuple[WorkflowDefinition, ExecutionGraph]:
    definition = WorkflowDefinition.from_raw(workflow)
    return definition, WorkflowParser().parse(definition)
