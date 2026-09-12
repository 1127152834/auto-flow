import asyncio
import json
from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

import pytest

from autoflow.adapters.events.workflows import workflow_event_stream
from autoflow.domain.profiles.errors import ProfileDirectoryBusy, ProxyUnavailable
from autoflow.domain.workflows.models import WorkflowError
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_runs import (
    SqlAlchemyWorkflowRunRepository,
)
from autoflow.infrastructure.filesystem.kernel_installations import kernel_target_lock
from autoflow.infrastructure.filesystem.workflow_artifacts import WorkflowArtifacts
from tests.fixtures.workflow_runs import close_workflow_runtime, workflow_runtime
from tests.fixtures.workflows import workflow_payload


@pytest.mark.asyncio
async def test_run_snapshot_idempotency_occupancy_and_cleanup(tmp_path):
    app, profile, worker = workflow_runtime(tmp_path)
    service = app.state.workflow_run_service
    payload = workflow_payload()
    run_id = str(uuid4())
    accepted = await service.start(run_id, **payload, profile_id=profile.id)
    assert accepted["document"] == payload["document"]
    assert accepted["state"] == "starting"
    await worker.started.wait()
    assert (await service.start(run_id, **payload, profile_id=profile.id))["runId"] == run_id
    assert worker.executions == 1
    with pytest.raises(WorkflowError, match="不同请求"):
        await service.start(run_id, {**payload["document"], "name": "different"}, payload["layout"], profile.id)
    with pytest.raises(WorkflowError, match="已有运行"):
        await service.start(str(uuid4()), **payload, profile_id=profile.id)
    payload["document"]["name"] = "编辑器已修改"
    assert service.get(run_id)["name"] == "测试流程"
    assert service.get(run_id)["document"]["name"] == "测试流程"
    app.state.profile_service.update(profile.id, replace(profile.spec, name="可以修改配置"))
    assert service.get(run_id)["profileName"] == "运行配置"
    with pytest.raises(ProfileDirectoryBusy):
        app.state.profile_service.remove(profile.id)
    lock = kernel_target_lock(app.state.paths.kernels, "public", "145.0.0.1")
    assert not lock.acquire()
    worker.cleanup.clear()
    stopping = asyncio.create_task(service.stop(run_id))
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert service.get(run_id)["state"] == "stopping"
    assert not stopping.done() and not lock.acquire()
    worker.cleanup.set()
    stopped = await asyncio.wait_for(stopping, 2)
    assert stopped["state"] == "cancelled" and worker.cleaned.is_set()
    assert not service.busy()
    assert lock.acquire()
    lock.release()
    assert await service.stop(run_id) == stopped
    app.state.profile_service.remove(profile.id)
    await close_workflow_runtime(app)


@pytest.mark.asyncio
async def test_stop_before_task_start_and_during_proxy_resolution_releases_resources(tmp_path):
    app, profile, worker = workflow_runtime(tmp_path)
    service = app.state.workflow_run_service
    payload = workflow_payload()
    run_id = str(uuid4())
    await service.start(run_id, **payload, profile_id=profile.id)
    assert (await service.stop(run_id))["state"] == "cancelled"
    assert worker.executions == 0
    entered = asyncio.Event()

    async def slow_proxy(_profile, _run_id):
        entered.set()
        await asyncio.Event().wait()

    service._resolve_proxy = slow_proxy
    run_id = str(uuid4())
    await service.start(run_id, **payload, profile_id=profile.id)
    await entered.wait()
    await asyncio.wait_for(service.stop(run_id), 2)
    assert service.get(run_id)["state"] == "cancelled"
    assert worker.executions == 0 and not service.busy()
    app.state.profile_service.remove(profile.id)
    await close_workflow_runtime(app)


@pytest.mark.asyncio
async def test_missing_resources_and_failed_proxy_are_safe_and_not_replayed(tmp_path):
    app, profile, worker = workflow_runtime(tmp_path)
    service = app.state.workflow_run_service
    payload = workflow_payload()
    with pytest.raises(WorkflowError) as missing:
        await service.start(str(uuid4()), **payload, profile_id=str(uuid4()))
    assert missing.value.code == "WORKFLOW_PROFILE_NOT_FOUND"
    assert missing.value.issues[0].path == ["profileId"]
    installed = service._installed_kernels
    service._installed_kernels = list
    with pytest.raises(WorkflowError) as kernel:
        await service.start(str(uuid4()), **payload, profile_id=profile.id)
    assert kernel.value.code == "WORKFLOW_KERNEL_UNAVAILABLE"
    service._installed_kernels = installed

    async def failed_proxy(_profile, _run_id):
        raise ProxyUnavailable("secret-password-must-not-leak")

    service._resolve_proxy = failed_proxy
    run_id = str(uuid4())
    await service.start(run_id, **payload, profile_id=profile.id)
    task = service._active[run_id].task
    await task
    result = service.get(run_id)
    assert result["state"] == "failed"
    assert result["error"]["code"] == "WORKFLOW_PROXY_UNAVAILABLE"
    assert "secret-password" not in json.dumps(result)
    assert worker.executions == 0
    assert (await service.start(run_id, **payload, profile_id=profile.id))["state"] == "failed"
    await close_workflow_runtime(app)


