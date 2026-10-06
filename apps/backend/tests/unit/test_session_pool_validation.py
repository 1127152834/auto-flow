"""Remediation M3 R3-07: an automation reusing browsers is blocked when its workflow needs its own."""

from types import SimpleNamespace

import pytest

from autoflow.application.project_automations import service as module
from autoflow.application.project_automations.service import ProjectAutomationService


class _Fakes:
    def __init__(self, document, session_mode):
        self.automation = SimpleNamespace(workflow_id="w", input_plan={"inputs": []}, run_policy={"sessionMode": session_mode})
        self.document = document

    def get(self, *_args):
        return self.automation if len(_args) == 2 else SimpleNamespace(document=self.document, lifecycle_state="active")

    def inspect_resources(self, _automation):
        return []

    def inspect_capabilities(self, _workflow_id):
        return []


@pytest.mark.parametrize(("retain", "mode", "status"), [(True, "pool", "blocked"), (False, "pool", "ready"), (True, "perTask", "ready")])
def test_validation_blocks_a_pool_whose_workflow_saves_its_environment(monkeypatch, retain, mode, status):
    monkeypatch.setattr(module, "prepare_run", lambda _document: None)
    fakes = _Fakes({"nodes": [{"id": "e", "data": {"moduleType": "project_end", "retainEnvironment": retain}}]}, mode)
    service = ProjectAutomationService(fakes, fakes, fakes, fakes, fakes)
    result = service.validation("p", "a")
    assert result.status == status
    if status == "blocked":
        assert [issue.code for issue in result.issues] == ["SESSION_POOL_UNSUPPORTED"]


@pytest.mark.parametrize(("nodes", "status"), [
    ([{"id": "e", "data": {"moduleType": "project_end", "retainEnvironment": True}}], "ready"),
    ([{"id": "m", "data": {"moduleType": "project_manual"}}], "blocked"),
])
def test_validation_for_a_browser_shared_per_account(monkeypatch, nodes, status):
    monkeypatch.setattr(module, "prepare_run", lambda _document: None)
    fakes = _Fakes({"nodes": nodes}, "perIdentity")
    result = ProjectAutomationService(fakes, fakes, fakes, fakes, fakes).validation("p", "a")
    assert result.status == status
    if status == "blocked":
        assert [issue.code for issue in result.issues] == ["SESSION_POOL_UNSUPPORTED"]
        assert "同账号" in result.issues[0].message
