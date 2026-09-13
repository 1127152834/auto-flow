from time import monotonic, sleep
from uuid import uuid4

from fastapi.testclient import TestClient

from tests.contract.test_settings_dashboard import _app


def test_real_batch_http_and_operation_recovery(tmp_path):
    with TestClient(_app(tmp_path), headers={"x-autoflow-token": "renderer"}) as client:

        def post(path, body, key=None):
            return client.post(
                path, json=body, headers={"Idempotency-Key": key or str(uuid4())}
            )

        p = post("/api/v1/projects", {"name": "Batch project"}).json()["projectId"]
        base = f"/api/v1/projects/{p}"
        t = post(base + "/tables", {"name": "Rows"}).json()
        table = base + "/tables/" + t["tableId"]
        r = post(
            table + "/records",
            {"datasetGeneration": t["datasetGeneration"], "values": []},
        ).json()
        body = {
            "targets": [
                {"recordRef": r["ref"], "expectedStatusRevision": r["statusRevision"]}
            ],
            "statusId": None,
        }
        key = str(uuid4())
        accepted = post(table + "/record-status-batches", body, key)
        assert accepted.status_code == 202, accepted.text
        original = accepted.json()["operation"]
        assert original["kind"] == "setRecordStatuses"
        deadline = monotonic() + 3
        result = original
        while (
            result["status"] not in {"succeeded", "failed"} and monotonic() < deadline
        ):
            result = client.get(base + "/operations/by-idempotency-key/" + key).json()
            sleep(0.01)
        assert result["status"] == "succeeded", result
        assert result["result"]["changedCount"] == 1
        replay = post(table + "/record-status-batches", body, key).json()["operation"]
        assert replay["operationId"] == original["operationId"]
        assert replay["result"] == result["result"]
        assert (
            client.get(base + "/operations?kind=setRecordStatuses").json()["total"] == 1
        )
        # Current block has committed and no pending work remains to block switching.
        assert (
            client.post(
                "/internal/settings/quiesce", headers={"x-autoflow-host-token": "host"}
            ).status_code
            == 200
        )
