import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from autoflow.application.android.devices import AndroidDeviceService
from autoflow.domain.android.ports import AndroidError


class Repository:
    def __init__(self):
        self.device = {"deviceId": "device", "name": "test", "ownerRunId": None, "control": "idle", "generation": 0}

    def save(self, device):
        self.device = deepcopy(device)

    def claim(self, device_id, run_id):
        if self.device["ownerRunId"]:
            raise AndroidError("ANDROID_BUSY", "busy")
        self.device.update(ownerRunId=run_id, control="workflow")
        return deepcopy(self.device)

    def list(self):
        return [deepcopy(self.device)]


class Runtime:
    def __init__(self):
        self.locked = False
        self.opened = False
        self.commands = 0
        self.disconnect = AsyncMock()
        self.recover = AsyncMock()
        self.open_gate = asyncio.Event()
        self.open_gate.set()

    def lock(self):
        if self.locked:
            raise AndroidError("ANDROID_BUSY", "busy")
        self.locked = True

    def unlock(self):
        self.locked = False

    def window_open(self):
        return self.opened

    async def open_window(self, title):
        await self.open_gate.wait()
        self.opened = True

    async def close_window(self):
        self.opened = False

    async def command(self, *_args):
        self.commands += 1
        return b"ok"


async def wait_until(predicate):
    async with asyncio.timeout(2):
        while not predicate():
            await asyncio.sleep(.01)


async def fixture():
    runtime, repository = Runtime(), Repository()
    service = AndroidDeviceService(repository, runtime)
    service.claim("device", "run")
    emit = AsyncMock()
    waiting = asyncio.create_task(service.manual("node", {"timeoutSeconds": 30, "prompt": "manual"}, emit))
    await wait_until(lambda: service.handoff is not None)
    return service, runtime, repository, emit, waiting


@pytest.mark.asyncio
async def test_window_close_keeps_run_waiting_then_continue_only_once():
    service, runtime, repo, emit, waiting = await fixture()
    handoff_id = service.handoff["handoffId"]
    await service.control(handoff_id, "open", "open")
    await wait_until(runtime.window_open)
    with pytest.raises(AndroidError, match="不允许自动"):
        await service.command("android_key", {"key": "BACK"}, 1)
    assert runtime.commands == 0
    runtime.opened = False
    await wait_until(lambda: service.handoff["state"] == "closed")
    assert not waiting.done() and repo.device["ownerRunId"] == "run"
    await service.control(handoff_id, "resume", "continue")
    await service.control(handoff_id, "resume", "continue")
    await waiting
    assert sum(call.args[0]["type"] == "resumed" for call in emit.call_args_list) == 1
    assert not runtime.opened
    await service.cleanup()
    assert repo.device["control"] == "idle" and repo.device["ownerRunId"] is None


@pytest.mark.asyncio
async def test_old_handoff_rejected_and_cleanup_failure_retains_ownership():
    service, runtime, repo, _, waiting = await fixture()
    with pytest.raises(AndroidError, match="过期"):
        await service.control("old", "request", "open")
    waiting.cancel()
    await asyncio.gather(waiting, return_exceptions=True)
    runtime.disconnect.side_effect = OSError("transport unknown")
    with pytest.raises(OSError):
        await service.cleanup()
    assert repo.device["control"] == "recovery_required" and repo.device["ownerRunId"] == "run"
    assert runtime.locked
    runtime.disconnect.side_effect = None
    await service.cleanup()
    assert not runtime.locked


@pytest.mark.asyncio
async def test_stop_during_window_start_prevents_continue():
    service, runtime, repo, _, waiting = await fixture()
    runtime.open_gate.clear()
    await service.control(service.handoff["handoffId"], "open", "open")
    await wait_until(lambda: repo.device["control"] == "opening_manual")
    service.request_stop()
    with pytest.raises(AndroidError):
        await service.control(service.handoff["handoffId"], "resume", "continue")
    await asyncio.gather(waiting, return_exceptions=True)
    await service.cleanup()
    assert repo.device["control"] == "idle" and not runtime.opened


@pytest.mark.asyncio
async def test_persistence_failure_never_starts_window_or_resumes():
    service, runtime, _, emit, waiting = await fixture()
    emit.side_effect = OSError("database full")
    for action in ("open", "continue"):
        with pytest.raises(OSError):
            await service.control(service.handoff["handoffId"], action, action)
    assert service.open_task is None and not service.continued.is_set() and not runtime.opened
    waiting.cancel()
    await asyncio.gather(waiting, return_exceptions=True)
    await service.cleanup()


@pytest.mark.asyncio
async def test_expired_manual_cannot_resume_or_run_automatic_input():
    from datetime import UTC, datetime, timedelta
    service, runtime, _, _, waiting = await fixture()
    service.handoff['deadlineAt'] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    with pytest.raises(AndroidError, match='超时'):
        await service.control(service.handoff['handoffId'], 'late', 'continue')
    assert not service.continued.is_set() and runtime.commands == 0
    waiting.cancel()
    await asyncio.gather(waiting, return_exceptions=True)
    await service.cleanup()


