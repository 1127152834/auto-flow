"""Project admission of Studio documents using real SQLite and production services.

The existing project-start fixture supplies a resource-resolution seam only.
No test here launches a browser or claims real webpage execution.
"""

from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.workflow_catalog import workflow_catalog_router
from autoflow.application.project_automations.service import ProjectAutomationService
from autoflow.application.workflows.documents import WorkflowDocumentService
from autoflow.application.workflows.service import WorkflowService
from autoflow.domain.workflows.runtime import thaw_json
from autoflow.infrastructure.database.project_automations import (
    SqlAlchemyProjectAutomations,
)
from autoflow.infrastructure.database.project_run_models import ProjectTaskRow
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from autoflow.infrastructure.database.workflows import (
    SqlAlchemyWorkflowDocuments,
    SqlAlchemyWorkflowRepository,
)
from tests.fixtures.workflows import workflow_payload
from tests.integration.test_project_run_start import setup, start_payload


class AvailableResources:
    """Isolate admission shape from installed Profile/kernel availability."""

    def inspect_resources(self, _automation):
        return []


def studio_five_nodes(workflow_id, project_id):
    # Toolbar.exportWorkflow exports business `type` and flat data fields.
    # Use the existing four-node source fixture plus the actual Studio PNG node.
    content = deepcopy(workflow_payload(workflow_id)["content"])
    content.update(id=workflow_id, name="Studio 五节点项目任务", projectId=project_id)
    content["nodes"][0]["data"]["url"] = "http://127.0.0.1:18080/workflow-page.html"
    content["nodes"].append(
        {
            "id": "screenshot",
            "type": "screenshot",
            "position": {"x": 100, "y": 560},
            "data": {
                "moduleType": "screenshot",
                "label": "网页截图",
                "screenshotType": "fullpage",
                "savePath": "",
                "variableName": "capture",
            },
        }
    )
    content["edges"].append(
        {
            "id": "to-screenshot",
            "source": "read",
            "target": "screenshot",
            "type": "smoothstep",
        }
    )
    return content


@pytest.fixture
def project_studio_bridge(tmp_path):
    factory, _, _, coordinator, runtime, project, automation = setup(tmp_path)
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    saved = documents.update(
        automation.workflow_id,
        studio_five_nodes(automation.workflow_id, project.project_id),
        expected_revision=1,
        client_request_id=str(uuid4()),
    )
    catalog = WorkflowService(SqlAlchemyWorkflowRepository(factory))
    automations = ProjectAutomationService(
        SqlAlchemyProjects(factory),
        SqlAlchemyProjectAutomations(factory),
        workflow_service=catalog,
        resource_query=AvailableResources(),
        capability_query=coordinator,
    )
    assert saved.revision == 2
    assert documents.get(saved.id).to_payload()["projectId"] == project.project_id
    assert [node["data"]["moduleType"] for node in saved.document["nodes"]] == [
        "open_page",
        "input_text",
        "click_element",
        "get_element_info",
        "screenshot",
    ]
    yield factory, coordinator, runtime, project, automation, catalog, automations
    factory.dispose()


def test_studio_five_node_project_catalog_is_runnable(project_studio_bridge):
    _, _, _, project, automation, catalog, _ = project_studio_bridge
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(workflow_catalog_router(catalog))
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/workflows/{automation.workflow_id}",
            params={"projectId": project.project_id},
        )
    assert response.status_code == 200, response.text
    assert response.json()["validation"] == {
        "status": "ready",
        "runnable": True,
        "issues": [],
    }, response.text


def test_studio_five_node_project_automation_validation_is_ready(project_studio_bridge):
    _, _, _, project, automation, _, automations = project_studio_bridge
    validation = automations.validation(project.project_id, automation.automation_id)
    assert validation.status == "ready", validation
    assert validation.runnable and validation.valid
    assert validation.issues == []


def test_studio_five_node_batch_freezes_full_document_and_preserves_save(
    project_studio_bridge,
):
    factory, coordinator, runtime, project, automation, catalog, _ = (
        project_studio_bridge
    )
    before = deepcopy(catalog.get(automation.workflow_id).document)
    batch, _, replayed = coordinator.start(
        project.project_id,
        automation.automation_id,
        str(uuid4()),
        start_payload(automation),
    )
    assert not replayed
    with factory() as session:
        tasks = session.scalars(
            select(ProjectTaskRow).where(ProjectTaskRow.batch_id == batch.batch_id)
        ).all()
        assert len(tasks) == 1
        run = session.get(WorkflowRunRow, tasks[0].run_id)
        assert run is not None
        prepared = runtime.query_prepared_content(
            prepared_content_id=run.prepared_content_id
        )
    assert prepared is not None
    assert thaw_json(prepared.document) == before
    assert len(thaw_json(prepared.document)["content"]["nodes"]) == 5
    assert catalog.get(automation.workflow_id).document == before
    assert catalog.get(automation.workflow_id).revision == 2


def test_existing_frozen_chain_v1_survives_studio_document_replacement(tmp_path):
    factory, _, _, _coordinator, runtime, project, automation = setup(tmp_path)
    try:
        operation_id = str(uuid4())
        prepared = runtime.prepare_content(
            prepare_operation_id=operation_id,
            workflow_id=automation.workflow_id,
            source_revision=1,
            available_capabilities=["browser.cloakbrowser"],
        )
        assert prepared.adapter_version == "webrpa-chain/v1"
        frozen_document = thaw_json(prepared.document)
        frozen_plan = thaw_json(prepared.execution_plan)
        assert frozen_plan["orderedNodeIds"] == ["open", "input", "click", "read"]
        documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
        documents.update(
            automation.workflow_id,
            studio_five_nodes(automation.workflow_id, project.project_id),
            expected_revision=1,
            client_request_id=str(uuid4()),
        )
        recovered = runtime.prepare_content(
            prepare_operation_id=operation_id,
            workflow_id=automation.workflow_id,
            source_revision=1,
            available_capabilities=["browser.cloakbrowser"],
        )
        assert recovered.prepared_content_id == prepared.prepared_content_id
        assert recovered.adapter_version == "webrpa-chain/v1"
        assert thaw_json(recovered.document) == frozen_document
        assert thaw_json(recovered.execution_plan) == frozen_plan
        with factory() as session:
            run = runtime.prepare_run(
                run_request_id=str(uuid4()),
                prepared_content_id=recovered.prepared_content_id,
                parameters={},
                input_snapshot_ref=None,
                resource_request={"browser": "none"},
                capability_bindings=[],
                uow=session,
            )
            session.commit()
        restored = runtime.query_run(run_id=run.run_id)
        assert (
            restored is not None
            and restored.prepared_content_id == prepared.prepared_content_id
        )
    finally:
        factory.dispose()
