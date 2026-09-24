"""Project defaults freeze execution choices without rewriting editor documents."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from autoflow.domain.workflows.runs import WorkflowRunError
from autoflow.infrastructure.database.models import ProjectRow
from tests.unit.workflows.test_run_resource_retry import RetryHarness


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit", [False, True])
async def test_project_default_only_fills_execution_copy(
    tmp_path: Path, explicit: bool
) -> None:
    harness = RetryHarness(tmp_path)
    try:
        with harness.sessions() as session:
            session.add(
                ProjectRow(
                    id="project",
                    name="project",
                    name_key="project",
                    description="",
                    search_text="project",
                    default_resources={},
                    management_revision=1,
                    lifecycle_state="active",
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            session.commit()
        harness.request["projectId"] = "project"
        harness.request["documentId"] = "unsaved-project-flow"
        harness.request["document"]["id"] = "unsaved-project-flow"
        if not explicit:
            del harness.request["document"]["nodes"][1]["data"]["config"]["modelId"]
        raw = copy.deepcopy(harness.request)
        calls = []

        def default_model(project_id: str) -> str:
            calls.append(project_id)
            return "project-default"

        harness.coordinator._resolve_default_model = default_model
        await harness.coordinator.start("unsaved-project-flow", harness.request)
        payload = harness.workers.payloads[0]
        assert payload["document"]["nodes"][1]["data"]["config"]["modelId"] == (
            "model-1" if explicit else "project-default"
        )
        assert calls == ([] if explicit else ["project"])
        assert harness.request == raw
        snapshot = harness.runs.get("retry-run").document_snapshot
        config = snapshot["nodes"][1]["data"]["config"]
        assert config.get("modelId") == ("model-1" if explicit else None)
        assert harness.model.reads == [("model-1" if explicit else "project-default")]
        assert harness.runs.get("retry-run").profile_snapshot.get(
            "resolvedDefaultModelId"
        ) == (None if explicit else "project-default")
        # A changed project default must not change an already accepted run.
        harness.coordinator._resolve_default_model = lambda _: "other-default"
        await harness.coordinator.start("unsaved-project-flow", raw)
        assert len(harness.workers.payloads) == 1
    finally:
        harness.sessions.dispose()


@pytest.mark.asyncio
async def test_invalid_explicit_model_is_not_hidden_by_default(tmp_path: Path) -> None:
    harness = RetryHarness(tmp_path)
    try:
        harness.request["document"]["nodes"][1]["data"]["config"]["modelId"] = 123
        harness.request["projectId"] = "project"
        harness.request["documentId"] = "unsaved-project-flow"
        harness.request["document"]["id"] = "unsaved-project-flow"
        harness.coordinator._resolve_default_model = lambda _: "project-default"
        with pytest.raises(WorkflowRunError) as error:
            await harness.coordinator.start("unsaved-project-flow", harness.request)
        assert error.value.code == "MODEL_ID_INVALID"
        assert error.value.details == {"nodeId": "ask", "path": "config.modelId"}
        assert not harness.workers.payloads
    finally:
        harness.sessions.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("via_module", [False, True])
async def test_dependency_execution_inherits_without_mutating_saved_definition(
    tmp_path: Path, via_module: bool
) -> None:
    from autoflow.application.workflows.modules import CustomModuleService
    from autoflow.infrastructure.database.workflow_modules import (
        SqlAlchemyWorkflowModules,
    )

    harness = RetryHarness(tmp_path)
    try:
        with harness.sessions() as session:
            session.add(
                ProjectRow(
                    id="project",
                    name="project",
                    name_key="project",
                    description="",
                    search_text="project",
                    default_resources={},
                    management_revision=1,
                    lifecycle_state="active",
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            session.commit()
        child = copy.deepcopy(harness.document)
        child.update(id="child", name="child", nodes=[child["nodes"][1]], edges=[])
        del child["nodes"][0]["data"]["config"]["modelId"]
        modules = CustomModuleService(SqlAlchemyWorkflowModules(harness.sessions))
        harness.coordinator._modules = modules
        module = modules.create(
            {
                "name": "child-module",
                "display_name": "子模块",
                "parameters": [],
                "outputs": [],
                "workflow": child,
            },
            client_request_id="module",
        )
        harness.coordinator._documents.create(child, client_request_id="child")
        root = {
            "id": "root",
            "name": "root",
            "nodes": [
                {
                    "id": "call",
                    "type": "moduleNode",
                    "data": {"moduleType": "custom_module", "customModuleId": module.id}
                    if via_module
                    else {"moduleType": "run_workflow_file", "workflowFile": "child"},
                }
            ],
            "edges": [],
            "variables": [],
        }
        request = {
            **harness.request,
            "documentId": "root",
            "document": root,
            "projectId": "project",
        }
        calls = []

        def default_model(project_id: str) -> str:
            calls.append(project_id)
            return "default-child"

        harness.coordinator._resolve_default_model = default_model
        await harness.coordinator.start("root", request)
        payload = harness.workers.payloads[0]
        executed = (
            payload["customModuleDependencies"][module.id]["workflow"]
            if via_module
            else payload["workflowDependencies"]["child"]
        )
        assert executed["nodes"][0]["data"]["config"]["modelId"] == "default-child"
        assert harness.model.reads == ["default-child"]
        assert calls == ["project"]
        assert (
            "modelId"
            not in modules.get(module.id).definition["workflow"]["nodes"][0]["data"][
                "config"
            ]
        )
        assert (
            "modelId"
            not in harness.coordinator._documents.get("child").document["nodes"][0][
                "data"
            ]["config"]
        )
        if via_module:
            frozen = harness.runs.get("retry-run").custom_module_snapshots[module.id][
                "workflow"
            ]
            assert "modelId" not in frozen["nodes"][0]["data"]["config"]
    finally:
        harness.sessions.dispose()


@pytest.mark.asyncio
async def test_default_lookup_error_has_node_location_and_no_run(
    tmp_path: Path,
) -> None:
    harness = RetryHarness(tmp_path)
    try:
        harness.request.update(projectId="project", documentId="unsaved")
        harness.request["document"]["id"] = "unsaved"
        del harness.request["document"]["nodes"][1]["data"]["config"]["modelId"]

        def missing(_: str) -> str:
            raise WorkflowRunError(
                "PROJECT_DEFAULT_MODEL_MISSING", "项目没有默认模型", 422
            )

        harness.coordinator._resolve_default_model = missing
        with pytest.raises(WorkflowRunError) as captured:
            await harness.coordinator.start("unsaved", harness.request)
        assert captured.value.code == "PROJECT_DEFAULT_MODEL_MISSING"
        assert captured.value.details == {"nodeId": "ask", "path": "config.modelId"}
        assert not harness.workers.payloads
        assert harness.repository.get("retry-run") is None
    finally:
        harness.sessions.dispose()


@pytest.mark.parametrize(
    "node_type",
    sorted(
        {
            "ai_chat",
            "ai_vision",
            "ai_vision_act",
            "ai_extract",
            "ai_classify",
            "ai_summarize",
            "ai_translate",
            "ai_sentiment",
            "ai_normalize",
            "ai_dedup_semantic",
            "ai_route",
            "ai_smart_scraper",
            "ai_element_selector",
            "ai_generate_image",
            "ai_generate_video",
        }
    ),
)
@pytest.mark.parametrize("nested_config", [False, True])
def test_all_managed_ai_entries_share_model_resolution(
    tmp_path: Path, node_type: str, nested_config: bool
) -> None:
    harness = RetryHarness(tmp_path)
    try:
        harness.coordinator._resolve_default_model = lambda _: "default"
        data: dict[str, Any] = {"moduleType": node_type, **({"config": {}} if nested_config else {})}
        doc = {"nodes": [{"id": "ai", "type": "moduleNode", "data": data}]}
        assert (
            harness.coordinator._apply_project_model_default([doc], "project")
            == "default"
        )
        assert (data["config"] if nested_config else data)["modelId"] == "default"
    finally:
        harness.sessions.dispose()


@pytest.mark.asyncio
async def test_execution_document_keeps_existing_request_identity(tmp_path: Path) -> None:
    harness = RetryHarness(tmp_path)
    try:
        harness.request['documentId'] = 'execution-document'
        await harness.coordinator.start('retry-flow', harness.request)
        assert harness.workers.payloads[0]['document']['id'] == 'execution-document'
        assert harness.request['document']['id'] == 'retry-flow'
    finally:
        harness.sessions.dispose()
