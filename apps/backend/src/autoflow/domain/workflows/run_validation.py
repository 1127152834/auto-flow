"""Freeze the current WebRPA React Flow document for the PM3 worker boundary."""

import math
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .canvas_subflows import CanvasSubflowGraph
from .catalog import runnable_module_types
from .graph import WorkflowDefinition, parse_workflow
from .manual_contract import validate_declaration
from .models import WorkflowError, WorkflowIssue
from .parallel_graph import structured_fork
from .validation import project_document

_DEFAULT_CONFIGS: dict[str, dict[str, Any]] = {
    "open_page": {"openMode": "new_tab", "waitUntil": "load", "timeout": 60},
    "click_element": {
        "clickType": "single",
        "followNewTab": False,
        "timeout": 60,
    },
    "input_text": {"clearBefore": True, "timeout": 60},
    "get_element_info": {
        "attribute": "text",
        "variableName": "element_value",
        "timeout": 60,
    },
}


@dataclass(frozen=True)
class PreparedWorkflow:
    document: dict[str, Any]
    node_ids: list[str]
    module_types: list[str]
    graph_adapter: bool = False


def prepare_run(document: object) -> PreparedWorkflow:
    projected = project_document(document)
    assert isinstance(document, dict)
    nodes = projected["content"]["nodes"]
    graph = CanvasSubflowGraph(projected["content"])
    project_semantics = projected["content"].get("schemaVersion") != 3 or any(
        node["data"]["moduleType"].startswith("project_") for node in nodes
    )
    scopes = graph.project_scopes() if project_semantics else {
        "": {node["id"] for node in graph.top_level_document()["nodes"]}
    }
    supported = runnable_module_types()
    graph_adapter = projected["content"].get("schemaVersion") == 3 or any(
        node["data"]["moduleType"] not in _DEFAULT_CONFIGS for node in nodes
    )
    connected = {
        endpoint
        for edge in projected["content"]["edges"]
        for endpoint in (edge["source"], edge["target"])
    }
    issues = []
    for index, node in enumerate(nodes):
        node_id = node["id"]
        module_type = node["data"]["moduleType"]
        visual = module_type in {"group", "note"} and not graph._is_definition(node)
        if (visual and node_id in connected) or (module_type not in supported and not graph._is_definition(node) and not (graph_adapter and (visual or module_type == "custom_module"))):
            issues.append(
                WorkflowIssue(
                    node_id,
                    ["content", "nodes", str(index), "data", "moduleType"],
                    "WORKFLOW_NOT_RUNNABLE",
                    "展示节点不能接入执行链" if visual and node_id in connected else f"服务端尚不支持运行节点 {module_type}",
                )
            )
    if issues:
        raise WorkflowError(
            "WORKFLOW_NOT_RUNNABLE", "工作流包含尚不可执行的节点", 422, issues
        )
    by_id = {node["id"]: node for node in nodes}
    if graph_adapter and not any(node["data"]["moduleType"] not in {"group", "note", "subflow_header"} for node in nodes):
        raise WorkflowError("WORKFLOW_NOT_RUNNABLE", "工作流没有可执行节点", 422)
    for scope, members in scopes.items():
        subset = graph._subset(members)
        ends = [n['id'] for n in subset['nodes'] if n['data']['moduleType'] == 'project_end']
        if len(ends) > 1 or any(edge['source'] in ends for edge in subset['edges']):
            raise WorkflowError('WORKFLOW_NOT_RUNNABLE', 'End 必须是唯一的最终节点，不能有后续连线', 422)
        for node in subset['nodes']:
            if node['data']['moduleType'] == 'project_manual':
                validate_declaration(node['data'].get('config', node['data']), node['id'], subset['nodes'], subset['edges'])
        _validate_lifecycle_graph(subset['nodes'], subset['edges'], ends)
        valid, errors = WorkflowDefinition.from_raw(subset).validate()
        if not valid and (members or not scope) and not all(n["data"]["moduleType"] in _DEFAULT_CONFIGS for n in nodes):
            raise WorkflowError(
                "WORKFLOW_NOT_RUNNABLE", "；".join(errors), 422,
                [WorkflowIssue(None, ["content", "edges"], "INVALID_EXECUTION_GRAPH", message) for message in errors],
            )
    # Defaults validate Studio content without rewriting its frozen snapshot.
    validation_nodes = deepcopy(nodes) if graph_adapter else nodes
    for node in validation_nodes:
        data = node["data"]
        config = data.get("config", data)
        if not isinstance(config, dict):
            raise WorkflowError("WORKFLOW_NOT_RUNNABLE", "节点配置必须是对象", 422)
        for key, value in _DEFAULT_CONFIGS.get(data["moduleType"], {"timeout": 60}).items():
            config.setdefault(key, value)
    config_issues = [
        issue
        for index, node in enumerate(validation_nodes)
        for issue in _config_issues(node, index, studio=graph_adapter)
    ]
    if config_issues:
        raise WorkflowError(
            "WORKFLOW_NOT_RUNNABLE",
            "工作流节点配置不完整或无效",
            422,
            config_issues,
        )
    if graph_adapter:
        node_ids = [node["id"] for node in nodes if node["data"]["moduleType"] not in {"group", "note"}]
        if not node_ids:
            raise WorkflowError("WORKFLOW_NOT_RUNNABLE", "工作流没有可执行节点", 422)
    else:
        node_ids = _ordered_chain(nodes, projected["content"]["edges"])
    return PreparedWorkflow(
        deepcopy(document) if graph_adapter else projected,
        node_ids,
        [by_id[node_id]["data"]["moduleType"] for node_id in node_ids],
        graph_adapter,
    )


