from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
    WorkflowWorkerError,
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
    instance, executable = manager(tmp_path)
    real_cleanup = instance._cleanup_owned
    fail = True

    async def cleanup(*args, **kwargs):
        if fail:
            raise RuntimeError('synthetic cleanup failure')
        return await real_cleanup(*args, **kwargs)

    monkeypatch.setattr(instance, '_cleanup_owned', cleanup)

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
    instance, executable = manager(tmp_path)
    spawning, release = asyncio.Event(), asyncio.Event()
    original_spawn = asyncio.create_subprocess_exec
    real_cleanup = instance._cleanup_owned
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
    monkeypatch.setattr(instance, '_cleanup_owned', cleanup)

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
    instance, executable = manager(tmp_path)
    import autoflow.infrastructure.process.project_workflow_worker as module

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

@pytest.mark.asyncio
async def test_capability_reply_waits_for_authoritative_handler(tmp_path):
    child = CHILD.replace("send('finished',status='succeeded',error=None,cleanupConfirmed=True)", """
send('capability',commandId='command',nodeId='open',nodeVisitId='visit-1',attempt=1,operation='inputs',arguments={})
reply=json.loads(sys.stdin.readline())
assert reply['type']=='capability_result' and reply['commandId']=='command'
assert reply['result']=={'confirmed':True}
send('finished',status='succeeded',error=None,cleanupConfirmed=True)
""")
    seen = []

    async def capability(run_id, generation, request):
        seen.append((run_id, generation, request['operation']))
        return {'confirmed': True}

    executable = tmp_path / 'kernel'
    executable.write_text('identity')
    instance = ProjectWorkflowWorkerManager(tmp_path / 'temp', command=(sys.executable, '-c', child), worker_env={'PROOF': str(tmp_path / 'proof')}, on_capability=capability)
    outcome = await start(instance, executable, lambda _event: asyncio.sleep(0))
    assert outcome.status == 'succeeded'
    assert seen == [('a088a638-5afb-4b4b-8d83-45410a3cab42', 1, 'inputs')]


@pytest.mark.asyncio
async def test_worker_exit_interrupts_pending_manual_capability(tmp_path):
    from uuid import uuid4
    instance, executable = manager(tmp_path)
    instance._command = (sys.executable, '-c', CHILD[:CHILD.index("\ne=dict")] + "\nsend('capability', commandId='manual')\n")
    cancelled = asyncio.Event()
    async def capability(*_args):
        try:
            await asyncio.Future()
        finally:
            cancelled.set()
    async def event(_event): pass
    instance._on_capability = capability
    with pytest.raises(WorkflowWorkerError, match='执行进程'):
        await asyncio.wait_for(instance.run(run_id=str(uuid4()), execution_generation=1, execution_plan={}, parameters={}, variables={}, browser={}, executable=executable, on_event=event), 3)
    assert cancelled.is_set()
    assert not instance.busy()


def test_worker_protocol_is_utf8_even_with_legacy_pipe_encoding():
    import os
    import subprocess
    code = "from autoflow.bootstrap.test_browser_worker import browser_worker_main; import sys; browser_worker_main(lambda stopped: print(sys.stdin.readline().strip()) or 0)"
    result = subprocess.run([sys.executable, '-c', code], input='中文参数\n'.encode(), capture_output=True, env={**os.environ, 'PYTHONIOENCODING': 'ascii'}, timeout=10, check=False)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    assert result.stdout.decode().splitlines() == ['中文参数']


@pytest.mark.asyncio
async def test_windows_cleanup_confirms_exit_after_kill_access_denied(tmp_path, monkeypatch):
    from autoflow.infrastructure.process import project_workflow_worker as module
    instance, _ = manager(tmp_path)
    exited = False
    class Process:
        returncode = None
        def kill(self):
            raise PermissionError('process already exiting')
        async def wait(self):
            nonlocal exited
            exited = True
            return 0
    worker = SimpleNamespace(process=Process(), created_directory=False)
    instance._worker = worker
    monkeypatch.setattr(module.sys, 'platform', 'win32')
    await instance._cleanup_owned(worker)
    assert exited and not instance.busy()
