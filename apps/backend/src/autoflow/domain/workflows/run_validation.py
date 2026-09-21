"""Freeze the current WebRPA React Flow document for the PM3 worker boundary."""

import math
from dataclasses import dataclass
from typing import Any

from .canvas_subflows import CanvasSubflowGraph
from .catalog import runnable_module_types
from .graph import WorkflowDefinition
from .manual_contract import validate_declaration
from .models import WorkflowError, WorkflowIssue
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


def prepare_run(document: object) -> PreparedWorkflow:
    projected = project_document(document)
    nodes = projected["content"]["nodes"]
    graph = CanvasSubflowGraph(projected["content"])
    scopes = graph.project_scopes()
    supported = runnable_module_types()
    issues = []
    for index, node in enumerate(nodes):
        node_id = node["id"]
        module_type = node["data"]["moduleType"]
        if module_type not in supported and not graph._is_definition(node):
            issues.append(
                WorkflowIssue(
                    node_id,
                    ["content", "nodes", str(index), "data", "moduleType"],
                    "WORKFLOW_NOT_RUNNABLE",
                    f"服务端尚不支持运行节点 {module_type}",
                )
            )
    if issues:
        raise WorkflowError(
            "WORKFLOW_NOT_RUNNABLE", "工作流包含尚不可执行的节点", 422, issues
        )
    by_id = {node["id"]: node for node in nodes}
    for scope, members in scopes.items():
        subset = graph._subset(members)
        ends = [n['id'] for n in subset['nodes'] if n['data']['moduleType'] == 'project_end']
        if len(ends) > 1 or any(edge['source'] in ends for edge in subset['edges']):
            raise WorkflowError('WORKFLOW_NOT_RUNNABLE', 'End 必须是唯一的最终节点，不能有后续连线', 422)
        for node in subset['nodes']:
            if node['data']['moduleType'] == 'project_manual':
                validate_declaration(node['data'], node['id'], subset['nodes'], subset['edges'])
        _validate_lifecycle_graph(subset['nodes'], subset['edges'], ends)
        valid, errors = WorkflowDefinition.from_raw(subset).validate()
        if not valid and (members or not scope) and not all(n["data"]["moduleType"] in _DEFAULT_CONFIGS for n in nodes):
            raise WorkflowError('WORKFLOW_NOT_RUNNABLE', '；'.join(errors), 422)
    for node in nodes:
        for key, value in _DEFAULT_CONFIGS.get(node["data"]["moduleType"], {}).items():
            node["data"].setdefault(key, value)
    config_issues = [
        issue
        for index, node in enumerate(nodes)
        for issue in _config_issues(node, index)
    ]
    if config_issues:
        raise WorkflowError(
            "WORKFLOW_NOT_RUNNABLE",
            "工作流节点配置不完整或无效",
            422,
            config_issues,
        )
    if all(node['data']['moduleType'] in _DEFAULT_CONFIGS for node in nodes):
        node_ids = _ordered_chain(nodes, projected["content"]["edges"])
    else:
        node_ids = list(by_id)
    return PreparedWorkflow(
        projected,
        node_ids,
        [by_id[node_id]["data"]["moduleType"] for node_id in node_ids],
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


def _config_issues(node: dict[str, Any], index: int) -> list[WorkflowIssue]:
    data = node["data"]
    module_type = data["moduleType"]
    node_id = node["id"]
    base = ["content", "nodes", str(index), "data"]
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
        field("text", _nonempty_string(data.get("text")), "必须是非空字符串")
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
        field('operation', isinstance(data.get('operation'), str) and data.get('operation') in {'inputs', 'readRecord', 'queryRecords', 'createRecord', 'updateRecord', 'deleteRecord', 'setRecordStatus', 'addField', 'ensureField', 'modifyField', 'previewFieldChange'}, '不受支持')
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
    owns_control = any(n['data']['moduleType'] in {'project_manual', 'subflow', 'loop', 'foreach', 'foreach_dict'} for n in nodes)
    if not ends and not owns_control:
        return
    outgoing = {node['id']: [] for node in nodes}
    incoming = {node['id']: [] for node in nodes}
    for edge in edges:
        if edge['source'] in outgoing and edge['target'] in incoming:
            outgoing[edge['source']].append(edge['target'])
            incoming[edge['target']].append(edge['source'])
    # Lifecycle commands own the single browser. Exclusive conditions and loop
    # bodies are supported; concurrent roots/fan-out must first be joined.
    # ponytail: shared loop/control state cannot cross parallel branches; enable
    # this shape only after the shared Runtime isolates branch control state.
    if owns_control and (
        sum(not value for value in incoming.values()) != 1 or any(
            len(outgoing[n['id']]) > 1 and not (n['data']['moduleType'] == 'project_manual' and n['data'].get('resumeTargets')) and (
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
