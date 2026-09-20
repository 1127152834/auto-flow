import base64

import pytest
from sqlalchemy import select

from autoflow.infrastructure.database.models import ProjectOperationRow
from tests.contract.test_project_data_catalog import (
    catalog as catalog,  # noqa: PLC0414 -- explicit pytest fixture re-export
)
from tests.contract.test_project_data_catalog import (
    key,
)


def record_url(base, record):
    raw = record["ref"]["recordKey"]["value"]
    return (
        base + "/records/" + base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    )


@pytest.mark.parametrize("explicit_null", [False, True])
def test_record_http_preserves_missing_cells_and_historical_nulls(
    catalog, explicit_null
):
    client, project, table, base = catalog
    generation = table["datasetGeneration"]

    def add_optional(name, revision):
        response = client.post(
            base + "/fields",
            headers=key(),
            json={
                "definition": {
                    "key": name,
                    "name": name,
                    "type": "string",
                    "required": False,
                    "validation": {},
                },
                "sourceColumnPolicy": "localOnly",
                "expectedTableRevision": revision,
            },
        )
        assert response.status_code == 200, response.text
        return response.json()["field"]["ref"]["fieldId"]

    field_id = add_optional("optional", 1)
    values = [{"fieldId": field_id, "value": None}] if explicit_null else []
    payload = {"datasetGeneration": generation, "values": values}
    identity = key()
    response = client.post(base + "/records", headers=identity, json=payload)
    assert response.status_code == 201, response.text
    created = response.json()
    assert [
        {"fieldId": c["fieldId"], "value": c["value"]} for c in created["values"]
    ] == values
    added_id = add_optional("later", 2)
    url = record_url(base, created)
    params = {"datasetGeneration": generation, "recordKeyType": "uuid"}
    assert client.get(url, params=params).json() == created
    changed = client.patch(
        url,
        headers=key(),
        json={
            **params,
            "expectedContentRevision": 1,
            "values": [{"fieldId": added_id, "value": None}],
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["contentRevision"] == 2
    assert {c["fieldId"]: c["value"] for c in changed.json()["values"]} == {
        **{c["fieldId"]: c["value"] for c in values},
        added_id: None,
    }
    operation_url = f"/api/v1/projects/{project}/operations/by-idempotency-key/{identity['Idempotency-Key']}"
    assert client.get(operation_url).json()["result"] == created
    assert (
        client.post(base + "/records", headers=identity, json=payload).json() == created
    )

    # Simulate a pre-fix persisted result, which filled an absent cell with null.
    legacy = {
        **created,
        "values": [
            {"fieldId": field_id, "value": None, "source": "local", "readable": True}
        ],
    }
    with client.app.state.session_factory() as session:
        operation = session.scalar(
            select(ProjectOperationRow).where(
                ProjectOperationRow.idempotency_key == identity["Idempotency-Key"]
            )
        )
        operation.result = legacy
        session.commit()
    assert client.get(operation_url).json()["result"] == legacy
    replay = client.post(base + "/records", headers=identity, json=payload)
    assert replay.status_code == 200 and replay.json() == legacy
    assert client.get(url, params=params).json() == changed.json()
    with client.app.state.session_factory() as session:
        operation = session.scalar(
            select(ProjectOperationRow).where(
                ProjectOperationRow.idempotency_key == identity["Idempotency-Key"]
            )
        )
        assert operation.result == legacy


def test_record_http_persists_typed_values_nulls_and_original_operation(catalog):
    client, project, table, base = catalog
    fields = []
    for index, field_type in enumerate(["string", "number", "boolean", "date"]):
        result = client.post(
            base + "/fields",
            headers=key(),
            json={
                "definition": {
                    "key": field_type,
                    "name": field_type,
                    "type": field_type,
                    "required": False,
                    "validation": {},
                },
                "sourceColumnPolicy": "localOnly",
                "expectedTableRevision": index + 1,
            },
        )
        assert result.status_code == 200
        fields.append(result.json()["field"]["ref"]["fieldId"])
    scalars = [
        "001",
        2,
        False,
        {"kind": "date", "precision": "date", "value": "2026-09-13", "offset": None},
    ]
    body = {
        "datasetGeneration": table["datasetGeneration"],
        "values": [
            {"fieldId": field, "value": value}
            for field, value in zip(fields, scalars, strict=True)
        ],
    }
    identity = key()
    response = client.post(base + "/records", headers=identity, json=body)
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["ref"]["recordKey"]["type"] == "uuid"
    assert record["statusId"] is None and record["currentEnvironmentId"] is None
    assert [cell["value"] for cell in record["values"]] == scalars
    assert record["values"][2]["value"] is False
    url = record_url(base, record)
    assert (
        client.get(
            url,
            params={
                "datasetGeneration": table["datasetGeneration"],
                "recordKeyType": "uuid",
            },
        ).json()
        == record
    )
    edit = client.patch(
        url,
        headers=key(),
        json={
            "datasetGeneration": table["datasetGeneration"],
            "recordKeyType": "uuid",
            "expectedContentRevision": 1,
            "values": [{"fieldId": fields[0], "value": "changed"}],
        },
    )
    assert edit.status_code == 200 and edit.json()["contentRevision"] == 2
    replay = client.post(base + "/records", headers=identity, json=body)
    assert replay.status_code == 200 and replay.json() == record
    recovered = client.get(
        f"/api/v1/projects/{project}/operations/by-idempotency-key/{identity['Idempotency-Key']}"
    )
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["resource"] == {
        "type": "record",
        "recordRef": record["ref"],
    }
    assert recovered.json()["result"] == record
    assert (
        client.get(
            f"/api/v1/projects/{project}/operations?kind=createRecord&resourceType=record"
        ).json()["total"]
        == 1
    )


def test_record_http_explicit_status_null_and_precondition(catalog):
    client, _, table, base = catalog
    record = client.post(
        base + "/records",
        headers=key(),
        json={"datasetGeneration": table["datasetGeneration"], "values": []},
    ).json()
    assert "ref" in record, record
    url = record_url(base, record)
    body = {
        "datasetGeneration": table["datasetGeneration"],
        "recordKeyType": "uuid",
        "statusId": None,
        "expectedFromStatusId": None,
        "expectedStatusRevision": 1,
    }
    changed = client.put(url + "/status", headers=key(), json=body)
    assert changed.status_code == 200 and changed.json()["statusRevision"] == 2
    assert changed.json()["statusId"] is None and changed.json()["contentRevision"] == 1
    stale = client.put(url + "/status", headers=key(), json=body)
    assert (
        stale.status_code == 409
        and stale.json()["error"]["code"] == "REVISION_CONFLICT"
    )
    assert (
        client.put(
            url + "/status", headers=key(), json={**body, "recordKeyType": []}
        ).status_code
        == 422
    )
    client.headers.pop("x-autoflow-token")
    assert client.get(url).status_code == 401
    client.headers["x-autoflow-token"] = "renderer"
    assert (
        client.post(
            "/internal/settings/quiesce", headers={"x-autoflow-host-token": "host"}
        ).status_code
        == 200
    )
    assert (
        client.put(
            url + "/status", headers=key(), json={**body, "expectedStatusRevision": 2}
        ).status_code
        == 409
    )


def test_record_http_rejects_cell_metadata_and_unsafe_scalar(catalog):
    client, _, table, base = catalog
    field = client.post(
        base + "/fields",
        headers=key(),
        json={
            "definition": {
                "key": "n",
                "name": "N",
                "type": "number",
                "required": False,
                "validation": {},
            },
            "sourceColumnPolicy": "localOnly",
            "expectedTableRevision": 1,
        },
    ).json()["field"]["ref"]["fieldId"]
    for value in [True, 2**53, {"unexpected": "object"}, [1, 2]]:
        response = client.post(
            base + "/records",
            headers=key(),
            json={
                "datasetGeneration": table["datasetGeneration"],
                "values": [{"fieldId": field, "value": value}],
            },
        )
        assert response.status_code == 422, response.text
    response = client.post(
        base + "/records",
        headers=key(),
        json={
            "datasetGeneration": table["datasetGeneration"],
            "values": [
                {"fieldId": field, "value": 1, "readable": True, "source": "local"}
            ],
        },
    )
    assert response.status_code == 422


def test_busy_database_does_not_accept_or_duplicate_a_record_command(catalog):
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    client, project, table, base = catalog
    identity = key()
    body = {"datasetGeneration": table["datasetGeneration"], "values": []}
    # The existing fixture owns lifespan; this client only observes HTTP errors.
    quiet = TestClient(client.app, headers=client.headers, raise_server_exceptions=False)
    try:
        with client.app.state.session_factory() as writer:
            writer.execute(text("BEGIN IMMEDIATE"))
            response = quiet.post(base + "/records", headers=identity, json=body)
            assert response.status_code == 503, response.text
            assert response.json()["error"]["code"] == "DATABASE_BUSY"
            assert response.headers["retry-after"] == "1"
    finally:
        quiet.close()
    operation = f"/api/v1/projects/{project}/operations/by-idempotency-key/{identity['Idempotency-Key']}"
    assert client.get(operation).status_code == 404
    created = client.post(base + "/records", headers=identity, json=body)
    assert created.status_code == 201, created.text
    replay = client.post(base + "/records", headers=identity, json=body)
    assert replay.status_code == 200 and replay.json() == created.json()
    assert client.get(base).json()["recordCount"] == 1
