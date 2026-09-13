from copy import deepcopy

import pytest

from autoflow.domain.workflows.catalog import node_catalog
from tests.fixtures.workflows import workflow_payload

ROOT = "/api/v1/workflows"


def test_catalog_and_openapi_have_one_explicit_editing_contract(client):
    response = client.get(f"{ROOT}/node-catalog")
    assert response.status_code == 200
    assert response.json()["items"] == node_catalog()
    assert len(response.json()["items"]) == 13
    for item in response.json()["items"]:
        assert item["runnable"] is True
        assert item["defaultConfig"]["timeoutSeconds"] == 60
        expected_ports = {'condition': ['true', 'false'], 'loop': ['body', 'done'], 'loop_end': [], 'break_loop': [], 'continue_loop': []}.get(item['type'], ['out'])
        assert item["inputPorts"] == ["in"] and item["outputPorts"] == expected_ports
        assert set(item["defaultConfig"]) == set(item["configSchema"]["properties"])
    assert (
        client.get(
            f"{ROOT}/node-catalog", headers={"x-autoflow-token": "wrong"}
        ).status_code
        == 401
    )
    schema = client.get("/openapi.json").json()
    names = {
        "WorkflowDocument",
        "WorkflowNode",
        "WorkflowEdge",
        "WorkflowVariable",
        "WorkflowLayout",
        "WorkflowRead",
        "WorkflowWrite",
        "WorkflowNodeDefinition",
        "WorkflowIssue",
        "WorkflowList",
        "WorkflowCatalog",
    }
    assert names <= schema["components"]["schemas"].keys()
    assert set(
        schema["components"]["schemas"]["WorkflowNode"]["properties"]["type"]["enum"]
    ) == {item["type"] for item in node_catalog()}
    assert not any(
        path.startswith(ROOT) and "execute" in path for path in schema["paths"]
    )


def test_save_load_update_and_retry_are_atomic_and_idempotent(client):
    payload = workflow_payload()
    created = client.post(ROOT, json=payload)
    assert created.status_code == 201
    initial = created.json()
    assert initial["document"] == payload["document"]
    assert initial["layout"] == {**payload["layout"], "breakpoints": []}
    assert initial["issues"] == []
    assert initial["revision"] == 1
    assert client.post(ROOT, json=payload).json() == initial
    endpoint = f"{ROOT}/{payload['document']['id']}"
    assert client.get(endpoint).json() == initial
    changed = deepcopy(payload)
    changed["document"]["name"] = "更新后的流程"
    changed["layout"]["nodes"]["n0"]["x"] = 123
    updated = client.put(endpoint, json={**changed, "expectedRevision": 1})
    assert updated.status_code == 200
    saved = updated.json()
    assert saved["revision"] == 2
    assert saved["createdAt"] == initial["createdAt"]
    assert saved["document"] == changed["document"]
    assert saved["layout"] == {**changed["layout"], "breakpoints": []}
    assert client.put(endpoint, json={**changed, "expectedRevision": 1}).json() == saved
    conflict = client.put(endpoint, json={**payload, "expectedRevision": 1})
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "WORKFLOW_REVISION_CONFLICT"
    assert client.post(ROOT, json=payload).status_code == 409
    assert client.get(endpoint).json() == saved
    assert client.get(ROOT).json()["items"] == [
        {
            "id": saved["document"]["id"],
            "name": "更新后的流程",
            "revision": 2,
            "updatedAt": saved["updatedAt"],
        }
    ]


def test_incomplete_invalid_config_and_variables_remain_editable_drafts(client):
    payload = workflow_payload()
    nodes = payload["document"]["nodes"]
    nodes[0]["config"]["url"] = ""
    nodes[1]["config"]["clickType"] = "invalid"
    nodes[1]["config"]["followNewTab"] = "false"
    nodes[2]["config"]["text"] = "${missing} ${bad.name}"
    nodes[3]["config"]["timeoutSeconds"] = 0
    nodes[5]["config"]["screenshotType"] = "element"
    payload["document"]["edges"] = []
    payload["document"]["variables"] = [
        {"name": "name", "type": "number", "value": "a draft"},
        {"name": "name", "type": "string", "value": "another draft"},
    ]
    response = client.post(ROOT, json=payload)
    assert response.status_code == 201
    saved = response.json()
    assert saved["document"] == payload["document"]
    assert {issue["code"] for issue in saved["issues"]} >= {
        "REQUIRED",
        "INVALID_CONFIG_VALUE",
        "INVALID_CONFIG_TYPE",
        "INVALID_TIMEOUT",
        "UNKNOWN_VARIABLE",
        "INVALID_REFERENCE",
        "DUPLICATE_VARIABLE",
        "VARIABLE_TYPE_MISMATCH",
        "DISCONNECTED_NODE",
    }
    assert any(
        issue["nodeId"] == "n5" and issue["path"] == ["config", "selector"]
        for issue in saved["issues"]
    )
    assert client.get(f"{ROOT}/{payload['document']['id']}").json() == saved


