from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.workflow_catalog import workflow_catalog_router
from autoflow.adapters.http.workflows import workflows_router
from autoflow.application.workflows.core_runtime import WorkflowRuntimeService
from autoflow.application.workflows.documents import WorkflowDocumentService
from autoflow.application.workflows.runs import WorkflowRunService
from autoflow.application.workflows.service import WorkflowService
from autoflow.domain.projects.models import ProjectError
from autoflow.domain.workflows.errors import WorkflowDocumentError
from autoflow.domain.workflows.models import WorkflowError
from autoflow.domain.workflows.runs import WorkflowRunError, WorkflowRunStart
from autoflow.infrastructure.database.core_workflows import SqlAlchemyWorkflowRepository
from autoflow.infrastructure.database.models import ProjectRow
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_runs import SqlAlchemyWorkflowRuns
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowDocuments
from tests.fixtures.workflows import workflow_payload


def _payload(name: str = "项目工作流", project_id: str | None = None) -> dict:
    payload = {
        "id": str(uuid4()),
        "name": name,
        "schemaVersion": 3,
        "nodes": [
            {
                "id": "open",
                "type": "open_page",
                "position": {"x": 0, "y": 0},
                "data": {
                    "moduleType": "open_page",
                    "url": "https://example.invalid",
                },
            }
        ],
        "edges": [],
        "variables": [],
    }
    if project_id is not None:
        payload["projectId"] = project_id
    return payload


def _project(factory, project_id: str, state: str = "active") -> None:
    now = datetime.now(UTC)
    with factory() as session:
        session.add(ProjectRow(id=project_id, name=project_id, name_key=project_id,
            description="", search_text=project_id, default_resources={},
            management_revision=1, lifecycle_state=state, created_at=now, updated_at=now))
        session.commit()


@pytest.mark.parametrize("state,code", [("archived", "LIFECYCLE_CONFLICT"), ("closing", "PROJECT_CLOSING"), ("deleted", "PROJECT_NOT_FOUND")])
def test_studio_run_admission_checks_stored_owner_without_client_scope(tmp_path, state, code):
    database = tmp_path / "run-project.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    _project(factory, "owner")
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    saved = documents.create(_payload(project_id="owner"), client_request_id="create")
    with factory() as session:
        session.get(ProjectRow, "owner").lifecycle_state = state
        session.commit()
    runs = WorkflowRunService(SqlAlchemyWorkflowRuns(factory))
    # The editor rebuilds its draft snapshot without project metadata. Stored
    # ownership must still stop archived/deleting projects from starting work.
    request = WorkflowRunStart("run", saved.id, saved.id, saved.name, {"nodes": []}, {}, "profile", {}, "run")
    with pytest.raises(WorkflowRunError) as failure:
        runs.start(request)
    assert failure.value.code == code
    assert runs.list_runs(document_id=None, cursor=0, limit=20)[1] == 0


def test_studio_run_resolves_owner_and_rejects_cross_project_snapshot(tmp_path):
    database = tmp_path / "run-owner.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    for owner in ("owner", "other"):
        _project(factory, owner)
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    saved = documents.create(_payload(project_id="owner"), client_request_id="create")
    runs = WorkflowRunService(SqlAlchemyWorkflowRuns(factory))
    from dataclasses import replace
    request = WorkflowRunStart("run", saved.id, saved.id, saved.name, {"nodes": []}, {}, "profile", {}, "run")
    other = documents.create(_payload(project_id="other"), client_request_id="other")
    for conflicting in (
        replace(request, project_id="other"),
        replace(request, document_snapshot={"nodes": [], "projectId": "other"}),
        replace(request, document_id=other.id),
    ):
        with pytest.raises(WorkflowRunError) as failure:
            runs.start(conflicting)
        assert failure.value.code == "WORKFLOW_PROJECT_MISMATCH"
    created = runs.start(request)
    assert created.project_id == "owner"
    assert WorkflowRunService(SqlAlchemyWorkflowRuns(factory)).get("run").project_id == "owner"
    assert runs.start(request) == created


def test_unsaved_project_run_keeps_identity_without_creating_a_workflow(tmp_path):
    database = tmp_path / "run-unsaved.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    _project(factory, "owner")
    runs = WorkflowRunService(SqlAlchemyWorkflowRuns(factory))
    request = WorkflowRunStart("run", "unsaved", "unsaved", "未保存", {"nodes": []}, {}, "profile", {}, "debug", project_id="owner")
    assert runs.start(request).project_id == "owner"
    assert WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory)).list_summaries().items == ()
    runs.finish("run", status="stopped", cleanup_completed=True)
    with factory() as session:
        session.get(ProjectRow, "owner").lifecycle_state = "archived"
        session.commit()
    # Query/replay of the identical admitted command is not a second start.
    assert runs.start(request).status == "stopped"