@pytest.mark.asyncio
async def test_persisted_events_resume_without_loss_and_full_results_are_files(tmp_path):
    app, profile, worker = workflow_runtime(tmp_path)
    service = app.state.workflow_run_service
    run_id = str(uuid4())
    await service.start(run_id, **workflow_payload(), profile_id=profile.id)
    await worker.started.wait()
    files = WorkflowArtifacts(app.state.paths.workspace / "runs", run_id)
    artifact = files.save_json("n4", "x" * 70000)
    worker.artifact = artifact
    for index in range(420):
        await worker.callback({"type": "log", "message": f"event-{index}"})
    cursor = service.events(run_id, 0, 2)
    assert cursor["hasMore"] and cursor["nextSeq"] == 2
    worker.complete.set()
    await service._active[run_id].task
    result = service.get(run_id)
    assert result["state"] == "succeeded"
    assert result["completedNodeIds"] == result["nodeOrder"]
    assert len(result["artifacts"][0]["preview"]) <= 240
    frames = [frame async for frame in workflow_event_stream(service, run_id, 2)]
    events = [json.loads(frame.split("data: ")[1]) for frame in frames]
    assert [item["seq"] for item in events] == list(range(3, result["latestSeq"] + 1))
    assert len(json.dumps(events)) < 160000
    path, registered = service.artifact(run_id, artifact["id"])
    assert registered == artifact and len(json.loads(path.read_text())) == 70000
    with pytest.raises(WorkflowError):
        service.artifact(run_id, "unregistered")
    outside = tmp_path / "private.json"
    outside.write_text('"private"')
    path.unlink()
    path.symlink_to(outside)
    with pytest.raises(WorkflowError):
        service.artifact(run_id, artifact["id"])
    database = app.state.paths.database
    await close_workflow_runtime(app)
    migrate_database(database)
    factory = create_session_factory(database)
    reopened = SqlAlchemyWorkflowRunRepository(factory)
    assert reopened.get(run_id).data == result
    assert reopened.events(run_id, 2, 1000) == events
    factory.dispose()


@pytest.mark.asyncio
async def test_live_stream_sees_new_commits_and_shutdown_awaits_cleanup(tmp_path):
    app, profile, worker = workflow_runtime(tmp_path)
    service = app.state.workflow_run_service
    run_id = str(uuid4())
    await service.start(run_id, **workflow_payload(), profile_id=profile.id)
    await worker.started.wait()
    stream = workflow_event_stream(service, run_id, service.get(run_id)["latestSeq"], heartbeat_interval=.01)
    assert await anext(stream) == ": heartbeat\n\n"
    pending = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    await worker.callback({"type": "log", "message": "new event"})
    assert "new event" in await pending
    worker.cleanup.clear()
    shutdown = asyncio.create_task(service.shutdown())
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert not shutdown.done()
    with pytest.raises(WorkflowError):
        await service.start(str(uuid4()), **workflow_payload(), profile_id=profile.id)
    worker.cleanup.set()
    await asyncio.wait_for(shutdown, 2)
    assert service.get(run_id)["state"] == "cancelled" and not service.busy()
    await stream.aclose()
    await close_workflow_runtime(app)


@pytest.mark.asyncio
async def test_recovery_marks_stale_run_interrupted_without_replay(tmp_path):
    app, profile, _worker = workflow_runtime(tmp_path)
    service = app.state.workflow_run_service
    payload = workflow_payload()
    run_id = str(uuid4())
    await service.start(run_id, **payload, profile_id=profile.id)
    await service.stop(run_id)
    # Recreate the durable state left by a killed service, without leaving a process.
    service.repository.append(run_id, {"type": "log", "message": "fixture"}, {"state": "running", "finishedAt": None})
    service.repository.recover_interrupted()
    record = service.get(run_id)
    assert record["state"] == "interrupted" and record["finishedAt"]
    assert service.repository.active_id() is None
    assert (await service.start(run_id, **payload, profile_id=profile.id)) == record
    count = record["latestSeq"]
    service.repository.recover_interrupted()
    assert service.get(run_id)["latestSeq"] == count
    await close_workflow_runtime(app)


