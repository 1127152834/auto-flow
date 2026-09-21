"""Frozen canvas dependency selection shared by preparation and both workers."""
from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any


class CanvasSubflowGraph:
    def __init__(self, document: dict[str, Any]) -> None:
        self._document = copy.deepcopy(document)

    def top_level_document(self) -> dict[str, Any]:
        excluded: set[str] = set()
        for node in self._nodes():
            if self._is_definition(node):
                excluded.add(str(node.get("id") or ""))
                excluded.update(self._members(node))
        return self._subset(excluded, invert=True)

    def project_scopes(self) -> dict[str, set[str]]:
        """Validate project call ownership without reading mutable Studio content."""
        from .models import WorkflowError

        def reject(message: str) -> None:
            raise WorkflowError("WORKFLOW_NOT_RUNNABLE", message, 422)

        definitions = [n for n in self._nodes() if self._is_definition(n)]
        scopes = {str(n["id"]): self._members(n) for n in definitions}
        scopes[""] = {n["id"] for n in self.top_level_document()["nodes"]}
        owners: dict[str, str] = {}
        for scope, members in scopes.items():
            for identity in members:
                if identity in owners:
                    reject(f"子流程节点归属重叠: {identity}")
                owners[identity] = scope
        for edge in self._edges():
            source, target = edge["source"], edge["target"]
            if source in scopes and target in scopes[source]:
                continue  # Definition header edges introduce the child graph.
            if source not in owners or target not in owners or owners[source] != owners[target]:
                reject(f"连线跨越子流程边界: {source} -> {target}")
        names = [str(_node_data(n).get("subflowName") or "") for n in definitions]
        if len([n for n in names if n]) != len({n for n in names if n}):
            reject("子流程名称重复")
        calls: dict[str, list[tuple[str, str]]] = {scope: [] for scope in scopes}
        for node in self._nodes():
            kind = _node_type(node)
            if node["id"] not in owners:
                continue
            owner = owners[node["id"]]
            if owner and kind == "project_end":
                reject("子流程不能包含 End")
            if kind != "subflow":
                continue
            config = _node_data(node)
            config = config.get("config", config)
            group_id, name = config.get("subflowGroupId", ""), config.get("subflowName", "")
            definition = self._find_definition(group_id, name)
            if definition is None:
                reject(f"找不到子流程: {node['id']} -> {name or group_id}")
                continue
            if group_id and definition["id"] != group_id:
                reject(f"子流程名称与身份不一致: {node['id']}")
            inputs, outputs = config.get("inputs"), config.get("outputs")
            if not isinstance(inputs, dict) or not isinstance(outputs, dict) or any(not isinstance(k, str) or not k.strip() for k in [*inputs, *outputs]) or any(not isinstance(v, str) or not v.strip() for v in outputs.values()) or len(set(outputs.values())) != len(outputs):
                reject(f"子流程必须声明独立 inputs 和唯一 outputs: {node['id']}")
            calls[owner].append((node["id"], definition["id"]))

        validated_depth: dict[str, int] = {}

        def visit(scope: str, stack: tuple[str, ...], path: tuple[str, ...]) -> None:
            if validated_depth.get(scope, -1) >= len(stack):
                return
            for call, target in calls[scope]:
                route = (*path, call, target)
                if target in stack:
                    reject(f"子流程循环引用: {' -> '.join(route)}")
                if len(stack) >= 32:
                    reject(f"子流程嵌套层数过深(>32): {' -> '.join(route)}")
                visit(target, (*stack, target), route)
            validated_depth[scope] = len(stack)
        # Validate unused definitions too; they are part of the frozen document.
        for scope in ["", *(key for key in scopes if key)]:
            visit(scope, (scope,) if scope else (), (scope,) if scope else ())
        return scopes

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

