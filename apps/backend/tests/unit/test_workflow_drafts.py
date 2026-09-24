from copy import deepcopy
from datetime import UTC, datetime

import pytest

from autoflow.domain.workflows.models import WorkflowError, WorkflowRecord
from autoflow.domain.workflows.validation import project_document
from tests.fixtures.workflows import (
    grouped_payload,
    transient_payload,
    workflow_payload,
)

SENSITIVE_FIELDS = (
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
)


def test_source_document_projection_preserves_editor_graph_and_removes_runtime_state():
    projected = project_document(transient_payload())
    assert projected["source"] == {
        "product": "WebRPA",
        "commit": "5ccb900e8dcf1530aae66f676d87593c416c7ebb",
    }
    assert projected["format"] == {"kind": "webrpa-workflow", "version": 1}
    first = projected["content"]["nodes"][0]
    assert first["type"] == "open_page"
    assert first["data"]["moduleType"] == "open_page"
    assert first["position"] == {"x": 100, "y": 80}
    assert first["style"] == {"width": 220, "height": 72}
    assert (first["width"], first["height"]) == (220, 72)
    assert not {
        "selected",
        "dragging",
        "resizing",
        "measured",
        "dimensions",
    } & first.keys()
    assert not {"isHighlighted", "__aiSpawning"} & first["data"].keys()
    assert "selected" not in projected["content"]["edges"][0]
    assert "createdAt" not in projected["content"]
    assert "updatedAt" not in projected["content"]


def test_group_geometry_and_port_identity_survive_projection():
    projected = project_document(grouped_payload())
    group, child = projected["content"]["nodes"]
    assert group["style"] == {"width": 480, "height": 300}
    assert (group["width"], group["height"]) == (480, 300)
    assert "dimensions" not in group
    assert child["parentId"] == "group"
    assert child["extent"] == "parent"
    edge = project_document(workflow_payload())["content"]["edges"][0]
    assert (edge["sourceHandle"], edge["targetHandle"]) == (None, None)
    assert projected["content"]["variables"][0]["builtin"] is False


def test_unknown_nested_configuration_is_preserved_without_a_second_wire_schema():
    payload = workflow_payload()
    payload["content"]["nodes"][0]["data"]["futureConfig"] = {
        "mode": "new",
        "items": [{"enabled": True}],
    }
    projected = project_document(payload)
    assert projected["content"]["nodes"][0]["data"]["futureConfig"] == {
        "mode": "new",
        "items": [{"enabled": True}],
    }


def test_current_text_read_output_field_survives_projection():
    projected = project_document(workflow_payload())
    assert projected["content"]["nodes"][3]["data"]["variableName"] == "结果"
    assert "resultVariable" not in projected["content"]["nodes"][3]["data"]


@pytest.mark.parametrize("secret", SENSITIVE_FIELDS)
def test_known_secret_fields_are_rejected_at_any_configuration_depth(secret):
    payload = workflow_payload()
    payload["content"]["nodes"][0]["data"]["nested"] = {
        "credentials": {secret: "must-not-persist"}
    }
    with pytest.raises(WorkflowError) as caught:
        project_document(payload)
    assert caught.value.code == "WORKFLOW_INVALID"
    assert caught.value.details["issues"] == [
        {
            "nodeId": "open",
            "path": [
                "content",
                "nodes",
                "0",
                "data",
                "nested",
                "credentials",
                secret,
            ],
            "code": "SECRET_FIELD_FORBIDDEN",
            "message": f"工作流文档不能保存密钥字段 {secret}",
        }
    ]


def test_empty_ui_secret_placeholders_are_removed_instead_of_persisted():
    payload = workflow_payload()
    payload["content"]["nodes"][0]["data"]["credentials"] = {
        **{field: "" for field in SENSITIVE_FIELDS},
        "account": "kept",
    }
    projected = project_document(payload)
    assert projected["content"]["nodes"][0]["data"]["credentials"] == {
        "account": "kept"
    }


def test_secret_field_preserves_only_an_exact_managed_credential_reference():
    payload = workflow_payload()
    payload["content"]["nodes"][0]["data"]["config"] = {
        "password": "{{cred:SSH测试.password}}"
    }
    projected = project_document(payload)
    assert projected["content"]["nodes"][0]["data"]["config"]["password"] == "{{cred:SSH测试.password}}"
    payload["content"]["nodes"][0]["data"]["config"]["password"] += "extra"
    with pytest.raises(WorkflowError) as caught:
        project_document(payload)
    assert caught.value.details["issues"][0]["code"] == "SECRET_FIELD_FORBIDDEN"


def test_sensitive_variable_value_keys_and_credential_variable_names_are_rejected():
    nested = workflow_payload()
    nested["content"]["variables"][0]["value"] = {
        "connection": {"access_token": "must-not-persist"}
    }
    with pytest.raises(WorkflowError) as caught:
        project_document(nested)
    assert caught.value.details["issues"][0] == {
        "nodeId": None,
        "path": ["content", "variables", "0", "value", "connection", "access_token"],
        "code": "SECRET_FIELD_FORBIDDEN",
        "message": "工作流文档不能保存密钥字段 access_token",
    }
    assert "must-not-persist" not in str(caught.value.details)

    named = workflow_payload()
    named["content"]["variables"][0].update(
        name="apiKey", value="must-not-persist"
    )
    with pytest.raises(WorkflowError) as caught:
        project_document(named)
    assert caught.value.details["issues"][0]["path"] == [
        "content",
        "variables",
        "0",
        "value",
    ]
    assert "must-not-persist" not in str(caught.value.details)


def test_business_variable_named_token_is_not_treated_as_a_credential_field():
    payload = workflow_payload()
    payload["content"]["variables"][0].update(name="token", value="page-2")
    projected = project_document(payload)
    assert projected["content"]["variables"][0]["value"] == "page-2"


@pytest.mark.parametrize(
    ("node_type", "module_type"),
    [("click_element", "input_text"), ("group", "open_page")],
)
def test_exported_node_type_must_agree_with_module_type(node_type, module_type):
    payload = workflow_payload()
    payload["content"]["nodes"][0]["type"] = node_type
    payload["content"]["nodes"][0]["data"]["moduleType"] = module_type
    with pytest.raises(WorkflowError) as caught:
        project_document(payload)
    assert caught.value.code == "WORKFLOW_INVALID"
    assert caught.value.details["issues"][0]["code"] == "MODULE_TYPE_MISMATCH"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_json_is_rejected(value):
    payload = workflow_payload()
    payload["content"]["nodes"][0]["position"]["x"] = value
    with pytest.raises(WorkflowError) as caught:
        project_document(payload)
    assert caught.value.code == "WORKFLOW_INVALID"
    assert caught.value.details["issues"][0]["code"] == "INVALID_JSON"


def test_boolean_and_number_are_distinct_in_projected_document_matches():
    document = project_document(workflow_payload())
    now = datetime.now(UTC)
    record = WorkflowRecord(document, 1, now, now)
    changed = deepcopy(document)
    changed["content"]["nodes"][1]["data"]["clearBefore"] = 1
    assert not record.matches(changed)


def test_legacy_m1_document_is_not_accepted_as_current_source_format():
    with pytest.raises(WorkflowError) as caught:
        project_document(
            {
                "id": workflow_payload()["id"],
                "name": "旧格式",
                "schemaVersion": 2,
                "nodes": [],
                "edges": [],
                "variables": [],
                "layout": {},
            }
        )
    assert caught.value.code == "WORKFLOW_INVALID"
