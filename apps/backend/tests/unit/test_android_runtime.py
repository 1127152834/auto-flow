import json
import struct
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock

import pytest

from autoflow.bootstrap import android_prepare
from autoflow.domain.android.ports import AndroidError
from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.providers.android import mac_runtime as mac


def test_database_claim_has_one_winner(tmp_path):
    path = tmp_path / 'test.db'
    migrate_database(path)
    sessions = create_session_factory(path)
    repo = SqlAlchemyDeviceRepository(sessions)
    repo.save({'deviceId': 'device', 'control': 'idle', 'ownerRunId': None})
    def claim(owner):
        try:
            return repo.claim('device', owner)['ownerRunId']
        except AndroidError:
            return None
    with ThreadPoolExecutor(2) as pool:
        winners = list(pool.map(claim, ['one', 'two']))
    assert sum(winner is not None for winner in winners) == 1
    assert repo.get('device')['ownerRunId'] in winners
    sessions.dispose()


def test_package_inventory_accepts_platform_package_without_dot():
    assert mac.package_inventory(b"package:android versionCode:33\n") == {"android": 33}


def test_controller_lock_is_shared_across_workspaces(tmp_path, monkeypatch):
    monkeypatch.setattr(mac.platform, 'system', lambda: 'Darwin')
    first = mac.MacAndroidRuntime(tmp_path / 'shared', tmp_path / 'one')
    second = mac.MacAndroidRuntime(tmp_path / 'shared', tmp_path / 'two')
    first.lock()
    try:
        with pytest.raises(AndroidError, match='控制器'):
            second.lock()
    finally:
        first.unlock()
    second.lock()
    second.unlock()


@pytest.mark.asyncio
async def test_unsupported_platform_is_unavailable_without_running_commands(tmp_path, monkeypatch):
    monkeypatch.setattr(mac.platform, 'system', lambda: 'Windows')
    command = AsyncMock()
    monkeypatch.setattr(mac, 'docker', command)
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    assert not (await runtime.environment())['available']
    command.assert_not_awaited()
    with pytest.raises(AndroidError):
        runtime.lock()


