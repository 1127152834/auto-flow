from copy import deepcopy

import pytest

from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.domain.workflows.catalog import node_catalog
from autoflow.domain.workflows.models import WorkflowError
from autoflow.domain.workflows.run_validation import prepare_run
from autoflow.domain.workflows.scope import APPROVED_NODE_TYPES
from tests.fixtures.workflows import workflow_payload


def test_project_catalog_admits_studio_browser_data_and_managed_ai_nodes():
    runnable = {item["moduleType"] for item in node_catalog() if item["runnable"]}
    assert {
        "open_page",
        "input_text",
        "click_element",
        "get_element_info",
        "condition", "loop", "foreach", "foreach_dict", "break_loop",
        "continue_loop", "set_variable", "subflow", "project_data", "project_end", "project_manual",
        "screenshot",
        "list_reverse",
        "dict_merge",
    } <= runnable
    assert {"ai_chat", "ai_extract", "ai_generate_image", "ai_vision_act"} <= runnable
    assert "notification" not in runnable


def test_project_ai_catalog_matches_approved_scope_and_real_executors():
    project_ai = {
        item["moduleType"] for item in node_catalog()
        if item["moduleType"].startswith("ai_")
    }
    assert project_ai == {node for node in APPROVED_NODE_TYPES if node.startswith("ai_")}
    registry = build_production_executor_registry()
    assert all(registry.get(module_type) is not None for module_type in project_ai)


def test_prepared_document_is_projected_and_deeply_frozen_from_input_mutation():
    payload = workflow_payload()
    payload["content"]["nodes"] = list(reversed(payload["content"]["nodes"]))
    prepared = prepare_run(payload)
    payload["content"]["nodes"][3]["data"]["url"] = "https://changed.test/"
    open_node = next(
        node for node in prepared.document["content"]["nodes"] if node["id"] == "open"
    )
    assert open_node["data"]["url"] == (
        "https://example.test/"
    )
    assert prepared.node_ids == ["open", "input", "click", "read"]


def test_prepare_applies_frozen_ui_fallbacks_without_overwriting_values():
    payload = workflow_payload()
    for node in payload["content"]["nodes"]:
        data = node["data"]
        for key in (
            "openMode",
            "waitUntil",
            "timeout",
            "clickType",
            "followNewTab",
            "clearBefore",
            "attribute",
            "variableName",
        ):
            data.pop(key, None)
    prepared = prepare_run(payload)
    by_id = {node["id"]: node["data"] for node in prepared.document["content"]["nodes"]}
    assert {key: by_id["open"][key] for key in ("openMode", "waitUntil", "timeout")} == {
        "openMode": "new_tab",
        "waitUntil": "load",
        "timeout": 60,
    }
    assert {
        key: by_id["click"][key]
        for key in ("clickType", "followNewTab", "timeout")
    } == {
        "clickType": "single",
        "followNewTab": False,
        "timeout": 60,
    }
    assert {key: by_id["input"][key] for key in ("clearBefore", "timeout")} == {
        "clearBefore": True,
        "timeout": 60,
    }
    assert {
        key: by_id["read"][key]
        for key in ("attribute", "variableName", "timeout")
    } == {
        "attribute": "text",
        "variableName": "element_value",
        "timeout": 60,
    }

    overridden = workflow_payload()
    overridden["content"]["nodes"][0]["data"]["openMode"] = "current_tab"
    assert prepare_run(overridden).document["content"]["nodes"][0]["data"][
        "openMode"
    ] == "current_tab"


@pytest.mark.parametrize(
    ("node_id", "field"),
    [
        ("open", "url"),
        ("input", "selector"),
        ("input", "text"),
        ("click", "selector"),
        ("read", "selector"),
    ],
)
def test_prepare_requires_each_worker_input(node_id, field):
    payload = workflow_payload()
    node = next(node for node in payload["content"]["nodes"] if node["id"] == node_id)
    node["data"].pop(field, None)
    with pytest.raises(WorkflowError) as caught:
        prepare_run(payload)
    issue = caught.value.details["issues"][0]
    assert caught.value.code == "WORKFLOW_NOT_RUNNABLE"
    assert issue["nodeId"] == node_id
    assert issue["path"][-1] == field
    assert issue["code"] == "CONFIG_REQUIRED"