def test_empty_workflow_and_empty_input_text_are_valid_drafts(client):
    payload = workflow_payload()
    payload["document"]["nodes"] = []
    payload["document"]["edges"] = []
    payload["layout"]["nodes"] = {}
    created = client.post(ROOT, json=payload)
    assert created.status_code == 201
    assert created.json()["issues"][0]["code"] == "EMPTY_WORKFLOW"
    full = workflow_payload("d45f286f-129d-4e3b-a09b-995c3b491610")
    assert full["document"]["nodes"][2]["config"]["text"] == ""
    assert client.post(ROOT, json=full).json()["issues"] == []


def test_missing_output_variables_are_saved_with_required_issues(client):
    payload = workflow_payload()
    payload["document"]["nodes"][4]["config"]["variableName"] = ""
    payload["document"]["nodes"][5]["config"].pop("variableName")
    response = client.post(ROOT, json=payload)
    assert response.status_code == 201
    assert response.json()["document"] == payload["document"]
    assert {
        issue["nodeId"]
        for issue in response.json()["issues"]
        if issue["code"] == "REQUIRED" and issue["path"] == ["config", "variableName"]
    } == {"n4", "n5"}


@pytest.mark.parametrize("location", ["node_field", "layout_node_id"])
def test_structure_error_paths_preserve_fields_and_node_ids_named_body(
    client, location
):
    payload = workflow_payload()
    if location == "node_field":
        payload["document"]["nodes"][0]["body"] = "unexpected"
        expected_path = ["document", "nodes", "0", "body"]
    else:
        payload["document"]["nodes"][0]["id"] = "body"
        payload["document"]["edges"][0]["source"] = "body"
        positions = payload["layout"]["nodes"]
        positions["body"] = positions.pop("n0")
        positions["body"]["x"] = "invalid"
        expected_path = ["layout", "nodes", "body", "x"]
    response = client.post(ROOT, json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["details"]["issues"][0]["path"] == expected_path
    assert client.get(ROOT).json()["items"] == []


@pytest.mark.parametrize(
    "defect",
    [
        "schema",
        "boolean_schema",
        "unknown_node",
        "duplicate_node",
        "duplicate_edge",
        "self",
        "missing_target",
        "cycle",
        "branch",
        "handle",
        "layout",
        "nan",
    ],
)
def test_damaged_structures_are_rejected_without_modifying_saved_content(
    client, defect
):
    payload = workflow_payload()
    before = client.post(ROOT, json=payload).json()
    broken = deepcopy(payload)
    doc = broken["document"]
    if defect == "schema":
        doc["schemaVersion"] = 3
    elif defect == "boolean_schema":
        doc["schemaVersion"] = True
    elif defect == "unknown_node":
        doc["nodes"][0]["type"] = "run_script"
    elif defect == "duplicate_node":
        doc["nodes"].append(doc["nodes"][0])
    elif defect == "duplicate_edge":
        doc["edges"].append(doc["edges"][0])
    elif defect == "self":
        doc["edges"][0]["target"] = "n0"
    elif defect == "missing_target":
        doc["edges"][0]["target"] = "ghost"
    elif defect == "cycle":
        doc["edges"].append(
            {
                "id": "back",
                "source": "n5",
                "target": "n0",
                "sourceHandle": "out",
                "targetHandle": "in",
            }
        )
    elif defect == "branch":
        doc["edges"].append(
            {
                "id": "branch",
                "source": "n0",
                "target": "n5",
                "sourceHandle": "out",
                "targetHandle": "in",
            }
        )
    elif defect == "handle":
        doc["edges"][0]["sourceHandle"] = "error"
    elif defect == "layout":
        broken["layout"]["nodes"].pop("n0")
    else:
        broken["layout"]["viewport"]["zoom"] = "NaN"
    endpoint = f"{ROOT}/{doc['id']}"
    response = client.put(endpoint, json={**broken, "expectedRevision": 1})
    assert response.status_code == 422
    assert response.json()["error"]["details"]["issues"]
    assert client.get(endpoint).json() == before


def test_missing_id_wrong_id_and_quiesce_return_expected_errors(client):
    payload = workflow_payload()
    assert client.get(f"{ROOT}/{payload['document']['id']}").status_code == 404
    assert (
        client.put(
            f"{ROOT}/{payload['document']['id']}",
            json={**payload, "expectedRevision": 1},
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"{ROOT}/wrong-id", json={**payload, "expectedRevision": 1}
        ).status_code
        == 422
    )
    client.app.state.settings_runtime.gate.pause(list)
    response = client.post(ROOT, json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SERVICE_QUIESCED"
    assert client.get(ROOT).json()["items"] == []