@pytest.mark.asyncio
async def test_resume_finishing_after_deadline_does_not_advance():
    from datetime import UTC, datetime, timedelta
    service, runtime, repo, emit, waiting = await fixture()
    async def late_close():
        service.handoff['deadlineAt'] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    runtime.close_window = late_close
    await service.control(service.handoff['handoffId'], 'late', 'continue')
    await service.continue_task
    assert not service.continued.is_set()
    assert repo.device['control'] == 'recovery_required'
    assert not any(call.args[0]['type'] == 'resumed' for call in emit.call_args_list)
    waiting.cancel()
    await asyncio.gather(waiting, return_exceptions=True)
    await service.cleanup()


@pytest.mark.asyncio
async def test_manual_budget_exhaustion_and_failed_open_cleanup_stay_safe():
    runtime, repo = Runtime(), Repository()
    service = AndroidDeviceService(repo, runtime)
    service.claim('device', 'run')
    with pytest.raises(AndroidError, match='超时'):
        await service.manual('node', {'timeoutSeconds': .01, 'prompt': 'wait'}, AsyncMock())
    await service.cleanup()
    service, runtime, repo, _, waiting = await fixture()
    runtime.open_window = AsyncMock(side_effect=OSError('start failed'))
    runtime.close_window = AsyncMock(side_effect=OSError('close unknown'))
    await service.control(service.handoff['handoffId'], 'open', 'open')
    await service.open_task
    assert repo.device['control'] == 'recovery_required'
    with pytest.raises(AndroidError):
        await service.control(service.handoff['handoffId'], 'continue', 'continue')
    waiting.cancel()
    await asyncio.gather(waiting, return_exceptions=True)
    await service.cleanup()


@pytest.mark.asyncio
async def test_stop_while_continuing_cancels_close_before_resume_publication():
    service, runtime, repo, emit, waiting = await fixture()
    closing = asyncio.Event()
    async def slow_close():
        closing.set()
        await asyncio.Event().wait()
    runtime.close_window = slow_close
    await service.control(service.handoff['handoffId'], 'resume', 'continue')
    await closing.wait()
    service.request_stop()
    await asyncio.gather(waiting, return_exceptions=True)
    await service.cleanup()
    assert repo.device['control'] == 'idle' and not service.continued.is_set()
    assert not any(call.args[0]['type'] == 'resumed' for call in emit.call_args_list)


@pytest.mark.asyncio
async def test_recover_keeps_needs_verification_device_quarantined():
    runtime, repo = Runtime(), Repository()
    repo.device.update(
        control="managing",
        operation={"state": "needs_verification", "action": "start"},
    )
    service = AndroidDeviceService(repo, runtime)

    await service.recover()

    assert repo.device["control"] == "recovery_required"
    assert repo.device["lastError"]
    runtime.recover.assert_not_awaited()
    assert not runtime.locked


@pytest.mark.asyncio
async def test_recover_quarantines_idle_projection_with_unknown_operation():
    runtime, repo = Runtime(), Repository()
    repo.device.update(
        control="idle",
        operation={"state": "needs_verification", "action": "start"},
    )
    service = AndroidDeviceService(repo, runtime)

    await service.recover()

    assert repo.device["control"] == "recovery_required"
    runtime.recover.assert_not_awaited()


@pytest.mark.asyncio
async def test_startup_recovery_keeps_unresolved_app_marker_quarantined():
    runtime, repo = Runtime(), Repository()
    marker = "/data/local/tmp/autoflow-operation-" + "a" * 32
    repo.device.update(control="manual", ownerRunId="old-session", pendingCommand=marker)
    service = AndroidDeviceService(repo, runtime)

    await service.recover()

    assert repo.device["control"] == "recovery_required"
    assert repo.device["pendingCommand"] == marker
    assert repo.device["lastError"]
    runtime.recover.assert_awaited_once_with(repo.device, preserve_command=True)


@pytest.mark.asyncio
async def test_session_cleanup_does_not_release_unresolved_app_marker():
    runtime, repo = Runtime(), Repository()
    service = AndroidDeviceService(repo, runtime)
    service.claim("device", "old-session")
    marker = "/data/local/tmp/autoflow-operation-" + "b" * 32
    service.device["pendingCommand"] = marker
    service._save()

    await service.cleanup()

    assert repo.device["control"] == "recovery_required"
    assert repo.device["pendingCommand"] == marker
    assert repo.device["ownerRunId"] is None
    runtime.recover.assert_awaited_once_with(repo.device, preserve_command=True)


def test_current_runtime_boundary_rejects_retired_workflow_takeover():
    from autoflow.bootstrap.android import CurrentAndroidRunBoundary

    boundary = CurrentAndroidRunBoundary()
    assert boundary.device_context("device") is None
    with pytest.raises(AndroidError) as error:
        boundary.request_takeover("device")
    assert error.value.code == "ANDROID_TAKEOVER_UNAVAILABLE"