def _ordered_chain(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> list[str]:
    node_ids = [node["id"] for node in nodes]
    incoming: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    routes: set[tuple[str, str]] = set()
    valid = bool(nodes) and len(edges) == len(nodes) - 1
    for edge in edges:
        source, target = edge.get("source"), edge.get("target")
        if not isinstance(source, str) or not isinstance(target, str):
            valid = False
            continue
        if source not in outgoing or target not in incoming:
            valid = False
            continue
        route = (source, target)
        if (
            source == target
            or route in routes
            or edge.get("sourceHandle") is not None
            or edge.get("targetHandle") is not None
        ):
            valid = False
        routes.add(route)
        outgoing[source].append(target)
        incoming[target].append(source)
    if any(len(items) > 1 for items in incoming.values()) or any(
        len(items) > 1 for items in outgoing.values()
    ):
        valid = False
    starts = [node_id for node_id in node_ids if not incoming[node_id]]
    ends = [node_id for node_id in node_ids if not outgoing[node_id]]
    if len(starts) != 1 or len(ends) != 1:
        valid = False
    ordered: list[str] = []
    current = starts[0] if len(starts) == 1 else None
    seen: set[str] = set()
    while current is not None and current not in seen:
        ordered.append(current)
        seen.add(current)
        current = outgoing[current][0] if outgoing[current] else None
    if len(ordered) != len(nodes):
        valid = False
    if not valid:
        issue = WorkflowIssue(
            None,
            ["content", "edges"],
            "INVALID_EXECUTION_CHAIN",
            "运行只支持覆盖所有节点的一条无分支有向链",
        )
        raise WorkflowError(
            "WORKFLOW_NOT_RUNNABLE", "工作流执行图不受支持", 422, [issue]
        )
    return ordered


def _config_issues(node: dict[str, Any], index: int, *, studio: bool = False) -> list[WorkflowIssue]:
    module_type = node["data"]["moduleType"]
    data = node["data"].get("config", node["data"])
    node_id = node["id"]
    base = ["content", "nodes", str(index), "data"]
    if "config" in node["data"]:
        base.append("config")
    issues: list[WorkflowIssue] = []

    def field(name: str, valid: bool, description: str) -> None:
        code = "CONFIG_REQUIRED" if name not in data else "CONFIG_INVALID"
        if name not in data or not valid:
            issues.append(
                WorkflowIssue(
                    node_id,
                    [*base, name],
                    code,
                    f"{module_type} 的 {name} {description}",
                )
            )

    if module_type == "open_page":
        field("url", _nonempty_string(data.get("url")), "必须是非空字符串")
        field(
            "openMode",
            data.get("openMode") in {"new_tab", "current_tab"},
            "必须是 new_tab 或 current_tab",
        )
        field(
            "waitUntil",
            data.get("waitUntil") in {"load", "domcontentloaded", "networkidle"},
            "不受支持",
        )
    elif module_type == "input_text":
        field("selector", _nonempty_string(data.get("selector")), "必须是非空字符串")
        field("text", isinstance(data.get("text"), str) if studio else _nonempty_string(data.get("text")), "必须是字符串" if studio else "必须是非空字符串")
        field("clearBefore", type(data.get("clearBefore")) is bool, "必须是布尔值")
    elif module_type == "click_element":
        field("selector", _nonempty_string(data.get("selector")), "必须是非空字符串")
        field(
            "clickType",
            data.get("clickType") in {"single", "double", "right"},
            "必须是 single、double 或 right",
        )
        field("followNewTab", type(data.get("followNewTab")) is bool, "必须是布尔值")
    elif module_type == "get_element_info":
        field("selector", _nonempty_string(data.get("selector")), "必须是非空字符串")
        field(
            "attribute",
            _nonempty_string(data.get("attribute")),
            "必须是非空字符串",
        )
        field(
            "variableName",
            _nonempty_string(data.get("variableName")),
            "必须是非空字符串",
        )
    elif module_type == 'project_data':
        field('operation', isinstance(data.get('operation'), str) and data.get('operation') in {'inputs', 'readRecord', 'queryRecords', 'queryTableSchema', 'createRecord', 'updateRecord', 'deleteRecord', 'setRecordStatus', 'addField', 'ensureField', 'modifyField', 'previewFieldChange', 'deleteField', 'previewFieldDeletion'}, '不受支持')
        field('arguments', isinstance(data.get('arguments'), dict) and data.get('argumentsValid', True) is True, '必须是有效对象')
        field('variableName', _nonempty_string(data.get('variableName')), '必须是非空字符串')
    elif module_type == 'project_manual':
        data.setdefault('timeoutSeconds', 1800)
        field('timeoutSeconds', _nonnegative_number(data['timeoutSeconds']) and 0 < data['timeoutSeconds'] <= 86400, '必须大于 0 且不超过 86400 秒')
        field('reason', _nonempty_string(data.get('reason')), '必须是非空字符串')
    elif module_type == 'project_end':
        data.setdefault('retainEnvironment', {'enabled': False})
        retain = data.get('retainEnvironment')
        field('retainEnvironment', isinstance(retain, dict) and type(retain.get('enabled')) is bool and data.get('retentionValid', True) is True, '必须明确是否保留环境')
    elif module_type == "screenshot":
        mode = data.get("screenshotType", "fullpage")
        if mode not in {"fullpage", "viewport", "element"}:
            field("screenshotType", False, "必须是 fullpage、viewport 或 element")
        if mode == "element":
            field("selector", _nonempty_string(data.get("selector")), "必须是非空字符串")
        for name in ("savePath", "fileNamePattern", "variableName"):
            if name in data:
                field(name, isinstance(data[name], str), "必须是字符串")
    elif module_type.startswith("ai_") and data.get("modelId") is not None:
        field("modelId", isinstance(data["modelId"], str), "必须是字符串")
    if module_type in _DEFAULT_CONFIGS or 'timeout' in data:
        field("timeout", _nonnegative_number(data.get("timeout")), "必须是有限非负数")
    return issues


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _nonnegative_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        and value >= 0
    )


