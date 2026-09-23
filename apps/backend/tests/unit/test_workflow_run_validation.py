from copy import deepcopy

import pytest

from autoflow.domain.workflows.catalog import node_catalog
from autoflow.domain.workflows.models import WorkflowError
from autoflow.domain.workflows.run_validation import prepare_run
from tests.fixtures.workflows import workflow_payload


def test_project_catalog_admits_the_five_node_studio_bridge():
    assert {item["moduleType"] for item in node_catalog() if item["runnable"]} == {
        "open_page",
        "input_text",
        "click_element",
        "get_element_info",
        "screenshot",
    }


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
    "module_type", ["wait_element", "ai_chat", "condition", "group"]
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
            "message": f"服务端尚不支持运行节点 {module_type}",
        }
    ]


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
