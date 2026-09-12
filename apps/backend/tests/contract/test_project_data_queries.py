import base64
import json
from uuid import uuid4

from tests.contract.test_project_data_catalog import (
    catalog as catalog,  # noqa: PLC0414 -- explicit pytest fixture re-export
)
from tests.contract.test_project_data_catalog import key


def encoded(value):
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")


def test_record_collection_filters_before_pagination_and_preserves_missing(catalog):
    client, _, table, base = catalog
    generation = table["datasetGeneration"]
    field = client.post(
        base + "/fields",
        headers=key(),
        json={
            "definition": {
                "key": "code",
                "name": "编号",
                "type": "string",
                "required": False,
                "validation": {},
            },
            "sourceColumnPolicy": "localOnly",
            "expectedTableRevision": 1,
        },
    ).json()["field"]["ref"]["fieldId"]
    for value in ["001", "010", "002", None]:
        response = client.post(
            base + "/records",
            headers=key(),
            json={
                "datasetGeneration": generation,
                "values": [{"fieldId": field, "value": value}],
            },
        )
        assert response.status_code == 201
    assert (
        client.post(
            base + "/records",
            headers=key(),
            json={"datasetGeneration": generation, "values": []},
        ).status_code
        == 201
    )
    order = [{"fieldId": field, "direction": "asc"}]
    response = client.get(
        base + "/records",
        params={
            "datasetGeneration": generation,
            "page": 2,
            "pageSize": 1,
            "filter": encoded(
                {
                    "type": "compare",
                    "fieldId": field,
                    "operator": "startsWith",
                    "value": "00",
                }
            ),
            "orderBy": encoded(order),
        },
    )
    assert response.status_code == 200, response.text
    page = response.json()
    assert (page["total"], page["page"], page["pageSize"]) == (2, 2, 1)
    assert page["items"][0]["values"][0]["value"] == "002"
    assert json.loads(page["sort"]) == [
        *order,
        {"systemField": "recordKey", "direction": "asc"},
    ]
    all_rows = client.get(
        base + "/records", params={"datasetGeneration": generation}
    ).json()
    assert all_rows["total"] == 5 and len(all_rows["items"]) == 5
    assert any(row["values"] == [] for row in all_rows["items"])
    assert any(
        row["values"] and row["values"][0]["value"] is None for row in all_rows["items"]
    )
    schema = client.get("/openapi.json").json()
    assert (
        "get"
        in schema["paths"]["/api/v1/projects/{projectId}/tables/{tableId}/records"]
    )
    assert "sort" in schema["components"]["schemas"]["DataRecordPage"]["required"]


def test_record_collection_rejects_bad_queries_and_invalid_scope(catalog):
    client, _, table, base = catalog
    params = {"datasetGeneration": table["datasetGeneration"]}
    for query in [
        {"filter": "not_base64"},
        {"filter": encoded({"type": "bad"})},
        {"orderBy": encoded([{"systemField": "bad", "direction": "asc"}])},
        {"page": 0},
        {"pageSize": 201},
    ]:
        response = client.get(base + "/records", params={**params, **query})
        assert response.status_code == 422, response.text
    assert client.get(base + "/records").status_code == 422
    assert (
        client.get(
            base + "/records", params={"datasetGeneration": str(uuid4())}
        ).status_code
        == 410
    )
    other = client.post(
        "/api/v1/projects", headers=key(), json={"name": "other"}
    ).json()["projectId"]
    assert (
        client.get(
            f"/api/v1/projects/{other}/tables/{table['tableId']}/records", params=params
        ).status_code
        == 404
    )
    client.headers.clear()
    assert client.get(base + "/records", params=params).status_code == 401