@pytest.mark.asyncio
async def test_draft_errors_reject_before_acceptance_and_duplicate_outputs_warn(tmp_path):
    app, profile, worker = workflow_runtime(tmp_path)
    service = app.state.workflow_run_service
    payload = workflow_payload()
    invalid = deepcopy(payload)
    invalid["document"]["nodes"][0]["config"]["url"] = ""
    with pytest.raises(WorkflowError) as failed:
        await service.start(str(uuid4()), **invalid, profile_id=profile.id)
    assert failed.value.issues[0].node_id == "n0"
    assert service.list(None, 0, 20)["items"] == []
    payload["document"]["nodes"][5]["config"]["variableName"] = "element_value"
    run_id = str(uuid4())
    result = await service.start(run_id, **payload, profile_id=profile.id)
    assert result["warnings"]
    await worker.started.wait()
    assert any(event["level"] == "warning" for event in service.events(run_id, 0, 20)["items"])
    await service.stop(run_id)
    await close_workflow_runtime(app)


@pytest.mark.asyncio
async def test_initial_event_failure_rolls_back_acceptance_and_resource_guards(tmp_path):
    from sqlalchemy import event

    app, profile, worker = workflow_runtime(tmp_path)
    service = app.state.workflow_run_service
    engine = app.state.session_factory.kw["bind"]

    def fail_event(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.startswith("INSERT INTO workflow_run_events"):
            raise RuntimeError("simulated disk write failure")

    event.listen(engine, "before_cursor_execute", fail_event)
    run_id = str(uuid4())
    try:
        with pytest.raises(WorkflowError):
            await service.start(run_id, **workflow_payload(), profile_id=profile.id)
    finally:
        event.remove(engine, "before_cursor_execute", fail_event)
    assert service.repository.get(run_id) is None
    assert not service.busy() and worker.executions == 0
    with app.state.profile_service.profile_usage.guard(profile.id):
        pass
    await close_workflow_runtime(app)


@pytest.mark.asyncio
async def test_shutdown_request_cancellation_still_waits_for_cleanup(tmp_path):
    app, profile, worker = workflow_runtime(tmp_path)
    service = app.state.workflow_run_service
    run_id = str(uuid4())
    await service.start(run_id, **workflow_payload(), profile_id=profile.id)
    await worker.started.wait()
    worker.cleanup.clear()
    shutdown = asyncio.create_task(service.shutdown())
    await asyncio.sleep(0)
    shutdown.cancel()
    await asyncio.sleep(0)
    assert not shutdown.done() and service.busy()
    worker.cleanup.set()
    await asyncio.wait_for(shutdown, 2)
    assert worker.cleaned.is_set() and service.get(run_id)["state"] == "cancelled"
    await close_workflow_runtime(app)


@pytest.mark.asyncio
async def test_failed_stopping_event_cannot_block_cleanup_or_idempotent_stop(tmp_path, monkeypatch):
    app, profile, worker = workflow_runtime(tmp_path)
    service = app.state.workflow_run_service
    run_id = str(uuid4())
    await service.start(run_id, **workflow_payload(), profile_id=profile.id)
    await worker.started.wait()
    original = service.repository.append

    def fail_stopping(run_id, event, changes):
        if event["type"] == "stopping":
            raise OSError("simulated stopping event write failure")
        return original(run_id, event, changes)

    monkeypatch.setattr(service.repository, "append", fail_stopping)
    first, second = await asyncio.wait_for(asyncio.gather(service.stop(run_id), service.stop(run_id)), 2)
    assert first == second and first["state"] == "cancelled"
    assert worker.cleaned.is_set() and not service.busy()
    assert await service.stop(run_id) == first
    assert [event["type"] for event in service.events(run_id, 0, 100)["items"]].count("cancelled") == 1
    await close_workflow_runtime(app)


@pytest.mark.asyncio
@pytest.mark.parametrize("recovery", ["get", "list", "busy", "start", "stop"])
async def test_terminal_write_failure_keeps_bounded_retry_ownership(tmp_path, monkeypatch, recovery):
    app, profile, worker = workflow_runtime(tmp_path)
    service = app.state.workflow_run_service
    run_id = str(uuid4())
    payload = workflow_payload()
    await service.start(run_id, **payload, profile_id=profile.id)
    await worker.started.wait()
    original = service.repository.append

    def fail_terminal(run_id, event, changes):
        if event["type"] == "succeeded":
            raise OSError("simulated persistent terminal write failure")
        return original(run_id, event, changes)

    monkeypatch.setattr(service.repository, "append", fail_terminal)
    task = service._active[run_id].task
    worker.complete.set()
    await asyncio.wait_for(task, 2)
    assert worker.cleaned.is_set() and run_id not in service._active
    assert service.repository.get(run_id).data["state"] == "finishing"
    assert service.repository.active_id() == run_id and service.busy()
    with app.state.profile_service.profile_usage.guard(profile.id):
        pass
    lock = kernel_target_lock(app.state.paths.kernels, "public", "145.0.0.1")
    assert lock.acquire()
    lock.release()
    with pytest.raises(WorkflowError) as failed:
        await asyncio.wait_for(service.stop(run_id), 2)
    assert failed.value.status == 503 and failed.value.code == "WORKFLOW_RUN_PERSISTENCE_PENDING"
    finished_at = service._pending_completions[run_id].changes["finishedAt"]
    monkeypatch.setattr(service.repository, "append", original)
    if recovery == "get":
        # Reads may run in the HTTP threadpool; retry notifications must remain safe.
        assert (await asyncio.to_thread(service.get, run_id))["state"] == "succeeded"
    elif recovery == "list":
        assert service.list(None, 0, 10)["activeRunId"] is None
    elif recovery == "busy":
        assert not service.busy()
    elif recovery == "start":
        assert (await service.start(run_id, **payload, profile_id=profile.id))["state"] == "succeeded"
    else:
        assert (await service.stop(run_id))["state"] == "succeeded"
    assert service.get(run_id)["finishedAt"] == finished_at
    assert service.repository.active_id() is None and not service.busy()
    assert not service._pending_completions
    assert [event["type"] for event in service.events(run_id, 0, 100)["items"]].count("succeeded") == 1
    assert worker.executions == 1
    await close_workflow_runtime(app)


@pytest.mark.asyncio
async def test_terminal_commit_with_lost_acknowledgment_does_not_duplicate_event(tmp_path, monkeypatch):
    app, profile, worker = workflow_runtime(tmp_path)
    service = app.state.workflow_run_service
    run_id = str(uuid4())
    await service.start(run_id, **workflow_payload(), profile_id=profile.id)
    await worker.started.wait()
    original = service.repository.append

    def uncertain_commit(run_id, event, changes):
        result = original(run_id, event, changes)
        if event["type"] == "succeeded":
            raise OSError("simulated lost acknowledgment after commit")
        return result

    monkeypatch.setattr(service.repository, "append", uncertain_commit)
    task = service._active[run_id].task
    worker.complete.set()
    await asyncio.wait_for(task, 2)
    assert service.get(run_id)["state"] == "succeeded"
    assert not service._pending_completions and not service.busy()
    assert [event["type"] for event in service.events(run_id, 0, 100)["items"]].count("succeeded") == 1
    await close_workflow_runtime(app)


@pytest.mark.asyncio
async def test_shutdown_cleans_when_database_reads_and_writes_fail(tmp_path, monkeypatch):
    app, profile, worker = workflow_runtime(tmp_path)
    service = app.state.workflow_run_service
    run_id = str(uuid4())
    await service.start(run_id, **workflow_payload(), profile_id=profile.id)
    await worker.started.wait()
    read, append = service.repository.get, service.repository.append

    def unavailable(*_args, **_kwargs):
        raise OSError("simulated unavailable database")

    monkeypatch.setattr(service.repository, "get", unavailable)
    monkeypatch.setattr(service.repository, "append", unavailable)
    await asyncio.wait_for(service.shutdown(), 2)
    assert worker.cleaned.is_set() and not service._active
    assert run_id in service._pending_completions
    with app.state.profile_service.profile_usage.guard(profile.id):
        pass
    monkeypatch.setattr(service.repository, "get", read)
    monkeypatch.setattr(service.repository, "append", append)
    assert read(run_id).data["state"] == "running"
    assert service.get(run_id)["state"] == "cancelled"
    assert not service.busy()
    await close_workflow_runtime(app)


@pytest.mark.asyncio
async def test_acceptance_read_failure_cannot_release_a_running_tasks_guards(tmp_path, monkeypatch):
    app, profile, _worker = workflow_runtime(tmp_path)
    service = app.state.workflow_run_service
    original = service.repository.get
    reads = 0

    def fail_after_initial_lookup(run_id):
        nonlocal reads
        reads += 1
        if reads > 1:
            raise OSError("simulated post-acceptance read failure")
        return original(run_id)

    monkeypatch.setattr(service.repository, "get", fail_after_initial_lookup)
    run_id = str(uuid4())
    accepted = await service.start(run_id, **workflow_payload(), profile_id=profile.id)
    assert accepted["state"] == "starting" and run_id in service._active
    with pytest.raises(ProfileDirectoryBusy), app.state.profile_service.profile_usage.guard(profile.id):
        pass
    monkeypatch.setattr(service.repository, "get", original)
    assert (await service.stop(run_id))["state"] == "cancelled"
    await close_workflow_runtime(app)


@pytest.mark.asyncio
async def test_final_cleanup_failure_retains_guards_until_stop_retries(tmp_path, monkeypatch):
    app, profile, worker = workflow_runtime(tmp_path)
    service = app.state.workflow_run_service
    run_id = str(uuid4())
    await service.start(run_id, **workflow_payload(), profile_id=profile.id)
    await worker.started.wait()
    original = worker.stop
    attempts = 0

    async def fail_first_cleanup(run_id):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise WorkflowError("WORKFLOW_CLEANUP_FAILED", "浏览器清理尚未完成，请重试停止", 503)
        await original(run_id)

    monkeypatch.setattr(worker, "stop", fail_first_cleanup)
    task = service._active[run_id].task
    worker.complete.set()
    await asyncio.wait_for(task, 2)
    assert attempts == 1
    record = service.get(run_id)
    assert record["state"] == "finishing" and record["finishedAt"] is None
    assert record["error"]["code"] == "WORKFLOW_CLEANUP_FAILED"
    assert service.busy() and run_id in service._active
    assert not service._pending_completions
    with pytest.raises(ProfileDirectoryBusy):
        app.state.profile_service.remove(profile.id)
    lock = kernel_target_lock(app.state.paths.kernels, "public", "145.0.0.1")
    assert not lock.acquire()
    assert not any(event["type"] in {"succeeded", "failed", "cancelled"} for event in service.events(run_id, 0, 100)["items"])
    result = await asyncio.wait_for(service.stop(run_id), 2)
    assert attempts == 2 and result["state"] == "cancelled"
    assert result["finishedAt"] and result["error"] is None
    assert not service.busy() and run_id not in service._active
    assert lock.acquire()
    lock.release()
    app.state.profile_service.remove(profile.id)
    await close_workflow_runtime(app)


@pytest.mark.asyncio
async def test_execute_cleanup_error_keeps_owner_and_shutdown_can_retry(tmp_path, monkeypatch):
    app, profile, worker = workflow_runtime(tmp_path)
    service = app.state.workflow_run_service
    allow_cleanup = False

    async def execute_with_failed_cleanup(*args, **kwargs):
        worker.active = True
        raise WorkflowError("WORKFLOW_CLEANUP_FAILED", "浏览器清理尚未完成，请重试停止", 503)

    async def retry_cleanup(_run_id):
        if not allow_cleanup:
            raise WorkflowError("WORKFLOW_CLEANUP_FAILED", "浏览器清理尚未完成，请重试停止", 503)
        worker.active = False
        worker.cleaned.set()

    monkeypatch.setattr(worker, "execute", execute_with_failed_cleanup)
    monkeypatch.setattr(worker, "stop", retry_cleanup)
    run_id = str(uuid4())
    await service.start(run_id, **workflow_payload(), profile_id=profile.id)
    await service._active[run_id].task
    assert service.get(run_id)["state"] == "finishing"
    assert worker.busy() and service.busy()
    with pytest.raises(WorkflowError) as failed:
        await asyncio.wait_for(service.shutdown(), 2)
    assert failed.value.code == "WORKFLOW_CLEANUP_FAILED"
    assert run_id in service._active and service.get(run_id)["finishedAt"] is None
    with pytest.raises(ProfileDirectoryBusy), app.state.profile_service.profile_usage.guard(profile.id):
        pass
    allow_cleanup = True
    await asyncio.wait_for(service.shutdown(), 2)
    assert worker.cleaned.is_set() and not service.busy()
    assert service.get(run_id)["state"] == "cancelled"
    assert await service.stop(run_id) == service.get(run_id)
    await close_workflow_runtime(app)
