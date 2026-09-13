from uuid import uuid4

from tests.contract.test_project_data_catalog import catalog as catalog  # noqa: PLC0414
from tests.contract.test_project_data_catalog import key


def test_batch_http_and_query_recover_exact_result(catalog):
    client, project, table, base = catalog
    body = {
        "datasetGeneration": table["datasetGeneration"],
        "expectedTableRevision": 1,
        "rows": [{"clientRowId": str(uuid4()), "values": []} for _ in range(2)],
    }
    headers = key()
    response = client.post(base + "/records/batch", headers=headers, json=body)
    assert response.status_code == 201, response.text
    result = response.json()
    assert len(result["records"]) == 2
    assert result["operation"]["kind"] == "createRecords"
    query = client.get(
        f"/api/v1/projects/{project}/operations/by-idempotency-key/{headers['Idempotency-Key']}"
    )
    assert query.status_code == 200 and query.json()["result"] == {
        "records": result["records"]
    }
    replay = client.post(base + "/records/batch", headers=headers, json=body)
    assert replay.status_code == 200 and replay.json() == result
    body["rows"].reverse()
    mismatch = client.post(base + "/records/batch", headers=headers, json=body)
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "OPERATION_PAYLOAD_MISMATCH"


def test_batch_http_validation_and_project_scope(catalog):
    client, project, table, base = catalog
    body = {
        "datasetGeneration": table["datasetGeneration"],
        "expectedTableRevision": 1,
        "rows": [],
    }
    assert (
        client.post(base + "/records/batch", headers=key(), json=body).status_code
        == 422
    )
    body["rows"] = [{"clientRowId": str(uuid4()), "values": []}]
    headers = key()
    assert (
        client.post(base + "/records/batch", headers=headers, json=body).status_code
        == 201
    )
    other = client.post(
        "/api/v1/projects", headers=key(), json={"name": "other"}
    ).json()["projectId"]
    assert (
        client.get(
            f"/api/v1/projects/{other}/operations/by-idempotency-key/{headers['Idempotency-Key']}"
        ).status_code
        == 404
    )
    assert (
        client.post(
            base.replace(project, other) + "/records/batch", headers=key(), json=body
        ).status_code
        == 404
    )
