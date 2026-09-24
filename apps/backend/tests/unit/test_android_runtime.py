import asyncio
import json
import os
import shlex
import signal
import struct
import sys
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


@pytest.mark.asyncio
async def test_file_backed_command_streams_stdin_and_stdout(tmp_path):
    source = tmp_path / "source.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(b"android-volume-data" * 4096)

    await mac.run_file([sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read()[::-1])"], 5, input_path=source, output_path=target)

    assert target.read_bytes() == source.read_bytes()[::-1]


@pytest.mark.asyncio
@pytest.mark.skipif(os.name != "posix", reason="Mac command descendants use POSIX process groups")
@pytest.mark.parametrize("runner", ["run", "run_file"])
@pytest.mark.parametrize("stop", ["cancel", "timeout"])
async def test_command_cancellation_or_timeout_stops_descendant_writes(tmp_path, runner, stop):
    written = tmp_path / "written"
    child_pid = tmp_path / "child.pid"
    child = "import sys,time\nf=open(sys.argv[1],'ab',buffering=0)\nwhile True:\n f.write(b'x')\n time.sleep(.01)\n"
    parent = "import pathlib,subprocess,sys,time\np=subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\npathlib.Path(sys.argv[3]).write_text(str(p.pid))\ntime.sleep(30)\n"
    task = asyncio.create_task(getattr(mac, runner)([sys.executable, "-c", parent, child, str(written), str(child_pid)], 2 if stop == "timeout" else 30))
    try:
        async with asyncio.timeout(5):
            while not written.exists() or written.stat().st_size == 0:
                await asyncio.sleep(.01)
        if stop == "cancel":
            task.cancel()
        with pytest.raises(asyncio.CancelledError if stop == "cancel" else TimeoutError):
            await task
        after_stop = written.stat().st_size
        await asyncio.sleep(.15)
        assert written.stat().st_size == after_stop, "A descendant is still writing after the command stopped"
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if child_pid.exists():
            try:
                os.kill(int(child_pid.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


@pytest.mark.asyncio
@pytest.mark.skipif(os.name != "posix", reason="Mac commands can start a persistent ADB daemon")
@pytest.mark.parametrize("runner", ["run", "run_file"])
async def test_successful_command_preserves_started_daemon(tmp_path, runner):
    written = tmp_path / "written"
    child_pid = tmp_path / "child.pid"
    child = "import sys,time\nf=open(sys.argv[1],'ab',buffering=0)\nwhile True:\n f.write(b'x')\n time.sleep(.01)\n"
    parent = "import pathlib,subprocess,sys,time\np=subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\npathlib.Path(sys.argv[3]).write_text(str(p.pid))\nwhile not pathlib.Path(sys.argv[2]).exists(): time.sleep(.01)\n"
    try:
        await getattr(mac, runner)([sys.executable, "-c", parent, child, str(written), str(child_pid)], 5)
        after_exit = written.stat().st_size
        async with asyncio.timeout(1):
            while written.stat().st_size == after_exit:
                await asyncio.sleep(.01)
        assert written.stat().st_size > after_exit
    finally:
        if child_pid.exists():
            try:
                os.kill(int(child_pid.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


@pytest.mark.asyncio
async def test_advanced_log_collection_checks_owned_running_container_before_logcat(tmp_path, monkeypatch):
    from autoflow.providers.android import management

    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path / "workspace")
    device = {"deviceId": "d1", "containerId": "owned-container"}
    verify = AsyncMock(return_value=([{"State": {"Running": True}}], [{}]))
    command = AsyncMock(return_value=b"prefix\nprivate-message")
    monkeypatch.setattr(management, "verify", verify)
    monkeypatch.setattr(mac, "docker", command)
    assert await runtime.collect_diagnostic_logs(device, window_seconds=300, max_bytes=15) == b"private-message"
    verify.assert_awaited_once_with(device, runtime.workspace_id)
    command.assert_awaited_once_with("exec", "owned-container", "logcat", "-d", "-v", "epoch", "-t", "200", timeout=10)
    verify.side_effect = AndroidError("ANDROID_OWNERSHIP", "foreign", 403)
    with pytest.raises(AndroidError, match="foreign"):
        await runtime.collect_diagnostic_logs(device, window_seconds=300, max_bytes=15)
    assert command.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(("volumes", "expected"), [([], "missing"), ([{"Labels": {}}], "retained")])
async def test_delete_verification_reads_owned_objects_even_when_snapshot_is_not_retained(tmp_path, monkeypatch, volumes, expected):
    from autoflow.providers.android import management

    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path / "workspace")
    device = {"deviceId": "d", "dataRetained": False, "containerId": "gone", "volumeId": "data"}
    verifier = AsyncMock(return_value=([], volumes))
    monkeypatch.setattr(management, "verify", verifier)
    assert (await runtime.verify_deleted(device))["androidStatus"] == expected
    verifier.assert_awaited_once_with(device, runtime.workspace_id)


@pytest.mark.asyncio
async def test_restarted_install_inventory_uses_verified_owned_container_without_adb(tmp_path, monkeypatch):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path / "workspace")
    runtime.device = {"deviceId": "d", "containerId": "owned"}
    runtime.inspect = AsyncMock(return_value={"androidStatus": "ready"})
    command = AsyncMock(return_value=b"package:com.example.test versionCode:7\n")
    monkeypatch.setattr(mac, "docker", command)
    assert (await runtime.app_info_for_verification())["applications"] == [{"packageName": "com.example.test", "versionCode": 7}]
    runtime.inspect.assert_awaited_once_with(runtime.device)
    command.assert_awaited_once_with("exec", "owned", "pm", "list", "packages", "--show-versioncode", timeout=15)


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
async def test_backup_volume_uses_guest_tar_with_metadata_without_starting_android_image(tmp_path, monkeypatch):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    calls = []

    async def fake_docker(*args, **kwargs):
        calls.append((args, kwargs))
        if args[:2] == ("volume", "inspect"):
            return json.dumps([{"Labels": {mac.LABEL: runtime.workspace_id, "io.autoflow.android.device": "device"}, "Mountpoint": "/var/lib/docker/volumes/volume/_data"}]).encode()
        return b""

    monkeypatch.setattr(mac, "docker", fake_docker)
    guest = AsyncMock(return_value=b"tar-bytes")
    monkeypatch.setattr(mac, "run", guest)
    result = await runtime.backup_volume({"volumeId": "volume", "imageId": "image", "deviceId": "device", "workspaceId": runtime.workspace_id})
    assert result == b"tar-bytes"
    assert [args for args, _ in calls] == [("volume", "inspect", "volume")]
    command = guest.await_args.args[0]
    assert {"--xattrs", "--xattrs-include=*", "--acls", "--selinux", "--numeric-owner"} <= set(command)
    assert "--transform=s@^_data@data@S" in command
    assert command[-3:] == ["-cf", "-", "_data"]
    stream = AsyncMock(side_effect=lambda _argv, _timeout, **kwargs: kwargs["output_path"].write_bytes(b"tar-bytes"))
    monkeypatch.setattr(mac, "run_file", stream)
    output = tmp_path / "backup.tar"
    await runtime.backup_volume_to_path({"volumeId": "volume", "imageId": "image", "deviceId": "device", "workspaceId": runtime.workspace_id}, output)
    assert output.read_bytes() == b"tar-bytes"
    assert stream.await_args.kwargs["output_path"] == output


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
async def test_restore_volume_extracts_guest_archive_with_xattrs_into_empty_target(tmp_path, monkeypatch):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    calls = []

    async def fake_docker(*args, **_kwargs):
        calls.append(args)
        if args[:2] == ("volume", "inspect"):
            return json.dumps([{"Labels": {mac.LABEL: runtime.workspace_id, "io.autoflow.android.device": "device"}, "Mountpoint": "/var/lib/docker/volumes/device-data/_data"}]).encode()
        if args[0] == "create":
            return b"restore-container\n"
        return b""

    guest = AsyncMock(side_effect=[b"empty\n", b""])
    monkeypatch.setattr(mac, "docker", fake_docker)
    monkeypatch.setattr(mac, "run", guest)
    await runtime.restore_volume({"deviceId": "device", "workspaceId": runtime.workspace_id, "volumeId": "device-data", "imageId": "image", "androidStatus": "stopped", "control": "idle"}, b"archive")

    assert calls == [("volume", "inspect", "device-data")]
    assert guest.await_count == 2
    extract = guest.await_args_list[1]
    assert {"--xattrs", "--xattrs-include=*", "--acls", "--selinux", "--transform=s@^data@_data@S"} <= set(extract.args[0])
    assert "--strip-components=1" not in extract.args[0]
    assert extract.args[2] == b"archive"


@pytest.mark.asyncio
async def test_restore_volume_streams_archive_file_into_empty_owned_target(tmp_path, monkeypatch):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    archive = tmp_path / "data.tar"
    archive.write_bytes(b"archive")
    monkeypatch.setattr(mac, "docker", AsyncMock(return_value=json.dumps([{"Labels": {mac.LABEL: runtime.workspace_id, "io.autoflow.android.device": "device"}, "Mountpoint": "/var/lib/docker/volumes/device-data/_data"}]).encode()))
    monkeypatch.setattr(mac, "run", AsyncMock(return_value=b"empty\n"))
    stream = AsyncMock()
    monkeypatch.setattr(mac, "run_file", stream)
    device = {"deviceId": "device", "workspaceId": runtime.workspace_id, "volumeId": "device-data", "imageId": "image", "androidStatus": "stopped", "control": "idle"}

    await runtime.restore_volume_from_path(device, archive)

    assert stream.await_args.kwargs["input_path"] == archive
    assert "--transform=s@^data@_data@S" in stream.await_args.args[0]


@pytest.mark.asyncio
async def test_restore_volume_refuses_nonempty_target_before_extraction(tmp_path, monkeypatch):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    docker = AsyncMock(return_value=json.dumps([{"Labels": {mac.LABEL: runtime.workspace_id, "io.autoflow.android.device": "device"}, "Mountpoint": "/var/lib/docker/volumes/device-data/_data"}]).encode())
    guest = AsyncMock(return_value=b"occupied\n")
    monkeypatch.setattr(mac, "docker", docker)
    monkeypatch.setattr(mac, "run", guest)

    with pytest.raises(AndroidError) as rejected:
        await runtime.restore_volume({"deviceId": "device", "workspaceId": runtime.workspace_id, "volumeId": "device-data", "imageId": "image", "androidStatus": "stopped", "control": "idle"}, b"archive")

    assert rejected.value.code == "ANDROID_RESTORE_TARGET_INVALID"
    guest.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["backup", "restore"])
async def test_guest_tar_failure_never_exposes_private_path(tmp_path, monkeypatch, action):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    volume = {"Labels": {mac.LABEL: runtime.workspace_id, "io.autoflow.android.device": "device"}, "Mountpoint": "/var/lib/docker/volumes/device-data/_data"}
    monkeypatch.setattr(mac, "docker", AsyncMock(return_value=json.dumps([volume]).encode()))
    failure = AndroidError("ANDROID_COMMAND_FAILED", "tar: data/private-account-name: read error", 502)
    guest = AsyncMock(side_effect=[b"empty\n", failure] if action == "restore" else failure)
    monkeypatch.setattr(mac, "run", guest)
    device = {"deviceId": "device", "workspaceId": runtime.workspace_id, "volumeId": "device-data", "imageId": "image", "androidStatus": "stopped", "control": "idle"}

    with pytest.raises((AndroidError, TimeoutError)) as rejected:
        if action == "restore":
            await runtime.restore_volume(device, b"archive")
        else:
            await runtime.backup_volume(device)

    assert "private-account-name" not in str(rejected.value)
    if action == "restore":
        assert isinstance(rejected.value, TimeoutError)
    else:
        assert isinstance(rejected.value, AndroidError)
        assert rejected.value.code == "ANDROID_BACKUP_UNAVAILABLE"


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
    docker = AsyncMock(side_effect=[b"v2:0\n", b""])
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


@pytest.mark.asyncio
async def test_legacy_zero_exit_marker_does_not_prove_app_success(tmp_path, monkeypatch):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    runtime.device = {"containerId": "container", "pendingCommand": "/data/local/tmp/autoflow-operation-" + "a" * 32}
    runtime.inspect = AsyncMock(return_value={"androidStatus": "ready"})
    monkeypatch.setattr(mac, "docker", AsyncMock(return_value=b"0\n"))
    with pytest.raises(AndroidError) as error:
        await runtime.verify_pending_command()
    assert error.value.code == "ANDROID_OPERATION_UNKNOWN"


@pytest.mark.asyncio
@pytest.mark.parametrize(("operation", "output", "exit_code", "successful"), [
    ("android_launch_app", "Error: Activity not started\n", 0, False),
    ("android_launch_app", "Status: timeout\n", 0, None),
    ("android_uninstall_app", "Failure [DELETE_FAILED_INTERNAL_ERROR]\n", 0, False),
    ("android_clear_app_data", "Failed\n", 0, False),
    ("android_stop_app", "Error: Permission Denial\n", 0, False),
    ("android_launch_app", "Status: ok\n", 1, False),
    ("android_launch_app", "Status: ok\n", 0, True),
    ("android_uninstall_app", "Success\n", 0, True),
    ("android_clear_app_data", "Success\n", 0, True),
    ("android_stop_app", "", 0, True),
    ("install", "Failure [INSTALL_FAILED_INVALID_APK]\n", 0, False),
    ("install", "Success\n", 0, True),
    ("android_launch_app", "Starting: Intent {}\n", 0, None),
    ("android_stop_app", "Unexpected response\n", 0, None),
    ("android_uninstall_app", "Unexpected response\n", 0, None),
    ("android_clear_app_data", "Unexpected response\n", 0, None),
    ("install", "Unexpected response\n", 0, None),
])
async def test_lost_app_response_marker_records_semantic_result(tmp_path, monkeypatch, operation, output, exit_code, successful):
    # Execute the production shell script, replacing only Android IO and its marker path.
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    runtime.device = {"containerId": "container"}
    runtime.inspect = AsyncMock(return_value={"androidStatus": "ready"})
    marker_file = tmp_path / "completion"

    async def adb(*args, **_kwargs):
        if args[0] == "push":
            return b""
        if args[:3] == ("shell", "cmd", "package"):
            return b"com.example.app/.MainActivity\n"
        if args[:4] == ("shell", "pm", "list", "packages"):
            return b"" if args[-1] == "-s" else b"package:com.example.app\n"
        assert args[:3] == ("shell", "sh", "-c")
        script = shlex.split(args[3])[0].replace(runtime.device["pendingCommand"], shlex.quote(str(marker_file)))
        stub = "() { printf '%s' " + shlex.quote(output) + "; return " + str(exit_code) + "; }; "
        try:
            await mac.run(["sh", "-c", "am" + stub + "pm" + stub + script])
        except AndroidError:
            pass  # The transport loses either success or failure, after execution.
        raise TimeoutError("response lost")

    runtime._adb = adb
    with pytest.raises(TimeoutError):
        if operation == "install":
            from tests.unit.test_android_apk import _apk, _manifest
            await runtime.install_apk(_apk(_manifest()))
        else:
            await runtime.command(operation, {"packageName": "com.example.app"}, 1)
    monkeypatch.setattr(mac, "docker", AsyncMock(return_value=marker_file.read_bytes()))
    if successful is None:
        with pytest.raises(AndroidError) as error:
            await runtime.verify_pending_command()
        assert error.value.code == "ANDROID_OPERATION_UNKNOWN"
    else:
        assert (await runtime.verify_pending_command() == 0) is successful
    assert "pendingCommand" in runtime.device


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["android_stop_app", "install"])
async def test_successful_app_response_keeps_marker_until_receipt_acknowledgement(tmp_path, operation):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    runtime.device = {"containerId": "container"}

    async def adb(*args, **_kwargs):
        if args[0] == "push":
            return b""
        return b"Success\n" if operation == "install" else b""

    runtime._adb = adb
    if operation == "install":
        from tests.unit.test_android_apk import _apk, _manifest
        await runtime.install_apk(_apk(_manifest()))
    else:
        await runtime.command(operation, {"packageName": "com.example.app"}, 1, retain_completion=True)
    assert runtime.device["pendingCommand"].startswith("/data/local/tmp/autoflow-operation-")


