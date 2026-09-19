from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.projects import projects_router
from autoflow.application.projects.overview import ProjectOverviewService
from autoflow.application.projects.service import ProjectService
from autoflow.infrastructure.database.models import Base, ProjectOperationRow
from autoflow.infrastructure.database.projects import SqlAlchemyProjects


def _app(service, overview_service):
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(projects_router(service, overview_service))
    return app


def make_client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'p.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    service = ProjectService(SqlAlchemyProjects(factory))
    return TestClient(_app(service, ProjectOverviewService(factory)))


def test_all_ten_routes_and_dto_names_are_exposed(tmp_path):
    client = make_client(tmp_path)
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/projects/{projectId}" in paths
    assert "/api/v1/projects/{projectId}/operations/{operationId}" in paths
    assert len([p for p in paths if p.startswith("/api/v1/projects")]) == 7
    assert sum(len(methods) for methods in paths.values()) == 10
    assert "/api/v1/workspace/operations/by-idempotency-key/{key}" in paths
    names = client.get("/openapi.json").json()["components"]["schemas"]
    assert {
        "ProjectView",
        "ProjectSummary",
        "ProjectOverview",
        "ProjectPage",
        "ProjectOperationView",
        "ProjectOperationPage",
        "ProjectOpenResult",
        "ProjectCreate",
        "ProjectPatch",
    } <= set(names)
    assert "ProjectResourceLocator" in names
    create_responses = paths["/api/v1/projects"]["post"]["responses"]
    assert {"200", "201", "409", "422"} <= set(create_responses)
    for path in paths.values():
        for operation in path.values():
            assert "401" in operation["responses"]
    assert "HTTPValidationError" not in str(paths)
    assert not any("delete" in methods for methods in paths.values())


