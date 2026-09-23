from __future__ import annotations

import asyncio
import sys
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
    WorkflowWorkerError,
)
from autoflow.providers.browser.project_workflow_worker import (
    MAX_EVENT_JSONL_BYTES,
    ProtocolFailure,
    _write,
)

CHILD = r'''
import json, os, sys
c=json.loads(sys.stdin.readline())
def send(type, **data):
 value=dict(type=type, protocolVersion=1, runId=c['runId'], executionGeneration=c['executionGeneration'], **data)
 if os.environ.get('MODE')=='boolean-identity': value['executionGeneration']=True
 if os.environ.get('MODE')=='float-version': value['protocolVersion']=1.0
 print(json.dumps(value), flush=True)
send('ready')
e=dict(eventId='event-1',runId=c['runId'],executionGeneration=c['executionGeneration'],kind='nodeAttempt',nodeId='open',nodeVisitId='visit-1',attempt=1,occurredAt='2026-09-15T00:00:00+00:00',payload={'status':'running'})
if os.environ.get('MODE')=='large-output':
 e['kind']='output'
 e['payload']={'name':'captured','value':['x'*2048]*1024}
if os.environ.get('MODE')=='wrong-run': e['runId']='other'
if os.environ.get('MODE')=='unterminated':
 sys.stdout.write(json.dumps(dict(type='event',protocolVersion=1,runId=c['runId'],executionGeneration=c['executionGeneration'],event=e)))
 sys.stdout.flush()
 os.close(sys.stdout.fileno())
else:
 send('event',event=e)
a=json.loads(sys.stdin.readline())
if a.get('type')=='stop':
 a=json.loads(sys.stdin.readline())
assert a['type']=='event_committed' and a['eventId']=='event-1'
with open(os.environ['PROOF'],'w') as f: f.write('after-ack')
if os.environ.get('MODE')=='removed-cache':
 import shutil
 shutil.rmtree(os.environ['CLOAKBROWSER_CACHE_DIR'])
send('finished',status='succeeded',error=None,cleanupConfirmed=True)
if os.environ.get('MODE')=='wait-control-eof':
 assert sys.stdin.read()==''
'''


def manager(tmp_path: Path, mode: str = "normal"):
    executable = tmp_path / 'CloakBrowser'
    executable.write_text('synthetic-kernel')
    instance = ProjectWorkflowWorkerManager(
        tmp_path / 'temp', command=(sys.executable, '-c', CHILD),
        worker_env={'PROOF': str(tmp_path / 'proof'), 'MODE': mode},
        start_timeout=2, termination_timeout=.1,
    )
    return instance, executable


def test_discard_uncommitted_artifact_only_removes_the_exact_owned_file(tmp_path):
    instance, _ = manager(tmp_path)
    run_id = "a088a638-5afb-4b4b-8d83-45410a3cab42"
    artifact_id = "b088a638-5afb-4b4b-8d83-45410a3cab42"
    directory = tmp_path / "workspace" / "runs" / run_id / "generation-1"
    directory.mkdir(parents=True)
    artifact = directory / f"{artifact_id}.png"
    artifact.write_bytes(b"png")
    instance._worker = SimpleNamespace(  # type: ignore[assignment]
        run_id=run_id,
        generation=1,
        artifact_directory=directory,
        relative_artifact_directory=f"runs/{run_id}/generation-1",
    )

    instance.discard_uncommitted_artifact(
        run_id,
        1,
        artifact_id,
        f"runs/{run_id}/generation-1/not-the-artifact.png",
    )
    assert artifact.exists()

    instance.discard_uncommitted_artifact(
        run_id,
        1,
        artifact_id,
        f"runs/{run_id}/generation-1/{artifact_id}.png",
    )
    assert not artifact.exists()


def start(instance, executable, on_event):
    return instance.run(
        run_id='a088a638-5afb-4b4b-8d83-45410a3cab42', execution_generation=1,
        execution_plan={'orderedNodeIds': [], 'nodes': []},
        parameters={}, variables={}, browser={'headless': True},
        executable=executable, on_event=on_event,
    )


@pytest.mark.asyncio
async def test_large_project_output_reaches_durable_callback_before_ack(tmp_path):
    instance, executable = manager(tmp_path, 'large-output')
    received = []

    async def persist(event):
        received.append(event)

    outcome = await start(instance, executable, persist)
    assert outcome.status == 'succeeded'
    assert len(received) == 1
    assert len(received[0]['payload']['value']) == 1024
    assert all(len(item) == 2048 for item in received[0]['payload']['value'])
    assert (tmp_path / 'proof').read_text() == 'after-ack'
    assert not instance.busy()


def test_worker_event_limit_accepts_captured_results_but_rejects_unbounded_output():
    stream = StringIO()
    _write(stream, {'type': 'event', 'value': 'x' * (2 * 1024 * 1024)})
    assert len(stream.getvalue()) > 2 * 1024 * 1024
    with pytest.raises(ProtocolFailure, match='WORKFLOW_OUTPUT_TOO_LARGE'):
        _write(StringIO(), {'type': 'event', 'value': 'x' * MAX_EVENT_JSONL_BYTES})


