from __future__ import annotations

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
from autoflow.application.workflows.service import WorkflowService
from autoflow.domain.workflows.models import WorkflowError
from autoflow.infrastructure.database.core_workflows import SqlAlchemyWorkflowRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
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
    assert prepared.document["content"]["nodes"][0]["data"]["openMode"] == "new_tab"

    factory.dispose()


def test_studio_workflow_routes_keep_project_scopes_separate(tmp_path: Path) -> None:
    database = tmp_path / "studio-project-scope.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
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
