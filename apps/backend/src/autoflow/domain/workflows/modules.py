from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .errors import WorkflowDocumentError

_SAFE_NAME = re.compile(r"[^A-Za-z0-9_\-\u4e00-\u9fa5]")

# 与 workflows/document.py 的布局/语义分离保持一致：position、style 等布局字段
# 由画布与 layout 存储负责，不参与模块定义的语义校验。
_NODE_SEMANTIC_FIELDS = ("id", "type", "data")


def _invalid(code: str, message: str, path: str) -> WorkflowDocumentError:
    return WorkflowDocumentError(code, message, 422, {"path": path})


def custom_module_reference(node: Mapping[str, Any]) -> str | None:
    data = node.get("data")
    config = data.get("config") if isinstance(data, Mapping) else None
    for container in (config, data, node):
        if isinstance(container, Mapping):
            value = container.get("customModuleId")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def custom_module_dependencies(workflow: Mapping[str, Any]) -> tuple[str, ...]:
    nodes = workflow.get("nodes", [])
    if not isinstance(nodes, list):
        return ()
    result: list[str] = []
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        data = node.get("data")
        module_type = (
            data.get("moduleType") if isinstance(data, Mapping) else node.get("type")
        )
        if module_type != "custom_module":
            continue
        module_id = custom_module_reference(node)
        if module_id and module_id not in result:
            result.append(module_id)
    return tuple(result)


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise _invalid("CUSTOM_MODULE_INVALID", f"{path} 必须是列表", path)
    return copy.deepcopy(value)


def _workflow(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise _invalid("CUSTOM_MODULE_INVALID", "workflow 必须是对象", "workflow")
    workflow = copy.deepcopy(dict(value))
    nodes = workflow.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise _invalid(
            "CUSTOM_MODULE_WORKFLOW_EMPTY", "工作流必须包含至少一个节点", "workflow.nodes"
        )
    edges = workflow.setdefault("edges", [])
    if not isinstance(edges, list):
        raise _invalid("CUSTOM_MODULE_INVALID", "workflow.edges 必须是列表", "workflow.edges")
    variables = workflow.setdefault("variables", [])
    if not isinstance(variables, list):
        raise _invalid(
            "CUSTOM_MODULE_INVALID", "workflow.variables 必须是列表", "workflow.variables"
        )
    for index, node in enumerate(nodes):
        if not isinstance(node, Mapping):
            raise _invalid(
                "CUSTOM_MODULE_INVALID", f"节点 {index} 数据格式错误", f"workflow.nodes.{index}"
            )
        # 布局字段（position 等）不进语义校验：工作流文档侧把它们剥离到 layout
        # 存储，图解析器和运行时也从不读取，模块定义只用于建图和执行。
        for field in _NODE_SEMANTIC_FIELDS:
            if field not in node:
                raise _invalid(
                    "CUSTOM_MODULE_INVALID",
                    f"节点 {index} 缺少必需字段: {field}",
                    f"workflow.nodes.{index}.{field}",
                )
    return workflow


@dataclass(frozen=True, slots=True)
class CustomModuleDraft:
    name: str
    definition: dict[str, Any]
    dependencies: tuple[str, ...]

    @classmethod
    def from_payload(
        cls, payload: Mapping[str, Any], *, base: Mapping[str, Any] | None = None
    ) -> CustomModuleDraft:
        merged = copy.deepcopy(dict(base or {}))
        merged.update(copy.deepcopy(dict(payload)))
        for key in (
            "id",
            "revision",
            "created_at",
            "updated_at",
            "usage_count",
            "clientRequestId",
            "expectedRevision",
        ):
            merged.pop(key, None)
        raw_name = merged.get("name")
        name = raw_name.strip() if isinstance(raw_name, str) else ""
        if not name:
            raise _invalid("CUSTOM_MODULE_NAME_REQUIRED", "模块名称不能为空", "name")
        if len(name) > 50:
            raise _invalid("CUSTOM_MODULE_NAME_INVALID", "模块名称过长（最多 50 字符）", "name")
        display_name = merged.get("display_name", name)
        if not isinstance(display_name, str) or not display_name.strip():
            raise _invalid("CUSTOM_MODULE_INVALID", "显示名称不能为空", "display_name")
        merged.update(
            {
                "name": name,
                "display_name": display_name.strip(),
                "description": str(merged.get("description") or ""),
                "icon": str(merged.get("icon") or "📦"),
                "color": str(merged.get("color") or "#8B5CF6"),
                "category": str(merged.get("category") or "custom"),
                "parameters": _list(merged.get("parameters", []), "parameters"),
                "outputs": _list(merged.get("outputs", []), "outputs"),
                "workflow": _workflow(merged.get("workflow")),
                "author": str(merged.get("author") or ""),
                "version": str(merged.get("version") or "1.0.0"),
                "tags": _list(merged.get("tags", []), "tags"),
                "download_count": int(merged.get("download_count") or 0),
                "is_published": bool(merged.get("is_published", False)),
                "is_builtin": bool(merged.get("is_builtin", False)),
                "is_favorite": bool(merged.get("is_favorite", False)),
                "sort_order": int(merged.get("sort_order") or 0),
            }
        )
        workflow = merged["workflow"]
        return cls(name, merged, custom_module_dependencies(workflow))

    @staticmethod
    def generated_id(name: str, suffix: str) -> str:
        safe = _SAFE_NAME.sub("_", name)[:50] or "module"
        return f"custom_{safe}_{suffix}"


@dataclass(frozen=True, slots=True)
class SavedCustomModule:
    id: str
    definition: Mapping[str, Any]
    dependencies: tuple[str, ...]
    revision: int
    usage_count: int
    created_at: datetime
    updated_at: datetime

    @property
    def name(self) -> str:
        return str(self.definition["name"])

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            **copy.deepcopy(dict(self.definition)),
            "revision": self.revision,
            "usage_count": self.usage_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