@pytest.mark.asyncio
async def test_worker_waits_for_durable_callback_before_ack_and_completion(tmp_path):
    instance, executable = manager(tmp_path)
    arrived, committed = asyncio.Event(), asyncio.Event()

    async def persist(event):
        assert event['nodeId'] == 'open'
        arrived.set()
        await committed.wait()

    task = asyncio.create_task(start(instance, executable, persist))
    await asyncio.wait_for(arrived.wait(), 3)
    assert instance.busy()
    assert not (tmp_path / 'proof').exists()
    committed.set()
    result = await asyncio.wait_for(task, 5)
    assert result.status == 'succeeded'
    assert result.cleanup_confirmed
    assert (tmp_path / 'proof').read_text() == 'after-ack'
    assert not instance.busy()


@pytest.mark.asyncio
async def test_finished_worker_receives_control_eof_before_parent_waits_for_exit(tmp_path):
    instance, executable = manager(tmp_path, "wait-control-eof")

    async def persist(_event):
        pass

    result = await start(instance, executable, persist)
    assert result.status == "succeeded"
    assert result.cleanup_confirmed
    assert not instance.busy()


@pytest.mark.asyncio
async def test_failed_event_commit_never_acknowledges_or_runs_next_action(tmp_path):
    instance, executable = manager(tmp_path)

    async def persist(_event):
        raise RuntimeError('synthetic database failure')

    with pytest.raises(RuntimeError, match='synthetic database failure'):
        await asyncio.wait_for(start(instance, executable, persist), 5)
    assert not (tmp_path / 'proof').exists()
    assert not instance.busy()


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['wrong-run', 'boolean-identity', 'float-version'])
async def test_wrong_event_owner_is_rejected_before_callback(tmp_path, mode):
    instance, executable = manager(tmp_path, mode)
    events = []

    async def persist(event):
        events.append(event)

    with pytest.raises(WorkflowWorkerError) as caught:
        await asyncio.wait_for(start(instance, executable, persist), 5)
    assert caught.value.code == 'WORKFLOW_WORKER_PROTOCOL_INVALID'
    assert events == []
    assert not (tmp_path / 'proof').exists()
    assert not instance.busy()


@pytest.mark.asyncio
async def test_one_worker_capacity_and_force_cleanup(tmp_path):
    instance, executable = manager(tmp_path)
    arrived, release = asyncio.Event(), asyncio.Event()

    async def persist(_event):
        arrived.set()
        await release.wait()

    task = asyncio.create_task(start(instance, executable, persist))
    await asyncio.wait_for(arrived.wait(), 3)
    with pytest.raises(WorkflowWorkerError) as caught:
        await start(instance, executable, persist)
    assert caught.value.code == 'WORKFLOW_WORKER_BUSY'
    await instance.force_stop('a088a638-5afb-4b4b-8d83-45410a3cab42')
    release.set()
    with pytest.raises((WorkflowWorkerError, BrokenPipeError, ConnectionResetError)):
        await asyncio.wait_for(task, 5)
    assert not instance.busy()


@pytest.mark.asyncio
async def test_shutdown_rejects_future_launches(tmp_path):
    instance, executable = manager(tmp_path)
    await instance.shutdown()

    async def persist(_event):
        pass

    with pytest.raises(WorkflowWorkerError) as caught:
        await start(instance, executable, persist)
    assert caught.value.code == 'WORKFLOW_WORKER_UNAVAILABLE'


@pytest.mark.asyncio
async def test_failed_cleanup_retains_capacity_until_a_verified_retry(tmp_path, monkeypatch):
    import autoflow.infrastructure.process.project_workflow_worker as module

    instance, executable = manager(tmp_path)
    real_cleanup = module.force_process_tree
    fail = True

    async def cleanup(*args, **kwargs):
        if fail:
            raise RuntimeError('synthetic cleanup failure')
        return await real_cleanup(*args, **kwargs)

    monkeypatch.setattr(module, 'force_process_tree', cleanup)

    async def persist(_event):
        pass

    with pytest.raises(RuntimeError, match='synthetic cleanup failure'):
        await start(instance, executable, persist)
    assert instance.busy()
    fail = False
    await instance.force_stop('a088a638-5afb-4b4b-8d83-45410a3cab42')
    assert not instance.busy()


@pytest.mark.asyncio
async def test_cancelled_spawn_waits_for_ownership_before_cleanup(tmp_path, monkeypatch):
    instance, executable = manager(tmp_path)
    spawning, release = asyncio.Event(), asyncio.Event()
    original_spawn = asyncio.create_subprocess_exec
    children = []

    async def delayed_spawn(*args, **kwargs):
        child = await original_spawn(*args, **kwargs)
        children.append(child)
        spawning.set()
        await release.wait()
        return child

    monkeypatch.setattr(asyncio, 'create_subprocess_exec', delayed_spawn)

    async def persist(_event):
        pass

    task = asyncio.create_task(start(instance, executable, persist))
    await spawning.wait()
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 5)
    assert children[0].returncode is not None
    assert not instance.busy()