def test_workflow_scoped_operations_still_serialize_as_contract_resource_locators(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'p.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    client = TestClient(_app(ProjectService(SqlAlchemyProjects(factory)), ProjectOverviewService(factory)))
    key = "00000000-0000-0000-0000-0000000000f1"
    created = client.post(
        "/api/v1/projects",
        headers={"Idempotency-Key": key},
        json={"name": "工作流操作投影", "description": ""},
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["projectId"]
    now = datetime.now(UTC)
    record_ref = {
        "projectId": project_id,
        "tableId": "00000000-0000-0000-0000-0000000000aa",
        "datasetGeneration": "00000000-0000-0000-0000-0000000000bb",
        "recordKey": {"type": "uuid", "value": "00000000-0000-0000-0000-0000000000cc"},
    }
    # 工作流能力操作把 task/run/执行代次与目标资源存在同一行，用于按任务回查；
    # 项目操作视图按契约只暴露 ResourceLocator，不能因此 500。
    run_scoped = {
        "projectId": project_id,
        "taskId": "00000000-0000-0000-0000-0000000000dd",
        "runId": "00000000-0000-0000-0000-0000000000ee",
        "executionGeneration": 1,
    }
    with factory() as session:
        session.add_all(
            [
                ProjectOperationRow(
                    id="00000000-0000-0000-0000-000000000101",
                    project_id=project_id,
                    idempotency_key="00000000-0000-0000-0000-000000000102",
                    kind="setRecordStatus",
                    request_digest="0" * 64,
                    status="succeeded",
                    status_revision=1,
                    resource={**run_scoped, "type": "record", "recordRef": record_ref},
                    result=None,
                    error=None,
                    created_at=now,
                    updated_at=now,
                    completed_at=now,
                ),
                ProjectOperationRow(
                    id="00000000-0000-0000-0000-000000000103",
                    project_id=project_id,
                    idempotency_key="00000000-0000-0000-0000-000000000104",
                    kind="setRecordStatus",
                    request_digest="1" * 64,
                    status="succeeded",
                    status_revision=1,
                    resource={**run_scoped, "type": "task"},
                    result=None,
                    error=None,
                    created_at=now,
                    updated_at=now,
                    completed_at=now,
                ),
            ]
        )
        session.commit()
    response = client.get(f"/api/v1/projects/{project_id}/operations")
    assert response.status_code == 200, response.text
    resources = {
        item["operationId"]: item["resource"] for item in response.json()["items"]
    }
    assert resources["00000000-0000-0000-0000-000000000101"] == {
        "type": "record",
        "recordRef": record_ref,
    }
    assert resources["00000000-0000-0000-0000-000000000103"] == {
        "type": "task",
        "projectId": project_id,
        "taskId": run_scoped["taskId"],
    }


def test_create_list_patch_open_overview_and_operations(tmp_path):
    client = make_client(tmp_path)
    key1 = "00000000-0000-0000-0000-000000000001"
    created = client.post(
        "/api/v1/projects",
        headers={"Idempotency-Key": key1},
        json={"name": " Alpha ", "description": ""},
    )
    assert created.status_code == 201
    project = created.json()
    project_id = project["projectId"]
    assert (
        client.post(
            "/api/v1/projects",
            headers={"Idempotency-Key": key1},
            json={"name": " Alpha ", "description": ""},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/projects?q=alp").json()["total"] == 1
    listed = client.get("/api/v1/projects?q=alp").json()["items"][0]
    assert listed["availability"] == {
        "automations": "available",
        "data": "available",
        "runs": "available",
        "environments": "available",
        "statistics": "available",
        "sync": "available",
    }
    overview = client.get(f"/api/v1/projects/{project_id}/overview").json()
    assert overview["counts"] == {
        "automations": 0,
        "tables": 0,
        "batches": 0,
        "environments": 0,
    }
    assert overview["activity"] == [] and overview["recent"] == []
    assert overview["dataChanges"]["newRecords"] == 0
    assert overview["availability"] == listed["availability"]
    assert client.get(f"/api/v1/projects/{project_id}/overview?timezone=Nope/Nowhere").status_code == 422
    opened = client.post(f"/api/v1/projects/{project_id}/open").json()
    assert opened["project"]["lastOpenedAt"]
    assert opened["lastOpenedAt"] == opened["project"]["lastOpenedAt"]
    key2 = "00000000-0000-0000-0000-000000000002"
    patched = client.patch(
        f"/api/v1/projects/{project_id}",
        headers={"Idempotency-Key": key2},
        json={"description": "changed", "expectedManagementRevision": 1},
    )
    assert patched.json()["managementRevision"] == 2
    operations = client.get(f"/api/v1/projects/{project_id}/operations").json()
    assert operations["total"] == 2
    assert (
        client.get(
            f"/api/v1/projects/{project_id}/operations?kind=updateProject"
        ).json()["total"]
        == 1
    )
    assert (
        client.get(
            f"/api/v1/projects/{project_id}/operations?status=succeeded&resourceType=project"
        ).json()["total"]
        == 2
    )
    failed = client.get(f"/api/v1/projects/{project_id}/operations?status=failed")
    assert failed.status_code == 200
    assert failed.json()["items"] == [] and failed.json()["total"] == 0
    create_operation_id = client.get(
        f"/api/v1/workspace/operations/by-idempotency-key/{key1}"
    ).json()["operationId"]
    assert (
        client.get(
            f"/api/v1/projects/{project_id}/operations/{create_operation_id}"
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/projects/{project_id}/operations/by-idempotency-key/{key2}"
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/workspace/operations/by-idempotency-key/{key1}"
        ).status_code
        == 200
    )


def test_validation_and_revision_errors_use_envelope(tmp_path):
    client = make_client(tmp_path)
    assert (
        client.post(
            "/api/v1/projects", json={"name": "A", "description": ""}
        ).status_code
        == 422
    )
    key = "00000000-0000-0000-0000-000000000001"
    project = client.post(
        "/api/v1/projects",
        headers={"Idempotency-Key": key},
        json={"name": "A", "description": ""},
    ).json()
    conflict = client.patch(
        f"/api/v1/projects/{project['projectId']}",
        headers={"Idempotency-Key": "00000000-0000-0000-0000-000000000002"},
        json={"name": "B", "expectedManagementRevision": 2},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["details"]["currentRevision"] == 1
    missing = client.get("/api/v1/projects/00000000-0000-0000-0000-000000000099")
    assert missing.json()["error"]["details"]["domainCode"] == "project_not_found"


def test_project_request_validation_has_domain_details(tmp_path):
    client = make_client(tmp_path)
    for response in (
        client.post(
            "/api/v1/projects",
            headers={"Idempotency-Key": "00000000-0000-0000-0000-000000000001"},
            json=None,
        ),
        client.get("/api/v1/projects?pageSize=0"),
        client.get("/api/v1/projects/00000000-0000-0000-0000-not-a-uuid"),
    ):
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert response.json()["error"]["details"]["domainCode"] == "validation_error"
        assert response.json()["error"]["details"]["retryable"] is False


def test_boolean_revision_and_oversized_pages_are_rejected_before_storage(tmp_path):
    client = make_client(tmp_path)
    project = client.post(
        "/api/v1/projects",
        headers={"Idempotency-Key": "00000000-0000-0000-0000-000000000001"},
        json={"name": "Alpha", "description": ""},
    ).json()
    boolean_revision = client.patch(
        f"/api/v1/projects/{project['projectId']}",
        headers={"Idempotency-Key": "00000000-0000-0000-0000-000000000002"},
        json={"description": "must not save", "expectedManagementRevision": True},
    )
    assert boolean_revision.status_code == 422
    assert (
        client.get(f"/api/v1/projects/{project['projectId']}").json()["description"]
        == ""
    )
    for endpoint in (
        "/api/v1/projects?page=9223372036854775808",
        f"/api/v1/projects/{project['projectId']}/operations?page=9223372036854775808",
    ):
        response = client.get(endpoint)
        assert response.status_code == 422
        assert response.json()["error"]["details"]["domainCode"] == "validation_error"
