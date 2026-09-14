from autoflow.infrastructure.database.models import ProjectRow
from tests.contract.test_project_data_catalog import (
    catalog as catalog,  # noqa: PLC0414 -- fixture re-export
)
from tests.contract.test_project_data_catalog import key
from tests.contract.test_project_data_records import record_url


def test_status_delete_http_preview_202_operation_and_replay(catalog):
    client, project, _, base = catalog
    status = client.post(
        base + "/statuses",
        headers=key(),
        json={
            "name": "Open",
            "color": "#abcdef",
            "order": 0,
            "expectedTableRevision": 1,
        },
    ).json()
    target = {
        "type": "status",
        "projectId": project,
        "tableId": base.split("/")[-1],
        "statusId": status["statusId"],
    }
    impact = client.post(
        f"/api/v1/projects/{project}/mutation-impact",
        json={"action": "deleteStatus", "target": target},
    )
    assert impact.status_code == 200, impact.text
    body = {
        "expectedStatusRevision": 1,
        "expectedTableRevision": 2,
        "impactRevision": impact.json()["impactRevision"],
    }
    identity = key()
    deleted = client.request(
        "DELETE", base + "/statuses/" + status["statusId"], headers=identity, json=body
    )
    assert deleted.status_code == 202, deleted.text
    operation = deleted.json()["operation"]
    assert operation["status"] == "succeeded" and operation["result"] == {
        "action": "delete",
        "statusId": status["statusId"],
        "deleted": True,
        "tableRevision": 3,
    }
    replay = client.request(
        "DELETE", base + "/statuses/" + status["statusId"], headers=identity, json=body
    )
    assert replay.status_code == 202 and replay.json() == deleted.json()
    queried = client.get(
        f"/api/v1/projects/{project}/operations/by-idempotency-key/{identity['Idempotency-Key']}"
    )
    assert queried.json() == operation
    assert client.get(base + "/statuses").json()["items"] == []


def test_record_delete_http_and_scope_payload_auth_errors(catalog):
    client, project, table, base = catalog
    created = client.post(
        base + "/records",
        headers=key(),
        json={"datasetGeneration": table["datasetGeneration"], "values": []},
    ).json()
    url = record_url(base, created)
    target = {"type": "record", "recordRef": created["ref"]}
    impact_url = f"/api/v1/projects/{project}/mutation-impact"
    impact = client.post(impact_url, json={"action": "deleteRecord", "target": target})
    assert impact.status_code == 200, impact.text
    body = {
        "datasetGeneration": table["datasetGeneration"],
        "recordKeyType": "uuid",
        "expectedContentRevision": 1,
        "expectedStatusRevision": 1,
        "expectedLinkRevision": 1,
        "impactRevision": impact.json()["impactRevision"],
    }
    assert (
        client.request(
            "DELETE", url, headers=key(), json={**body, "extra": 1}
        ).status_code
        == 422
    )
    identity = key()
    deleted = client.request("DELETE", url, headers=identity, json=body)
    assert deleted.status_code == 202, deleted.text
    assert deleted.json()["operation"]["kind"] == "deleteRecord"
    queried = client.get(
        f"/api/v1/projects/{project}/operations/by-idempotency-key/"
        + identity["Idempotency-Key"]
    )
    assert queried.status_code == 200 and queried.json() == deleted.json()["operation"]
    filtered = client.get(
        f"/api/v1/projects/{project}/operations?kind=deleteRecord&resourceType=record"
    )
    assert filtered.status_code == 200 and filtered.json()["total"] == 1
    assert (
        client.get(
            url,
            params={
                "datasetGeneration": table["datasetGeneration"],
                "recordKeyType": "uuid",
            },
        ).status_code
        == 404
    )
    other = client.post(
        "/api/v1/projects", headers=key(), json={"name": "other"}
    ).json()["projectId"]
    assert (
        client.post(
            f"/api/v1/projects/{other}/mutation-impact",
            json={"action": "deleteRecord", "target": target},
        ).status_code
        == 404
    )
    client.headers.pop("x-autoflow-token")
    assert client.request("DELETE", url, headers=key(), json=body).status_code == 401