@pytest.mark.asyncio
async def test_environment_reports_each_runtime_check(tmp_path, monkeypatch):
    monkeypatch.setattr(mac.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(mac.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(mac.shutil, "which", lambda tool: "/usr/bin/" + tool)
    vendor = tmp_path / mac.VENDOR
    vendor.mkdir()
    (vendor / "scrcpy").write_bytes(b"binary")

    async def fake_run(argv, *_args, **_kwargs):
        if argv[:2] == ["limactl", "list"]:
            return b"autoflow-redroid Running\n"
        if "/proc/filesystems" in argv:
            return b"nodev\tbinder\n"
        raise AssertionError(argv)

    monkeypatch.setattr(mac, "run", fake_run)
    monkeypatch.setattr(mac, "docker", AsyncMock(return_value=json.dumps({"OSType": "linux", "Architecture": "aarch64", "NCPU": 6, "MemTotal": 8 * 1024**3}).encode()))
    from autoflow.providers.android import management
    monkeypatch.setattr(management, "images", AsyncMock(return_value=[{"id": "sha256:image"}]))
    checks = (await mac.MacAndroidRuntime(tmp_path, tmp_path).environment())["checks"]
    assert {name: checks[name]["status"] for name in ("platform", "adb", "lima", "ssh", "scrcpy", "vm", "docker", "binder", "images", "capacity", "disk")} == {name: "pass" for name in ("platform", "adb", "lima", "ssh", "scrcpy", "vm", "docker", "binder", "images", "capacity", "disk")}


@pytest.mark.asyncio
async def test_capacity_rejects_unverified_host_resources(monkeypatch):
    from autoflow.providers.android import management

    monkeypatch.setattr(management, "docker", AsyncMock(return_value=b"{}"))
    with pytest.raises(AndroidError) as caught:
        await management.capacity({"containerId": "device", "cpu": 1, "memoryMb": 1536})
    assert caught.value.code == "ANDROID_CAPACITY_UNKNOWN"


@pytest.mark.asyncio
async def test_container_and_volume_ownership_are_independently_checked(tmp_path, monkeypatch):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    device = {'containerId': 'container', 'volumeId': 'data', 'workspaceId': runtime.workspace_id, 'deviceId': 'id'}
    container = {'Config': {'Labels': {'autoflow.demo': 'true'}}}
    docker = AsyncMock(return_value=json.dumps([container]).encode())
    monkeypatch.setattr(mac, 'docker', docker)
    with pytest.raises(AndroidError, match='归属'):
        await runtime.inspect(device)
    container['Config']['Labels'] = {mac.LABEL: runtime.workspace_id, 'io.autoflow.android.device': 'id'}
    container['Mounts'] = [{'Name': 'data', 'Destination': '/data'}]
    docker.side_effect = [json.dumps([container]).encode(), json.dumps([{'Labels': {mac.LABEL: runtime.workspace_id, 'io.autoflow.android.device': 'another-device'}}]).encode()]
    with pytest.raises(AndroidError, match='标签'):
        await runtime.inspect(device)


@pytest.mark.asyncio
async def test_stale_screenshot_basis_never_sends_tap(tmp_path):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    png = b'\x89PNG\r\n\x1a\n' + b'\0\0\0\rIHDR' + struct.pack('>II', 720, 1280)
    runtime._adb = AsyncMock(return_value=png)
    with pytest.raises(AndroidError, match='尺寸'):
        await runtime.command('android_tap', {'basisWidth': 1280, 'basisHeight': 720, 'x': 1, 'y': 1}, 1)
    assert runtime._adb.await_count == 1


@pytest.mark.asyncio
async def test_app_mutations_use_package_scoped_adb_commands(tmp_path):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    runtime.device = {}
    runtime.save = lambda: None
    runtime._adb = AsyncMock(side_effect=[b"", b"package:org.vendor.settings\n", b"package:com.example.app\n", b"Success\n"])
    await runtime.command("android_stop_app", {"packageName": "com.example.app"}, 1)
    await runtime.command("android_uninstall_app", {"packageName": "com.example.app"}, 1)
    assert runtime._adb.await_args_list[0].args[:3] == ("shell", "sh", "-c")
    assert "force-stop" in runtime._adb.await_args_list[0].args[3]
    assert "pm uninstall" in runtime._adb.await_args_list[3].args[3]


@pytest.mark.asyncio
async def test_reused_pid_is_not_signalled_but_unknown_live_identity_is_quarantined(tmp_path, monkeypatch):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    monkeypatch.setattr(mac, 'process_birth', lambda _: 222)
    signals = []
    monkeypatch.setattr(mac.os, 'kill', lambda pid, signal: signals.append((pid, signal)))
    await runtime.recover({'processes': {'viewer': {'pid': 123, 'birth': 111}}})
    assert not signals
    with pytest.raises(AndroidError, match='身份'):
        await runtime.recover({'processes': {'viewer': {'pid': 123, 'birth': None}}})
    assert signals == [(123, 0)]


@pytest.mark.asyncio
async def test_app_inventory_exposes_versions_and_actual_system_packages(tmp_path):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    async def adb(*args, **_kwargs):
        if args == ("shell", "pm", "list", "packages", "--show-versioncode"):
            return b"package:org.example.notes versionCode:42\npackage:org.vendor.settings versionCode:7\n"
        if args == ("shell", "pm", "list", "packages", "-s"):
            return b"package:org.vendor.settings\n"
        if args == ("shell", "dumpsys", "activity", "activities"):
            return b"mResumedActivity= ActivityRecord{abc u0 org.example.notes/.Main}"
        if args == ("shell", "id", "-u"):
            return b"2000\n"
        return b""
    runtime._adb = adb
    from autoflow.adapters.http.android_fleet_schemas import AppInfo
    info = AppInfo.model_validate(await runtime.app_info()).model_dump(by_alias=True)
    assert info["packages"] == ["org.example.notes", "org.vendor.settings"]
    assert info["applications"] == [
        {"packageName": "org.example.notes", "versionCode": 42, "versionName": None, "system": False, "protected": False},
        {"packageName": "org.vendor.settings", "versionCode": 7, "versionName": None, "system": True, "protected": True},
    ]
    assert info["currentPackage"] == "org.example.notes"


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["android_uninstall_app", "android_clear_app_data"])
async def test_oem_system_apps_are_protected_by_device_metadata(tmp_path, operation):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    runtime.device = {}
    calls = []
    async def adb(*args, **_kwargs):
        calls.append(args)
        if args[:5] == ("shell", "pm", "list", "packages", "-s"):
            return b"package:org.vendor.settings\n"
        return b"Success\n"
    runtime._adb = adb
    with pytest.raises(AndroidError) as error:
        await runtime.command(operation, {"packageName": "org.vendor.settings"}, 1)
    assert error.value.code == "ANDROID_PROTECTED_APP"
    assert not any(args[:3] == ("shell", "sh", "-c") for args in calls)
    assert "pendingCommand" not in runtime.device


@pytest.mark.asyncio
@pytest.mark.parametrize("inventory", [b"", b"Error: service unavailable\n"])
async def test_destructive_app_command_requires_confirmed_user_package(tmp_path, inventory):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    runtime.device = {}
    runtime._adb = AsyncMock(side_effect=[b"", inventory])
    with pytest.raises(AndroidError) as error:
        await runtime.command("android_clear_app_data", {"packageName": "org.example.notes"}, 1)
    assert error.value.code == "ANDROID_APP_INFO_UNKNOWN"
    assert "pendingCommand" not in runtime.device


@pytest.mark.asyncio
async def test_backup_volume_uses_docker_copy_without_starting_android_image(tmp_path, monkeypatch):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    calls = []

    async def fake_docker(*args, **kwargs):
        calls.append((args, kwargs))
        if args[0] == "create":
            return b"backup-container\n"
        if args[0] == "cp":
            return b"tar-bytes"
        return b""

    monkeypatch.setattr(mac, "docker", fake_docker)
    result = await runtime.backup_volume({"volumeId": "volume", "imageId": "image", "deviceId": "device"})
    assert result == b"tar-bytes"
    assert calls[0][0][0] == "create"
    assert calls[1][0] == ("cp", "backup-container:/data", "-")
    assert calls[-1][0] == ("rm", "backup-container")


@pytest.mark.asyncio
async def test_restore_volume_rejects_foreign_workspace_before_docker_write(tmp_path, monkeypatch):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    docker = AsyncMock()
    monkeypatch.setattr(mac, "docker", docker)

    with pytest.raises(AndroidError, match="归属"):
        await runtime.restore_volume(
            {
                "deviceId": "device",
                "workspaceId": "foreign-workspace",
                "volumeId": "device-data",
                "imageId": "sha256:" + "a" * 64,
                "androidStatus": "stopped",
                "control": "idle",
            },
            b"archive",
        )

    docker.assert_not_awaited()


@pytest.mark.asyncio
async def test_restore_volume_rejects_running_target_before_docker_write(tmp_path, monkeypatch):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    docker = AsyncMock()
    monkeypatch.setattr(mac, "docker", docker)

    with pytest.raises(AndroidError, match="停止"):
        await runtime.restore_volume(
            {
                "deviceId": "device",
                "workspaceId": runtime.workspace_id,
                "volumeId": "device-data",
                "imageId": "sha256:" + "a" * 64,
                "androidStatus": "ready",
                "control": "idle",
            },
            b"archive",
        )

    docker.assert_not_awaited()


@pytest.mark.asyncio
async def test_restore_volume_rejects_foreign_volume_labels_before_write(tmp_path, monkeypatch):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    calls = []

    async def fake_docker(*args, **kwargs):
        calls.append((args, kwargs))
        if args[:2] == ("volume", "inspect"):
            return json.dumps([{"Labels": {mac.LABEL: runtime.workspace_id, "io.autoflow.android.device": "another-device"}}]).encode()
        raise AssertionError(args)

    monkeypatch.setattr(mac, "docker", fake_docker)

    with pytest.raises(AndroidError, match="归属"):
        await runtime.restore_volume(
            {
                "deviceId": "device",
                "workspaceId": runtime.workspace_id,
                "volumeId": "device-data",
                "imageId": "sha256:" + "a" * 64,
                "androidStatus": "stopped",
                "control": "idle",
            },
            b"archive",
        )

    assert calls and calls[0][0][:2] == ("volume", "inspect")


@pytest.mark.asyncio
async def test_inspect_image_reports_missing_digest_as_not_found(tmp_path, monkeypatch):
    async def missing(*_args, **_kwargs):
        raise AndroidError("ANDROID_COMMAND_FAILED", "docker image inspect: No such image", 502)

    monkeypatch.setattr(mac, "docker", missing)
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)

    with pytest.raises(AndroidError) as error:
        await runtime.inspect_image("sha256:" + "a" * 64)

    assert error.value.status == 404
    assert error.value.code == "ANDROID_IMAGE_NOT_FOUND"


