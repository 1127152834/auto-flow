from uuid import uuid4

from fastapi.testclient import TestClient

from autoflow.infrastructure.database.project_data_models import DataTableRow
from tests.contract.test_settings_dashboard import _app


def test_unpublished_import_candidates_are_invisible_to_public_read_and_write(tmp_path):
    app = _app(tmp_path)
    with TestClient(app, headers={"x-autoflow-token": "renderer"}) as client:
        project = client.post(
            "/api/v1/projects",
            headers={"Idempotency-Key": str(uuid4())},
            json={"name": "候选隔离"},
        ).json()["projectId"]
        root = f"/api/v1/projects/{project}/tables"
        table = client.post(
            root, headers={"Idempotency-Key": str(uuid4())}, json={"name": "隐藏候选"}
        ).json()
        table_id = table["tableId"]
        with app.state.session_factory.begin() as session:
            session.get(DataTableRow, table_id).published = False
        listing = client.get(root)
        assert listing.status_code == 200, listing.text
        assert listing.json()["items"] == []
        assert listing.json()["total"] == 0
        for path in ("", "/fields", "/statuses", "/records"):
            response = client.get(
                root + "/" + table_id + path,
                params={"datasetGeneration": table["datasetGeneration"]}
                if path == "/records"
                else {},
            )
            assert response.status_code == 404, (path, response.text)
        patch = client.patch(
            root + "/" + table_id,
            headers={"Idempotency-Key": str(uuid4())},
            json={"name": "泄露", "expectedTableRevision": table["tableRevision"]},
        )
        assert patch.status_code == 404, patch.text
        record = client.post(
            root + "/" + table_id + "/records",
            headers={"Idempotency-Key": str(uuid4())},
            json={"datasetGeneration": table["datasetGeneration"], "values": []},
        )
        assert record.status_code == 404, record.text
        with app.state.session_factory.begin() as session:
            session.get(DataTableRow, table_id).published = True
        assert client.get(root).json()["total"] == 1
        assert client.get(root + "/" + table_id).status_code == 200
