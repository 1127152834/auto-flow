import base64
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


def test_partial_batch_conflict_remains_readable_over_http(tmp_path):
    """A post-preview competing writer must not turn the durable result into HTTP 500."""
    with TestClient(
        _app(tmp_path),
        headers={"x-autoflow-token": "renderer"},
        raise_server_exceptions=False,
    ) as client:

        def post(path, body, key=None):
            response = client.post(
                path, json=body, headers={"Idempotency-Key": key or str(uuid4())}
            )
            assert response.is_success, response.text
            return response.json()

        project = post("/api/v1/projects", {"name": "Partial batch"})["projectId"]
        base = f"/api/v1/projects/{project}"
        table = post(base + "/tables", {"name": "Rows"})
        path = base + "/tables/" + table["tableId"]
        records = [
            post(
                path + "/records",
                {"datasetGeneration": table["datasetGeneration"], "values": []},
            )
            for _ in range(3)
        ]
        body = {
            "targets": [
                {"recordRef": r["ref"], "expectedStatusRevision": r["statusRevision"]}
                for r in records
            ],
            "statusId": None,
            "blockSize": 2,
        }
        preview = post(path + "/record-status-batches/preview", body)
        assert not any(block["blockers"] for block in preview["blocks"])
        # Explicit clear is a real write and advances the status revision even at null.
        record_key = (
            base64.urlsafe_b64encode(records[0]["ref"]["recordKey"]["value"].encode())
            .decode()
            .rstrip("=")
        )
        competing = client.put(
            path + f"/records/{record_key}/status",
            json={
                "datasetGeneration": table["datasetGeneration"],
                "recordKeyType": records[0]["ref"]["recordKey"]["type"],
                "statusId": None,
                "expectedStatusRevision": records[0]["statusRevision"],
            },
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert competing.status_code == 200, competing.text
        key = str(uuid4())
        accepted = post(path + "/record-status-batches", body, key)["operation"]
        result = accepted
        deadline = monotonic() + 3
        while (
            result["status"] not in {"succeeded", "failed"} and monotonic() < deadline
        ):
            response = client.get(base + "/operations/by-idempotency-key/" + key)
            assert response.status_code == 200, response.text
            result = response.json()
            sleep(0.01)
        assert result["status"] == "failed", result
        outcome = result["result"]
        assert (
            outcome["changedCount"],
            outcome["conflictCount"],
            outcome["notStartedCount"],
        ) == (1, 2, 0)
        assert outcome["blocks"][0]["blockers"][0]["details"] == {
            "expectedRevision": 1,
            "currentRevision": 2,
        }
        replay = post(path + "/record-status-batches", body, key)["operation"]
        assert replay["operationId"] == accepted["operationId"]
        assert replay["result"] == outcome
        listing = client.get(base + "/operations?kind=setRecordStatuses")
        assert listing.status_code == 200, listing.text
        assert listing.json()["total"] == 1

        by_id = client.get(base + "/operations/" + accepted["operationId"])
        assert by_id.status_code == 200, by_id.text
        assert by_id.json()["result"] == outcome
        records_path = path + "/records?datasetGeneration=" + table["datasetGeneration"]
        before_restart = client.get(records_path).json()
        assert sorted(row["statusRevision"] for row in before_restart["items"]) == [
            1,
            2,
            2,
        ]
        stale_preview = post(path + "/record-status-batches/preview", body)
        assert stale_preview["blocks"][0]["blockers"][0]["details"] == {
            "expectedRevision": 1,
            "currentRevision": 2,
        }

    # A new lifespan/service instance reads the same durable result, never reprocesses it.
    with TestClient(
        _app(tmp_path), headers={"x-autoflow-token": "renderer"}
    ) as restarted:
        recovered = restarted.get(base + "/operations/by-idempotency-key/" + key)
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()["result"] == outcome
        assert restarted.get(records_path).json() == before_restart
