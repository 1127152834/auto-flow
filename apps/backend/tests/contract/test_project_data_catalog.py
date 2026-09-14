from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.contract.test_settings_dashboard import _app


def key():
    return {"Idempotency-Key": str(uuid4())}


@pytest.fixture
def catalog(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        client.headers["x-autoflow-token"] = "renderer"
        p = client.post("/api/v1/projects", headers=key(), json={"name": "P"}).json()[
            "projectId"
        ]
        t = client.post(
            f"/api/v1/projects/{p}/tables", headers=key(), json={"name": "T"}
        ).json()
        yield client, p, t, f"/api/v1/projects/{p}/tables/{t['tableId']}"


def test_field_http_returns_complete_ref_and_recoverable_snapshot(catalog):
    client, project, table, base = catalog
    assert client.get(base + "/fields").json() == {"items": [], "tableRevision": 1}
    identity = key()
    payload = {
        "definition": {
            "key": "account.name",
            "name": "账户名",
            "type": "string",
            "required": False,
            "validation": {},
        },
        "expectedTableRevision": 1,
        "sourceColumnPolicy": "localOnly",
    }
    response = client.post(base + "/fields", headers=identity, json=payload)
    assert response.status_code == 200, response.text
    created = response.json()
    assert set(created) == {"field", "tableRevision"}
    field = created["field"]
    assert field["ref"] == {
        "projectId": project,
        "tableId": table["tableId"],
        "datasetGeneration": table["datasetGeneration"],
        "fieldId": field["ref"]["fieldId"],
    }
    assert field["validation"] == {} and field["fieldRevision"] == 1
    assert client.get(base + "/fields").json()["items"] == [field]
    replay = client.post(base + "/fields", headers=identity, json=payload)
    assert replay.status_code == 200 and replay.json() == created
    op = client.get(
        f"/api/v1/projects/{project}/operations/by-idempotency-key/{identity['Idempotency-Key']}"
    )
    assert op.status_code == 200, op.text
    assert op.json()["resource"] == {"type": "field", "fieldRef": field["ref"]}
    assert op.json()["result"] == {"action": "create", **created}
    assert (
        client.get(
            f"/api/v1/projects/{project}/operations?kind=mutateField&resourceType=field"
        ).json()["total"]
        == 1
    )


def test_status_http_create_edit_and_original_result_are_distinct(catalog):
    client, project, _, base = catalog
    assert client.get(base + "/statuses").json()["items"] == []
    identity = key()
    payload = {
        "name": " 可用 ",
        "color": "#ABCDEF",
        "order": 0,
        "expectedTableRevision": 1,
    }
    created = client.post(base + "/statuses", headers=identity, json=payload)
    assert created.status_code == 201, created.text
    status = created.json()
    assert status["name"] == "可用" and status["color"] == "#abcdef"
    edited = client.patch(
        base + "/statuses/" + status["statusId"],
        headers=key(),
        json={"name": "完成", "expectedTableRevision": 2, "expectedStatusRevision": 1},
    )
    assert edited.status_code == 200 and edited.json()["statusRevision"] == 2
    replay = client.post(base + "/statuses", headers=identity, json=payload)
    assert replay.status_code == 200 and replay.json() == status
    op = client.get(
        f"/api/v1/projects/{project}/operations/by-idempotency-key/{identity['Idempotency-Key']}"
    )
    assert op.status_code == 200 and op.json()["result"] == {
        "action": "create",
        "status": status,
        "tableRevision": 2,
    }
    assert client.get(base + "/statuses").json() == {
        "items": [edited.json()],
        "tableRevision": 3,
    }


def test_catalog_http_input_security_and_quiesce(catalog):
    client, _project, table, base = catalog
    uri = base + "/fields"
    payload = {
        "definition": {
            "key": "n",
            "name": "N",
            "type": "number",
            "required": True,
            "validation": {},
        },
        "expectedTableRevision": 1,
        "sourceColumnPolicy": "localOnly",
    }
    assert (
        client.post(
            uri, headers=key(), json={**payload, "existingRecordDefault": True}
        ).status_code
        == 422
    )
    assert (
        client.post(
            uri, headers=key(), json={**payload, "expectedTableRevision": 2**53}
        ).status_code
        == 422
    )
    assert (
        client.post(
            uri, headers=key(), json={**payload, "sourceColumnPolicy": "mapped"}
        ).status_code
        == 412
    )
    client.headers.pop("x-autoflow-token")
    assert client.get(uri).status_code == 401
    client.headers["x-autoflow-token"] = "renderer"
    other = client.post("/api/v1/projects", headers=key(), json={"name": "Q"}).json()[
        "projectId"
    ]
    assert (
        client.get(
            f"/api/v1/projects/{other}/tables/{table['tableId']}/fields"
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/internal/settings/quiesce", headers={"x-autoflow-host-token": "host"}
        ).status_code
        == 200
    )
    denied = client.post(uri, headers=key(), json=payload)
    assert (
        denied.status_code == 409
        and denied.json()["error"]["code"] == "SERVICE_QUIESCED"
    )
    assert client.get(uri).json()["items"] == []


def test_status_patch_optional_properties_are_not_nullable(catalog):
    client, _, _, base = catalog
    created = client.post(
        base + "/statuses",
        headers=key(),
        json={
            "name": "Ready",
            "color": "#abcdef",
            "order": 0,
            "expectedTableRevision": 1,
        },
    ).json()
    for field in ("name", "color", "order"):
        invalid = client.patch(
            base + "/statuses/" + created["statusId"],
            headers=key(),
            json={
                field: None,
                "expectedTableRevision": 2,
                "expectedStatusRevision": 1,
            },
        )
        assert invalid.status_code == 422
    schema = client.get("/openapi.json").json()["components"]["schemas"][
        "DataStatusPatch"
    ]
    for field, expected_type in (
        ("name", "string"),
        ("color", "string"),
        ("order", "integer"),
    ):
        assert field not in schema["required"]
        assert schema["properties"][field]["type"] == expected_type
        assert "default" not in schema["properties"][field]
    updated = client.patch(
        base + "/statuses/" + created["statusId"],
        headers=key(),
        json={
            "name": "Done",
            "expectedTableRevision": 2,
            "expectedStatusRevision": 1,
        },
    )
    assert updated.status_code == 200 and updated.json()["name"] == "Done"
    assert updated.json()["color"] == "#abcdef" and updated.json()["order"] == 0
