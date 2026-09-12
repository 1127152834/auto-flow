from copy import deepcopy

import pytest

from autoflow.domain.workflows.models import WorkflowError
from autoflow.domain.workflows.run_validation import prepare_run, resolve_node_config
from autoflow.domain.workflows.validation import workflow_issues
from tests.fixtures.workflows import workflow_payload


def test_order_and_defaults_are_frozen_without_mutating_draft():
    payload = workflow_payload()
    payload["document"]["nodes"].reverse()
    payload["document"]["nodes"][-1]["config"] = {"url": "https://example.com"}
    before = deepcopy(payload)
    prepared = prepare_run(**payload)
    assert prepared.node_ids == [f"n{i}" for i in range(6)]
    assert prepared.document["nodes"][-1]["config"]["timeoutSeconds"] == 60
    assert payload == before


@pytest.mark.parametrize("change,code", [
    (lambda d: d["nodes"][0]["config"].update(url=""), "REQUIRED"),
    (lambda d: d["nodes"][1]["config"].update(timeoutSeconds=0), "INVALID_TIMEOUT"),
    (lambda d: d["edges"].clear(), "DISCONNECTED_NODE"),
    (lambda d: d["nodes"][2]["config"].update(text="{element_value}"), "VARIABLE_NOT_AVAILABLE"),
    (lambda d: d["nodes"][2]["config"].update(text="${user.name}"), "INVALID_REFERENCE"),
    (lambda d: d["nodes"][5]["config"].update(screenshotType="element"), "REQUIRED"),
])
def test_unrunnable_drafts_have_located_issues(change, code):
    payload = workflow_payload()
    change(payload["document"])
    with pytest.raises(WorkflowError) as caught:
        prepare_run(**payload)
    assert any(issue.code == code and issue.node_id for issue in caught.value.issues)


def test_initial_dependencies_unicode_and_single_substitution():
    payload = workflow_payload()
    payload["document"]["variables"] = [
        {"name": "网址", "type": "string", "value": "https://{host}/"},
        {"name": "host", "type": "string", "value": "example.com"},
        {"name": "flag", "type": "boolean", "value": True},
        {"name": "nested", "type": "object", "value": {"list": ["${flag}"]}},
    ]
    payload["document"]["nodes"][0]["config"]["url"] = "${网址}"
    prepared = prepare_run(**payload)
    assert prepared.variables["网址"] == "https://example.com/"
    assert prepared.variables["nested"] == {"list": ["true"]}
    node = prepared.document["nodes"][2]
    node["config"]["text"] = "{literal} ${flag} {list} {nothing}"
    config = resolve_node_config(node, {"literal": "{untouched}", "flag": False, "list": [1, "中文"], "nothing": None})
    assert config["text"] == '{untouched} false [1,"中文"] '


@pytest.mark.parametrize("variables,code", [
    ([{"name": "a", "type": "string", "value": "{b}"}, {"name": "b", "type": "string", "value": "{a}"}], "VARIABLE_DEPENDENCY_CYCLE"),
    ([{"name": "a", "type": "string", "value": "{element_value}"}], "INITIAL_VARIABLE_UNAVAILABLE"),
    ([{"name": "a", "type": "number", "value": "unfinished"}], "VARIABLE_TYPE_MISMATCH"),
])
def test_invalid_initialization_is_rejected(variables, code):
    payload = workflow_payload()
    payload["document"]["variables"] = variables
    with pytest.raises(WorkflowError) as caught:
        prepare_run(**payload)
    assert any(issue.code == code and issue.path[0] == "variables" for issue in caught.value.issues)


def test_output_reassignment_is_a_warning_and_fractional_timeout_is_kept():
    payload = workflow_payload()
    doc = payload["document"]
    doc["nodes"][5]["config"]["variableName"] = "element_value"
    doc["nodes"][5]["config"]["savePath"] = "{element_value}"
    doc["nodes"][3]["config"]["timeoutSeconds"] = 0.25
    prepared = prepare_run(**payload)
    assert len(prepared.warnings) == 2
    assert prepared.document["nodes"][3]["config"]["timeoutSeconds"] == 0.25
    assert prepared.variables == {}


def test_invalid_resolved_url_and_empty_selector_report_the_field():
    doc = workflow_payload()["document"]
    node = doc["nodes"][0]
    node["config"]["url"] = "{target}"
    with pytest.raises(WorkflowError) as caught:
        resolve_node_config(node, {"target": "file:///private/file"})
    assert caught.value.issues[0].path == ["config", "url"]
    node = doc["nodes"][1]
    node["config"]["selector"] = "{target}"
    with pytest.raises(WorkflowError) as caught:
        resolve_node_config(node, {"target": None})
    assert caught.value.issues[0].path == ["config", "selector"]


def test_two_thousand_initial_dependencies_do_not_recurse_by_variable_count():
    payload = workflow_payload()
    payload["document"]["variables"] = [
        {"name": f"v{i}", "type": "string", "value": f"{{v{i+1}}}" if i < 1999 else "end"}
        for i in range(2000)
    ]
    assert prepare_run(**payload).variables["v0"] == "end"


@pytest.mark.parametrize("screenshot_type", ["fullpage", "viewport", "element"])
@pytest.mark.parametrize("selector,code", [
    ("${removed_selector}", "UNKNOWN_VARIABLE"),
    ("${user.name}", "INVALID_REFERENCE"),
])
def test_screenshot_selector_references_only_apply_to_elements(screenshot_type, selector, code):
    payload = workflow_payload()
    screenshot = payload["document"]["nodes"][-1]
    screenshot["config"].update(screenshotType=screenshot_type, selector=selector)
    issues = workflow_issues(payload["document"])
    if screenshot_type == "element":
        assert [(issue.node_id, issue.path, issue.code) for issue in issues] == [
            (screenshot["id"], ["config", "selector"], code),
        ]
        with pytest.raises(WorkflowError):
            prepare_run(**payload)
    else:
        assert issues == []
        prepared = prepare_run(**payload)
        config = resolve_node_config(prepared.document["nodes"][-1], prepared.variables)
        assert config["selector"] == selector