def _validate_lifecycle_graph(nodes, edges, ends):
    _, graph = parse_workflow({'nodes': nodes, 'edges': edges})
    forks = {identity for identity, node in graph.nodes.items() if 'parallel' in node.data.get('config', node.data)}
    for identity in forks:
        structured_fork(graph, identity)
    owns_control = any(n['data']['moduleType'] in {'project_manual', 'subflow', 'loop', 'foreach', 'foreach_dict'} for n in nodes)
    if not ends and not owns_control:
        return
    outgoing = {node['id']: [] for node in nodes}
    incoming = {node['id']: [] for node in nodes}
    for edge in edges:
        if edge['source'] in outgoing and edge['target'] in incoming:
            outgoing[edge['source']].append(edge['target'])
            incoming[edge['target']].append(edge['source'])
    # Only validated forks create isolated branch schedulers. Undeclared fan-out
    # still shares control state and cannot own loops or manual checkpoints.
    if owns_control and (
        sum(not value for value in incoming.values()) != 1 or any(
            len(outgoing[n['id']]) > 1 and n['id'] not in forks and not (n['data']['moduleType'] == 'project_manual' and n['data'].get('resumeTargets')) and (
                n['data']['moduleType'] not in {'condition', 'loop', 'foreach', 'foreach_dict'}
                or len({edge.get('sourceHandle') for edge in edges if edge['source'] == n['id']}) != len(outgoing[n['id']])
            ) for n in nodes
        )
    ):
        raise WorkflowError('WORKFLOW_NOT_RUNNABLE', '人工处理或循环节点不能与其他分支并行执行', 422)
    if not ends:
        return
    reachable = set(ends)
    while True:
        previous = set(reachable)
        reachable.update(source for target in tuple(reachable) for source in incoming[target])
        if previous == reachable:
            break
    # Loop bodies return to their owner without explicit back edges. They must
    # not contain End, which would close the browser in the first iteration.
    for node in nodes:
        if node['data']['moduleType'] not in {'loop', 'foreach', 'foreach_dict'}:
            continue
        body = [e['target'] for e in edges if e['source'] == node['id'] and e.get('sourceHandle') == 'loop']
        done = {e['target'] for e in edges if e['source'] == node['id'] and e.get('sourceHandle') != 'loop'}
        seen = {node['id'], *done}
        while body:
            current = body.pop()
            if current in seen:
                continue
            seen.add(current)
            if current in ends:
                raise WorkflowError('WORKFLOW_NOT_RUNNABLE', 'End 不能放在循环体内', 422)
            if node['id'] in reachable:
                reachable.add(current)
            body.extend(outgoing[current])
    if reachable != set(outgoing):
        raise WorkflowError('WORKFLOW_NOT_RUNNABLE', '所有执行分支必须汇合到唯一 End', 422)
