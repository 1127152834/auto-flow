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
from autoflow.bootstrap.test_browser_worker import _windows_kill_on_exit_job
job = _windows_kill_on_exit_job()
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
 raise SystemExit(0)
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
    instance._workers[run_id] = SimpleNamespace(  # type: ignore[assignment]
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
@pytest.mark.parametrize('kind, status, cleanup, exit_code, error_code', [
    ('finished', 'failed', True, 1, None),
    ('finished', 'cancelled', True, 0, None),
    ('finished', 'succeeded', True, 0, 'WORKFLOW_WORKER_PROTOCOL_INVALID'),
    ('finished', 'timed_out', True, 1, 'WORKFLOW_WORKER_PROTOCOL_INVALID'),
    ('finished', 'failed', False, 1, 'WORKFLOW_CLEANUP_FAILED'),
    ('finished', 'failed', True, 17, 'WORKFLOW_WORKER_LOST'),
    ('event', 'failed', True, 1, 'WORKFLOW_WORKER_PROTOCOL_INVALID'),
    ('capability', 'failed', True, 1, 'WORKFLOW_WORKER_PROTOCOL_INVALID'),
])
async def test_pre_ready_terminal_requires_failure_cleanup_and_valid_exit(
    tmp_path, kind, status, cleanup, exit_code, error_code,
):
    instance, executable = manager(tmp_path)
    child = CHILD[:CHILD.index("send('ready')")] + (
        f"send({kind!r},status={status!r},cleanupConfirmed={cleanup!r})\n"
        f"raise SystemExit({exit_code})\n"
    )
    instance._command = (sys.executable, '-c', child)
    events = []

    async def persist(event):
        events.append(event)

    if error_code:
        with pytest.raises(WorkflowWorkerError) as caught:
            await asyncio.wait_for(start(instance, executable, persist), 10)
        assert caught.value.code == error_code
    else:
        outcome = await asyncio.wait_for(start(instance, executable, persist), 10)
        assert outcome.status == status
        assert outcome.cleanup_confirmed
    assert events == []
    assert not instance.busy()
    assert not list((tmp_path / 'temp' / 'workflow-runs').glob('*/generation-*'))


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["failed", "cancelled", "timed_out"])
async def test_confirmed_failure_waits_for_owned_cleanup_of_native_thread(tmp_path, status):
    import os

    instance, executable = manager(tmp_path)
    child = CHILD[:CHILD.index("send('ready')")] + (
        "from threading import Event, Thread\n"
        "Thread(target=Event().wait, daemon=False).start()\n"
        "with open(os.environ['PROOF'],'w') as f: f.write(str(os.getpid()))\n"
        "send('ready')\n"
        f"send('finished',status={status!r},cleanupConfirmed=True)\n"
        "raise SystemExit(1)\n"
    )
    instance._command = (sys.executable, '-c', child)

    async def persist(_event):
        raise AssertionError("terminal-only worker cannot produce node events")

    outcome = await asyncio.wait_for(start(instance, executable, persist), 10)
    assert outcome.status == status
    assert outcome.cleanup_confirmed
    assert not instance.busy()
    assert not list((tmp_path / 'temp' / 'workflow-runs').glob('*/generation-*'))
    pid = int((tmp_path / 'proof').read_text())
    if sys.platform != 'win32':
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("spawn_delay", [0, 3.2])
async def test_worker_waits_for_durable_callback_before_ack_and_completion(tmp_path, monkeypatch, spawn_delay):
    instance, executable = manager(tmp_path)
    # This checks commit ordering, not a three-second cold-start performance target.
    instance._start_timeout = 10
    arrived, committed = asyncio.Event(), asyncio.Event()
    spawn = asyncio.create_subprocess_exec

    async def delayed_spawn(*args, **kwargs):
        await asyncio.sleep(spawn_delay)
        return await spawn(*args, **kwargs)

    monkeypatch.setattr(asyncio, 'create_subprocess_exec', delayed_spawn)

    async def persist(event):
        assert event['nodeId'] == 'open'
        arrived.set()
        await committed.wait()

    task = asyncio.create_task(start(instance, executable, persist))
    waiting = asyncio.create_task(arrived.wait())
    try:
        done, _ = await asyncio.wait({task, waiting}, timeout=15, return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            await task  # Report the actual startup/ownership/protocol failure.
        assert waiting in done, f"event missing; worker states: {[(w.ready, w.process is not None) for w in instance._workers.values()]}"
        assert instance.busy()
        assert not (tmp_path / 'proof').exists()
        committed.set()
        result = await asyncio.wait_for(task, 5)
        assert result.status == 'succeeded'
        assert result.cleanup_confirmed
        assert (tmp_path / 'proof').read_text() == 'after-ack'
        assert not instance.busy()
    finally:
        waiting.cancel()
        if not task.done():
            task.cancel()
        await asyncio.gather(waiting, task, return_exceptions=True)


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
        await asyncio.wait_for(start(instance, executable, persist), 5)
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


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX process-tree completion barrier')
async def test_force_stop_keeps_capacity_and_directory_until_accepted_capability_settles(tmp_path, monkeypatch):
    from autoflow.infrastructure.process import project_workflow_worker as module
    from autoflow.infrastructure.process.project_test_browser_worker import (
        wait_for_cleanup,
    )

    instance, executable = manager(tmp_path)
    instance._command = (sys.executable, '-c', CHILD[:CHILD.index("\ne=dict")] + "\nsend('capability', commandId='end')\nsys.stdin.readline()\n")
    entered, release, cancelled = asyncio.Event(), asyncio.Event(), asyncio.Event()
    killed = asyncio.Event()
    original_force = module.force_process_tree

    async def force(*args, **kwargs):
        await original_force(*args, **kwargs)
        killed.set()

    monkeypatch.setattr(module, 'force_process_tree', force)

    async def capability(*_args):
        entered.set()
        accepted = asyncio.create_task(release.wait())
        try:
            return await asyncio.shield(accepted)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        finally:
            await wait_for_cleanup(accepted)

    instance._on_capability = capability
    run = asyncio.create_task(start(instance, executable, lambda _event: asyncio.sleep(0)))
    await asyncio.wait_for(entered.wait(), 5)
    worker, = instance._workers.values()
    stopping = asyncio.create_task(instance.force_stop(worker.run_id))
    try:
        await asyncio.wait_for(cancelled.wait(), 5)
        await asyncio.wait_for(killed.wait(), 5)
        assert not stopping.done()
        assert instance.busy(worker.run_id)
        assert worker.directory.exists()
    finally:
        release.set()
        await stopping
        await asyncio.gather(run, return_exceptions=True)
    assert not instance.busy()
    assert not worker.directory.exists()


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
    worker = SimpleNamespace(run_id='test-run', process=Process(), created_directory=False, ready=False, job=None, capability=None)
    instance._workers[worker.run_id] = worker
    monkeypatch.setattr(module.sys, 'platform', 'win32')
    await instance._cleanup_owned(worker)
    assert exited and not instance.busy()


@pytest.mark.asyncio
async def test_two_actual_workers_keep_ack_cancellation_and_cleanup_owned_by_run(tmp_path):
    from uuid import uuid4
    instance, executable = manager(tmp_path)
    instance._capacity = 2
    identities = [str(uuid4()), str(uuid4())]
    gates = {identity: asyncio.Event() for identity in identities}
    arrived = set()
    async def on_event(event):
        arrived.add(event['runId'])
        await gates[event['runId']].wait()
    tasks = [asyncio.create_task(instance.run(run_id=identity, execution_generation=1, execution_plan={'orderedNodeIds': ['open'], 'nodes': []}, parameters={}, variables={}, browser={}, executable=executable, on_event=on_event)) for identity in identities]
    try:
        async with asyncio.timeout(3):
            while len(arrived) != 2:
                for task in tasks:
                    if task.done(): task.result()
                await asyncio.sleep(.01)
        assert len({worker.process.pid for worker in instance._workers.values()}) == 2
        tasks[0].cancel()
        with pytest.raises(asyncio.CancelledError): await tasks[0]
        assert not instance.busy(identities[0]) and instance.busy(identities[1])
        assert not (instance._root / identities[0] / 'generation-1').exists()
        assert (instance._root / identities[1] / 'generation-1').exists()
        gates[identities[1]].set()
        assert (await tasks[1]).status == 'succeeded'
        assert not instance.busy()
    finally:
        for task in tasks:
            if not task.done(): task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await instance.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize('ownership', ['confirmed', 'unknown'])
async def test_windows_ownership_precedes_start_command(tmp_path, monkeypatch, ownership):
    from autoflow.infrastructure.process import project_workflow_worker as module
    from autoflow.infrastructure.process import windows_job
    instance, executable = manager(tmp_path)
    calls = []
    # This portable ordering check stubs native ownership only; the separate
    # native pre-ready test exercises the real bootstrap and Job membership.
    instance._command = (sys.executable, '-c', CHILD.replace('job = _windows_kill_on_exit_job()', 'job = None'))
    monkeypatch.setattr(module, 'sys', SimpleNamespace(platform='win32'))
    monkeypatch.setattr(module.subprocess, 'CREATE_NEW_PROCESS_GROUP', 0, raising=False)
    monkeypatch.setattr(windows_job, 'create_run_job', lambda name: calls.append('create') or 10, raising=False)
    def record(*args):
        calls.append('attach')
        if ownership == 'unknown': raise OSError('birth unavailable')
        return 11
    monkeypatch.setattr(windows_job, 'record_worker_job', record)
    monkeypatch.setattr(windows_job, 'terminate_worker_job', lambda *args: calls.append('terminate'))
    monkeypatch.setattr(windows_job, 'close_worker_job', lambda *args: None)
    send = instance._send
    async def checked_send(worker, message):
        if message['type'] == 'start':
            assert calls == ['create', 'attach']
            assert worker.job == 11
        await send(worker, message)
    monkeypatch.setattr(instance, '_send', checked_send)
    async def on_event(_event): pass
    run_id = 'a088a638-5afb-4b4b-8d83-45410a3cab42'
    run = instance.run(run_id=run_id, execution_generation=1, execution_plan={'nodes': []}, parameters={}, variables={}, browser={}, executable=executable, on_event=on_event)
    if ownership == 'unknown':
        with pytest.raises(WorkflowWorkerError, match='所有权尚未确认'):
            await run
        assert instance.busy(run_id)
        assert instance._workers[run_id].directory.exists()
        assert instance._workers[run_id].process.returncode is not None
    else:
        assert (await run).cleanup_confirmed
        assert not instance.busy()
    assert calls == ['create', 'attach', 'terminate']


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform != 'win32', reason='requires native Windows Job accounting')
@pytest.mark.parametrize('stop', ['cancel', 'timeout'])
async def test_native_windows_pre_ready_cleanup_confirms_all_descendants(tmp_path, stop):
    import json

    from autoflow.infrastructure.process.browser_processes import (
        process_birth,
        process_identity_is_alive,
    )
    instance, executable = manager(tmp_path)
    instance._termination_timeout = 3
    instance._start_timeout = 2 if stop == 'timeout' else 20
    instance._command = (sys.executable, '-c', r'''
import json, os, subprocess, sys, time
from autoflow.bootstrap.test_browser_worker import browser_worker_main
def run(stopped):
    json.loads(sys.stdin.readline())
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    with open(os.environ['PROOF'], 'w') as output: json.dump(child.pid, output)
    time.sleep(60)
    return 0
browser_worker_main(run)
''')
    async def on_event(_event): raise AssertionError('not ready')
    run_id = 'a088a638-5afb-4b4b-8d83-45410a3cab42'
    task = asyncio.create_task(instance.run(run_id=run_id, execution_generation=1, execution_plan={'nodes': []}, parameters={}, variables={}, browser={}, executable=executable, on_event=on_event))
    try:
        async with asyncio.timeout(10):
            while not (tmp_path / 'proof').exists():
                if task.done(): task.result()
                await asyncio.sleep(.01)
        child_pid = json.loads((tmp_path / 'proof').read_text())
        birth = process_birth(child_pid)
        assert birth is not None
        worker = instance._workers[run_id]
        assert worker.job is not None and not worker.ready
        if stop == 'cancel': task.cancel()
        with pytest.raises(asyncio.CancelledError if stop == 'cancel' else TimeoutError):
            await task
        assert not process_identity_is_alive(child_pid, birth)
        assert not worker.directory.exists() and not instance.busy()
    finally:
        if not task.done(): task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows venv redirector owns a nested Job')
