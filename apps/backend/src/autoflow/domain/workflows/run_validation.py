"""Compile a saved or unsaved draft into a single, isolated execution snapshot."""

import json
from collections.abc import Callable, Iterator
from copy import deepcopy
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any
from urllib.parse import urlsplit

from .catalog import node_catalog
from .control import CONTROL_TYPES, compile_control
from .models import WorkflowError, WorkflowIssue
from .references import REFERENCE_PATTERN, is_variable_name
from .validation import validate_structure, workflow_issues


@dataclass(frozen=True)
class PreparedWorkflow:
    document: dict[str, Any]
    node_ids: list[str]
    variables: dict[str, Any]
    warnings: list[WorkflowIssue]
    plan: list[dict[str, Any]] = dataclass_field(default_factory=list)


def _fail(code: str, message: str, path: list[str], node_id: str | None = None) -> None:
    raise WorkflowError(
        "WORKFLOW_RUN_INVALID", message, 422,
        [WorkflowIssue(node_id, path, code, message)],
    )


def _references(value: object, path: list[str]) -> Iterator[tuple[str, list[str]]]:
    pending = [(value, path)]
    while pending:
        current, current_path = pending.pop()
        if isinstance(current, dict):
            pending.extend((child, [*current_path, key]) for key, child in current.items())
        elif isinstance(current, list):
            pending.extend((child, [*current_path, str(i)]) for i, child in enumerate(current))
        elif isinstance(current, str):
            for match in REFERENCE_PATTERN.finditer(current):
                name = match.group(1) if match.group(1) is not None else match.group(2)
                if is_variable_name(name):
                    yield name, current_path


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _substitute(value: Any, lookup: Callable[[str], Any]) -> Any:
    if isinstance(value, dict):
        return {key: _substitute(child, lookup) for key, child in value.items()}
    if isinstance(value, list):
        return [_substitute(child, lookup) for child in value]
    if not isinstance(value, str):
        return value

    def replace(match: Any) -> str:
        name = match.group(1) if match.group(1) is not None else match.group(2)
        return _as_text(lookup(name)) if is_variable_name(name) else match.group(0)

    # re.sub does not rescan inserted text. A value containing braces stays literal.
    return REFERENCE_PATTERN.sub(replace, value)


def initial_values(document: dict[str, Any]) -> dict[str, Any]:
    declarations = {item["name"]: item["value"] for item in document["variables"]}
    indices = {item["name"]: str(i) for i, item in enumerate(document["variables"])}
    dependencies: dict[str, set[str]] = {}
    for name, value in declarations.items():
        deps: set[str] = set()
        for dependency, path in _references(value, ["variables", indices[name], "value"]):
            if dependency not in declarations:
                _fail("INITIAL_VARIABLE_UNAVAILABLE", f"初值引用的变量 {dependency} 尚不可用", path)
            deps.add(dependency)
        dependencies[name] = deps
    dependents: dict[str, list[str]] = {name: [] for name in declarations}
    for name, deps in dependencies.items():
        for dependency in deps:
            dependents[dependency].append(name)
    pending = [name for name, deps in dependencies.items() if not deps]
    result: dict[str, Any] = {}
    while pending:
        name = pending.pop()
        result[name] = _substitute(declarations[name], result.__getitem__)
        for dependent in dependents[name]:
            dependencies[dependent].remove(name)
            if not dependencies[dependent]:
                pending.append(dependent)
    if len(result) != len(declarations):
        name = next(name for name in declarations if name not in result)
        _fail("VARIABLE_DEPENDENCY_CYCLE", "变量初值存在循环引用", ["variables", indices[name], "value"])
    return result


