"""Observe real native cleanup exceptions without changing behavior or responses."""
import traceback

import pytest


@pytest.fixture(autouse=True)
def observe_cleanup(monkeypatch):
    from autoflow.infrastructure.process import project_test_browser_worker as worker
    original = worker.capture_processes

    def capture(*args, **kwargs):
        try:
            return original(*args, **kwargs)
        except Exception:
            print("REAL_CLEANUP_DIAGNOSTIC", traceback.format_exc(), flush=True)
            raise

    monkeypatch.setattr(worker, "capture_processes", capture)
    from autoflow.infrastructure.process.project_workflow_worker import ProjectWorkflowWorkerManager
    run = ProjectWorkflowWorkerManager.run

    async def observed_run(self, **kwargs):
        try:
            return await run(self, **kwargs)
        except Exception:
            print("REAL_WORKER_DIAGNOSTIC", traceback.format_exc(), flush=True)
            raise

    monkeypatch.setattr(ProjectWorkflowWorkerManager, "run", observed_run)