@pytest.mark.parametrize("workflow_id", [str(uuid4()), "V1StGXR8_Z5jdHi6B-myT"])
@pytest.mark.parametrize("versioned", [False, True])
def test_direct_studio_document_is_visible_to_project_catalog_and_runtime(
    tmp_path: Path, workflow_id: str, versioned: bool,
) -> None:
    database = tmp_path / "studio-project-catalog.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    payload = _payload()
    payload["id"] = workflow_id
    if not versioned:
        del payload["schemaVersion"]
    saved = documents.create(payload, client_request_id="studio-create")

    repository = SqlAlchemyWorkflowRepository(factory)
    catalog = WorkflowService(repository)
    record = catalog.get(saved.id)
    assert record.workflow_id == saved.id
    assert record.name == "项目工作流"
    assert record.document["source"]["product"] == "WebRPA"
    assert record.document["content"]["nodes"][0]["id"] == "open"
    assert [item.workflow_id for item in catalog.list()] == [saved.id]
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(workflow_catalog_router(catalog))
    client = TestClient(app)
    response = client.get(f"/api/v1/workflows/{saved.id}")
    assert response.status_code == 200, response.text
    assert response.json()["validation"]["runnable"] is True

    runtime = WorkflowRuntimeService(factory, repository)
    prepared = runtime.prepare_content(
        prepare_operation_id=str(uuid4()),
        workflow_id=saved.id,
        source_revision=saved.revision,
        available_capabilities=["browser.cloakbrowser"],
    )
    assert prepared.document["content"]["name"] == "项目工作流"
    # v3 preparation validates defaults without changing the saved run snapshot.
    frozen_data = prepared.document["content"]["nodes"][0]["data"]
    assert frozen_data == record.document["content"]["nodes"][0]["data"]
    assert "openMode" not in frozen_data

    factory.dispose()


def test_studio_workflow_routes_keep_project_scopes_separate(tmp_path: Path) -> None:
    database = tmp_path / "studio-project-scope.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    _project(factory, "project-a")
    _project(factory, "project-b")
    first = documents.create(_payload("甲流程", "project-a"), client_request_id="a")
    second = documents.create(_payload("乙流程", "project-b"), client_request_id="b")
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(workflows_router(documents))
    client = TestClient(app)

    listed = client.get("/api/workflows?projectId=project-a")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [first.id]
    assert client.get(f"/api/workflows/{second.id}?projectId=project-a").status_code == 404

    update = client.put(
        f"/api/workflows/{second.id}",
        json={
            **_payload("越权", "project-a"),
            "id": second.id,
            "expectedRevision": second.revision,
            "clientRequestId": "cross-project-update",
        },
    )
    assert update.status_code == 404
    assert documents.get(second.id).name == "乙流程"
    factory.dispose()


@pytest.mark.parametrize("action", ["create", "update", "delete", "catalog_save"])
def test_project_lifecycle_guards_studio_document_writes(tmp_path: Path, action: str) -> None:
    database = tmp_path / "archive.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    _project(factory, "project")
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    saved = documents.create(_payload(project_id="project"), client_request_id="create")
    with factory() as session:
        session.get(ProjectRow, "project").lifecycle_state = "archived"
        session.commit()
    with pytest.raises(ProjectError) as raised:
        if action == "create":
            documents.create(_payload(project_id="project"), client_request_id="other")
        elif action == "update":
            # Omitting caller context cannot bypass the stored owner's lifecycle.
            payload = saved.to_payload()
            payload.pop("projectId")
            payload["name"] = "试图写入归档项目"
            documents.update(saved.id, payload, expected_revision=1, client_request_id="update")
        elif action == "delete":
            documents.delete(saved.id, expected_revision=1)
        else:
            catalog = WorkflowService(SqlAlchemyWorkflowRepository(factory))
            record = catalog.get(saved.id)
            catalog.save(saved.id, record.document, 1, str(uuid4()))
    assert raised.value.code == "LIFECYCLE_CONFLICT"
    assert documents.get(saved.id).revision == 1
    factory.dispose()


def test_project_filter_is_applied_before_pagination(tmp_path: Path) -> None:
    database = tmp_path / "pages.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    _project(factory, "a")
    _project(factory, "b")
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    expected = []
    for index in range(5):
        saved = documents.create(_payload(project_id="a"), client_request_id=f"a-{index}")
        expected.insert(0, saved.id)
        documents.create(_payload(project_id="b"), client_request_id=f"b-{index}")
    first = documents.list_summaries(project_id="a", limit=2)
    second = documents.list_summaries(project_id="a", limit=2, cursor=first.next_cursor)
    third = documents.list_summaries(project_id="a", limit=2, cursor=second.next_cursor)
    assert [item.id for page in (first, second, third) for item in page.items] == expected
    assert third.next_cursor is None
    factory.dispose()


