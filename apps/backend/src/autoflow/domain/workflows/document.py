from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .errors import WorkflowDocumentError

_NODE_LAYOUT_KEYS = frozenset(
    {"position", "positionAbsolute", "style", "width", "height", "measured"}
)
_EPHEMERAL_NODE_KEYS = frozenset({"selected", "dragging"})
_EPHEMERAL_EDGE_KEYS = frozenset({"selected"})


def _problem(code: str, message: str, path: str) -> WorkflowDocumentError:
    return WorkflowDocumentError(code, message, 422, {"path": path})


def _json_copy(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise _problem(
            "INVALID_DOCUMENT", "工作流包含无法序列化的数据", "document"
        ) from error
    return copy.deepcopy(value)


def _require_list(document: dict[str, Any], key: str) -> list[Any]:
    value = document.get(key, [])
    if not isinstance(value, list):
        raise _problem("INVALID_DOCUMENT", f"{key} 必须是数组", key)
    return value


@dataclass(frozen=True, slots=True)
class WorkflowDraft:
    id: str | None
    name: str
    document: dict[str, Any]
    layout: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> WorkflowDraft:
        source = _json_copy(dict(payload))
        name = source.pop("name", "未命名工作流")
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise _problem(
                "INVALID_DOCUMENT", "工作流名称必须为 1 至 120 个字符", "name"
            )
        workflow_id = source.pop("id", None)
        if workflow_id is not None and (
            not isinstance(workflow_id, str) or not workflow_id.strip()
        ):
            raise _problem("INVALID_DOCUMENT", "工作流 ID 无效", "id")
        for transport_key in ("revision", "expectedRevision", "clientRequestId"):
            source.pop(transport_key, None)

        supplied_layout = source.pop("layout", {})
        if not isinstance(supplied_layout, dict):
            raise _problem("INVALID_DOCUMENT", "layout 必须是对象", "layout")
        layout = copy.deepcopy(supplied_layout)
        layout_nodes = layout.get("nodes", {})
        if not isinstance(layout_nodes, dict):
            raise _problem(
                "INVALID_DOCUMENT", "layout.nodes 必须是对象", "layout.nodes"
            )
        layout["nodes"] = layout_nodes
        if "viewport" in source:
            layout["viewport"] = source.pop("viewport")

        nodes = _require_list(source, "nodes")
        node_ids: set[str] = set()
        semantic_nodes: list[dict[str, Any]] = []
        for index, value in enumerate(nodes):
            if not isinstance(value, dict):
                raise _problem("INVALID_DOCUMENT", "节点必须是对象", f"nodes.{index}")
            node = copy.deepcopy(value)
            node_id = node.get("id")
            if not isinstance(node_id, str) or not node_id:
                raise _problem("INVALID_DOCUMENT", "节点 ID 无效", f"nodes.{index}.id")
            if node_id in node_ids:
                raise _problem("DUPLICATE_NODE_ID", "节点 ID 重复", f"nodes.{index}.id")
            node_ids.add(node_id)
            node_layout = (
                dict(layout_nodes.get(node_id, {}))
                if isinstance(layout_nodes.get(node_id), dict)
                else {}
            )
            for key in _NODE_LAYOUT_KEYS:
                if key in node:
                    node_layout[key] = node.pop(key)
            if node_layout:
                layout_nodes[node_id] = node_layout
            for key in _EPHEMERAL_NODE_KEYS:
                node.pop(key, None)
            semantic_nodes.append(node)
        source["nodes"] = semantic_nodes

        edges = _require_list(source, "edges")
        edge_ids: set[str] = set()
        semantic_edges: list[dict[str, Any]] = []
        for index, value in enumerate(edges):
            if not isinstance(value, dict):
                raise _problem("INVALID_DOCUMENT", "连线必须是对象", f"edges.{index}")
            edge = copy.deepcopy(value)
            edge_id = edge.get("id")
            if not isinstance(edge_id, str) or not edge_id:
                raise _problem("INVALID_DOCUMENT", "连线 ID 无效", f"edges.{index}.id")
            if edge_id in edge_ids:
                raise _problem("DUPLICATE_EDGE_ID", "连线 ID 重复", f"edges.{index}.id")
            edge_ids.add(edge_id)
            for endpoint in ("source", "target"):
                if edge.get(endpoint) not in node_ids:
                    raise _problem(
                        "DANGLING_EDGE",
                        "连线引用了不存在的节点",
                        f"edges.{index}.{endpoint}",
                    )
            for key in _EPHEMERAL_EDGE_KEYS:
                edge.pop(key, None)
            semantic_edges.append(edge)
        source["edges"] = semantic_edges
        _require_list(source, "variables")
        return cls(workflow_id, name, source, layout)

    def with_id(self, workflow_id: str) -> WorkflowDraft:
        return WorkflowDraft(workflow_id, self.name, self.document, self.layout)

    def to_payload(self) -> dict[str, Any]:
        result = copy.deepcopy(self.document)
        layout_nodes = self.layout.get("nodes", {})
        for node in result.get("nodes", []):
            node_layout = layout_nodes.get(node.get("id"), {})
            if isinstance(node_layout, dict):
                node.update(copy.deepcopy(node_layout))
        if "viewport" in self.layout:
            result["viewport"] = copy.deepcopy(self.layout["viewport"])
        result["name"] = self.name
        if self.id is not None:
            result["id"] = self.id
        return result


@dataclass(frozen=True, slots=True)
class SavedWorkflow:
    id: str
    name: str
    document: dict[str, Any]
    layout: dict[str, Any]
    revision: int
    created_at: datetime
    updated_at: datetime

    def to_payload(self) -> dict[str, Any]:
        payload = WorkflowDraft(
            self.id, self.name, self.document, self.layout
        ).to_payload()
        payload["revision"] = self.revision
        payload["createdAt"] = self.created_at.isoformat()
        payload["updatedAt"] = self.updated_at.isoformat()
        return payload


@dataclass(frozen=True, slots=True)
class WorkflowSummary:
    id: str
    name: str
    revision: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowSummaryPage:
    items: tuple[WorkflowSummary, ...]
    next_cursor: int | None
