import json
import math
from copy import deepcopy
from typing import Any, NoReturn

from .models import WorkflowError, WorkflowIssue
from .references import is_workflow_id

SOURCE_PRODUCT = "WebRPA"
SOURCE_COMMIT = "5ccb900e8dcf1530aae66f676d87593c416c7ebb"
FORMAT_KIND = "webrpa-workflow"
FORMAT_VERSION = 1

_NODE_FIELDS = (
    "id",
    "type",
    "position",
    "data",
    "style",
    "parentId",
    "extent",
    "width",
    "height",
    "zIndex",
    "hidden",
    "origin",
    "expandParent",
)
_EDGE_FIELDS = (
    "id",
    "type",
    "source",
    "target",
    "sourceHandle",
    "targetHandle",
    "data",
    "style",
    "markerStart",
    "markerEnd",
    "animated",
    "hidden",
    "zIndex",
    "interactionWidth",
)
_VARIABLE_FIELDS = ("name", "value", "type", "scope", "description", "builtin")
_SECRET_FIELDS = frozenset(
    {
        "apiKey",
        "api_key",
        "authCode",
        "auth_code",
        "password",
        "emailPassword",
        "email_password",
        "accessToken",
        "access_token",
        "appSecret",
        "app_secret",
        "azureApiKey",
        "azure_api_key",
        "imageApiKey",
        "image_api_key",
        "videoApiKey",
        "video_api_key",
        "token",
        "secret",
        "privateKey",
        "private_key",
    }
)
# Variable names are user data. Protect names that identify concrete Studio
# credential fields, while allowing generic business variables such as `token`.
_CREDENTIAL_VARIABLE_NAMES = _SECRET_FIELDS - {"token", "secret"}