@pytest.mark.parametrize(
    ("node_id", "field", "value"),
    [
        ("open", "url", " "),
        ("open", "openMode", "popup"),
        ("open", "waitUntil", "ready"),
        ("open", "timeout", -0.5),
        ("input", "selector", 1),
        ("input", "text", []),
        ("input", "text", ""),
        ("input", "clearBefore", 1),
        ("input", "timeout", False),
        ("click", "selector", ""),
        ("click", "clickType", "triple"),
        ("click", "followNewTab", 0),
        ("click", "timeout", -1),
        ("read", "selector", None),
        ("read", "attribute", ""),
        ("read", "attribute", 1),
        ("read", "variableName", ""),
        ("read", "timeout", "60"),
    ],
)
def test_prepare_rejects_invalid_worker_configuration(node_id, field, value):
    payload = workflow_payload()
    node = next(node for node in payload["content"]["nodes"] if node["id"] == node_id)
    node["data"][field] = value
    with pytest.raises(WorkflowError) as caught:
        prepare_run(payload)
    issue = caught.value.details["issues"][0]
    assert caught.value.code == "WORKFLOW_NOT_RUNNABLE"
    assert issue["nodeId"] == node_id
    assert issue["path"][-1] == field
    assert issue["code"] == "CONFIG_INVALID"


@pytest.mark.parametrize("attribute", ["attributes", "custom", "data-testid"])
def test_prepare_accepts_any_nonempty_element_attribute(attribute):
    payload = workflow_payload()
    payload["content"]["nodes"][3]["data"]["attribute"] = attribute
    prepared = prepare_run(payload)
    assert prepared.document["content"]["nodes"][3]["data"]["attribute"] == attribute


def test_prepare_accepts_zero_timeout_as_no_limit_for_every_worker_node():
    payload = workflow_payload()
    for node in payload["content"]["nodes"]:
        node["data"]["timeout"] = 0
    prepared = prepare_run(payload)
    assert [node["data"]["timeout"] for node in prepared.document["content"]["nodes"]] == [
        0,
        0,
        0,
        0,
    ]


@pytest.mark.parametrize(
    "module_type", ["future_node", "group"]
)
def test_unimplemented_or_unknown_module_can_be_saved_but_not_run(module_type):
    payload = workflow_payload()
    payload["content"]["nodes"][0]["type"] = module_type
    payload["content"]["nodes"][0]["data"]["moduleType"] = module_type
    with pytest.raises(WorkflowError) as caught:
        prepare_run(payload)
    assert caught.value.code == "WORKFLOW_NOT_RUNNABLE"
    assert caught.value.details["issues"] == [
        {
            "nodeId": "open",
            "path": ["content", "nodes", "0", "data", "moduleType"],
            "code": "WORKFLOW_NOT_RUNNABLE",
            "message": "展示节点不能接入执行链" if module_type == "group" else f"服务端尚不支持运行节点 {module_type}",
        }
    ]


def test_migrated_list_export_is_admitted_with_its_real_fields():
    payload = workflow_payload()
    payload["content"]["nodes"] = [{
        "id": "export", "type": "list_export", "position": {"x": 0, "y": 0},
        "data": {"moduleType": "list_export", "listVariable": "items", "outputPath": "exports/items.txt"},
    }]
    payload["content"]["edges"] = []
    payload["content"]["variables"] = [{"name": "items", "type": "array", "value": ["甲"], "scope": "global"}]
    prepared = prepare_run(payload)
    assert prepared.document["content"]["nodes"] == payload["content"]["nodes"]
    assert prepared.document["content"]["variables"] == payload["content"]["variables"]


def test_visual_only_graph_cannot_start_project_run():
    payload = workflow_payload()
    payload["content"]["schemaVersion"] = 3
    payload["content"]["nodes"] = [
        {"id": "visual", "type": "group", "position": {"x": 0, "y": 0},
         "data": {"moduleType": "group", "isSubflow": True}}
    ]
    payload["content"]["edges"] = []
    with pytest.raises(WorkflowError) as caught:
        prepare_run(payload)
    assert caught.value.code == "WORKFLOW_NOT_RUNNABLE"
    assert str(caught.value) == "工作流没有可执行节点"


def test_condition_without_branch_remains_unrunnable():
    payload = workflow_payload()
    payload["content"]["nodes"][0]["type"] = "condition"
    payload["content"]["nodes"][0]["data"]["moduleType"] = "condition"
    with pytest.raises(WorkflowError) as caught:
        prepare_run(payload)
    assert caught.value.details["issues"][0]["code"] == "INVALID_EXECUTION_GRAPH"


