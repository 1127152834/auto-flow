from uuid import uuid4

from sqlalchemy import select

from autoflow.infrastructure.database.workflow_models import WorkflowDocumentRow
from tests.contract.test_project_automations import body, client


def test_owned_workflow_creation_replay_and_conflict_rollback(tmp_path):
    api, project, old_workflow = client(tmp_path)
    payload = body(old_workflow)
    payload.pop("workflowId")
    key = {"Idempotency-Key": str(uuid4())}
    url = f"/api/v1/projects/{project}/automations"
    first = api.post(url, json=payload, headers=key)
    assert first.status_code == 201, first.text
    value = first.json()
    assert value["workflowId"] != old_workflow
    replay = api.post(url, json=payload, headers=key)
    assert replay.status_code == 200
    assert replay.json() == value
    with api.app.state.automation_factory() as session:
        rows = session.scalars(select(WorkflowDocumentRow)).all()
        assert len(rows) == 2
        owned = session.get(WorkflowDocumentRow, value["workflowId"])
        assert owned.document["nodes"] == []
        assert owned.document["projectId"] == project
    conflict = api.post(url, json=payload, headers={"Idempotency-Key": str(uuid4())})
    assert conflict.status_code == 409
    with api.app.state.automation_factory() as session:
        assert len(session.scalars(select(WorkflowDocumentRow)).all()) == 2
    old = api.post(url, json=body(old_workflow), headers={"Idempotency-Key": str(uuid4())})
    assert old.status_code == 422
