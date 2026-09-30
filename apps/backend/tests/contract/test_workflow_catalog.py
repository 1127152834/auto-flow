import hashlib
from copy import deepcopy
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.workflow_catalog import workflow_catalog_router
from autoflow.application.workflows.service import WorkflowService
from autoflow.domain.workflows.models import canonical_json
from autoflow.infrastructure.database.models import Base
from autoflow.infrastructure.database.session import create_session_factory
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from tests.fixtures.workflows import workflow_payload


def client(tmp_path):
    factory = create_session_factory(tmp_path / "workflow-catalog.sqlite3")
    Base.metadata.create_all(factory.kw["bind"])
    service = WorkflowService(SqlAlchemyWorkflowRepository(factory))
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(workflow_catalog_router(service))
    return TestClient(app), service


def test_catalog_exposes_only_two_read_routes_and_unique_schema_names(tmp_path):
    api, _service = client(tmp_path)
    openapi = api.get("/openapi.json").json()
    assert set(openapi["paths"]) == {
        "/api/v1/workflows",
        "/api/v1/workflows/{workflowId}",
    }
    assert all(set(methods) == {"get"} for methods in openapi["paths"].values())
    assert {
        "WorkflowCatalogIssue",
        "WorkflowCatalogValidation",
        "WorkflowCatalogItem",
        "WorkflowCatalogList",
        "WorkflowCatalogDetail",
    } <= set(openapi["components"]["schemas"])
    assert all(
        "401" in operation["responses"]
        for methods in openapi["paths"].values()
        for operation in methods.values()
    )


def test_list_and_detail_return_stored_identity_checksum_and_real_validation(tmp_path):
    api, service = client(tmp_path)
    runnable = workflow_payload()
    blocked = deepcopy(workflow_payload(str(uuid4())))
    blocked["content"]["nodes"][0]["data"]["moduleType"] = "group"
    blocked["content"]["nodes"][0]["type"] = "group"
    ready_record = service.create(runnable, str(uuid4()))
    blocked_record = service.create(blocked, str(uuid4()))

    response = api.get("/api/v1/workflows")
    assert response.status_code == 200
    items = {item["workflowId"]: item for item in response.json()["items"]}
    ready = items[ready_record.workflow_id]
    assert ready == {
        "workflowId": ready_record.workflow_id,
        "name": ready_record.name,
        "revision": ready_record.revision,
        "browserEnvironmentVersion": None,
        "checksum": hashlib.sha256(
            canonical_json(ready_record.document).encode()
        ).hexdigest(),
        "validation": {"status": "ready", "runnable": True, "issues": []},
        "createdAt": ready_record.created_at.isoformat().replace("+00:00", "Z"),
        "updatedAt": ready_record.updated_at.isoformat().replace("+00:00", "Z"),
    }
    assert items[blocked_record.workflow_id]["validation"]["status"] == "blocked"
    assert items[blocked_record.workflow_id]["validation"]["runnable"] is False
    assert items[blocked_record.workflow_id]["validation"]["issues"]
    detail = api.get(f"/api/v1/workflows/{ready_record.workflow_id}")
    assert detail.status_code == 200 and detail.json() == ready


def test_invalid_workflow_id_uses_read_error_contract(tmp_path):
    api, _service = client(tmp_path)
    invalid = api.get("/api/v1/workflows/not-a-uuid")
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