def test_used_status_reports_blocker_and_delete_requires_matching_impact(catalog):
    client, project, table, base = catalog
    status = client.post(
        base + "/statuses",
        headers=key(),
        json={
            "name": "Used",
            "color": "#abcdef",
            "order": 0,
            "expectedTableRevision": 1,
        },
    ).json()
    record = client.post(
        base + "/records",
        headers=key(),
        json={"datasetGeneration": table["datasetGeneration"], "values": []},
    ).json()
    url = record_url(base, record)
    changed = client.put(
        url + "/status",
        headers=key(),
        json={
            "datasetGeneration": table["datasetGeneration"],
            "recordKeyType": "uuid",
            "statusId": status["statusId"],
            "expectedStatusRevision": 1,
        },
    )
    assert changed.status_code == 200
    impact = client.post(
        f"/api/v1/projects/{project}/mutation-impact",
        json={
            "action": "deleteStatus",
            "target": {
                "type": "status",
                "projectId": project,
                "tableId": table["tableId"],
                "statusId": status["statusId"],
            },
        },
    )
    assert impact.status_code == 200
    assert impact.json()["blockers"][0]["code"] == "STATUS_IN_USE"
    rejected = client.request(
        "DELETE",
        base + "/statuses/" + status["statusId"],
        headers=key(),
        json={
            "expectedStatusRevision": 1,
            "expectedTableRevision": 2,
            "impactRevision": impact.json()["impactRevision"],
        },
    )
    assert rejected.status_code == 412
    assert rejected.json()["error"]["code"] == "PRECONDITION_FAILED"


def test_delete_http_rejects_wrong_impact_cas_and_typed_identity(catalog):
    client, project, table, base = catalog
    first = client.post(
        base + "/statuses",
        headers=key(),
        json={
            "name": "First",
            "color": "#111111",
            "order": 0,
            "expectedTableRevision": 1,
        },
    ).json()
    second = client.post(
        base + "/statuses",
        headers=key(),
        json={
            "name": "Second",
            "color": "#222222",
            "order": 1,
            "expectedTableRevision": 2,
        },
    ).json()
    impact_url = f"/api/v1/projects/{project}/mutation-impact"

    def preview(status):
        return client.post(
            impact_url,
            json={
                "action": "deleteStatus",
                "target": {
                    "type": "status",
                    "projectId": project,
                    "tableId": table["tableId"],
                    "statusId": status["statusId"],
                },
            },
        ).json()

    wrong = client.request(
        "DELETE",
        base + "/statuses/" + first["statusId"],
        headers=key(),
        json={
            "expectedStatusRevision": 1,
            "expectedTableRevision": 3,
            "impactRevision": preview(second)["impactRevision"],
        },
    )
    assert wrong.status_code == 412
    stale_cas = client.request(
        "DELETE",
        base + "/statuses/" + first["statusId"],
        headers=key(),
        json={
            "expectedStatusRevision": 9,
            "expectedTableRevision": 3,
            "impactRevision": preview(first)["impactRevision"],
        },
    )
    assert stale_cas.status_code == 409
    record = client.post(
        base + "/records",
        headers=key(),
        json={"datasetGeneration": table["datasetGeneration"], "values": []},
    ).json()
    assert (
        client.post(
            impact_url,
            json={
                "action": "deleteRecord",
                "target": {
                    "type": "record",
                    "recordRef": {
                        **record["ref"],
                        "recordKey": {"type": [], "value": "x"},
                    },
                },
            },
        ).status_code
        == 422
    )
    assert (
        client.request(
            "DELETE",
            record_url(base, record),
            headers=key(),
            json={
                "datasetGeneration": table["datasetGeneration"],
                "recordKeyType": [],
                "expectedContentRevision": 1,
                "expectedStatusRevision": 1,
                "expectedLinkRevision": 1,
                "impactRevision": 1,
            },
        ).status_code
        == 422
    )


def test_delete_http_obeys_readonly_lifecycle_and_global_quiesce(catalog):
    client, project, table, base = catalog
    record = client.post(
        base + "/records",
        headers=key(),
        json={"datasetGeneration": table["datasetGeneration"], "values": []},
    ).json()
    target = {"type": "record", "recordRef": record["ref"]}
    impact = client.post(
        f"/api/v1/projects/{project}/mutation-impact",
        json={"action": "deleteRecord", "target": target},
    ).json()
    body = {
        "datasetGeneration": table["datasetGeneration"],
        "recordKeyType": "uuid",
        "expectedContentRevision": 1,
        "expectedStatusRevision": 1,
        "expectedLinkRevision": 1,
        "impactRevision": impact["impactRevision"],
    }
    url = record_url(base, record)
    with client.app.state.session_factory.begin() as session:
        session.get(ProjectRow, project).lifecycle_state = "archived"
    readonly = client.request("DELETE", url, headers=key(), json=body)
    assert readonly.status_code == 409
    with client.app.state.session_factory.begin() as session:
        session.get(ProjectRow, project).lifecycle_state = "active"
    assert (
        client.post(
            "/internal/settings/quiesce", headers={"x-autoflow-host-token": "host"}
        ).status_code
        == 200
    )
    blocked = client.request("DELETE", url, headers=key(), json=body)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "SERVICE_QUIESCED"
