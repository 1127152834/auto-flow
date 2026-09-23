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

    def get(self, kind, identifier):
        return next(deepcopy(item) for saved_kind, item in reversed(self.saved) if saved_kind == kind and item["id"] == identifier)


class _AppRuntime:
    def __init__(self, failure=None):
        self.failure = failure
        self.calls = []
        self.console = None

    def window_open(self):
        return False

    async def command(self, operation, args, timeout, *, retain_completion=False):
        self.calls.append((operation, args, timeout))
        if self.console is not None:
            receipt = next(iter(self.console.sessions["s"].get("appReceipts", {}).values()), None)
            assert receipt is not None
            assert receipt["state"] == "running"
        if self.failure is not None:
            raise self.failure

    async def install_apk(self, value):
        self.calls.append(("install", value))
        if self.console is not None:
            receipt = next(iter(self.console.sessions["s"].get("appReceipts", {}).values()), None)
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
@pytest.mark.parametrize("fail_terminal_save", [False, True])
async def test_successful_app_command_acknowledges_marker_after_terminal_receipt(fail_terminal_save):
    console, runtime, resources = _app_console()
    expect_save_failure = fail_terminal_save
    marker = "/data/local/tmp/autoflow-operation-" + "a" * 32
    device = console.sessions["s"]["context"].device
    original_command = runtime.command
    original_save = resources.save
    acknowledged = []

    async def command(*args, **kwargs):
        device["pendingCommand"] = marker
        return await original_command(*args, **kwargs)

    async def acknowledge(value):
        assert value == marker
        assert resources.saved[-1][1]["appReceipts"]["req"]["state"] == "succeeded"
        acknowledged.append(value)
        device.pop("pendingCommand")

    def save(kind, item):
        nonlocal fail_terminal_save
        if fail_terminal_save and item.get("appReceipts", {}).get("req", {}).get("state") == "succeeded":
            fail_terminal_save = False
            raise OSError("receipt write failed")
        original_save(kind, item)

    runtime.command = command
    runtime.acknowledge_pending_command = acknowledge
    resources.save = save
    if expect_save_failure:
        with pytest.raises(OSError, match="receipt write failed"):
            await console.app_operation("s", 3, "stop", "com.example.app", "req")
        assert device["pendingCommand"] == marker
        assert acknowledged == []
        await console.verify_app("s", 3, "req")
    else:
        await console.app_operation("s", 3, "stop", "com.example.app", "req")
    assert acknowledged == [marker]
    assert "pendingCommand" not in device


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

@pytest.mark.asyncio
async def test_install_observes_package_and_version_before_success():
    console, _runtime, _resources = _app_console()
    await console.app_operation(
        "s", 3, "install", b"opaque", "install-req",
        {"packageName": "com.example.app", "versionCode": 1, "versionName": None},
    )
    assert console.sessions["s"]["appReceipts"]["install-req"]["state"] == "succeeded"


@pytest.mark.asyncio
async def test_unknown_app_action_can_be_reconciled_by_marker_without_replay():
    console, runtime, _resources = _app_console(TimeoutError("adb timeout"))
    from unittest.mock import AsyncMock
    runtime.verify_pending_command = AsyncMock(return_value=0)
    runtime.acknowledge_pending_command = AsyncMock()
    original_command = runtime.command

    async def marked_command(*args, **kwargs):
        console.sessions["s"]["context"].device["pendingCommand"] = "completion-marker"
        return await original_command(*args, **kwargs)

    runtime.command = marked_command
    with pytest.raises(AndroidError) as error:
        await console.app_operation("s", 3, "stop", "com.example.app", "stop-req")
    assert error.value.code == "ANDROID_OPERATION_UNKNOWN"
    await console.verify_app("s", 3, "stop-req")
    assert console.sessions["s"]["appReceipts"]["stop-req"]["state"] == "succeeded"
    runtime.verify_pending_command.assert_awaited_once()
    assert len(runtime.calls) == 1

@pytest.mark.asyncio
async def test_install_version_mismatch_stays_unverified_until_explicit_reconciliation():
    console, runtime, _resources = _app_console()
    runtime.app_info = lambda: asyncio.sleep(0, result={"applications": [{"packageName": "com.example.app", "versionCode": 9}]})
    with pytest.raises(AndroidError) as error:
        await console.app_operation(
            "s", 3, "install", b"opaque", "install-mismatch",
            {"packageName": "com.example.app", "versionCode": 1, "versionName": None},
        )
    assert error.value.code == "ANDROID_INSTALL_VERIFY_FAILED"
    assert console.sessions["s"]["appReceipts"]["install-mismatch"]["state"] == "needs_verification"
    with pytest.raises(AndroidError) as verified:
        await console.verify_app("s", 3, "install-mismatch")
    assert verified.value.code == "ANDROID_INSTALL_VERIFY_FAILED"
    assert console.sessions["s"]["appReceipts"]["install-mismatch"]["state"] == "failed"


