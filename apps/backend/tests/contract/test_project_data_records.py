import base64

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
