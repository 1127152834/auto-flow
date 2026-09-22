from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.workflows import workflows_router
from autoflow.application.workflows.core_runtime import WorkflowRuntimeService
from autoflow.application.workflows.documents import WorkflowDocumentService
from autoflow.application.workflows.service import WorkflowService
from autoflow.infrastructure.database.core_workflows import SqlAlchemyWorkflowRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowDocuments
from fastapi import FastAPI
from fastapi.testclient import TestClient


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


def test_direct_studio_document_is_visible_to_project_catalog_and_runtime(
    tmp_path: Path,
) -> None:
    database = tmp_path / "studio-project-catalog.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    saved = documents.create(_payload(), client_request_id="studio-create")

    repository = SqlAlchemyWorkflowRepository(factory)
    catalog = WorkflowService(repository)
    record = catalog.get(saved.id)
    assert record.workflow_id == saved.id
    assert record.name == "项目工作流"
    assert record.document["source"]["product"] == "WebRPA"
    assert record.document["content"]["nodes"][0]["id"] == "open"
    assert [item.workflow_id for item in catalog.list()] == [saved.id]

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
