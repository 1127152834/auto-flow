import asyncio
import hashlib
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

    async def app_info(self):
        return {
            "applications": [
                {
                    "packageName": "org.vendor.settings",
                    "versionCode": 7,
                    "versionName": None,
                    "system": True,
                    "protected": True,
                },
                {
                    "packageName": "com.example.app",
                    "versionCode": 1,
                    "versionName": None,
                    "system": False,
                    "protected": False,
                },
            ]
        }


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


@pytest.mark.asyncio
async def test_apk_receipt_binds_request_id_to_content_digest():
    console, runtime, _resources = _app_console()
    first = b"PK\x03\x04first"
    second = b"PK\x03\x04second"

    await console.app_operation("s", 3, "install", first, "req")

    receipt = console.sessions["s"]["appReceipts"]["req"]
    assert receipt["request"]["payloadDigest"] == hashlib.sha256(first).hexdigest()
    with pytest.raises(AndroidError) as conflict:
        await console.app_operation("s", 3, "install", second, "req")
    assert conflict.value.code == "ANDROID_REQUEST_CONFLICT"
    assert len(runtime.calls) == 1


@pytest.mark.asyncio
async def test_destructive_app_operation_uses_runtime_metadata_to_protect_system_apps():
    console, runtime, _resources = _app_console()
    with pytest.raises(AndroidError) as error:
        await console.app_operation("s", 3, "uninstall", "org.vendor.settings", "req")
    assert error.value.code == "ANDROID_PROTECTED_APP"
    assert runtime.calls == []


@pytest.mark.asyncio
async def test_native_window_is_not_reaped_by_embedded_heartbeat_timeout(monkeypatch):
    console, runtime, _resources = _app_console()
    context = console.sessions["s"]["context"]
    context.device["control"] = "manual"
    context.runtime.window_open = lambda: True
    context.runtime.close_window = lambda: (_ for _ in ()).throw(AssertionError("native window closed"))
    console.sessions["s"]["view"].update(endpoint="native", state="connected")
    console.sessions["s"]["owned"] = True
    console.sessions["s"]["seen"] = 0

    sleep_calls = 0

    async def stop_after_one_tick(_delay):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls == 1:
            return
        raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "sleep", stop_after_one_tick)
    with pytest.raises(asyncio.CancelledError):
        await console._expire()

    assert console.sessions["s"]["view"]["state"] == "connected"
    assert context.device["control"] == "manual"
    assert runtime.calls == []