def project_document(value: object) -> dict[str, Any]:
    issues: list[WorkflowIssue] = []

    def issue(
        code: str, message: str, path: list[str], node_id: str | None = None
    ) -> None:
        issues.append(WorkflowIssue(node_id, path, code, message))

    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        issue("INVALID_JSON", "工作流必须是有限、可编码的 JSON", [])
        _raise_invalid(issues)
    if not _strict_json(value):
        issue("INVALID_JSON", "工作流必须是有限、可编码的 JSON", [])
        _raise_invalid(issues)
    if not isinstance(value, dict):
        issue("INVALID_DOCUMENT", "工作流文档必须是对象", [])
        _raise_invalid(issues)
    document = value
    workflow_id = document.get("id")
    if not is_workflow_id(workflow_id):
        issue("INVALID_WORKFLOW_ID", "工作流标识必须是 UUID 或 Studio Nano ID", ["id"])
    source_metadata = document.get("source")
    if source_metadata != {"product": SOURCE_PRODUCT, "commit": SOURCE_COMMIT}:
        issue("INVALID_SOURCE", "工作流来源标识不受支持", ["source"])
    format_metadata = document.get("format")
    if format_metadata != {"kind": FORMAT_KIND, "version": FORMAT_VERSION}:
        issue("INVALID_FORMAT", "工作流格式标识不受支持", ["format"])
    content = document.get("content")
    if not isinstance(content, dict):
        issue("INVALID_CONTENT", "工作流内容必须是对象", ["content"])
        _raise_invalid(issues)
    if not isinstance(content.get("id"), str) or not content["id"]:
        issue("INVALID_SOURCE_ID", "来源工作流标识不能为空", ["content", "id"])
    if not isinstance(content.get("name"), str):
        issue("INVALID_NAME", "工作流名称必须是字符串", ["content", "name"])
    nodes = content.get("nodes")
    edges = content.get("edges")
    variables = content.get("variables")
    if not isinstance(nodes, list):
        issue("INVALID_NODES", "节点必须是数组", ["content", "nodes"])
    if not isinstance(edges, list):
        issue("INVALID_EDGES", "连线必须是数组", ["content", "edges"])
    if not isinstance(variables, list):
        issue("INVALID_VARIABLES", "变量必须是数组", ["content", "variables"])
    if issues:
        _raise_invalid(issues)
    assert isinstance(nodes, list)
    assert isinstance(edges, list)
    assert isinstance(variables, list)

    projected_nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    for index, raw in enumerate(nodes):
        path = ["content", "nodes", str(index)]
        if not isinstance(raw, dict):
            issue("INVALID_NODE", "节点必须是对象", path)
            continue
        node_id = raw.get("id")
        if not isinstance(node_id, str) or not node_id:
            issue("INVALID_NODE_ID", "节点标识不能为空", [*path, "id"])
            continue
        if node_id in node_ids:
            issue("DUPLICATE_NODE", "节点标识重复", [*path, "id"], node_id)
        node_ids.add(node_id)
        if not isinstance(raw.get("type"), str) or not raw["type"]:
            issue("INVALID_NODE_TYPE", "React Flow 节点类型不能为空", [*path, "type"], node_id)
        data = raw.get("data")
        if not isinstance(data, dict):
            issue("INVALID_NODE_DATA", "节点 data 必须是对象", [*path, "data"], node_id)
            continue
        if not isinstance(data.get("moduleType"), str) or not data["moduleType"]:
            issue(
                "MODULE_TYPE_REQUIRED",
                "节点 data.moduleType 不能为空",
                [*path, "data", "moduleType"],
                node_id,
            )
        elif raw.get("type") != data["moduleType"]:
            issue(
                "MODULE_TYPE_MISMATCH",
                "导出节点 type 必须与 data.moduleType 一致",
                [*path, "type"],
                node_id,
            )
        position = raw.get("position")
        if not _point(position):
            issue("INVALID_POSITION", "节点位置必须包含有限数值 x/y", [*path, "position"], node_id)
        projected = {
            field: deepcopy(raw[field]) for field in _NODE_FIELDS if field in raw
        }
        projected_data = _project_config(data, [*path, "data"], node_id, issue)
        projected_data.pop("isHighlighted", None)
        projected_data.pop("__aiSpawning", None)
        projected["data"] = projected_data
        projected_nodes.append(projected)

    projected_edges: list[dict[str, Any]] = []
    edge_ids: set[str] = set()
    for index, raw in enumerate(edges):
        path = ["content", "edges", str(index)]
        if not isinstance(raw, dict):
            issue("INVALID_EDGE", "连线必须是对象", path)
            continue
        edge_id = raw.get("id")
        if not isinstance(edge_id, str) or not edge_id:
            issue("INVALID_EDGE_ID", "连线标识不能为空", [*path, "id"])
            continue
        if edge_id in edge_ids:
            issue("DUPLICATE_EDGE", "连线标识重复", [*path, "id"])
        edge_ids.add(edge_id)
        source_id, target_id = raw.get("source"), raw.get("target")
        if source_id not in node_ids or target_id not in node_ids:
            issue("MISSING_NODE", "连线引用了不存在的节点", path)
        for field in ("sourceHandle", "targetHandle"):
            if field in raw and raw[field] is not None and not isinstance(raw[field], str):
                issue("INVALID_HANDLE", "端口标识必须是字符串或 null", [*path, field])
        projected_edges.append(
            {field: deepcopy(raw[field]) for field in _EDGE_FIELDS if field in raw}
        )

    projected_variables: list[dict[str, Any]] = []
    variable_names: set[str] = set()
    for index, raw in enumerate(variables):
        path = ["content", "variables", str(index)]
        if not isinstance(raw, dict):
            issue("INVALID_VARIABLE", "变量必须是对象", path)
            continue
        name = raw.get("name")
        if not isinstance(name, str) or not name:
            issue("INVALID_VARIABLE_NAME", "变量名不能为空", [*path, "name"])
        elif name in variable_names:
            issue("DUPLICATE_VARIABLE", "变量名称重复", [*path, "name"])
        else:
            variable_names.add(name)
        projected_raw = _project_config(raw, path, None, issue)
        if (
            isinstance(name, str)
            and name in _CREDENTIAL_VARIABLE_NAMES
            and raw.get("value") not in ("", None)
        ):
            issue(
                "SECRET_FIELD_FORBIDDEN",
                f"工作流变量 {name} 不能保存明文凭据",
                [*path, "value"],
            )
        projected_variables.append(
            {
                field: projected_raw[field]
                for field in _VARIABLE_FIELDS
                if field in projected_raw
            }
        )
    if issues:
        _raise_invalid(issues)
    return {
        "id": workflow_id,
        "source": deepcopy(source_metadata),
        "format": deepcopy(format_metadata),
        "content": {
            "id": content["id"],
            "name": content["name"],
            "nodes": projected_nodes,
            "edges": projected_edges,
            "variables": projected_variables,
        },
    }


def _point(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) >= {"x", "y"}
        and _finite_number(value["x"])
        and _finite_number(value["y"])
    )


def _finite_number(value: object) -> bool:
    return type(value) is int or type(value) is float and math.isfinite(value)


def _strict_json(value: object) -> bool:
    if value is None or type(value) in (bool, int, str):
        return True
    if type(value) is float:
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_strict_json(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _strict_json(item)
            for key, item in value.items()
        )
    return False


def _project_config(
    value: object,
    path: list[str],
    node_id: str | None,
    issue: Any,
) -> Any:
    if isinstance(value, dict):
        projected = {}
        for key, item in value.items():
            item_path = [*path, str(key)]
            if key in _SECRET_FIELDS:
                if item not in ("", None):
                    issue(
                        "SECRET_FIELD_FORBIDDEN",
                        f"工作流文档不能保存密钥字段 {key}",
                        item_path,
                        node_id,
                    )
                continue
            projected[key] = _project_config(item, item_path, node_id, issue)
        return projected
    if isinstance(value, list):
        return [
            _project_config(item, [*path, str(index)], node_id, issue)
            for index, item in enumerate(value)
        ]
    return deepcopy(value)


def _raise_invalid(issues: list[WorkflowIssue]) -> NoReturn:
    raise WorkflowError("WORKFLOW_INVALID", "工作流文档无效", 422, issues)