@pytest.mark.asyncio
async def test_already_removed_cache_is_successfully_cleaned(tmp_path):
    instance, executable = manager(tmp_path, 'removed-cache')

    async def persist(_event):
        pass

    result = await start(instance, executable, persist)
    assert result.status == 'succeeded'
    assert not instance.busy()


@pytest.mark.asyncio
@pytest.mark.parametrize('shutdown', [False, True])
async def test_stop_during_spawn_reports_cleanup_failure_and_retains_retry(tmp_path, monkeypatch, shutdown):
    import autoflow.infrastructure.process.project_workflow_worker as module

    instance, executable = manager(tmp_path)
    spawning, release = asyncio.Event(), asyncio.Event()
    original_spawn = asyncio.create_subprocess_exec
    real_cleanup = module.force_process_tree
    fail = True

    async def delayed_spawn(*args, **kwargs):
        child = await original_spawn(*args, **kwargs)
        spawning.set()
        await release.wait()
        return child

    async def cleanup(*args, **kwargs):
        if fail:
            raise RuntimeError('synthetic cleanup failure')
        return await real_cleanup(*args, **kwargs)

    monkeypatch.setattr(asyncio, 'create_subprocess_exec', delayed_spawn)
    monkeypatch.setattr(module, 'force_process_tree', cleanup)

    async def persist(_event):
        pass

    task = asyncio.create_task(start(instance, executable, persist))
    await spawning.wait()
    stopping = asyncio.create_task(instance.shutdown() if shutdown else instance.force_stop(
        'a088a638-5afb-4b4b-8d83-45410a3cab42'
    ))
    await asyncio.sleep(0)
    release.set()
    with pytest.raises(WorkflowWorkerError) as caught:
        await stopping
    assert caught.value.code == 'WORKFLOW_CLEANUP_FAILED'
    with pytest.raises(RuntimeError, match='synthetic cleanup failure'):
        await task
    assert instance.busy()
    fail = False
    await instance.force_stop('a088a638-5afb-4b4b-8d83-45410a3cab42')
    assert not instance.busy()


@pytest.mark.asyncio
async def test_eof_fragment_never_gets_persisted_or_acknowledged(tmp_path):
    instance, executable = manager(tmp_path, 'unterminated')
    received = []

    async def persist(event):
        received.append(event)

    with pytest.raises(WorkflowWorkerError):
        await start(instance, executable, persist)
    assert received == []
    assert not (tmp_path / 'proof').exists()


@pytest.mark.asyncio
@pytest.mark.parametrize('direct_await', [False, True])
async def test_spawn_failure_and_directory_failure_can_retry_after_task_finished(tmp_path, monkeypatch, direct_await):
    import autoflow.infrastructure.process.project_workflow_worker as module

    instance, executable = manager(tmp_path)
    real_remove = module.shutil.rmtree
    fail = True

    async def failed_spawn(*_args, **_kwargs):
        raise OSError('synthetic spawn failure')

    def remove(path):
        if fail:
            raise OSError('synthetic directory failure')
        real_remove(path)

    monkeypatch.setattr(asyncio, 'create_subprocess_exec', failed_spawn)
    monkeypatch.setattr(module.shutil, 'rmtree', remove)

    async def persist(_event):
        pass

    task = start(instance, executable, persist)
    if not direct_await:
        task = asyncio.create_task(task)
    with pytest.raises(OSError, match='synthetic directory failure'):
        await task
    assert instance.busy()
    fail = False
    await instance.force_stop('a088a638-5afb-4b4b-8d83-45410a3cab42')
    assert not instance.busy()


def test_result_cleanup_is_confined_to_current_generation_artifacts(tmp_path):
    instance, _ = manager(tmp_path)
    directory = tmp_path / 'workspace' / 'runs' / 'run' / 'generation-1'
    result = directory / 'artifacts' / 'nested' / 'capture.png'
    result.parent.mkdir(parents=True)
    result.write_bytes(b'png')
    other = tmp_path / 'other.png'
    other.write_bytes(b'keep')
    (directory / 'artifacts' / 'linked.png').symlink_to(other)
    instance._worker = SimpleNamespace(
        run_id='run', generation=1, artifact_directory=directory,
        relative_artifact_directory='runs/run/generation-1',
    )
    for path in ['runs/run/generation-2/artifacts/nested/capture.png',
                 'runs/run/generation-1/artifacts/linked.png',
                 'runs/run/generation-1/artifacts/../../../other.png']:
        instance.discard_uncommitted_artifact('run', 1, 'new-id', path)
    assert result.read_bytes() == b'png'
    assert other.read_bytes() == b'keep'
    instance.discard_uncommitted_artifact('run', 1, 'new-id', 'runs/run/generation-1/artifacts/nested/capture.png')
    assert not result.exists()
    assert other.read_bytes() == b'keep'
