"""Remediation M1 R1-14: a crashing worker leaves safe, findable evidence and is never re-run."""

import asyncio
import sys
from pathlib import Path

import pytest

from autoflow.application.settings.runtime import QuiesceGate
from autoflow.application.workflows.dispatcher import WorkflowRunDispatcher
from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
    WorkflowWorkerError,
)
from tests.fixtures.workflow_runs import SyntheticResources, create_queued_run
from tests.integration.test_workflow_dispatch import runtime  # noqa: F401 - fixture reuse

SECRET_LINE = "RuntimeError: request failed Authorization: Bearer topsecrettoken123 https://u:hunter2pw@host/x?token=querysecret"
CRASH = r'''
import json, os, sys
c = json.loads(sys.stdin.readline())
with open(os.environ['LAUNCHES'], 'a') as launches: launches.write('x')
print(json.dumps(dict(type='ready', protocolVersion=1, runId=c['runId'], executionGeneration=c['executionGeneration'])), flush=True)
sys.stderr.write('y' * 70000 + '\n')            # one 70 KB line
for _ in range(60): sys.stderr.write(('z' * 99 + '\n') * 500)   # ~3 MB: far beyond any pipe buffer
sys.stderr.write('Traceback (most recent call last):\n')
sys.stderr.write('  File "/home/runner/private-dir/app/worker.py", line 3, in main\n')
sys.stderr.write('  File "C:\\Users\\someone\\private\\other.py", line 9, in run\n')
sys.stderr.write(os.environ['SECRET_LINE'] + '\n')
sys.stderr.flush()
raise SystemExit(17)
'''


def make_manager(tmp_path: Path) -> ProjectWorkflowWorkerManager:
    return ProjectWorkflowWorkerManager(
        tmp_path / "temp", command=(sys.executable, "-c", CRASH),
        worker_env={"LAUNCHES": str(tmp_path / "launches"), "SECRET_LINE": SECRET_LINE},
        start_timeout=20, capacity=2,
    )


def assert_safe(details: dict):
    assert details["causeCode"] == "WORKFLOW_WORKER_LOST"
    tail = "\n".join(details["stderrTail"])
    assert details["stderrTailRedacted"] is True
    assert "topsecrettoken123" not in tail and "hunter2pw" not in tail and "querysecret" not in tail
    assert "[REDACTED]" in tail
    assert "/home/runner" not in tail and "private-dir" not in tail and "someone" not in tail
    assert "worker.py" in tail and "other.py" in tail  # file names stay useful
    assert all(len(line) <= 500 for line in details["stderrTail"]) and len(details["stderrTail"]) <= 50


@pytest.mark.asyncio
async def test_manager_drains_a_flooding_worker_and_reports_a_safe_tail_and_log(tmp_path):
    manager = make_manager(tmp_path)
    run_id = "a088a638-5afb-4b4b-8d83-45410a3cab42"

    async def persist(_event):
        raise AssertionError("no events expected")

    with pytest.raises(WorkflowWorkerError) as caught:
        await asyncio.wait_for(manager.run(
            run_id=run_id, execution_generation=1, execution_plan={"orderedNodeIds": [], "nodes": []},
            parameters={}, variables={}, browser={}, executable=None, on_event=persist,
        ), 60)
    assert caught.value.code == "WORKFLOW_WORKER_LOST"
    details = caught.value.details
    assert_safe(details)
    log = tmp_path / "workspace" / details["diagnosticLog"]
    assert details["diagnosticLog"] == f"runs/{run_id}/generation-1/worker-stderr.log"
    size = log.stat().st_size
    assert 0 < size <= 5 * 1024 * 1024  # bounded, although ~3 MB were written
    assert b"Traceback" in log.read_bytes()
    assert not manager.busy()


@pytest.mark.asyncio
async def test_real_dispatcher_keeps_the_unknown_result_and_publishes_the_diagnostics(runtime, tmp_path):  # noqa: F811
    run, _ = create_queued_run(runtime)
    manager = make_manager(tmp_path)
    gate = QuiesceGate()

    async def cleanup(_run):
        pass

    dispatcher = WorkflowRunDispatcher(runtime, manager, SyntheticResources(), gate, cleanup, capacity=1)
    try:
        await dispatcher.dispatch(run.run_id, expected_status_revision=1, execution_generation=0)
        async with asyncio.timeout(60):
            await dispatcher.wait_idle()
        final = dispatcher.query_run(run.run_id)
        assert final.status == "interrupted"
        error = dict(final.error)
        assert error["code"] == "WORKFLOW_RESULT_UNKNOWN"  # the rule for unknown results is unchanged
        assert_safe(dict(error["details"]))
        assert error["details"]["diagnosticLog"].startswith(f"runs/{run.run_id}/")
        assert (tmp_path / "launches").read_text() == "x"  # an unknown result is never re-run
        # A restarted service still shows it.
        restarted = WorkflowRunDispatcher(runtime, manager, SyntheticResources(), QuiesceGate(), cleanup, capacity=1)
        assert dict(restarted.query_run(run.run_id).error)["details"]["diagnosticLog"] == error["details"]["diagnosticLog"]
        await restarted.shutdown()
    finally:
        await dispatcher.shutdown()
        await manager.shutdown()
