from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from autoflow.application.project_automations.service import ProjectAutomationService
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import (
    Base,
    ProjectOperationRow,
    ProjectRow,
)
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.database.project_automations import (
    SqlAlchemyProjectAutomations,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import create_session_factory
from autoflow.infrastructure.database.workflow_models import WorkflowDocumentRow
from tests.fixtures.workflows import workflow_payload


def setup(tmp_path):
    factory = create_session_factory(tmp_path / "automation.sqlite3")
    engine = factory.kw["bind"]
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    project_id = "00000000-0000-0000-0000-000000000010"
    workflow_id = "00000000-0000-0000-0000-000000000020"
    with factory() as session:
        session.add(
            ProjectRow(
                id=project_id,
                name="P",
                name_key="p",
                description="",
                search_text="p",
                default_resources={
                    "profileId": None,
                    "proxy": {"mode": "sourceDefault"},
                    "modelProviderId": None,
                },
                management_revision=1,
                lifecycle_state="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            WorkflowDocumentRow(
                id=workflow_id,
                name="W",
                document={},
                layout={},
                revision=1,
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    return (
        engine,
        factory,
        ProjectAutomationService(
            SqlAlchemyProjects(factory), SqlAlchemyProjectAutomations(factory)
        ),
        project_id,
        workflow_id,
    )


def write(workflow_id, name="Alpha"):
    return {
        "name": name,
        "description": "",
        "workflowId": workflow_id,
        "inputPlan": {"inputs": []},
        "parameterSchema": [],
        "environmentPolicy": {"source": "newFromProfile"},
        "runPolicy": {
            "maxTasks": 1,
            "concurrency": 1,
            "maxLiveInstances": 1,
            "continueAfterFailure": False,
            "automaticExecutionTimeoutSeconds": 60,
            "manualDeadlineSeconds": 300,
        },
    }


def test_bound_project_workflow_is_visible_and_editable_in_studio(tmp_path):
    from autoflow.application.workflows.documents import WorkflowDocumentService
    from autoflow.application.workflows.service import WorkflowService
    from autoflow.infrastructure.database.workflows import (
        SqlAlchemyWorkflowDocuments,
        SqlAlchemyWorkflowRepository,
    )
    engine, factory, automations, project_id, workflow_id = setup(tmp_path)
    with factory() as session:
        session.get(WorkflowDocumentRow, workflow_id).document = workflow_payload(workflow_id)
        session.commit()
    automations.create(project_id, "00000000-0000-0000-0000-000000000001", write(workflow_id))
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    listed = documents.list_summaries(project_id=project_id)
    assert [item.id for item in listed.items] == [workflow_id]
    saved = documents.get(workflow_id)
    assert saved.to_payload()["projectId"] == project_id
    catalog = WorkflowService(SqlAlchemyWorkflowRepository(factory))
    assert catalog.get(workflow_id).project_id == project_id
    assert catalog.list()[0].project_id == project_id
    payload = saved.to_payload()
    payload["name"] = "项目内编辑"
    updated = documents.update(workflow_id, payload, expected_revision=1, client_request_id="edit")
    assert updated.to_payload()["projectId"] == project_id
    assert updated.name == "项目内编辑"
    from autoflow.domain.workflows.errors import WorkflowDocumentError
    with pytest.raises(WorkflowDocumentError) as deletion:
        documents.delete(workflow_id, expected_revision=updated.revision)
    assert deletion.value.code == "WORKFLOW_IN_USE"
    assert documents.get(workflow_id).revision == updated.revision
    with factory() as session:
        session.get(ProjectRow, project_id).lifecycle_state = "archived"
        session.commit()
    with pytest.raises(ProjectError):
        documents.update(workflow_id, payload, expected_revision=2, client_request_id="archived")
    engine.dispose()


def test_cannot_bind_a_workflow_draft_owned_by_another_project(tmp_path):
    engine, factory, automations, project_id, workflow_id = setup(tmp_path)
    with factory() as session:
        session.get(WorkflowDocumentRow, workflow_id).document = {
            "projectId": "another-project", "nodes": [], "edges": [], "variables": [],
        }
        session.commit()
    with pytest.raises(ProjectError) as raised:
        automations.create(project_id, "00000000-0000-0000-0000-000000000001", write(workflow_id))
    assert raised.value.code == "WORKFLOW_NOT_FOUND"
    with factory() as session:
        assert session.scalars(select(ProjectAutomationRow)).all() == []
    engine.dispose()


def test_atomic_idempotent_create_update_cas_and_snapshot(tmp_path):
    _engine, factory, service, project_id, workflow_id = setup(tmp_path)
    created, _, replayed = service.create(
        project_id, "00000000-0000-0000-0000-000000000001", write(workflow_id)
    )
    assert not replayed
    same, _, replayed = service.create(
        project_id, "00000000-0000-0000-0000-000000000001", write(workflow_id)
    )
    assert replayed and same == created
    changed, _ = service.update(
        project_id,
        created.automation_id,
        "00000000-0000-0000-0000-000000000002",
        {**write(workflow_id, "Beta"), "expectedManagementRevision": 1},
    )
    assert changed.management_revision == 2
    snapshot, _ = service.update(
        project_id,
        created.automation_id,
        "00000000-0000-0000-0000-000000000002",
        {**write(workflow_id, "Beta"), "expectedManagementRevision": 1},
    )
    assert snapshot.management_revision == 2
    unchanged, _ = service.update(
        project_id,
        created.automation_id,
        "00000000-0000-0000-0000-000000000003",
        {**write(workflow_id, "Beta"), "expectedManagementRevision": 2},
    )
    assert unchanged.management_revision == 2
    typed = write(workflow_id, "Beta")
    typed["parameterSchema"] = [
        {
            "parameterId": "00000000-0000-0000-0000-000000000030",
            "name": "值",
            "type": "boolean",
            "required": False,
            "defaultValue": True,
        }
    ]
    typed_change, _ = service.update(
        project_id,
        created.automation_id,
        "00000000-0000-0000-0000-000000000005",
        {**typed, "expectedManagementRevision": 2},
    )
    typed["parameterSchema"][0].update({"type": "number", "defaultValue": 1})
    numeric_change, _ = service.update(
        project_id,
        created.automation_id,
        "00000000-0000-0000-0000-000000000006",
        {**typed, "expectedManagementRevision": 3},
    )
    assert (
        typed_change.management_revision == 3
        and numeric_change.management_revision == 4
    )
    with pytest.raises(ProjectError):
        service.update(
            project_id,
            created.automation_id,
            "00000000-0000-0000-0000-000000000004",
            {**write(workflow_id, "Gamma"), "expectedManagementRevision": 1},
        )
    with factory() as session:
        assert session.scalar(select(ProjectAutomationRow)).name == "Beta"


def test_workflow_unique_parent_scope_and_archive_guard(tmp_path):
    _engine, factory, service, project_id, workflow_id = setup(tmp_path)
    created, _, _ = service.create(
        project_id, "00000000-0000-0000-0000-000000000011", write(workflow_id)
    )
    with pytest.raises(ProjectError):
        service.create(
            project_id,
            "00000000-0000-0000-0000-000000000012",
            write(workflow_id, "Other"),
        )
    assert (
        service.automations.get(
            "00000000-0000-0000-0000-000000000099", created.automation_id
        )
        is None
    )
    with factory() as session:
        session.get(ProjectRow, project_id).lifecycle_state = "archived"
        session.commit()
    assert service.get(project_id, created.automation_id).name == "Alpha"
    replay, _, replayed = service.create(
        project_id, "00000000-0000-0000-0000-000000000011", write(workflow_id)
    )
    assert replayed and replay == created
    with pytest.raises(ProjectError):
        service.update(
            project_id,
            created.automation_id,
            "00000000-0000-0000-0000-000000000013",
            {**write(workflow_id), "expectedManagementRevision": 1},
        )


def test_validation_projects_ready_blocked_and_real_capability_facts(tmp_path):
    _engine, _factory, service, project_id, workflow_id = setup(tmp_path)
    created, _, _ = service.create(
        project_id,
        "00000000-0000-0000-0000-000000000021",
        write(workflow_id),
    )

    class Workflows:
        def get(self, _workflow_id):
            return SimpleNamespace(document=workflow_payload())

    class Resources:
        def inspect_resources(self, _automation):
            return []

    class Capabilities:
        def __init__(self, available=True):
            self.available = available

        def inspect_capabilities(self, _workflow_id):
            return [
                {
                    "capability": "browser.cloakbrowser",
                    "required": True,
                    "available": self.available,
                    "reason": None if self.available else "Kernel missing",
                }
            ]

    ready_service = ProjectAutomationService(
        service.projects,
        service.automations,
        Workflows(),
        Resources(),
        Capabilities(),
    )
    assert ready_service.validation(project_id, created.automation_id).status == "ready"
    blocked_service = ProjectAutomationService(
        service.projects,
        service.automations,
        Workflows(),
        Resources(),
        Capabilities(False),
    )
    blocked = blocked_service.validation(project_id, created.automation_id)
    assert blocked.status == "blocked" and blocked.runnable is False

    class InvalidWorkflows:
        def get(self, _workflow_id):
            document = workflow_payload()
            document["content"]["nodes"][0]["data"]["moduleType"] = "group"
            document["content"]["nodes"][0]["type"] = "group"
            return SimpleNamespace(document=document)

    invalid_workflow = ProjectAutomationService(
        service.projects,
        service.automations,
        InvalidWorkflows(),
        Resources(),
        Capabilities(),
    ).validation(project_id, created.automation_id)
    assert invalid_workflow.status == "blocked"
    assert invalid_workflow.valid is False and invalid_workflow.runnable is False


def test_missing_workflow_is_404_and_leaves_no_automation_or_operation(tmp_path):
    _engine, factory, service, project_id, _workflow_id = setup(tmp_path)
    key = "00000000-0000-0000-0000-000000000031"
    with pytest.raises(ProjectError) as missing:
        service.create(
            project_id,
            key,
            write("00000000-0000-0000-0000-000000000099"),
        )
    assert missing.value.code == "WORKFLOW_NOT_FOUND"
    assert missing.value.details["fields"] == {"workflowId": "Workflow was not found"}
    with factory() as session:
        assert session.scalar(select(ProjectAutomationRow)) is None
        assert (
            session.scalar(
                select(ProjectOperationRow).where(
                    ProjectOperationRow.idempotency_key == key
                )
            )
            is None
        )
