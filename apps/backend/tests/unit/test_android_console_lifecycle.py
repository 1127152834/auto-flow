import asyncio
from copy import deepcopy

import pytest

from autoflow.application.android.console import AndroidConsole
from autoflow.domain.android.ports import AndroidError


@pytest.mark.asyncio
async def test_heartbeat_requires_session_identity_and_generation():
    console = AndroidConsole(None, None, None, None)
    console.sessions["s"] = {
        "view": {"id": "s", "generation": 3, "state": "connected", "clientSessionId": "client"},
        "clientSessionId": "client",
        "seen": 0,
    }
    view = await console.heartbeat("s", "client", 3)
    assert view["id"] == "s"
    with pytest.raises(AndroidError):
        await console.heartbeat("s", "other", 3)
    with pytest.raises(AndroidError):
        await console.heartbeat("s", "client", 2)


class _SessionResources:
    def __init__(self):
        self.saved = []

    def save(self, kind, item):
        self.saved.append((kind, deepcopy(item)))


class _AppRuntime:
    def __init__(self, failure=None):
        self.failure = failure
        self.calls = []
        self.console = None

    def window_open(self):
        return False

    async def command(self, operation, args, timeout):
        self.calls.append((operation, args, timeout))
        if self.console is not None:
            receipt = self.console.sessions["s"].get("appReceipts", {}).get("req")
            assert receipt is not None
            assert receipt["state"] == "running"
        if self.failure is not None:
            raise self.failure

    async def install_apk(self, value):
        self.calls.append(("install", value))
        if self.console is not None:
            receipt = self.console.sessions["s"].get("appReceipts", {}).get("req")
            assert receipt is not None
            assert receipt["state"] == "running"
        if self.failure is not None:
            raise self.failure


class _AppContext:
    def __init__(self, runtime):
        self.runtime = runtime
        self.device = {"generation": 3, "control": "manual"}
        self.stopping = False


def _app_console(failure=None):
    runtime = _AppRuntime(failure)
    resources = _SessionResources()
    console = AndroidConsole(None, None, resources, None)
    runtime.console = console
    console.sessions["s"] = {
        "view": {
            "id": "s",
            "deviceId": "device",
            "generation": 3,
            "access": "manual",
            "endpoint": "embedded",
            "state": "connected",
            "width": 720,
            "height": 1280,
            "latestOperation": None,
        },
        "context": _AppContext(runtime),
        "request": {"requestId": "s", "deviceId": "device", "access": "manual"},
        "stream": object(),
        "lock": asyncio.Lock(),
        "seen": 0,
    }
    return console, runtime, resources


@pytest.mark.asyncio
async def test_app_operation_records_running_before_side_effect_and_succeeded_after():
    console, runtime, resources = _app_console()
    view = await console.app_operation("s", 3, "launch", "com.example.app", "req")

    assert runtime.calls and runtime.calls[0][0] == "android_launch_app"
    assert resources.saved[0][1]["appReceipts"]["req"]["state"] == "running"
    assert console.sessions["s"]["appReceipts"]["req"] == {
        "request": {"generation": 3, "operation": "launch", "value": "com.example.app"},
        "state": "succeeded",
    }
    assert resources.saved[-1][1]["appReceipts"]["req"]["state"] == "succeeded"
    assert view["latestOperation"] == "应用已启动"


@pytest.mark.asyncio
async def test_app_operation_timeout_persists_unknown_and_replay_is_not_success():
    console, runtime, resources = _app_console(TimeoutError("adb timeout"))

    with pytest.raises(AndroidError) as error:
        await console.app_operation("s", 3, "launch", "com.example.app", "req")
    assert error.value.code == "ANDROID_OPERATION_UNKNOWN"
    assert error.value.status == 503
    receipt = console.sessions["s"]["appReceipts"]["req"]
    assert receipt["state"] == "needs_verification"
    assert resources.saved[-1][1]["appReceipts"]["req"]["state"] == "needs_verification"
    assert "核实" in console.sessions["s"]["view"]["latestOperation"]

    with pytest.raises(AndroidError) as replay:
        await console.app_operation("s", 3, "launch", "com.example.app", "req")
    assert replay.value.code == "ANDROID_OPERATION_UNKNOWN"
    assert len(runtime.calls) == 1


@pytest.mark.asyncio
async def test_app_operation_cancelled_persists_unknown_without_success_receipt():
    console, _runtime, resources = _app_console(asyncio.CancelledError())

    with pytest.raises(asyncio.CancelledError):
        await console.app_operation("s", 3, "install", b"PK apk", "req")
    assert console.sessions["s"]["appReceipts"]["req"]["state"] == "needs_verification"
    assert resources.saved[-1][1]["appReceipts"]["req"]["state"] == "needs_verification"
