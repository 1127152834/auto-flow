"""Aggregate schema routes use the real application, auth and operation query."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from autoflow.adapters.http.project_data_schema_schemas import DataSchemaIssue
from autoflow.infrastructure.database.models import ProjectRow
from autoflow.infrastructure.database.project_data_models import DataImpactRow
from tests.contract.test_project_data_catalog import catalog as catalog  # noqa: PLC0414
from tests.contract.test_project_data_catalog import key


def candidate(table):
    return {
        "datasetGeneration": table["datasetGeneration"],
        "expectedTableRevision": 1,
        "fields": [
            {
                "kind": "new",
                "clientId": str(uuid4()),
                "definition": {
                    "key": "title",
                    "name": "标题",
                    "type": "string",
                    "required": False,
                    "validation": {},
                },
                "sourceColumnPolicy": "localOnly",
            }
        ],
    }


def test_active_task_schema_issue_keeps_structured_dependency_identity():
    issue = {
        "code": "ACTIVE_TASK_FIELD_DEPENDENCY",
        "fieldId": str(uuid4()),
        "clientId": None,
        "message": "Active task field dependency",
        "affectedRecords": None,
        "taskId": str(uuid4()),
        "runId": str(uuid4()),
        "referenceSources": ["input.fieldMappings", "capability.tableGrants"],
    }

    assert DataSchemaIssue.model_validate(issue).model_dump(by_alias=True) == issue


def test_schema_http_atomic_save_and_operation_replay(catalog):
    client, project, table, base = catalog
    draft = candidate(table)
    preview = client.post(base + "/schema/preview", json=draft)
    assert preview.status_code == 200, preview.text
    assert preview.json()["blockers"] == []
    payload = {"candidate": draft, "impactRevision": preview.json()["impactRevision"]}
    identity = key()
    saved = client.post(base + "/schema", headers=identity, json=payload)
    assert saved.status_code == 200, saved.text
    result = saved.json()
    assert result["action"] == "saveSchema"
    field_id = result["createdFieldIds"][draft["fields"][0]["clientId"]]
    assert result["fields"][0]["ref"]["fieldId"] == field_id
    assert result["tableRevision"] == 2
    assert client.get(base + "/fields").json()["items"] == result["fields"]
    replay = client.post(base + "/schema", headers=identity, json=payload)
    assert replay.status_code == 200 and replay.json() == result
    operation = client.get(
        f"/api/v1/projects/{project}/operations/by-idempotency-key/{identity['Idempotency-Key']}"
    )
    assert operation.status_code == 200, operation.text
    assert operation.json()["kind"] == "saveTableSchema"
    assert operation.json()["result"] == result
    changed = {**payload, "impactRevision": payload["impactRevision"] + 1}
    mismatch = client.post(base + "/schema", headers=identity, json=changed)
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "OPERATION_PAYLOAD_MISMATCH"


def test_schema_http_auth_scope_and_quiesce(catalog):
    client, _, table, base = catalog
    draft = candidate(table)
    client.headers.pop("x-autoflow-token")
    assert client.post(base + "/schema/preview", json=draft).status_code == 401
    client.headers["x-autoflow-token"] = "renderer"
    other = client.post("/api/v1/projects", headers=key(), json={"name": "Q"}).json()[
        "projectId"
    ]
    assert (
        client.post(
            f"/api/v1/projects/{other}/tables/{table['tableId']}/schema/preview",
            json=draft,
        ).status_code
        == 404
    )
    preview = client.post(base + "/schema/preview", json=draft)
    assert preview.status_code == 200, preview.text
    payload = {"candidate": draft, "impactRevision": preview.json()["impactRevision"]}
    assert client.post(base + "/schema", json=payload).status_code == 422
    assert (
        client.post(
            base + "/schema/preview",
            json={
                "datasetGeneration": table["datasetGeneration"],
                "expectedTableRevision": 1,
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/internal/settings/quiesce", headers={"x-autoflow-host-token": "host"}
        ).status_code
        == 200
    )
    for suffix, body in (("/schema/preview", draft), ("/schema", payload)):
        denied = client.post(base + suffix, headers=key(), json=body)
        assert denied.status_code == 409
        assert denied.json()["error"]["code"] == "SERVICE_QUIESCED"


def test_schema_empty_candidate_is_valid_but_missing_candidate_is_not(catalog):
    client, _, table, base = catalog
    draft = {**candidate(table), "fields": []}
    preview = client.post(base + "/schema/preview", json=draft)
    assert preview.status_code == 200, preview.text
    payload = {"candidate": draft, "impactRevision": preview.json()["impactRevision"]}
    saved = client.post(base + "/schema", headers=key(), json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["tableRevision"] == 1
    assert saved.json()["fields"] == []
    assert client.post(base + "/schema", headers=key(), json={}).status_code == 422


@pytest.mark.parametrize(
    "state,status",
    [("archived", 409), ("closing", 423), ("deleted", 404), ("deleting", 409)],
)
def test_schema_http_lifecycle_admission(catalog, state, status):
    client, project, table, base = catalog
    draft = candidate(table)
    preview = client.post(base + "/schema/preview", json=draft)
    assert preview.status_code == 200
    payload = {"candidate": draft, "impactRevision": preview.json()["impactRevision"]}
    with client.app.state.session_factory.begin() as session:
        session.get(ProjectRow, project).lifecycle_state = state
    assert client.post(base + "/schema/preview", json=draft).status_code == status
    assert (
        client.post(base + "/schema", headers=key(), json=payload).status_code == status
    )


def test_schema_expired_preview_rejected_by_real_http(catalog):
    client, _, table, base = catalog
    draft = candidate(table)
    preview = client.post(base + "/schema/preview", json=draft).json()
    with client.app.state.session_factory.begin() as session:
        session.get(DataImpactRow, preview["impactRevision"]).expires_at = datetime.now(
            UTC
        ) - timedelta(minutes=1)
    rejected = client.post(
        base + "/schema",
        headers=key(),
        json={"candidate": draft, "impactRevision": preview["impactRevision"]},
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "IMPACT_STALE"
    assert client.get(base + "/fields").json()["items"] == []
