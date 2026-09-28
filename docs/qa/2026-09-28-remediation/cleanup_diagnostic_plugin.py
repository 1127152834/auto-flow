"""Observe real native cleanup exceptions without changing behavior or responses."""
import subprocess
import traceback

import pytest


@pytest.fixture(autouse=True)
def observe_cleanup(monkeypatch):
    from autoflow.infrastructure.process import project_test_browser_worker as worker
    original = worker.capture_processes

    def capture(*args, **kwargs):
        try:
            return original(*args, **kwargs)
        except Exception as error:
            from autoflow.infrastructure.process import project_browser_processes as processes
            trace = error.__traceback__
            while trace is not None:
                if trace.tb_frame.f_code.co_name == "capture_processes":
                    local = trace.tb_frame.f_locals
                    candidate = local.get("item")
                    if isinstance(candidate, int):
                        state = subprocess.run(
                            ["ps", "-p", str(candidate), "-o", "stat="],
                            capture_output=True, text=True, check=False,
                        ).stdout.strip()
                        print("REAL_CANDIDATE_DIAGNOSTIC", {
                            "candidatePid": candidate,
                            "workerPid": local.get("pid"),
                            "snapshotBirth": local.get("identities", {}).get(candidate),
                            "currentBirth": processes.process_birth(candidate),
                            "currentState": state or "gone",
                            "exists": processes._process_exists(candidate),
                            "nativeArgumentsAvailable": processes._native_arguments(candidate) is not None,
                        }, flush=True)
                trace = trace.tb_next
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
