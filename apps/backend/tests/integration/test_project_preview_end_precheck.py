"""Remediation M5 5B-A1: a preview start is refused up front when End would keep the login environment."""

from copy import deepcopy

import pytest
from sqlalchemy import text

from autoflow.application.workflows.service import WorkflowService
from autoflow.domain.project_runs.models import ProjectRunError
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from tests.fixtures.workflows import workflow_payload
from tests.integration.test_project_debug_inputs import debug_inputs
from tests.integration.test_project_run_data_start import _setup, uid


def _row_counts(factory) -> dict[str, int]:
    with factory() as session:
        names = session.scalars(text("select name from sqlite_master where type='table' and name not like 'sqlite_%'")).all()
        return {name: session.scalar(text(f'select count(*) from "{name}"')) for name in names}


def _save_end(factory, workflow_id: str, retain: bool) -> None:
    document = workflow_payload(workflow_id)
    document["content"]["nodes"] = [
        {"id": "value", "type": "set_variable", "position": {"x": 0, "y": 0}, "data": {"moduleType": "set_variable", "label": "v", "variableName": "answer", "variableValue": "x"}},
        {"id": "end", "type": "project_end", "position": {"x": 0, "y": 100}, "data": {"moduleType": "project_end", "label": "结束", "retainEnvironment": retain, "saveMode": "save_as"}},
    ]
    document["content"]["edges"] = [{"id": "e", "source": "value", "target": "end"}]
    WorkflowService(SqlAlchemyWorkflowRepository(factory)).save(workflow_id, document, 1, uid())


def _payload(factory, project, automation, **extra):
    with factory() as session:
        selection = debug_inputs(session, project, automation.input_plan, {})["selection"]
    return {"expectedAutomationRevision": automation.management_revision, "parameters": {}, "maxTasks": 1, "concurrency": 1, "debugSelection": selection, **extra}


def test_preview_start_with_retained_environment_is_refused_without_any_row(tmp_path):
    factory, project, automation, coordinator = _setup(tmp_path)
    _save_end(factory, automation.workflow_id, True)
    payload, key = _payload(factory, project, automation), uid()
    before = _row_counts(factory)
    for _ in range(2):  # the same idempotency key replays the same refusal
        with pytest.raises(ProjectRunError) as caught:
            coordinator.start(project, automation.automation_id, key, deepcopy(payload))
        assert (caught.value.code, caught.value.status) == ("PREVIEW_CANNOT_SAVE_ENVIRONMENT", 409)
        assert "保留当前环境" in caught.value.message and "真实写入" in caught.value.message
        assert _row_counts(factory) == before


@pytest.mark.parametrize("retain,mode,refused", [(False, None, False), (True, "realWrites", False)])
def test_other_combinations_still_start(tmp_path, retain, mode, refused):
    factory, project, automation, coordinator = _setup(tmp_path)
    _save_end(factory, automation.workflow_id, retain)
    extra = {"executionMode": mode} if mode else {}
    batch, _, _ = coordinator.start(project, automation.automation_id, uid(), _payload(factory, project, automation, **extra))
    assert batch.batch_id
