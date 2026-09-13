import base64
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_data_models import (
    DataGenerationRow,
    DataRecordRow,
)
from autoflow.infrastructure.database.project_data_status_batch_models import (
    DataStatusBatchBlockRow,
    DataStatusBatchRow,
)
from tests.contract.test_settings_dashboard import _app


def uid() -> str:
    return str(uuid4())


def test_status_usage_projects_current_records_and_active_batch_references(tmp_path):
    app = _app(tmp_path)
    with TestClient(app, headers={"x-autoflow-token": "renderer"}) as client:

        def post(path, body):
            return client.post(path, json=body, headers={"Idempotency-Key": uid()})

        project = post("/api/v1/projects", {"name": "Usage"}).json()["projectId"]
        table = post(f"/api/v1/projects/{project}/tables", {"name": "Rows"}).json()
        base = f"/api/v1/projects/{project}/tables/{table['tableId']}"
        statuses = []
        revision = 1
        for order, name in enumerate(("Current", "Destination", "Unused")):
            status = post(
                base + "/statuses",
                {
                    "name": name,
                    "color": "#123456",
                    "order": order,
                    "expectedTableRevision": revision,
                },
            ).json()
            statuses.append(status)
            revision += 1
        current = post(
            base + "/records",
            {"datasetGeneration": table["datasetGeneration"], "values": []},
        ).json()
        null_record = post(
            base + "/records",
            {"datasetGeneration": table["datasetGeneration"], "values": []},
        ).json()
        changed = client.put(
            base
            + "/records/"
            + base64.urlsafe_b64encode(current["ref"]["recordKey"]["value"].encode())
            .decode()
            .rstrip("=")
            + "/status",
            headers={"Idempotency-Key": uid()},
            json={
                "datasetGeneration": table["datasetGeneration"],
                "recordKeyType": current["ref"]["recordKey"]["type"],
                "statusId": statuses[0]["statusId"],
                "expectedStatusRevision": 1,
            },
        )
        assert changed.status_code == 200, changed.text

        now = datetime.now(UTC)
        old_generation, operation_id, cancelled_id = uid(), uid(), uid()
        with app.state.session_factory.begin() as session:
            session.add(
                DataGenerationRow(
                    id=old_generation,
                    project_id=project,
                    table_id=table["tableId"],
                    identity={"kind": "uuid"},
                    source={"kind": "local"},
                    created_at=now,
                )
            )
            session.flush()
            session.add(
                DataRecordRow(
                    project_id=project,
                    table_id=table["tableId"],
                    dataset_generation=old_generation,
                    key_type="uuid",
                    key_value=uid(),
                    values_json={},
                    record_slots=[],
                    status_id=statuses[0]["statusId"],
                    current_environment_id=None,
                    content_revision=1,
                    status_revision=1,
                    link_revision=1,
                    deleted=False,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add_all(
                [
                    ProjectOperationRow(
                        id=operation_id,
                        project_id=project,
                        idempotency_key=uid(),
                        kind="setRecordStatuses",
                        request_digest="0" * 64,
                        status="running",
                        status_revision=1,
                        resource={
                            "type": "table",
                            "projectId": project,
                            "tableId": table["tableId"],
                        },
                        result=None,
                        error=None,
                        created_at=now,
                        updated_at=now,
                        completed_at=None,
                    ),
                    ProjectOperationRow(
                        id=cancelled_id,
                        project_id=project,
                        idempotency_key=uid(),
                        kind="setRecordStatuses",
                        request_digest="1" * 64,
                        status="accepted",
                        status_revision=1,
                        resource={
                            "type": "table",
                            "projectId": project,
                            "tableId": table["tableId"],
                        },
                        result=None,
                        error=None,
                        created_at=now,
                        updated_at=now,
                        completed_at=None,
                    ),
                ]
            )
            session.flush()
            session.add_all(
                [
                    DataStatusBatchRow(
                        operation_id=operation_id,
                        project_id=project,
                        table_id=table["tableId"],
                        status_id=statuses[1]["statusId"],
                        request={},
                        block_size=100,
                        cancel_requested=False,
                    ),
                    DataStatusBatchRow(
                        operation_id=cancelled_id,
                        project_id=project,
                        table_id=table["tableId"],
                        status_id=statuses[0]["statusId"],
                        request={},
                        block_size=100,
                        cancel_requested=True,
                    ),
                ]
            )
            session.flush()
            session.add_all(
                [
                    DataStatusBatchBlockRow(
                        operation_id=operation_id,
                        block_index=0,
                        targets=[
                            {"recordRef": current["ref"], "expectedStatusRevision": 2},
                            {"recordRef": current["ref"], "expectedStatusRevision": 2},
                            {
                                "recordRef": null_record["ref"],
                                "expectedStatusRevision": 1,
                            },
                        ],
                        state="notStarted",
                        blockers=[],
                        committed_revisions=[],
                    ),
                    DataStatusBatchBlockRow(
                        operation_id=cancelled_id,
                        block_index=0,
                        targets=[
                            {"recordRef": current["ref"], "expectedStatusRevision": 2}
                        ],
                        state="notStarted",
                        blockers=[],
                        committed_revisions=[],
                    ),
                ]
            )

        response = client.get(base + "/statuses/usage")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["datasetGeneration"] == table["datasetGeneration"]
        assert datetime.fromisoformat(payload["calculatedAt"])
        assert payload["configurationReferences"] == {"availability": "notImplemented"}
        assert payload["items"] == [
            {
                "statusId": statuses[0]["statusId"],
                "currentRecords": 1,
                "activeBatchOperations": 1,
            },
            {
                "statusId": statuses[1]["statusId"],
                "currentRecords": 0,
                "activeBatchOperations": 1,
            },
            {
                "statusId": statuses[2]["statusId"],
                "currentRecords": 0,
                "activeBatchOperations": 0,
            },
        ]

        with app.state.session_factory.begin() as session:
            session.get(ProjectOperationRow, operation_id).status = "succeeded"
            session.get(ProjectRow, project).lifecycle_state = "archived"
        archived = client.get(base + "/statuses/usage")
        assert archived.status_code == 200
        assert all(
            item["activeBatchOperations"] == 0 for item in archived.json()["items"]
        )


def test_status_usage_rejects_cross_project_table_and_usage_is_not_a_status_id(
    tmp_path,
):
    app = _app(tmp_path)
    with TestClient(app, headers={"x-autoflow-token": "renderer"}) as client:

        def post(path, body):
            return client.post(path, json=body, headers={"Idempotency-Key": uid()})

        first = post("/api/v1/projects", {"name": "First"}).json()["projectId"]
        second = post("/api/v1/projects", {"name": "Second"}).json()["projectId"]
        table = post(f"/api/v1/projects/{first}/tables", {"name": "Rows"}).json()
        assert (
            client.get(
                f"/api/v1/projects/{second}/tables/{table['tableId']}/statuses/usage"
            ).status_code
            == 404
        )


def test_status_usage_keeps_one_sqlite_read_snapshot_during_concurrent_change(tmp_path):
    import sqlite3

    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    app = _app(tmp_path)
    path = tmp_path / "data" / "autoflow.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
    with TestClient(app, headers={"x-autoflow-token": "renderer"}) as client:

        def post(url, body):
            result = client.post(url, headers={"Idempotency-Key": uid()}, json=body)
            assert result.status_code in (200, 201), result.text
            return result.json()

        project = post("/api/v1/projects", {"name": "Consistent"})["projectId"]
        table = post(f"/api/v1/projects/{project}/tables", {"name": "Rows"})
        base = f"/api/v1/projects/{project}/tables/{table['tableId']}"
        status = post(
            base + "/statuses",
            {
                "name": "Ready",
                "color": "#123456",
                "order": 0,
                "expectedTableRevision": 1,
            },
        )
        post(
            base + "/records",
            {"datasetGeneration": table["datasetGeneration"], "values": []},
        )
        changed = []

        def concurrent_write(
            connection, cursor, statement, parameters, context, executemany
        ):
            if (
                "count(*)" in statement.lower()
                and "project_data_records.status_id" in statement
                and not changed
            ):
                changed.append(True)
                with sqlite3.connect(path) as writer:
                    writer.execute(
                        "UPDATE project_data_records SET status_id=?",
                        (status["statusId"],),
                    )

        event.listen(Engine, "before_cursor_execute", concurrent_write)
        try:
            result = client.get(base + "/statuses/usage")
        finally:
            event.remove(Engine, "before_cursor_execute", concurrent_write)
        assert result.status_code == 200, result.text
        assert changed == [True]
        assert result.json()["items"][0]["currentRecords"] == 0
        assert (
            client.get(base + "/statuses/usage").json()["items"][0]["currentRecords"]
            == 1
        )