def test_frontend_node_type_cannot_impersonate_a_runnable_module():
    payload = workflow_payload()
    payload["content"]["nodes"][0]["type"] = "open_page"
    payload["content"]["nodes"][0]["data"]["moduleType"] = "ai_chat"
    with pytest.raises(WorkflowError) as caught:
        prepare_run(payload)
    assert caught.value.code == "WORKFLOW_INVALID"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["content"]["edges"].pop(),
        lambda payload: payload["content"]["edges"].append(
            {
                "id": "branch",
                "source": "open",
                "target": "click",
                "sourceHandle": "out",
                "targetHandle": "in",
            }
        ),
        lambda payload: payload["content"]["edges"].append(
            {
                "id": "merge",
                "source": "open",
                "target": "read",
                "sourceHandle": "out",
                "targetHandle": "in",
            }
        ),
        lambda payload: payload["content"]["edges"].append(
            {
                "id": "cycle",
                "source": "read",
                "target": "open",
                "sourceHandle": "out",
                "targetHandle": "in",
            }
        ),
        lambda payload: payload["content"]["edges"].append(
            {
                "id": "self",
                "source": "open",
                "target": "open",
                "sourceHandle": "out",
                "targetHandle": "in",
            }
        ),
        lambda payload: payload["content"]["edges"].append(
            {
                **payload["content"]["edges"][0],
                "id": "duplicate-route",
            }
        ),
    ],
    ids=["disconnected", "branch", "merge", "cycle", "self-loop", "duplicate-edge"],
)
def test_prepare_rejects_any_graph_that_is_not_one_complete_chain(mutate):
    payload = workflow_payload()
    mutate(payload)
    with pytest.raises(WorkflowError) as caught:
        prepare_run(payload)
    assert caught.value.code == "WORKFLOW_NOT_RUNNABLE"
    assert caught.value.details["issues"][0]["code"] == "INVALID_EXECUTION_CHAIN"


@pytest.mark.parametrize("source_handle", ["true", "false", "error", "loop"])
def test_prepare_rejects_branch_ports_even_when_edges_form_one_chain(source_handle):
    payload = workflow_payload()
    payload["content"]["edges"][0]["sourceHandle"] = source_handle
    with pytest.raises(WorkflowError) as caught:
        prepare_run(payload)
    assert caught.value.code == "WORKFLOW_NOT_RUNNABLE"
    assert caught.value.details["issues"][0]["code"] == "INVALID_EXECUTION_CHAIN"


def test_prepare_rejects_non_finite_configuration_values():
    payload = deepcopy(workflow_payload())
    payload["content"]["nodes"][0]["data"]["timeout"] = float("nan")
    with pytest.raises(WorkflowError) as caught:
        prepare_run(payload)
    assert caught.value.code == "WORKFLOW_INVALID"


def test_prepare_project_graph_preserves_branch_edges_and_capability_config():
    payload = workflow_payload()
    template = payload['content']['nodes'][0]
    payload['content']['nodes'] = [
        {**deepcopy(template), 'id': 'branch', 'type': 'condition', 'data': {'moduleType': 'condition', 'leftValue': 1, 'rightValue': 1}},
        {**deepcopy(template), 'id': 'inputs', 'type': 'project_data', 'data': {'moduleType': 'project_data', 'operation': 'inputs', 'arguments': {}, 'variableName': 'inputs'}},
    ]
    payload['content']['edges'] = [{'id': 'route', 'source': 'branch', 'target': 'inputs', 'sourceHandle': 'true'}]
    prepared = prepare_run(payload)
    assert prepared.node_ids == ['branch', 'inputs']
    assert prepared.document['content']['edges'] == payload['content']['edges']


