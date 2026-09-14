from uuid import uuid4

from fastapi.testclient import TestClient

from tests.contract.test_settings_dashboard import _app


def test_table_http_persists_queries_and_recovers_original_operation(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        client.headers["x-autoflow-token"] = "renderer"
        p = client.post(
            "/api/v1/projects",
            headers={"Idempotency-Key": str(uuid4())},
            json={"name": "Data project"},
        ).json()["projectId"]
        base = f"/api/v1/projects/{p}/tables"
        key = str(uuid4())
        response = client.post(
            base,
            headers={"Idempotency-Key": key},
            json={"name": "  Data ", "sourceKind": "local"},
        )
        assert response.status_code == 201
        table = response.json()
        assert table["name"] == "Data" and table["identity"] == {"mode": "system"}
        assert (
            table["recordCount"] == 0
            and table["syncSummary"]["status"] == "notApplicable"
        )
        assert (
            client.post(
                base, headers={"Idempotency-Key": key}, json={"name": "Data"}
            ).status_code
            == 200
        )
        resource = f"{base}/{table['tableId']}"
        assert client.get(resource).json() == table
        updated = client.patch(
            resource,
            headers={"Idempotency-Key": str(uuid4())},
            json={"description": "edited", "expectedTableRevision": 1},
        )
        assert updated.status_code == 200 and updated.json()["tableRevision"] == 2
        assert client.get(base + "?q=edited&pageSize=1").json()["total"] == 1
        recovered = client.get(
            f"/api/v1/projects/{p}/operations/by-idempotency-key/{key}"
        )
        assert recovered.status_code == 200
        op = recovered.json()
        assert op["kind"] == "createTable" and op["result"] == table
        assert op["resource"] == {
            "type": "table",
            "projectId": p,
            "tableId": table["tableId"],
        }
        assert (
            client.get(f"/api/v1/projects/{p}/operations?kind=createTable").json()[
                "total"
            ]
            == 1
        )
    with TestClient(_app(tmp_path)) as client:
        client.headers["x-autoflow-token"] = "renderer"
        assert client.get(resource).json()["description"] == "edited"


def test_table_http_security_quiesce_and_error_envelope(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        project_key = str(uuid4())
        response = client.post(
            "/api/v1/projects",
            headers={"Idempotency-Key": project_key, "x-autoflow-token": "renderer"},
            json={"name": "One"},
        )
        p = response.json()["projectId"]
        base = f"/api/v1/projects/{p}/tables"
        assert client.get(base).status_code == 401
        client.headers["x-autoflow-token"] = "renderer"
        assert client.post(base, json={"name": "Data"}).status_code == 422
        for body in (
            {"name": ""},
            {"name": "Data", "sourceKind": "sheets"},
            {"name": "Data", "recordCount": 1},
        ):
            bad = client.post(
                base, headers={"Idempotency-Key": str(uuid4())}, json=body
            )
            assert bad.status_code == 422
            assert {"code", "message", "details", "requestId"} <= bad.json()[
                "error"
            ].keys()
        assert client.get(base + "?pageSize=201").status_code == 422
        assert client.get(base + "?sort=invalid").status_code == 422
        assert (
            client.post(
                "/internal/settings/quiesce", headers={"x-autoflow-host-token": "host"}
            ).status_code
            == 200
        )
        blocked = client.post(
            base, headers={"Idempotency-Key": str(uuid4())}, json={"name": "Data"}
        )
        assert (
            blocked.status_code == 409
            and blocked.json()["error"]["code"] == "SERVICE_QUIESCED"
        )
        assert client.get(base).json()["total"] == 0


def test_table_http_cas_scope_and_openapi_are_real(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        client.headers["x-autoflow-token"] = "renderer"
        p = client.post(
            "/api/v1/projects",
            headers={"Idempotency-Key": str(uuid4())},
            json={"name": "One"},
        ).json()["projectId"]
        base = f"/api/v1/projects/{p}/tables"
        t = client.post(
            base, headers={"Idempotency-Key": str(uuid4())}, json={"name": "Data"}
        ).json()
        assert "tableId" in t
        uri = f"{base}/{t['tableId']}"
        assert (
            client.patch(
                uri,
                headers={"Idempotency-Key": str(uuid4())},
                json={"name": "Changed", "expectedTableRevision": 1},
            ).status_code
            == 200
        )
        stale = client.patch(
            uri,
            headers={"Idempotency-Key": str(uuid4())},
            json={"name": "Stale", "expectedTableRevision": 1},
        )
        assert (
            stale.status_code == 409
            and stale.json()["error"]["code"] == "REVISION_CONFLICT"
        )
        assert (
            client.get(f"/api/v1/projects/{uuid4()}/tables/{t['tableId']}").status_code
            == 404
        )
        schema = client.get("/openapi.json").json()
        assert set(schema["paths"]["/api/v1/projects/{projectId}/tables"]) == {
            "get",
            "post",
        }
        assert set(
            schema["paths"]["/api/v1/projects/{projectId}/tables/{tableId}"]
        ) == {"get", "patch"}
        assert {"DataTableView", "DataTableCreate", "DataTablePatch"} <= schema[
            "components"
        ]["schemas"].keys()


def test_table_http_rejects_noncanonical_identity_strings(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        client.headers["x-autoflow-token"] = "renderer"
        p = client.post(
            "/api/v1/projects",
            headers={"Idempotency-Key": str(uuid4())},
            json={"name": "One"},
        ).json()["projectId"]
        key = str(uuid4())
        for raw_key in (key.upper(), key.replace("-", "")):
            response = client.post(
                f"/api/v1/projects/{p}/tables",
                headers={"Idempotency-Key": raw_key},
                json={"name": "Data"},
            )
            assert response.status_code == 422
        for raw_project in (p.upper(), p.replace("-", "")):
            assert (
                client.get(f"/api/v1/projects/{raw_project}/tables").status_code == 422
            )
        t = client.post(
            f"/api/v1/projects/{p}/tables",
            headers={"Idempotency-Key": key},
            json={"name": "Data"},
        ).json()["tableId"]
        assert client.get(f"/api/v1/projects/{p}/tables/{t.upper()}").status_code == 422