@pytest.mark.asyncio
async def test_interrupted_apk_push_records_guest_file_before_transport(tmp_path):
    from tests.unit.test_android_apk import _apk, _manifest

    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    runtime.device = {"containerId": "container"}
    saved = []
    runtime.save = lambda: saved.append(dict(runtime.device))

    async def lost_push(*args, **_kwargs):
        assert args[0] == "push"
        assert saved[-1]["pendingApk"] == args[2]
        raise TimeoutError("push result lost")

    runtime._adb = lost_push
    with pytest.raises(TimeoutError):
        await runtime.install_apk(_apk(_manifest()))
    assert runtime.device["pendingApk"].startswith("/data/local/tmp/autoflow-apk-")
    assert "pendingCommand" not in runtime.device


@pytest.mark.asyncio
async def test_recover_removes_interrupted_apk_push_only_from_owned_device(tmp_path, monkeypatch):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    remote = "/data/local/tmp/autoflow-apk-" + "a" * 32 + ".apk"
    device = {"containerId": "container", "pendingApk": remote}
    runtime.inspect = AsyncMock(return_value={"androidStatus": "ready"})
    command = AsyncMock(return_value=b"")
    monkeypatch.setattr(mac, "docker", command)
    await runtime.recover(device)
    assert "pendingApk" not in device
    command.assert_awaited_once_with("exec", "container", "rm", "-f", remote, timeout=5)

    device["pendingApk"] = "/data/local/tmp/other.apk"
    with pytest.raises(AndroidError) as error:
        await runtime.recover(device)
    assert error.value.code == "ANDROID_RECOVERY_REQUIRED"
    assert command.await_count == 1