def prepare_run(document: dict[str, Any], layout: dict[str, Any]) -> PreparedWorkflow:
    validate_structure(document, layout)
    effective = deepcopy(document)
    definitions = {definition["type"]: definition for definition in node_catalog()}
    for node in effective["nodes"]:
        if node["type"] not in definitions:
            _fail("NODE_NOT_RUNNABLE", "此节点尚不支持执行", ["type"], node["id"])
        node["config"] = {**deepcopy(definitions[node["type"]]["defaultConfig"]), **node["config"]}
    issues = workflow_issues(effective)
    warnings = [issue for issue in issues if issue.code == "DUPLICATE_OUTPUT_VARIABLE"]
    errors = [issue for issue in issues if issue.code != "DUPLICATE_OUTPUT_VARIABLE"]
    if errors:
        raise WorkflowError("WORKFLOW_RUN_INVALID", "请完成流程配置后再运行", 422, errors)
    variables = initial_values(effective)
    if effective.get("schemaVersion", 1) == 2:
        plan = compile_control(effective)
        return PreparedWorkflow(effective, [node["id"] for node in effective["nodes"]], variables, warnings, plan)
    nodes = {node["id"]: node for node in effective["nodes"]}
    outgoing = {edge["source"]: edge["target"] for edge in effective["edges"]}
    targets = {edge["target"] for edge in effective["edges"]}
    current = next(node_id for node_id in nodes if node_id not in targets)
    ordered: list[str] = []
    available = set(variables)
    while current is not None:
        ordered.append(current)
        node = nodes[current]
        config = node["config"]
        for field in ("url", "selector", "framePath", "text", "savePath", "packageName", "prompt"):
            # A hidden element selector is not used by viewport/full-page screenshots.
            if field in {"selector", "framePath"} and node["type"] == "screenshot" and config["screenshotType"] != "element":
                continue
            for name, path in _references(config.get(field), ["config", field]):
                if name not in available:
                    _fail("VARIABLE_NOT_AVAILABLE", f"变量 {name} 在此节点执行前尚未产生", path, current)
        if node["type"] in {"get_element_info", "screenshot", "android_screenshot"}:
            available.add(config["variableName"])
        current = outgoing.get(current)
    return PreparedWorkflow(effective, ordered, variables, warnings)


def resolve_node_config(node: dict[str, Any], variables: dict[str, Any]) -> dict[str, Any]:
    config = deepcopy(node["config"])
    for field in ("url", "selector", "framePath", "text", "savePath", "packageName", "prompt"):
        if field not in config:
            continue
        if field in {"selector", "framePath"} and node["type"] == "screenshot" and config["screenshotType"] != "element":
            continue
        for name, path in _references(config[field], ["config", field]):
            if name not in variables:
                _fail("VARIABLE_NOT_AVAILABLE", f"变量 {name} 尚未产生", path, node["id"])
        config[field] = _substitute(config[field], variables.__getitem__)
        if field == "framePath":
            for index, step in enumerate(config[field]):
                if not step.strip():
                    _fail("REQUIRED", "变量解析后框架路径为空", ["config", field, str(index)], node["id"])
        if field in {"url", "selector"} and not config[field].strip():
            _fail("REQUIRED", "变量解析后此字段为空", ["config", field], node["id"])
    if node["type"] == "open_page":
        try:
            parsed = urlsplit(config["url"])
            valid = parsed.scheme in {"http", "https"} and bool(parsed.hostname) and not any(c.isspace() for c in parsed.netloc)
            _ = parsed.port
        except ValueError:
            valid = False
        if not valid:
            _fail("INVALID_URL", "变量解析后须为有效 HTTP/HTTPS 网址", ["config", "url"], node["id"])
    return config


def validate_runtime(document: dict[str, Any], android: bool) -> None:
    for node in document["nodes"]:
        kind = node["type"]
        mismatch = kind not in CONTROL_TYPES and kind.startswith("android_") != android
        page_rule = android and kind in {"condition", "loop"} and any(r.get("kind") == "page" for r in node["config"].get("rules", []))
        if mismatch or page_rule:
            message = "安卓与浏览器动作不能混合运行，安卓流程不支持网页条件"
            raise WorkflowError("WORKFLOW_RUNTIME_MISMATCH", message, 422, [WorkflowIssue(node["id"], ["config", "rules"] if page_rule else ["type"], "WORKFLOW_RUNTIME_MISMATCH", message)])
