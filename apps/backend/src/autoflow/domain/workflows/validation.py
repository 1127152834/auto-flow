import json
import math
from collections import Counter
from typing import Any
from urllib.parse import urlsplit

from .catalog import node_catalog
from .control import CONTROL_TYPES, compile_control, control_config_issues
from .models import WorkflowError, WorkflowIssue
from .references import REFERENCE_PATTERN as _REFERENCE
from .references import is_variable_name as _name


def validate_structure(document: dict[str, Any], layout: dict[str, Any]) -> None:
    errors: list[WorkflowIssue] = []
    extended = document.get("schemaVersion", 1) == 2

    def error(
        code: str, message: str, path: list[str], node_id: str | None = None
    ) -> None:
        errors.append(WorkflowIssue(node_id, path, code, message))

    try:
        json.dumps([document, layout], allow_nan=False)
    except (ValueError, TypeError):
        error("INVALID_JSON", "文档必须是有效 JSON", [])
    nodes, edges = document["nodes"], document["edges"]
    for node in nodes:
        if not extended and node['type'] in CONTROL_TYPES:
            error('SCHEMA_VERSION_REQUIRED', '控制节点需要工作流格式版本2', ['schemaVersion'], node['id'])
        for field in ('endNodeId', 'ownerNodeId'):
            reference = node['config'].get(field)
            if isinstance(reference, str) and reference and not any(n['id'] == reference for n in nodes):
                error('MISSING_NODE', '配对引用了不存在的节点', ['config', field], node['id'])
    ids = {node["id"] for node in nodes}
    if len(ids) != len(nodes):
        error("DUPLICATE_NODE", "节点标识重复", ["nodes"])
    if ids != set(layout["nodes"]):
        error(
            "INVALID_LAYOUT", "节点布局必须与文档中的节点一一对应", ["layout", "nodes"]
        )
    seen_ids: set[str] = set()
    pairs: set[tuple[str, ...]] = set()
    incoming: Counter[str] = Counter()
    outgoing: dict[str, str] = {}
    for index, edge in enumerate(edges):
        source, target = edge["source"], edge["target"]
        path = ["edges", str(index)]
        pair = (source, target, edge.get("sourceHandle", "out")) if extended else (source, target)
        if edge["id"] in seen_ids or pair in pairs:
            error("DUPLICATE_EDGE", "连线重复", path, source)
        seen_ids.add(edge["id"])
        pairs.add(pair)
        if source not in ids or target not in ids:
            error("MISSING_NODE", "连线引用了不存在的节点", path, source)
        if source == target:
            error("SELF_CONNECTION", "节点不能连接自身", path, source)
        incoming[target] += 1
        if not extended and (incoming[target] > 1 or source in outgoing):
            error(
                "BRANCH_NOT_SUPPORTED",
                "基础流程的每个节点最多一个输入和一个输出",
                path,
                source,
            )
        outgoing[source] = target
    # With at most one successor, walk each component once without recursive depth limits.
    visited: set[str] = set()
    for start in (() if extended else ids):
        trail: set[str] = set()
        current: str | None = start
        while current is not None and current not in visited:
            if current in trail:
                error(
                    "CYCLE_NOT_SUPPORTED", "基础流程不允许循环连线", ["edges"], current
                )
                break
            trail.add(current)
            current = outgoing.get(current)
        visited.update(trail)
    if errors:
        raise WorkflowError("WORKFLOW_STRUCTURE_INVALID", "工作流结构无效", 422, errors)


