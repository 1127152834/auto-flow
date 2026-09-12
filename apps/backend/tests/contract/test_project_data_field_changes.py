from tests.contract.test_project_data_catalog import (
    catalog as catalog,  # noqa: PLC0414 -- explicit pytest fixture re-export
)
from tests.contract.test_project_data_catalog import (
    key,
)
from tests.contract.test_project_data_records import record_url


def test_field_http_preflight_binds_data_and_actual_update_is_recoverable(catalog):
    client, project, table, base = catalog
    original = {
        "key": "name",
        "name": "Name",
        "type": "string",
        "required": False,
        "validation": {},
    }
    field = client.post(
        base + "/fields",
        headers=key(),
        json={
            "definition": original,
            "expectedTableRevision": 1,
            "sourceColumnPolicy": "localOnly",
        },
    ).json()["field"]
    record = client.post(
        base + "/records",
        headers=key(),
        json={
            "datasetGeneration": table["datasetGeneration"],
            "values": [{"fieldId": field["ref"]["fieldId"], "value": "before"}],
        },
    ).json()
    change = {**original, "name": "Display name"}
    uri = f"/api/v1/projects/{project}/mutation-impact"
    request = {
        "action": "updateField",
        "target": {"type": "field", "fieldRef": field["ref"]},
        "change": change,
    }
    count = client.get(f"/api/v1/projects/{project}/operations").json()["total"]
    response = client.post(uri, json=request)
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["target"] == request["target"] and report["blockers"] == []
    assert client.get(f"/api/v1/projects/{project}/operations").json()["total"] == count
    record_uri = record_url(base, record)
    changed = client.patch(
        record_uri,
        headers=key(),
        json={
            "datasetGeneration": table["datasetGeneration"],
            "recordKeyType": "uuid",
            "expectedContentRevision": 1,
            "values": [{"fieldId": field["ref"]["fieldId"], "value": "after"}],
        },
    )
    assert changed.status_code == 200
    field_uri = base + "/fields/" + field["ref"]["fieldId"]
    command = {
        "definition": change,
        "expectedTableRevision": 2,
        "expectedFieldRevision": 1,
        "impactRevision": report["impactRevision"],
    }
    stale = client.patch(field_uri, headers=key(), json=command)
    assert (
        stale.status_code == 412
        and stale.json()["error"]["code"] == "PRECONDITION_FAILED"
    )
    command["impactRevision"] = client.post(uri, json=request).json()["impactRevision"]
    identity = key()
    saved = client.patch(field_uri, headers=identity, json=command)
    assert saved.status_code == 200, saved.text
    assert (
        saved.json()["field"]["fieldRevision"] == 2
        and saved.json()["tableRevision"] == 3
    )
    assert (
        client.patch(field_uri, headers=identity, json=command).json() == saved.json()
    )
    operation = client.get(
        f"/api/v1/projects/{project}/operations/by-idempotency-key/{identity['Idempotency-Key']}"
    )
    assert operation.status_code == 200, operation.text
    assert operation.json()["result"] == {"action": "update", **saved.json()}
    assert (
        client.get(
            record_uri,
            params={
                "datasetGeneration": table["datasetGeneration"],
                "recordKeyType": "uuid",
            },
        ).json()
        == changed.json()
    )


def test_impact_http_rejects_unknown_actions_and_cross_project_targets(catalog):
    client, project, _, base = catalog
    original = {
        "key": "f",
        "name": "Field",
        "type": "string",
        "required": False,
        "validation": {},
    }
    field = client.post(
        base + "/fields",
        headers=key(),
        json={
            "definition": original,
            "expectedTableRevision": 1,
            "sourceColumnPolicy": "localOnly",
        },
    ).json()["field"]
    uri = f"/api/v1/projects/{project}/mutation-impact"
    request = {
        "action": "updateField",
        "target": {"type": "field", "fieldRef": field["ref"]},
        "change": original,
    }
    assert (
        client.post(uri, json={**request, "action": "deleteField"}).status_code == 422
    )
    other = client.post("/api/v1/projects", headers=key(), json={"name": "Q"}).json()[
        "projectId"
    ]
    assert (
        client.post(
            f"/api/v1/projects/{other}/mutation-impact", json=request
        ).status_code
        == 404
    )
    client.headers.pop("x-autoflow-token")
    assert client.post(uri, json=request).status_code == 401