@pytest.mark.parametrize('case', ['parallel-end', 'parallel-manual', 'end-in-loop'])
def test_project_lifecycle_rejects_unsafe_graph_ownership(case):
    payload = workflow_payload()
    nodes, edges = payload['content']['nodes'], payload['content']['edges']
    kind = 'project_manual' if case == 'parallel-manual' else 'project_end'
    nodes.append({'id': 'lifecycle', 'type': kind, 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': kind, 'reason': '确认'}})
    if case == 'parallel-end':
        edges.append({'id': 'early-end', 'source': 'open', 'target': 'lifecycle'})
    elif case == 'parallel-manual':
        edges.append({'id': 'early-manual', 'source': 'open', 'target': 'lifecycle'})
    else:
        nodes.append({'id': 'loop', 'type': 'loop', 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': 'loop', 'count': 2}})
        edges.extend([{'id': 'loop-start', 'source': 'read', 'target': 'loop'}, {'id': 'loop-end', 'source': 'loop', 'target': 'lifecycle', 'sourceHandle': 'loop'}])
    with pytest.raises(WorkflowError):
        prepare_run(payload)


@pytest.mark.parametrize('with_end', [False, True])
def test_parallel_loop_graph_is_rejected_before_side_effects(with_end):
    payload = workflow_payload()
    payload['content']['nodes'] = [
        {'id': identity, 'type': 'loop', 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': 'loop', 'count': count}}
        for identity, count in [('left', 2), ('right', 5)]
    ]
    payload['content']['edges'] = []
    if with_end:
        payload['content']['nodes'].append({'id': 'end', 'type': 'project_end', 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': 'project_end'}})
        payload['content']['edges'] = [{'id': identity, 'source': identity, 'target': 'end', 'sourceHandle': 'done'} for identity in ('left', 'right')]
    with pytest.raises(WorkflowError, match='并行'):
        prepare_run(payload)


def subflow_payload():
    payload = workflow_payload()
    def n(identity, kind, **data):
        return {'id': identity, 'type': kind, 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': kind, **data}}
    payload['content']['nodes'] = [n('call', 'subflow', subflowGroupId='child', inputs={'value': 'frozen'}, outputs={'answer': 'result'}), n('child', 'subflow_header', subflowName='child'), n('write', 'set_variable', variableName='answer', variableValue='{value}'), n('end', 'project_end')]
    payload['content']['edges'] = [{'id': 'root', 'source': 'call', 'target': 'end'}, {'id': 'body', 'source': 'child', 'target': 'write'}]
    return payload


def test_prepare_freezes_dependency_body_and_rejects_missing_cycle_and_child_end():
    payload = subflow_payload()
    prepared = prepare_run(payload)
    payload['content']['nodes'][2]['data']['variableValue'] = 'changed'
    assert prepared.document['content']['nodes'][2]['data']['variableValue'] == '{value}'
    for mutation, message in [('missing', '找不到'), ('cycle', '循环引用'), ('end', '子流程')]:
        payload = subflow_payload()
        if mutation == 'missing': payload['content']['nodes'][0]['data']['subflowGroupId'] = 'missing'
        elif mutation == 'cycle': payload['content']['nodes'][2].update(type='subflow', data={'moduleType': 'subflow', 'subflowGroupId': 'child', 'inputs': {}, 'outputs': {}})
        else: payload['content']['nodes'][2].update(type='project_end', data={'moduleType': 'project_end'})
        with pytest.raises(WorkflowError, match=message): prepare_run(payload)


@pytest.mark.parametrize('change', ['undeclared', 'duplicate-output', 'overlap', 'cross-edge'])
def test_prepare_rejects_ambiguous_or_undeclared_subflow_boundaries(change):
    payload = subflow_payload()
    if change == 'undeclared': del payload['content']['nodes'][0]['data']['inputs']
    elif change == 'duplicate-output': payload['content']['nodes'][0]['data']['outputs'] = {'one': 'same', 'two': 'same'}
    elif change == 'cross-edge': payload['content']['edges'].append({'id': 'escape', 'source': 'call', 'target': 'write'})
    else:
        header = deepcopy(payload['content']['nodes'][1]); header['id'] = 'other'; header['data']['subflowName'] = 'other'
        payload['content']['nodes'].append(header)
        payload['content']['edges'].append({'id': 'other', 'source': 'other', 'target': 'write'})
    with pytest.raises(WorkflowError): prepare_run(payload)


def test_prepare_limits_nested_call_depth_with_call_path():
    payload = subflow_payload()
    prototype = payload['content']['nodes'][0]
    nodes = [deepcopy(prototype)]
    nodes[0]['data']['subflowGroupId'] = 'child-0'
    edges = []
    for index in range(33):
        header = deepcopy(payload['content']['nodes'][1]); header['id'] = f'child-{index}'; header['data']['subflowName'] = str(index)
        body = deepcopy(prototype if index < 32 else payload['content']['nodes'][2]); body['id'] = f'body-{index}'
        if index < 32: body['data']['subflowGroupId'] = f'child-{index + 1}'
        nodes.extend([header, body]); edges.append({'id': str(index), 'source': header['id'], 'target': body['id']})
    payload['content'].update(nodes=nodes, edges=edges)
    with pytest.raises(WorkflowError, match='嵌套层数过深.*call.*child-32'): prepare_run(payload)


@pytest.mark.parametrize('bad', ['reserved-input', 'wrong-type', 'end-target', 'past-target', 'missing-target-declaration'])
@pytest.mark.parametrize('nested', [False, True])
def test_prepare_rejects_unsafe_manual_declarations_before_checkpoint(bad, nested):
    payload = subflow_payload()
    payload['content']['nodes'] = [n for n in payload['content']['nodes'] if n['id'] in {'call', 'end'}]
    manual = payload['content']['nodes'][0]
    manual.update(type='project_manual', data={'moduleType': 'project_manual', 'reason': 'check', 'inputSchema': [{'name': 'code', 'type': 'string'}], 'resumeTargets': []})
    payload['content']['edges'] = [{'id': 'end', 'source': 'call', 'target': 'end'}]
    if bad == 'reserved-input': manual['data']['inputSchema'][0]['name'] = 'executionGeneration'
    elif bad == 'wrong-type': manual['data']['inputSchema'][0]['type'] = {}
    elif bad == 'end-target': manual['data']['resumeTargets'] = [{'nodeId': 'end'}]
    elif bad == 'past-target': manual['data']['resumeTargets'] = [{'nodeId': 'call'}]
    else:
        other = deepcopy(manual); other.update(id='other', type='set_variable', data={'moduleType': 'set_variable', 'variableName': 'x', 'variableValue': 1})
        payload['content']['nodes'].append(other)
        payload['content']['edges'].extend([{'id': 'other', 'source': 'call', 'target': 'other'}, {'id': 'other-end', 'source': 'other', 'target': 'end'}])
    if nested:
        manual['data'] = {'moduleType': 'project_manual', 'reason': 'outer', 'config': {key: value for key, value in manual['data'].items() if key != 'moduleType'}}
    with pytest.raises(WorkflowError): prepare_run(payload)


def parallel_payload():
    payload = workflow_payload()
    def n(identity, kind, **data):
        return {'id': identity, 'type': kind, 'position': {'x': 0, 'y': 0}, 'data': {'moduleType': kind, **data}}
    payload['content'] = {**payload['content'], 'nodes': [n('fork', 'set_variable', variableName='start', variableValue='yes', parallel={'joinNodeId': 'join', 'outputs': {}}), n('left', 'project_manual', reason='left'), n('right', 'loop', count=2), n('body', 'set_variable', variableName='x', variableValue='yes'), n('join', 'set_variable', variableName='done', variableValue='yes'), n('end', 'project_end')], 'edges': [{'id': str(i), **edge} for i, edge in enumerate([{'source': 'fork', 'target': 'left'}, {'source': 'fork', 'target': 'right'}, {'source': 'left', 'target': 'join'}, {'source': 'right', 'target': 'body', 'sourceHandle': 'loop'}, {'source': 'right', 'target': 'join', 'sourceHandle': 'done'}, {'source': 'join', 'target': 'end'}])]}
    return payload


def test_prepare_accepts_only_declared_disjoint_parallel_control_scopes():
    assert prepare_run(parallel_payload()).node_ids == ['fork', 'left', 'right', 'body', 'join', 'end']


@pytest.mark.parametrize('mutation', ['collision', 'cross-edge', 'missing-join', 'branch-end', 'escape', 'wrong-fork', 'external-join'])
def test_prepare_rejects_unsafe_structured_parallel_shapes(mutation):
    payload = parallel_payload()
    nodes, edges = payload['content']['nodes'], payload['content']['edges']
    if mutation == 'collision': nodes[0]['data']['parallel']['outputs'] = {'left': {'x': 'same'}, 'right': {'y': 'same'}}
    elif mutation == 'cross-edge': edges.append({'id': 'cross', 'source': 'left', 'target': 'body'})
    elif mutation == 'missing-join': nodes[0]['data']['parallel']['joinNodeId'] = 'missing'
    elif mutation == 'branch-end': nodes[1].update(type='project_end', data={'moduleType': 'project_end'})
    elif mutation == 'external-join': edges.append({'id': 'external', 'source': 'fork', 'target': 'join'})
    elif mutation == 'escape': edges[:] = [e for e in edges if e['source'] != 'left']
    else: nodes[0].update(type='project_manual', data={**nodes[0]['data'], 'moduleType': 'project_manual', 'reason': 'wrong'})
    with pytest.raises(WorkflowError): prepare_run(payload)


@pytest.mark.parametrize("mode", ["fullpage", "viewport", "element"])
def test_screenshot_modes_are_admitted_with_valid_config(mode):
    payload = workflow_payload()
    node = payload["content"]["nodes"][3]
    node["type"] = node["data"]["moduleType"] = "screenshot"
    node["data"]["screenshotType"] = mode
    prepared = prepare_run(payload)
    assert prepared.graph_adapter
    assert prepared.document == payload


@pytest.mark.parametrize("config", [{"screenshotType": "invalid"}, {"screenshotType": "element"}, {"savePath": 42}])
def test_screenshot_invalid_config_is_not_hidden_by_defaults(config):
    payload = workflow_payload()
    node = payload["content"]["nodes"][3]
    node.update(type="screenshot", data={"moduleType": "screenshot", **config})
    with pytest.raises(WorkflowError) as caught:
        prepare_run(payload)
    assert caught.value.details["issues"][0]["nodeId"] == "read"


def test_studio_nested_config_empty_input_and_snapshot_preserved():
    payload = workflow_payload()
    payload["content"]["schemaVersion"] = 3
    for node in payload["content"]["nodes"]:
        kind = node["data"]["moduleType"]
        node["data"] = {"moduleType": kind, "config": node["data"]}
        if kind == "input_text":
            node["data"]["config"]["text"] = ""
    prepared = prepare_run(payload)
    assert prepared.graph_adapter
    assert prepared.document == payload


def test_project_prepare_preserves_condition_and_loop_graph():
    payload = workflow_payload()
    payload["content"]["schemaVersion"] = 3
    payload["content"]["nodes"] = [
        {
            "id": node_id,
            "type": module_type,
            "position": {"x": index * 150, "y": 0},
            "data": {"moduleType": module_type, "config": config},
        }
        for index, (node_id, module_type, config) in enumerate(
            [
                ("gate", "condition", {"conditionType": "boolean", "leftValue": True}),
                ("repeat", "loop", {"loopType": "count", "loopCount": 3}),
                ("body", "set_variable", {"variableName": "last", "variableValue": "{index}"}),
                ("done", "set_variable", {"variableName": "finished", "variableValue": "完成"}),
                ("skipped", "set_variable", {"variableName": "skipped", "variableValue": "跳过"}),
            ]
        )
    ]
    payload["content"]["edges"] = [
        {"id": "gate-true", "source": "gate", "sourceHandle": "true", "target": "repeat"},
        {"id": "gate-false", "source": "gate", "sourceHandle": "false", "target": "skipped"},
        {"id": "loop-body", "source": "repeat", "sourceHandle": "loop", "target": "body"},
        {"id": "loop-done", "source": "repeat", "sourceHandle": "done", "target": "done"},
    ]
    prepared = prepare_run(payload)
    assert prepared.graph_adapter
    assert prepared.node_ids == ["gate", "repeat", "body", "done", "skipped"]
    assert prepared.document == payload


def test_project_control_catalog_reuses_approved_executors():
    control = {
        "condition", "loop", "foreach", "foreach_dict", "infinite_loop",
        "break_loop", "continue_loop", "set_variable", "increment_decrement",
    }
    runnable = {item["moduleType"] for item in node_catalog()}
    registry = build_production_executor_registry()
    assert control <= APPROVED_NODE_TYPES & runnable
    assert all(registry.get(module_type) is not None for module_type in control)


def test_project_graph_rejects_cycle_without_an_entry():
    payload = workflow_payload()
    payload["content"]["schemaVersion"] = 3
    payload["content"]["nodes"] = [
        {
            "id": name, "type": "set_variable", "position": {"x": index, "y": 0},
            "data": {"moduleType": "set_variable", "config": {"variableName": name, "variableValue": "1"}},
        }
        for index, name in enumerate(("a", "b"))
    ]
    payload["content"]["edges"] = [
        {"id": "ab", "source": "a", "target": "b"},
        {"id": "ba", "source": "b", "target": "a"},
    ]
    with pytest.raises(WorkflowError) as caught:
        prepare_run(payload)
    assert caught.value.details["issues"][0]["code"] == "INVALID_EXECUTION_GRAPH"