@pytest.mark.asyncio
async def test_post_install_android_observation_error_is_unknown():
    from unittest.mock import AsyncMock
    console, runtime, resources = _app_console()
    runtime.app_info = AsyncMock(side_effect=AndroidError("ANDROID_COMMAND_FAILED", "ADB disconnected", 502))
    with pytest.raises(AndroidError):
        await console.app_operation("s", 3, "install", b"opaque", "install-req",
                                    {"packageName": "com.example.app", "versionCode": 1})
    assert resources.saved[-1][1]["appReceipts"]["install-req"]["state"] == "needs_verification"


@pytest.mark.asyncio
async def test_unknown_receipt_blocks_new_application_writes_without_runtime_marker():
    console, runtime, _resources = _app_console(TimeoutError())
    with pytest.raises(AndroidError):
        await console.app_operation("s", 3, "stop", "com.example.app", "first")
    runtime.failure = None
    with pytest.raises(AndroidError) as error:
        await console.app_operation("s", 3, "stop", "com.example.app", "second")
    assert error.value.code == "ANDROID_OPERATION_UNKNOWN"
    assert len(runtime.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_receipt_save", [False, True])
async def test_app_verification_releases_marker_only_after_durable_receipt(tmp_path, monkeypatch, fail_receipt_save):
    from unittest.mock import AsyncMock

    from autoflow.providers.android import mac_runtime as mac

    console, _, resources = _app_console()
    session = console.sessions["s"]
    marker = "/data/local/tmp/autoflow-operation-" + "a" * 32
    session["appReceipts"] = {"req": {"state": "needs_verification", "commandMarker": marker,
                                      "request": {"operation": "stop", "generation": 3}}}
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    runtime.device = session["context"].device
    runtime.device.update(containerId="container", pendingCommand=marker)
    runtime.inspect = AsyncMock()
    session["context"].runtime = runtime
    original_save = resources.save

    def save(kind, item):
        nonlocal fail_receipt_save
        if fail_receipt_save and item["appReceipts"]["req"]["state"] == "succeeded":
            fail_receipt_save = False
            raise OSError("disk unavailable")
        original_save(kind, item)

    resources.save = save
    commands = []

    async def docker(*args, **kwargs):
        commands.append(args)
        if args[2] == "rm":
            assert resources.saved[-1][1]["appReceipts"]["req"]["state"] == "succeeded"
            return b""
        assert args == ("exec", "container", "cat", marker)
        return b"v2:0\n"

    monkeypatch.setattr(mac, "docker", docker)
    if fail_receipt_save:
        with pytest.raises(AndroidError):
            await console.verify_app("s", 3, "req")
        assert runtime.device["pendingCommand"] == marker
        assert all(command[2] == "cat" for command in commands)
    await console.verify_app("s", 3, "req")
    assert resources.saved[-1][1]["appReceipts"]["req"]["state"] == "succeeded"
    assert "pendingCommand" not in runtime.device
    assert commands[-1] == ("exec", "container", "rm", "-f", marker)


@pytest.mark.asyncio
async def test_app_verification_rejects_another_requests_marker():
    from unittest.mock import AsyncMock
    console, runtime, resources = _app_console()
    session = console.sessions["s"]
    session["appReceipts"] = {"req": {"state": "needs_verification", "commandMarker": "original",
                                      "request": {"operation": "stop", "generation": 3}}}
    session["context"].device["pendingCommand"] = "different"
    runtime.verify_pending_command = AsyncMock(return_value=0)
    with pytest.raises(AndroidError) as error:
        await console.verify_app("s", 3, "req")
    assert error.value.code == "ANDROID_OPERATION_UNKNOWN"
    assert resources.saved[-1][1]["appReceipts"]["req"]["state"] == "needs_verification"
    runtime.verify_pending_command.assert_not_awaited()


@pytest.mark.asyncio
async def test_installed_inventory_alone_cannot_resolve_timed_out_install():
    console, _runtime, resources = _app_console(TimeoutError())
    with pytest.raises(AndroidError):
        await console.app_operation("s", 3, "install", b"opaque", "req",
                                    {"packageName": "com.example.app", "versionCode": 1})
    with pytest.raises(AndroidError) as error:
        await console.verify_app("s", 3, "req")
    assert error.value.code == "ANDROID_OPERATION_UNKNOWN"
    assert resources.saved[-1][1]["appReceipts"]["req"]["state"] == "needs_verification"


@pytest.mark.asyncio
async def test_verification_retries_failed_receipt_save_before_acknowledging():
    from unittest.mock import AsyncMock
    console, runtime, resources = _app_console()
    session = console.sessions["s"]
    session["context"].device["pendingCommand"] = "marker"
    session["appReceipts"] = {"req": {"state": "needs_verification", "commandMarker": "marker",
                                      "request": {"operation": "stop", "generation": 3}}}
    runtime.verify_pending_command = AsyncMock(return_value=1)

    async def acknowledge(_marker):
        assert resources.saved[-1][1]["appReceipts"]["req"]["state"] == "failed"

    runtime.acknowledge_pending_command = acknowledge
    original_save = resources.save
    resources.save = lambda *_args: (_ for _ in ()).throw(OSError("disk unavailable"))
    with pytest.raises(OSError):
        await console.verify_app("s", 3, "req")
    resources.save = original_save
    with pytest.raises(AndroidError) as error:
        await console.verify_app("s", 3, "req")
    assert error.value.code == "ANDROID_APP_OPERATION_FAILED"


@pytest.mark.asyncio
@pytest.mark.parametrize("persisted_state", ["needs_verification", "running"])
async def test_restarted_console_verifies_persisted_app_receipt_before_releasing_marker(persisted_state):
    from autoflow.application.android.devices import AndroidDeviceService

    marker = "/data/local/tmp/autoflow-operation-" + "a" * 32
    device = {"deviceId": "device", "generation": 3, "control": "recovery_required", "pendingCommand": marker, "width": 720, "height": 1280}

    class Repository:
        def get(self, _device_id):
            return deepcopy(device)

        def save(self, value):
            device.clear()
            device.update(deepcopy(value))

    class Runtime:
        def __init__(self):
            self.device = None
            self.save = None
            self.acknowledged = []

        def lock(self):
            pass

        def unlock(self):
            pass

        async def verify_pending_command(self):
            assert self.device["pendingCommand"] == marker
            return 0

        async def acknowledge_pending_command(self, value):
            assert value == marker
            self.acknowledged.append(value)
            self.device.pop("pendingCommand")
            self.save()

    runtime = Runtime()
    resources = _SessionResources()
    receipt = {"state": persisted_state, "request": {"operation": "stop", "generation": 3}}
    if persisted_state != "running":
        receipt["commandMarker"] = marker
    resources.save("session", {"id": "s", "deviceId": "device", "request": {"requestId": "s", "deviceId": "device", "access": "manual"}, "appReceipts": {"req": receipt}})
    console = AndroidConsole(AndroidDeviceService(Repository(), runtime), None, resources, None)

    result = await console.verify_app("s", 3, "req")

    assert result["state"] == "recovery_required"
    assert resources.get("session", "s")["appReceipts"]["req"]["state"] == "succeeded"
    assert runtime.acknowledged == [marker]
    assert "pendingCommand" not in device


@pytest.mark.asyncio
async def test_restarted_install_verifies_package_without_disconnected_adb():
    from autoflow.application.android.devices import AndroidDeviceService

    marker = "/data/local/tmp/autoflow-operation-" + "b" * 32
    device = {"deviceId": "device", "generation": 3, "control": "recovery_required", "pendingCommand": marker, "width": 720, "height": 1280}

    class Repository:
        def get(self, _identifier):
            return deepcopy(device)

        def save(self, value):
            device.clear()
            device.update(deepcopy(value))

    class Runtime:
        def lock(self): pass
        def unlock(self): pass

        async def verify_pending_command(self):
            return 0

        async def app_info(self):
            raise AndroidError("ANDROID_DISCONNECTED", "no ADB tunnel", 503)

        async def app_info_for_verification(self):
            return {"applications": [{"packageName": "com.example.test", "versionCode": 7}]}

        async def acknowledge_pending_command(self, value):
            assert value == marker
            self.device.pop("pendingCommand")
            self.save()

    resources = _SessionResources()
    resources.save("session", {"id": "s", "deviceId": "device", "request": {"requestId": "s", "deviceId": "device", "access": "manual"}, "appReceipts": {"req": {"state": "needs_verification", "request": {"operation": "install", "generation": 3, "apkMetadata": {"packageName": "com.example.test", "versionCode": 7}}, "commandMarker": marker}}})
    result = await AndroidConsole(AndroidDeviceService(Repository(), Runtime()), None, resources, None).verify_app("s", 3, "req")
    assert result["state"] == "recovery_required"
    assert resources.get("session", "s")["appReceipts"]["req"]["state"] == "succeeded"
    assert "pendingCommand" not in device