def test_project_worker_launch_preserves_venv_without_redirector_job(tmp_path):
    import json
    import os
    import subprocess

    from autoflow.infrastructure.process.project_workflow_worker import (
        ProjectWorkflowWorkerManager,
    )
    script = 'import json,sys,autoflow,cloakbrowser; print(json.dumps([sys.prefix,sys.executable]))'
    manager = ProjectWorkflowWorkerManager(tmp_path / 'temp', command=(sys.executable, '-c', script))
    if sys.prefix != sys.base_prefix:
        assert manager._command[0] == sys._base_executable
    completed = subprocess.run(manager._command, env={**os.environ, **manager._worker_env}, capture_output=True, text=True, check=True)
    prefix, executable = json.loads(completed.stdout)
    assert Path(prefix).resolve() == Path(sys.prefix).resolve()
    assert Path(executable).resolve() == Path(sys.executable).resolve()


def test_result_cleanup_is_confined_to_current_generation_artifacts(tmp_path):
    instance, _ = manager(tmp_path)
    directory = tmp_path / 'workspace' / 'runs' / 'run' / 'generation-1'
    result = directory / 'artifacts' / 'nested' / 'capture.png'
    result.parent.mkdir(parents=True)
    result.write_bytes(b'png')
    other = tmp_path / 'other.png'
    other.write_bytes(b'keep')
    (directory / 'artifacts' / 'linked.png').symlink_to(other)
    instance._workers['run'] = SimpleNamespace(
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
