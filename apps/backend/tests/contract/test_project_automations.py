import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.project_automations import project_automations_router
from autoflow.application.project_automations.service import ProjectAutomationService
from autoflow.infrastructure.database.models import (
    Base,
    ProjectOperationRow,
    ProjectRow,
)
from autoflow.infrastructure.database.workflow_models import WorkflowDocumentRow
from autoflow.infrastructure.database.project_automations import (
    SqlAlchemyProjectAutomations,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import create_session_factory


def test_overflowing_json_parameter_is_a_field_error_without_writes(tmp_path):
    api, project_id, workflow_id = client(tmp_path)
    payload = body(workflow_id)
    payload['parameterSchema'][0].update(type='number', defaultValue=12345)
    response = api.post(
        f'/api/v1/projects/{project_id}/automations',
        headers={'Idempotency-Key': str(uuid4()), 'Content-Type': 'application/json'},
        content=json.dumps(payload).replace('12345', '1e400'),
    )
    assert response.status_code == 422, response.text
    assert 'parameterSchema.0.defaultValue' in response.json()['error']['details']['fields']
    with api.app.state.automation_factory() as session:
        assert session.scalars(select(ProjectOperationRow)).all() == []
    assert api.get(f'/api/v1/projects/{project_id}/automations').json()['total'] == 0


def client(tmp_path):
    factory = create_session_factory(tmp_path / "contract.sqlite3")
    Base.metadata.create_all(factory.kw["bind"])
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
    app = FastAPI()
    app.state.automation_factory = factory
    install_error_handlers(app)
    app.include_router(
        project_automations_router(
            ProjectAutomationService(
                SqlAlchemyProjects(factory), SqlAlchemyProjectAutomations(factory)
            )
        )
    )
    return TestClient(app), project_id, workflow_id


def body(workflow_id):
    return {
        "name": "配置",
        "description": "说明",
        "workflowId": workflow_id,
        "inputPlan": {"inputs": []},
        "parameterSchema": [
            {
                "parameterId": "00000000-0000-0000-0000-000000000030",
                "name": "开关",
                "description": "  是否启用后续步骤  ",
                "type": "boolean",
                "required": False,
            }
        ],
        "environmentPolicy": {"source": "newFromProfile", "modelProviderId": None},
        "runPolicy": {
            "maxTasks": 1,
            "concurrency": 1,
            "maxLiveInstances": 1,
            "continueAfterFailure": False,
            "automaticExecutionTimeoutSeconds": 60,
            "manualDeadlineSeconds": 300,
        },
    }


def test_five_routes_dtos_and_no_delete(tmp_path):
    api, _, _ = client(tmp_path)
    openapi = api.get("/openapi.json").json()
    paths = openapi["paths"]
    assert set(paths) == {
        "/api/v1/projects/{projectId}/automations",
        "/api/v1/projects/{projectId}/automations/{automationId}",
        "/api/v1/projects/{projectId}/automations/{automationId}/validation",
    }
    assert set(paths["/api/v1/projects/{projectId}/automations"]) == {"get", "post"}
    assert set(paths["/api/v1/projects/{projectId}/automations/{automationId}"]) == {
        "get",
        "put",
    }
    assert "delete" not in str(paths).lower()
    assert {
        "AutomationView",
        "AutomationWrite",
        "AutomationUpdate",
        "AutomationPage",
        "AutomationValidationView",
    } <= set(openapi["components"]["schemas"])
    schemas = openapi["components"]["schemas"]
    assert {"DataRecordRef", "DataRecordKey", "DataFieldRef"} <= set(schemas)
    assert not {
        "RecordRef",
        "RecordKey",
        "FieldRef",
        "FilterExpression",
        "OrderBy",
    } & set(schemas)


def test_create_list_get_put_validation_and_typed_values(tmp_path):
    api, project_id, workflow_id = client(tmp_path)
    payload = body(workflow_id)
    created = api.post(
        f"/api/v1/projects/{project_id}/automations",
        headers={"Idempotency-Key": "00000000-0000-0000-0000-000000000001"},
        json=payload,
    )
    assert created.status_code == 201
    item = created.json()
    automation_id = item["automationId"]
    assert "defaultValue" not in item["parameterSchema"][0]
    assert item["parameterSchema"][0]["description"] == "是否启用后续步骤"
    assert item["environmentPolicy"]["modelProviderId"] is None
    assert (
        api.get(f"/api/v1/projects/{project_id}/automations?q=配置&sort=name").json()[
            "total"
        ]
        == 1
    )
    detail = api.get(f"/api/v1/projects/{project_id}/automations/{automation_id}")
    assert detail.status_code == 200
    assert detail.json()["parameterSchema"][0]["description"] == "是否启用后续步骤"
    updated_payload = {
        **payload,
        "description": "新版",
        "expectedManagementRevision": 1,
    }
    updated_payload["runPolicy"] = {
        **payload["runPolicy"],
        "automaticExecutionTimeoutSeconds": 0.5,
        "manualDeadlineSeconds": 90.25,
    }
    updated = api.put(
        f"/api/v1/projects/{project_id}/automations/{automation_id}",
        headers={"Idempotency-Key": "00000000-0000-0000-0000-000000000002"},
        json=updated_payload,
    )
    assert updated.json()["managementRevision"] == 2
    assert updated.json()["runPolicy"]["automaticExecutionTimeoutSeconds"] == 0.5
    validation = api.get(
        f"/api/v1/projects/{project_id}/automations/{automation_id}/validation"
    ).json()
    assert validation["status"] == "unavailable" and validation["runnable"] is False
    bad = body(workflow_id)
    bad["parameterSchema"][0]["defaultValue"] = "false"
    assert (
        api.post(
            f"/api/v1/projects/{project_id}/automations",
            headers={"Idempotency-Key": "00000000-0000-0000-0000-000000000003"},
            json=bad,
        ).status_code
        == 422
    )


def test_parent_ownership_is_checked_on_every_item_route(tmp_path):
    api, project_id, workflow_id = client(tmp_path)
    item = api.post(
        f"/api/v1/projects/{project_id}/automations",
        headers={"Idempotency-Key": "00000000-0000-0000-0000-000000000001"},
        json=body(workflow_id),
    ).json()
    other = "00000000-0000-0000-0000-000000000099"
    for method, suffix, kwargs in (
        ("get", item["automationId"], {}),
        (
            "put",
            item["automationId"],
            {
                "headers": {"Idempotency-Key": "00000000-0000-0000-0000-000000000002"},
                "json": {**body(workflow_id), "expectedManagementRevision": 1},
            },
        ),
        ("get", f"{item['automationId']}/validation", {}),
    ):
        assert (
            getattr(api, method)(
                f"/api/v1/projects/{other}/automations/{suffix}", **kwargs
            ).status_code
            == 404
        )


def test_existing_typed_record_identity_and_record_query_round_trip(tmp_path):
    api, project_id, workflow_id = client(tmp_path)
    table_id = "00000000-0000-0000-0000-000000000040"
    generation = "00000000-0000-0000-0000-000000000041"
    field_id = "00000000-0000-0000-0000-000000000042"
    payload = body(workflow_id)
    payload["inputPlan"] = {
        "inputs": [
            {
                "inputId": "00000000-0000-0000-0000-000000000043",
                "alias": "目标记录",
                "tableId": table_id,
                "datasetGeneration": generation,
                "mode": "fixedRecord",
                "required": True,
                "fixedRecord": {
                    "projectId": project_id,
                    "tableId": table_id,
                    "datasetGeneration": generation,
                    "recordKey": {"type": "integer", "value": "42"},
                },
                "fieldBindings": [
                    {
                        "inputFieldId": "00000000-0000-0000-0000-000000000044",
                        "inputFieldAlias": "启用",
                        "fieldRef": {
                            "projectId": project_id,
                            "tableId": table_id,
                            "datasetGeneration": generation,
                            "fieldId": field_id,
                        },
                    }
                ],
                "filter": {
                    "type": "compare",
                    "fieldId": field_id,
                    "operator": "eq",
                    "value": True,
                },
                "orderBy": [{"fieldId": field_id, "direction": "asc"}],
            }
        ]
    }
    response = api.post(
        f"/api/v1/projects/{project_id}/automations",
        headers={"Idempotency-Key": "00000000-0000-0000-0000-000000000051"},
        json=payload,
    )
    assert response.status_code == 201, response.text
    saved = response.json()["inputPlan"]["inputs"][0]
    assert saved["fixedRecord"]["recordKey"] == {"type": "integer", "value": "42"}
    assert saved["filter"]["value"] is True
    assert saved["orderBy"] == [{"fieldId": field_id, "direction": "asc"}]

    foreign = payload.copy()
    foreign["inputPlan"] = {
        "inputs": [
            {
                **payload["inputPlan"]["inputs"][0],
                "fixedRecord": {
                    **payload["inputPlan"]["inputs"][0]["fixedRecord"],
                    "projectId": "00000000-0000-0000-0000-000000000099",
                },
            }
        ]
    }
    rejected = api.post(
        f"/api/v1/projects/{project_id}/automations",
        headers={"Idempotency-Key": "00000000-0000-0000-0000-000000000052"},
        json=foreign,
    )
    assert rejected.status_code == 422


def test_malformed_filter_json_is_422_without_persistent_facts(tmp_path):
    api, project_id, workflow_id = client(tmp_path)
    input_id = "00000000-0000-0000-0000-000000000061"
    table_id = "00000000-0000-0000-0000-000000000062"
    generation = "00000000-0000-0000-0000-000000000063"
    field_id = "00000000-0000-0000-0000-000000000064"
    leaf = {"type": "compare", "fieldId": field_id, "operator": "eq", "value": True}
    too_deep = leaf
    for _ in range(5):
        too_deep = {"type": "not", "item": too_deep}
    too_many_leaves = {
        "type": "all",
        "items": [
            {"type": "all", "items": [leaf] * 50},
            {"type": "all", "items": [leaf] * 50},
            leaf,
        ],
    }
    malformed_queries = (
        ({"type": []}, []),
        ({"type": "all", "items": None}, []),
        ({"type": "not", "item": []}, []),
        ({"type": "compare", "fieldId": [], "operator": "eq", "value": True}, []),
        ({"type": "compare", "fieldId": field_id, "operator": [], "value": True}, []),
        ({"type": "compare", "fieldId": field_id, "operator": "eq", "value": []}, []),
        ({"type": "status", "operator": [], "statusId": "ready"}, []),
        ({"type": "status", "operator": "eq", "statusId": []}, []),
        ({"type": "all", "items": []}, [{"fieldId": [], "direction": "asc"}]),
        ({"type": "all", "items": []}, [{"fieldId": field_id, "direction": []}]),
        ({"type": "all", "items": [leaf] * 51}, []),
        (too_deep, []),
        (too_many_leaves, []),
        (
            {
                "type": "compare",
                "fieldId": field_id,
                "operator": "eq",
                "value": "界" * 65_536,
            },
            [],
        ),
    )
    for index, (filter_value, order_by) in enumerate(malformed_queries, start=1):
        payload = body(workflow_id)
        payload["inputPlan"] = {
            "inputs": [
                {
                    "inputId": input_id,
                    "alias": "输入",
                    "tableId": table_id,
                    "datasetGeneration": generation,
                    "mode": "independent",
                    "required": False,
                    "fieldBindings": [
                        {
                            "inputFieldId": "00000000-0000-0000-0000-000000000065",
                            "inputFieldAlias": "字段",
                            "fieldRef": {
                                "projectId": project_id,
                                "tableId": table_id,
                                "datasetGeneration": generation,
                                "fieldId": field_id,
                            },
                        }
                    ],
                    "filter": filter_value,
                    "orderBy": order_by,
                }
            ]
        }
        response = api.post(
            f"/api/v1/projects/{project_id}/automations",
            headers={"Idempotency-Key": f"00000000-0000-0000-0000-{index:012d}"},
            json=payload,
        )
        assert response.status_code == 422, response.text
    assert api.get(f"/api/v1/projects/{project_id}/automations").json()["total"] == 0
    with api.app.state.automation_factory() as session:
        assert session.scalar(select(ProjectOperationRow)) is None


def test_overflowing_timeout_is_422_without_persistent_facts(tmp_path):
    api, project_id, workflow_id = client(tmp_path)
    for index, field in enumerate(
        ("automaticExecutionTimeoutSeconds", "manualDeadlineSeconds"), start=1
    ):
        payload = body(workflow_id)
        payload["runPolicy"] = {**payload["runPolicy"], field: 10**400}
        response = api.post(
            f"/api/v1/projects/{project_id}/automations",
            headers={"Idempotency-Key": f"00000000-0000-0000-0001-{index:012d}"},
            json=payload,
        )
        assert response.status_code == 422, response.text
    assert api.get(f"/api/v1/projects/{project_id}/automations").json()["total"] == 0
    with api.app.state.automation_factory() as session:
        assert session.scalar(select(ProjectOperationRow)) is None
