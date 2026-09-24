"""Real bootstrap, project/model/document/run repositories; controlled worker boundary."""

import copy
import json
from contextlib import nullcontext
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

from autoflow.bootstrap import workflows as workflow_bootstrap
from autoflow.domain.models.models import LocalModelSpec
from autoflow.domain.workflows.runs import WorkflowRunError
from autoflow.infrastructure.database.model_providers import (
    model_repository_transaction,
)
from autoflow.infrastructure.database.models import ProjectRow
from tests.fixtures.model_management import FakeCredentialStore
from tests.unit.test_model_service import _profile as model_profile
from tests.unit.test_model_service import _service
from tests.unit.workflows.test_run_coordinator import (
    FakeProfiles,
    FakeWorkers,
    _none,
    _profile,
)


class CountedCredentials(FakeCredentialStore):
    def __init__(self) -> None:
        super().__init__()
        self.reads: list[str] = []

    def read(self, key: str) -> bytes | None:
        self.reads.append(key)
        return super().read(key)


class ControlledWorkers(FakeWorkers):
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        super().__init__()

    async def shutdown(self) -> None:
        pass


class UnusedProfileGuard:
    def guard(self, _profile_id: str):
        return nullcontext()


@pytest_asyncio.fixture
async def project_models(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    credentials = CountedCredentials()
    models, factory = _service(tmp_path, credentials)
    other = await models.connect(
        replace(model_profile(), name="A other provider"),
        "other-private-key",
        [LocalModelSpec.from_values("Model-A", "Alpha")],
    )
    selected = await models.connect(
        replace(model_profile(), name="Z project provider"),
        "project-private-key",
        [
            LocalModelSpec.from_values("model-b", "Beta"),
            LocalModelSpec.from_values("Model-A", "Alpha"),
        ],
    )
    now = datetime.now(UTC)
    with factory() as session:
        session.add(
            ProjectRow(
                id="project-model-default",
                name="模型默认值",
                name_key="模型默认值",
                description="",
                search_text="",
                default_resources={"modelProviderId": selected.id},
                management_revision=1,
                lifecycle_state="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    monkeypatch.setattr(workflow_bootstrap, "WorkflowWorkerManager", ControlledWorkers)
    services = workflow_bootstrap.build_workflow_services(
        factory,
        profiles=FakeProfiles(_profile()),
        installed_kernels=list,
        resolve_proxy=lambda _profile, _run: _none(),
        read_license=lambda: None,
        profile_guard=UnusedProfileGuard(),
        kernels_root=tmp_path / "kernels",
        temp_root=tmp_path / "workers",
        artifact_root=tmp_path / "artifacts",
        models=models,
    )
    try:
        yield services, models, factory, credentials, selected, other
    finally:
        await services.shutdown()
        factory.dispose()


def _document(model_id: Any = "") -> dict[str, Any]:
    return {
        "id": "project-ai-flow",
        "name": "项目模型流程",
        "projectId": "project-model-default",
        "nodes": [
            {
                "id": "ask",
                "type": "moduleNode",
                "data": {
                    "moduleType": "ai_chat",
                    "config": {"modelId": model_id, "userPrompt": "问题"},
                },
            }
        ],
        "edges": [],
        "variables": [],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit", [False, True])
async def test_bootstrap_model_default_and_explicit_override_freeze_only_execution_copy(
    project_models,
    explicit: bool,
):
    services, models, factory, credentials, selected, other = project_models
    selected_id = next(
        item.id for item in selected.models if item.display_name == "Alpha"
    )
    expected = other.models[0].id if explicit else selected_id
    assert models.list_options()[0].id == other.models[0].id
    document = _document(other.models[0].id if explicit else "")
    saved = services.documents.create(document, client_request_id="save-ai-flow")
    original = copy.deepcopy(document)
    request = {
        "runId": "project-model-run",
        "documentId": document["id"],
        "profileId": "profile-1",
        "projectId": "project-model-default",
        "document": document,
    }

    result = await services.commands.start(document["id"], request)

    assert result["status"] == "running"
    payload = services.workers.payloads[0]
    assert payload["document"]["nodes"][0]["data"]["config"]["modelId"] == expected
    assert [item["modelId"] for item in payload["modelBindings"]] == [expected]
    assert payload["modelBindings"][0]["secret"] == (
        "other-private-key" if explicit else "project-private-key"
    )
    assert credentials.reads == [other.secret_ref if explicit else selected.secret_ref]
    assert document == original
    assert services.documents.get(document["id"]) == saved
    run = services.runs.get("project-model-run")
    assert (
        run.document_snapshot["nodes"][0]["data"]["config"]["modelId"]
        == original["nodes"][0]["data"]["config"]["modelId"]
    )
    persisted = json.dumps(
        {
            "document": run.document_snapshot,
            "profile": run.profile_snapshot,
            "modules": run.custom_module_snapshots,
            "events": [item.payload for item in services.runs.events(run.run_id)],
        },
        ensure_ascii=False,
    )
    assert "private-key" not in persisted
    with factory() as session:
        project = session.get(ProjectRow, "project-model-default")
        project.default_resources = {"modelProviderId": other.id}
        session.commit()
    credentials.reads.clear()
    assert await services.commands.start(document["id"], request) == result
    assert credentials.reads == []
    assert len(services.workers.payloads) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "condition,code,status",
    [
        ("empty", "PROJECT_DEFAULT_MODEL_UNAVAILABLE", 409),
        ("missing-provider", "MODEL_PROVIDER_NOT_FOUND", 404),
        ("missing-default", "PROJECT_DEFAULT_MODEL_MISSING", 422),
        ("archived", "PROJECT_NOT_ACTIVE", 409),
        ("missing-project", "PROJECT_NOT_FOUND", 404),
        ("explicit-invalid", "MODEL_NOT_FOUND", 404),
    ],
)
async def test_bootstrap_rejects_unavailable_model_with_node_path_without_starting_worker(
    project_models,
    condition: str,
    code: str,
    status: int,
):
    services, _models, factory, credentials, selected, _other = project_models
    if condition == "empty":
        with model_repository_transaction(factory) as repository:
            for model in selected.models:
                repository.remove_model(model.id)
    else:
        with factory() as session:
            project = session.get(ProjectRow, "project-model-default")
            if condition == "missing-provider":
                project.default_resources = {"modelProviderId": "missing"}
            elif condition == "missing-default":
                project.default_resources = {}
            elif condition == "archived":
                project.lifecycle_state = "archived"
            elif condition == "missing-project":
                session.delete(project)
            session.commit()
    document = _document(
        "explicit-missing-model" if condition == "explicit-invalid" else ""
    )

    with pytest.raises(WorkflowRunError) as captured:
        await services.commands.start(
            document["id"],
            {
                "runId": "rejected-model-run",
                "documentId": document["id"],
                "profileId": "profile-1",
                "projectId": "project-model-default",
                "document": document,
            },
        )

    assert captured.value.code == code
    assert captured.value.status == status
    assert captured.value.details["nodeId"] == "ask"
    assert captured.value.details["path"] == "config.modelId"
    assert credentials.reads == []
    assert services.workers.payloads == []