def workflow_issues(document: dict[str, Any]) -> list[WorkflowIssue]:
    issues: list[WorkflowIssue] = []

    def issue(
        code: str, message: str, path: list[str], node_id: str | None = None
    ) -> None:
        issues.append(WorkflowIssue(node_id, path, code, message))

    def check_references(
        value: object, path: list[str], node_id: str | None = None
    ) -> None:
        pending = [(value, path)]
        while pending:
            current, current_path = pending.pop()
            if isinstance(current, dict):
                pending.extend(
                    (child, [*current_path, str(key)]) for key, child in current.items()
                )
            elif isinstance(current, list):
                pending.extend(
                    (child, [*current_path, str(index)])
                    for index, child in enumerate(current)
                )
            elif isinstance(current, str):
                seen: set[str] = set()
                for match in _REFERENCE.finditer(current):
                    name = (
                        match.group(1) if match.group(1) is not None else match.group(2)
                    )
                    if not _name(name) and match.group(1) is None:
                        continue
                    if name in seen:
                        continue
                    seen.add(name)
                    if not _name(name):
                        # Bare braces can be literal JSON/text. Only ${...} explicitly
                        # requests a reference when its contents are not an identifier.
                        issue(
                            "INVALID_REFERENCE",
                            "变量引用须使用 {变量名} 或 ${变量名}",
                            current_path,
                            node_id,
                        )
                    elif name not in names:
                        issue(
                            "UNKNOWN_VARIABLE",
                            f"变量 {name} 尚未声明",
                            current_path,
                            node_id,
                        )

    definitions = {item["type"]: item for item in node_catalog()}
    declarations = document["variables"]
    counts = Counter(variable["name"] for variable in declarations)
    names = {variable["name"] for variable in declarations if _name(variable["name"])}
    # M1 checks declarations only, not execution order or availability of runtime values.
    names.update(
        node["config"]["variableName"]
        for node in document["nodes"]
        if _name(node["config"].get("variableName"))
    )
    names.update(n["config"].get(field, "") for n in document["nodes"] if n["type"] == "loop" for field in ("indexVariable", "itemVariable") if _name(n["config"].get(field)))
    outputs = Counter(
        node["config"]["variableName"]
        for node in document["nodes"]
        if _name(node["config"].get("variableName"))
    )
    for index, variable in enumerate(declarations):
        path = ["variables", str(index)]
        if not _name(variable["name"]):
            issue("INVALID_VARIABLE_NAME", "变量名须为有效标识符", [*path, "name"])
        if counts[variable["name"]] > 1:
            issue("DUPLICATE_VARIABLE", "变量名称重复", [*path, "name"])
        if not _matches_type(variable["value"], variable["type"]):
            issue("VARIABLE_TYPE_MISMATCH", "变量值与声明类型不符", [*path, "value"])
        check_references(variable["value"], [*path, "value"])
    for node in document["nodes"]:
        config = node["config"]
        if node["type"] not in definitions:
            issue("NODE_NOT_RUNNABLE", "不支持的节点类型", ["type"], node["id"])
            continue
        if node["type"] in CONTROL_TYPES:
            issues.extend(control_config_issues(node))
        schema = definitions[node["type"]]["configSchema"]
        required = set(schema["required"])
        if node["type"] == "screenshot" and config.get("screenshotType") == "element":
            required.add("selector")
        for field in required:
            if (
                field not in config
                or config[field] is None
                or config[field] == ""
                or (isinstance(config[field], str) and not config[field].strip())
            ):
                issue("REQUIRED", "此字段尚未填写", ["config", field], node["id"])
        for field, value in config.items():
            path = ["config", field]
            if node["type"] not in CONTROL_TYPES and field != "variableName" and not (
                field in {"selector", "framePath"}
                and node["type"] == "screenshot"
                and config.get("screenshotType", "fullpage") != "element"
            ):
                check_references(value, path, node["id"])
            definition = schema["properties"].get(field)
            if definition is None:
                issue(
                    "UNKNOWN_CONFIG_FIELD", "此节点不支持该配置字段", path, node["id"]
                )
                continue
            if not _matches_type(value, definition["type"]):
                issue("INVALID_CONFIG_TYPE", "配置值类型不符", path, node["id"])
                continue
            if field == "framePath":
                for index, step in enumerate(value):
                    if not isinstance(step, str) or not step.strip():
                        issue("INVALID_FRAME_PATH", "框架路径须为非空选择器", [*path, str(index)], node["id"])
            if "enum" in definition and value not in definition["enum"]:
                issue("INVALID_CONFIG_VALUE", "请选择有效选项", path, node["id"])
            if node["type"].startswith("android_"):
                if field in {"x", "y", "basisWidth", "basisHeight"} and (type(value) is not int or value < (1 if field.startswith("basis") else 0)):
                    issue("INVALID_COORDINATE", "坐标与画面尺寸必须为有效整数", path, node["id"])
                if field == "timeoutSeconds" and not (30 <= value <= 3600 if node["type"] == "android_manual" else 0 < value <= 180):
                    issue("INVALID_TIMEOUT", "安卓操作超时超出允许范围", path, node["id"])
            if field == "timeoutSeconds" and value <= 0:
                issue("INVALID_TIMEOUT", "超时须大于 0 秒", path, node["id"])
            if field == "variableName" and value and not _name(value):
                issue(
                    "INVALID_VARIABLE_NAME",
                    "输出变量名须为有效标识符",
                    path,
                    node["id"],
                )
            if field == "variableName" and _name(value) and outputs[value] > 1:
                issue(
                    "DUPLICATE_OUTPUT_VARIABLE",
                    "多个节点写入同名变量，运行时可能覆盖",
                    path,
                    node["id"],
                )
            if (
                isinstance(value, str)
                and field == "url"
                and value
                and not any(
                    match.group(1) is not None or _name(match.group(2))
                    for match in _REFERENCE.finditer(value)
                )
            ):
                try:
                    parsed = urlsplit(value)
                    valid = (
                        parsed.scheme in {"http", "https"}
                        and bool(parsed.hostname)
                        and not any(character.isspace() for character in parsed.netloc)
                    )
                except ValueError:
                    valid = False
                if not valid:
                    issue(
                        "INVALID_URL",
                        "请输入 HTTP/HTTPS 网址或变量引用",
                        path,
                        node["id"],
                    )
    nodes, edges = document["nodes"], document["edges"]
    if not nodes:
        issue("EMPTY_WORKFLOW", "添加节点后开始编排", ["nodes"])
    elif len(nodes) > 1 and (document.get("schemaVersion", 1) == 1 or not any(n["type"] in CONTROL_TYPES for n in nodes)):
        neighbors: dict[str, set[str]] = {node["id"]: set() for node in nodes}
        for edge in edges:
            neighbors[edge["source"]].add(edge["target"])
            neighbors[edge["target"]].add(edge["source"])
        reachable: set[str] = set()
        pending = [nodes[0]["id"]]
        while pending:
            current = pending.pop()
            if current not in reachable:
                reachable.add(current)
                pending.extend(neighbors[current] - reachable)
        if len(reachable) != len(nodes):
            for node in nodes:
                if not neighbors[node["id"]] or node["id"] not in reachable:
                    issue(
                        "DISCONNECTED_NODE",
                        "节点尚未连接到同一条流程",
                        ["edges"],
                        node["id"],
                    )
    if document.get("schemaVersion", 1) == 2 and not any(i.node_id and i.code not in {"UNKNOWN_VARIABLE", "DUPLICATE_OUTPUT_VARIABLE", "DISCONNECTED_NODE"} for i in issues):
        try:
            compile_control(document, check_variables=False)
        except WorkflowError as error:
            issues.extend(error.issues)
    return issues


def _matches_type(value: object, expected: str) -> bool:
    if expected == "number":
        return type(value) is int or (type(value) is float and math.isfinite(value))
    return (
        type(value)
        is {"string": str, "boolean": bool, "array": list, "object": dict}[expected]
    )