@pytest.mark.asyncio
async def test_prepare_uses_the_same_workspace_root_as_the_running_service(tmp_path, monkeypatch):
    seen: list[object] = []

    class Runtime:
        def __init__(self, _root, workspace):
            seen.append(workspace)

        def lock(self):
            return None

        def unlock(self):
            return None

        async def disconnect(self):
            return None

    monkeypatch.setattr(android_prepare, "MacAndroidRuntime", Runtime)

    await android_prepare.prepare(tmp_path, None, True)

    assert seen == [tmp_path / "workspace"]

@pytest.mark.asyncio
async def test_verify_pending_command_preserves_evidence_until_receipt_is_durable(tmp_path, monkeypatch):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    marker = "/data/local/tmp/autoflow-operation-" + "a" * 32
    runtime.device = {"containerId": "container", "pendingCommand": marker}
    runtime.inspect = AsyncMock(return_value={"androidStatus": "ready"})
    runtime.save = lambda: None
    docker = AsyncMock(side_effect=[b"0\n", b""])
    monkeypatch.setattr(mac, "docker", docker)
    assert await runtime.verify_pending_command() == 0
    assert runtime.device["pendingCommand"] == marker
    assert docker.await_args_list[0].args[:4] == ("exec", "container", "cat", marker)
    assert docker.await_count == 1


@pytest.mark.asyncio
async def test_missing_command_marker_is_not_evidence_of_success(tmp_path):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    runtime.device = {"containerId": "container"}
    with pytest.raises(AndroidError) as error:
        await runtime.verify_pending_command()
    assert error.value.code == "ANDROID_OPERATION_UNKNOWN"