def test_workflow_project_is_preserved_when_save_omits_context(tmp_path: Path) -> None:
    database = tmp_path / "owner.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    _project(factory, "project")
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    saved = documents.create(_payload(project_id="project"), client_request_id="create")
    payload = saved.to_payload()
    payload.pop("projectId")
    documents.update(saved.id, payload, expected_revision=1, client_request_id="update")
    assert documents.get(saved.id).to_payload()["projectId"] == "project"
    assert [item.id for item in documents.list_summaries(project_id="project").items] == [saved.id]
    factory.dispose()


def test_new_workflow_rejects_missing_project(tmp_path: Path) -> None:
    database = tmp_path / "missing-project.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    with pytest.raises(ProjectError) as raised:
        documents.create(_payload(project_id="missing"), client_request_id="create")
    assert raised.value.code == "PROJECT_NOT_FOUND"
    assert documents.list_summaries().items == ()
    factory.dispose()


@pytest.mark.parametrize("invalid", [[], {}, False, 1, "", " " * 3, "x" * 201])
def test_malformed_project_reference_is_a_document_error(tmp_path: Path, invalid) -> None:
    database = tmp_path / "invalid-owner.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    payload = _payload()
    payload["projectId"] = invalid
    with pytest.raises(WorkflowDocumentError) as raised:
        documents.create(payload, client_request_id="create")
    assert raised.value.status == 422
    assert raised.value.details["path"] == "projectId"
    factory.dispose()


def test_deleted_project_is_hidden_from_both_catalogs(tmp_path: Path) -> None:
    database = tmp_path / "deleted.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    _project(factory, "project")
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    saved = documents.create(_payload(project_id="project"), client_request_id="create")
    catalog = WorkflowService(SqlAlchemyWorkflowRepository(factory))
    with factory() as session:
        session.get(ProjectRow, "project").lifecycle_state = "deleted"
        session.commit()
    assert documents.list_summaries().items == ()
    assert catalog.list() == []
    for service in (documents, catalog):
        with pytest.raises(ProjectError) as raised:
            service.get(saved.id)
        assert raised.value.code == "PROJECT_NOT_FOUND"
    factory.dispose()


def test_project_document_opens_in_studio_and_saves_without_changing_identity(tmp_path: Path) -> None:
    database = tmp_path / "project-studio-roundtrip.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    catalog = WorkflowService(SqlAlchemyWorkflowRepository(factory))
    original = workflow_payload()
    record = catalog.create(original, str(uuid4()))
    stored_content = record.document["content"]
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    payload = documents.get(record.workflow_id).to_payload()
    assert payload["id"] == record.workflow_id
    assert payload["nodes"] == stored_content["nodes"]
    assert payload["edges"] == stored_content["edges"]
    assert payload["variables"] == stored_content["variables"]
    assert catalog.get(record.workflow_id) == record  # Reading does not rewrite storage.
    payload["name"] = "Studio 内编辑"
    saved = documents.update(record.workflow_id, payload, expected_revision=record.revision, client_request_id="studio-save")
    reopened = catalog.get(record.workflow_id)
    assert reopened.workflow_id == record.workflow_id
    assert reopened.revision == saved.revision == record.revision + 1
    assert reopened.name == "Studio 内编辑"
    assert reopened.document["content"]["nodes"] == stored_content["nodes"]
    factory.dispose()


@pytest.mark.parametrize("legacy", [
    {"schemaVersion": 2, "nodes": [], "edges": [], "variables": []},
    {"schemaVersion": 3, "nodes": [{"id": "old", "type": "open_page", "config": {"url": "https://example.invalid"}}], "edges": [], "variables": []},
])
def test_retired_documents_remain_legacy(tmp_path: Path, legacy: dict) -> None:
    database = tmp_path / "legacy.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    saved = documents.create({"id": str(uuid4()), "name": "旧流程", **legacy}, client_request_id="old")
    catalog = WorkflowService(SqlAlchemyWorkflowRepository(factory))
    assert catalog.list() == []
    with pytest.raises(WorkflowError) as raised:
        catalog.get(saved.id)
    assert raised.value.code == "WORKFLOW_LEGACY_DOCUMENT_UNSUPPORTED"
    assert documents.get(saved.id).document == saved.document
    factory.dispose()
