from copy import deepcopy

import pytest

from autoflow.domain.workflows.catalog import node_catalog
from autoflow.domain.workflows.validation import validate_structure, workflow_issues
from tests.fixtures.workflows import workflow_payload


@pytest.mark.parametrize(
    "kind,value,valid",
    [
        ("string", "", True),
        ("string", None, False),
        ("number", 0, True),
        ("number", True, False),
        ("number", 10**400, True),
        ("boolean", False, True),
        ("boolean", 0, False),
        ("array", [], True),
        ("array", {}, False),
        ("object", {}, True),
        ("object", [], False),
    ],
)
def test_draft_variable_types_are_preserved_without_coercion(kind, value, valid):
    payload = workflow_payload()
    payload["document"]["variables"] = [{"name": "value", "type": kind, "value": value}]
    before = deepcopy(payload)
    validate_structure(**payload)
    issues = workflow_issues(payload["document"])
    assert (
        not any(issue.code == "VARIABLE_TYPE_MISMATCH" for issue in issues)
    ) == valid
    assert payload == before


def test_catalog_is_independent_and_wait_timeout_is_explicit_in_one_unit():
    catalog = node_catalog()
    wait = next(item for item in catalog if item["type"] == "wait_element")
    assert wait["defaultConfig"] == {
        "selector": "",
        "waitCondition": "visible",
        "framePath": [],
        "timeoutSeconds": 60,
    }
    wait["defaultConfig"]["timeoutSeconds"] = 1
    assert node_catalog()[3]["defaultConfig"]["timeoutSeconds"] == 60
    assert next(item for item in node_catalog() if item["type"] == "screenshot")["configSchema"]["allOf"][0]["then"]["required"] == [
        "selector"
    ]


def test_empty_known_drafts_and_invalid_references_produce_repairable_issues():
    payload = workflow_payload()
    payload["document"]["nodes"][0]["config"] = {
        "url": "${missing}",
        "timeoutSeconds": True,
        "executablePath": "old.exe",
    }
    payload["document"]["nodes"][1]["config"] = {}
    payload["document"]["variables"] = [
        {"name": "invalid name", "type": "string", "value": "draft"}
    ]
    validate_structure(**payload)
    issues = workflow_issues(payload["document"])
    assert {issue.code for issue in issues} >= {
        "UNKNOWN_VARIABLE",
        "INVALID_CONFIG_TYPE",
        "UNKNOWN_CONFIG_FIELD",
        "REQUIRED",
        "INVALID_VARIABLE_NAME",
    }
    assert any(
        issue.node_id == "n1" and issue.path == ["config", "selector"]
        for issue in issues
    )


def test_json_boolean_and_number_are_distinct_for_idempotent_writes():
    from datetime import UTC, datetime

    from autoflow.domain.workflows.models import WorkflowRecord

    payload = workflow_payload()
    now = datetime.now(UTC)
    record = WorkflowRecord(payload["document"], payload["layout"], 1, now, now)
    changed = deepcopy(payload)
    changed["document"]["nodes"][1]["config"]["followNewTab"] = 0
    assert not record.matches(changed["document"], changed["layout"])


def test_chinese_references_nested_values_and_duplicate_outputs_are_diagnostics():
    payload = workflow_payload()
    doc = payload["document"]
    doc["variables"] = [
        {"name": "网址_2", "type": "string", "value": "https://example.com"},
        {"name": "嵌套", "type": "object", "value": {"items": ["${不存在}"]}},
    ]
    doc["nodes"][0]["config"]["url"] = "${网址_2}"
    doc["nodes"][4]["config"]["variableName"] = "结果"
    doc["nodes"][5]["config"]["variableName"] = "结果"
    issues = workflow_issues(doc)
    assert not any(issue.node_id == "n0" for issue in issues)
    assert any(
        issue.code == "UNKNOWN_VARIABLE"
        and issue.path == ["variables", "1", "value", "items", "0"]
        for issue in issues
    )
    assert {
        issue.node_id for issue in issues if issue.code == "DUPLICATE_OUTPUT_VARIABLE"
    } == {"n4", "n5"}
    # A rename with its references updated has no stale diagnostic.
    doc["variables"][0]["name"] = "新网址"
    doc["nodes"][0]["config"]["url"] = "{新网址}"
    assert not any(issue.node_id == "n0" for issue in workflow_issues(doc))


@pytest.mark.parametrize("name", ["1开头", "has space", "e\u0301", ""])
def test_invalid_names_follow_the_shared_unicode_letter_number_rule(name):
    doc = workflow_payload()["document"]
    doc["variables"] = [{"name": name, "type": "string", "value": ""}]
    assert any(issue.code == "INVALID_VARIABLE_NAME" for issue in workflow_issues(doc))


@pytest.mark.parametrize(
    "url", ["ftp://example.com", "https://", "https://a b", "https://@", "https://[bad"]
)
def test_obviously_invalid_literal_urls_are_saved_as_diagnostic_drafts(url):
    payload = workflow_payload()
    payload["document"]["nodes"][0]["config"]["url"] = url
    validate_structure(**payload)
    assert any(
        issue.code == "INVALID_URL" and issue.node_id == "n0"
        for issue in workflow_issues(payload["document"])
    )


def test_literal_json_in_input_text_is_not_an_invalid_variable_reference():
    doc = workflow_payload()["document"]
    doc["nodes"][2]["config"]["text"] = '{"answer": 42, "nested": {"key": "value"}}'
    assert workflow_issues(doc) == []
    doc["nodes"][2]["config"]["text"] = "{bad.name} ${bad.name}"
    assert any(issue.code == "INVALID_REFERENCE" for issue in workflow_issues(doc))