@pytest.mark.asyncio
async def test_receipt_acknowledgement_removes_apk_before_command_evidence(tmp_path, monkeypatch):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    remote = "/data/local/tmp/autoflow-apk-" + "a" * 32 + ".apk"
    marker = "/data/local/tmp/autoflow-operation-" + "b" * 32
    runtime.device = {"containerId": "container", "pendingApk": remote, "pendingCommand": marker}
    runtime.inspect = AsyncMock(return_value={"androidStatus": "ready"})
    runtime.save = lambda: None
    command = AsyncMock(return_value=b"")
    monkeypatch.setattr(mac, "docker", command)
    await runtime.acknowledge_pending_command(marker)
    assert "pendingApk" not in runtime.device and "pendingCommand" not in runtime.device
    assert [call.args[4] for call in command.await_args_list] == [remote, marker]


@pytest.mark.asyncio
async def test_automatic_recovery_preserves_app_evidence_until_explicit_verification(tmp_path, monkeypatch):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    marker = "/data/local/tmp/autoflow-operation-" + "a" * 32
    device = {"containerId": "container", "pendingCommand": marker}
    runtime.inspect = AsyncMock(return_value={"androidStatus": "ready"})
    command = AsyncMock(return_value=b"v2:0\n")
    monkeypatch.setattr(mac, "docker", command)

    await runtime.recover(device, preserve_command=True)
    assert device["pendingCommand"] == marker
    command.assert_awaited_once_with("exec", "container", "cat", marker, timeout=5)

    await runtime.recover(device)
    assert "pendingCommand" not in device
    assert [call.args[2] for call in command.await_args_list] == ["cat", "cat", "rm"]
    assert command.await_args_list[-1].args[4] == marker


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [b"v2:124\n", b"0\n"])
async def test_explicit_recovery_refuses_indeterminate_app_marker(tmp_path, monkeypatch, result):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    marker = "/data/local/tmp/autoflow-operation-" + "a" * 32
    device = {"containerId": "container", "pendingCommand": marker}
    runtime.inspect = AsyncMock(return_value={"androidStatus": "ready"})
    command = AsyncMock(return_value=result)
    monkeypatch.setattr(mac, "docker", command)

    with pytest.raises(AndroidError) as error:
        await runtime.recover(device)
    assert error.value.code == "ANDROID_RECOVERY_REQUIRED"
    assert device["pendingCommand"] == marker
    command.assert_awaited_once_with("exec", "container", "cat", marker, timeout=5)


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [b"20480\n", b"", b"unknown\n", b"-1\n"])
async def test_backup_size_estimate_counts_guest_tar_with_same_metadata_options(tmp_path, monkeypatch, result):
    runtime = mac.MacAndroidRuntime(tmp_path, tmp_path)
    runtime._owned_volume_mount = AsyncMock(return_value="/var/lib/docker/volumes/owned/_data")
    guest = AsyncMock(return_value=result)
    monkeypatch.setattr(mac, "run", guest)
    monkeypatch.setattr(mac, "run_file", AsyncMock())
    if result == b"20480\n":
        assert await runtime.estimate_backup_bytes({"deviceId": "owned"}) == 20480
        command = guest.await_args.args[0]
        assert command[:6] == ["limactl", "shell", "--workdir=/tmp", mac.VM, "sudo", "python3"]
        assert command[8:] == runtime._backup_argv("/var/lib/docker/volumes/owned/_data")[5:]
    else:
        with pytest.raises(AndroidError) as error:
            await runtime.estimate_backup_bytes({"deviceId": "owned"})
        assert error.value.code == "ANDROID_DISK_ESTIMATE_UNKNOWN"
    mac.run_file.assert_not_awaited()
