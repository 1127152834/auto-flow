"""Opt-in real HTTP restore interruption while an owned volume is being written."""

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import shutil
import signal
import sys
import tempfile
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

import httpx
from autoflow.application.android.backups import AndroidBackupService
from autoflow.application.android.management import AndroidManagement
from autoflow.domain.android.management_models import public_device_revision
from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.database.android_resources import AndroidResourceRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.filesystem.android_paths import android_runtime_root
from autoflow.infrastructure.filesystem.paths import AppPaths
from autoflow.providers.android.mac_runtime import VM, MacAndroidRuntime, docker, run


async def start_server(workspace):
    token = secrets.token_hex(32)
    env = {**os.environ, "AUTOFLOW_INSTANCE_TOKEN": token, "AUTOFLOW_HOST_TOKEN": secrets.token_hex(32)}
    with (workspace / "sidecar.log").open("ab") as log:
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "autoflow", "--instance-id", str(uuid4()),
            "--data-dir", str(workspace), "--port", "0", start_new_session=True,
            env=env, stdout=asyncio.subprocess.PIPE, stderr=log,
        )
    try:
        line = await asyncio.wait_for(process.stdout.readline(), 45)
        assert line.startswith(b"AUTOFLOW_READY "), line
        port = json.loads(line.removeprefix(b"AUTOFLOW_READY "))["port"]
        client = httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", headers={"x-autoflow-token": token}, timeout=180, trust_env=False)
        for _ in range(100):
            try:
                if (await client.get("/api/v1/android/management/environment")).status_code == 200:
                    return process, client
            except httpx.ConnectError:
                pass
            await asyncio.sleep(.1)
        await client.aclose()
        raise TimeoutError("Sidecar HTTP readiness")
    except BaseException:
        os.killpg(process.pid, signal.SIGKILL)
        await process.wait()
        raise


async def stop_server(process, client):
    await client.aclose()
    if process.returncode is None:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), 20)
        except TimeoutError:
            os.killpg(process.pid, signal.SIGKILL)
            await process.wait()
            raise


async def kill_owned_tree(process):
    assert os.getpgid(process.pid) == process.pid
    rows = [tuple(map(int, line.split())) for line in (await run(["ps", "-axo", "pid=,ppid=,pgid="], 5)).decode().splitlines()]
    owned = {process.pid}
    while descendants := {pid for pid, parent, _ in rows if parent in owned} - owned:
        owned.update(descendants)
    groups = {group for pid, _, group in rows if pid in owned}
    assert groups <= owned and os.getpgrp() not in groups
    for group in sorted(groups - {process.pid}) + [process.pid]:
        try:
            os.killpg(group, signal.SIGKILL)
        except ProcessLookupError:
            pass
    assert await process.wait() == -signal.SIGKILL
    return len(groups)


async def wait_device(repository, device_id, operation_id):
    for _ in range(180):
        row = repository.get(device_id)
        operation = row.get("operation") or {}
        if operation.get("id") == operation_id:
            state = operation.get("state")
            if state in {"failed", "needs_verification", "interrupted"}:
                raise AssertionError((state, row.get("lastError")))
            if state == "succeeded":
                return row
        await asyncio.sleep(.5)
    raise TimeoutError("Device operation")


def expect(response, status):
    assert response.status_code == status, (response.status_code, response.text[:400])
    return response.json()


async def operate(client, repository, device_id, action):
    result = expect(await client.post(f"/api/v1/android/devices/{device_id}/operations", json={
        "requestId": str(uuid4()), "action": action, "deleteData": action == "delete",
    }), 202)
    return await wait_device(repository, device_id, result["operation"]["id"])


async def exercise(interrupt_backup_first=False):
    workspace = Path(tempfile.mkdtemp(prefix="autoflow-am4-unpack-interrupt-"))
    paths = AppPaths.from_data_dir(workspace)
    paths.database.parent.mkdir(parents=True)
    migrate_database(paths.database)
    sessions = create_session_factory(paths.database)
    repository = SqlAlchemyDeviceRepository(sessions)
    runtime = MacAndroidRuntime(android_runtime_root(), paths.workspace)
    report = {"workspace": str(workspace), "status": "started"}
    process = client = monitor = transfer = None
    try:
        assert shutil.disk_usage(workspace).free > 2 * 1024**3
        root = (await docker("info", "--format", "{{.DockerRootDir}}")).decode().strip()
        guest_free = int(await run(["limactl", "shell", "--workdir=/tmp", VM, "python3", "-c", "import shutil,sys;print(shutil.disk_usage(sys.argv[1]).free)", root], 30))
        assert guest_free > 2 * 1024**3
        report["guestFreeBytesBefore"] = guest_free
        image = json.loads(await docker("image", "inspect", "redroid/redroid:13.0.0_64only-latest"))[0]["Id"]
        process, client = await start_server(workspace)
        expect(await client.post("/api/v1/android/management/images", json={
            "id": image, "name": "AM4 cached base", "reference": "redroid/redroid:13.0.0_64only-latest",
        }), 201)
        source_id = str(uuid4())
        created = expect(await client.post("/api/v1/android/devices", json={
            "deviceId": source_id, "name": "AM4 real unpack source", "imageId": image,
            "width": 720, "height": 1280, "dpi": 320, "cpu": 1, "memoryMb": 1536, "allowUnknownDiskEstimate": True, "start": True,
        }), 202)
        source = await wait_device(repository, source_id, created["operation"]["id"])
        assert source["androidStatus"] == "ready"
        probe = "/data/local/tmp/autoflow-unpack-probe"
        await docker("exec", source["containerId"], "dd", "if=/dev/urandom", f"of={probe}", "bs=1048576", "count=256", timeout=90)
        source_hash = (await docker("exec", source["containerId"], "sha256sum", probe)).decode().split()[0]
        source = await operate(client, repository, source_id, "stop")
        if interrupt_backup_first:
            backup_request = str(uuid4())
            body = {"requestId": backup_request, "deviceId": source_id, "expectedRevision": public_device_revision(source["generation"])}
            transfer = asyncio.create_task(client.post("/api/v1/android/management/backups", json=body))
            async with asyncio.timeout(90):
                while True:
                    assert not transfer.done(), "Backup completed before interruption"
                    partials = list((paths.workspace / "android-backups" / "staging").glob("*/data.tar"))
                    partial = partials[0].stat().st_size if partials else 0
                    if 1048576 <= partial < 256 * 1024**2:
                        break
                    await asyncio.sleep(.001)
            groups = await kill_owned_tree(process)
            await asyncio.gather(transfer, return_exceptions=True)
            await client.aclose()
            process = client = None
            resources = AndroidResourceRepository(sessions)
            assert not resources.list("backup")
            process, client = await start_server(workspace)
            unknown = expect(await client.get(f"/api/v1/android/management/operations/by-request/{backup_request}"), 200)
            assert unknown["state"] == "needs_verification"
            replay = await client.post("/api/v1/android/management/backups", json=body)
            assert replay.status_code == 409 and "ANDROID_BACKUP_REQUEST_REPLAYED" in replay.text
            inventory = expect(await client.get("/api/v1/android/management/cleanup/resources"), 200)
            staged_ids = [item["id"] for item in inventory["items"] if item["kind"] == "backup-staging"]
            if staged_ids:
                preview = expect(await client.post("/api/v1/android/management/cleanup/previews", json={"resourceIds": staged_ids}), 200)
                cleaned = expect(await client.post("/api/v1/android/management/cleanup", json={"requestId": str(uuid4()), "previewId": preview["previewId"], "confirmationDigest": preview["confirmationDigest"]}), 200)
                assert cleaned["state"] == "succeeded"
            assert not list((paths.workspace / "android-backups" / "staging").iterdir())
            report["interruptedBackup"] = {"requestId": backup_request, "bytesAtKill": partial, "terminatedOwnedProcessGroups": groups, "state": unknown["state"], "noPublishedBackup": True, "replayProtected": True, "stagingCleaned": True}
        backup = expect(await client.post("/api/v1/android/management/backups", json={
            "requestId": str(uuid4()), "deviceId": source_id, "expectedRevision": public_device_revision(source["generation"]),
        }), 201)
        backup_path = Path(next(row for row in AndroidResourceRepository(sessions).list("backup") if row["id"] == backup["id"])["path"])
        def backup_hashes():
            hashes = {}
            for path in backup_path.iterdir():
                with path.open("rb") as stream:
                    hashes[path.name] = hashlib.file_digest(stream, "sha256").hexdigest()
            return hashes
        source_backup_hashes = backup_hashes()
        report.update(sourceId=source_id, imageId=image, backupId=backup["id"], backupBytes=backup["bytes"], probeSha256=source_hash)
        request_id = str(uuid4())
        target_id = str(uuid5(NAMESPACE_URL, f"{paths.workspace.resolve()}/android-restore/{request_id}"))
        target_probe = f"{root}/volumes/autoflow-android-{target_id}-data/_data/local/tmp/autoflow-unpack-probe"
        watcher = """import os,sys,time
end=time.monotonic()+120
while time.monotonic()<end:
 try: size=os.stat(sys.argv[1]).st_size
 except FileNotFoundError: size=0
 if size>=1048576:
  print(size,flush=True)
  break
 time.sleep(.001)
else: raise TimeoutError('No real target write observed')
"""
        monitor = await asyncio.create_subprocess_exec(
            "limactl", "shell", "--workdir=/tmp", VM, "sudo", "python3", "-c", watcher, target_probe,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        body = {"requestId": request_id, "allowUnknownDiskEstimate": True, "newName": "AM4 interrupted unpack"}
        transfer = asyncio.create_task(client.post(f"/api/v1/android/management/backups/{backup['id']}/restore", json=body))
        observed = int(await asyncio.wait_for(monitor.stdout.readline(), 130))
        assert 0 < observed < 256 * 1024**2, observed
        assert not transfer.done(), "HTTP restore already completed before interruption"
        # Commands have their own groups so cancellation can reap SSH descendants.
        # This fault kills the complete self-owned sidecar tree, including those groups.
        report["terminatedOwnedProcessGroups"] = await kill_owned_tree(process)
        await asyncio.gather(transfer, return_exceptions=True)
        await monitor.wait()
        await client.aclose()
        process = client = None
        target = repository.get(target_id)
        target_mount = await runtime._owned_volume_mount(target)
        assert target_probe.startswith(target_mount + "/")
        await asyncio.sleep(1)
        size_argv = ["limactl", "shell", "--workdir=/tmp", VM, "sudo", "stat", "--format=%s", target_probe]
        partial = int(await run(size_argv, 30))
        await asyncio.sleep(1)
        assert int(await run(size_argv, 30)) == partial
        assert 0 < partial < 256 * 1024**2, partial
        assert target["restoreState"] == "pending"
        report.update(targetId=target_id, requestId=request_id, observedBytesBeforeKill=observed, stablePartialBytesAfterKill=partial, processExit=-signal.SIGKILL)
        process, client = await start_server(workspace)
        operation = expect(await client.get(f"/api/v1/android/management/operations/by-request/{request_id}"), 200)
        assert operation["state"] == "needs_verification", operation
        replay = await client.post(f"/api/v1/android/management/backups/{backup['id']}/restore", json=body)
        assert replay.status_code == 409 and "ANDROID_RESTORE_REQUEST_REPLAYED" in replay.text
        denied = [
            await client.post(f"/api/v1/android/devices/{target_id}/operations", json={"requestId": str(uuid4()), "action": "start"}),
            await client.post("/api/v1/android/management/backups", json={"requestId": str(uuid4()), "deviceId": target_id, "expectedRevision": public_device_revision(repository.get(target_id)["generation"])}),
            await client.post("/api/v1/android/sessions", json={"requestId": str(uuid4()), "deviceId": target_id, "access": "manual", "clientSessionId": str(uuid4())}),
        ]
        assert all(item.status_code == 409 and "ANDROID_RESTORE_INCOMPLETE" in item.text for item in denied), [(item.status_code, item.text[:200]) for item in denied]
        deleted = await operate(client, repository, target_id, "delete")
        assert (await runtime.verify_deleted(deleted))["androidStatus"] == "missing"
        report.update(recoveredOperationState=operation["state"], replayProtected=True, startBackupControlBlocked=True, interruptedTargetDeleted=True)
        restored = expect(await client.post(f"/api/v1/android/management/backups/{backup['id']}/restore", json={"requestId": str(uuid4()), "allowUnknownDiskEstimate": True, "newName": "AM4 new request after interruption"}), 202)
        assert restored["state"] == "restored"
        target = await operate(client, repository, restored["deviceId"], "start")
        restored_hash = (await docker("exec", target["containerId"], "sha256sum", probe)).decode().split()[0]
        assert restored_hash == source_hash
        await operate(client, repository, restored["deviceId"], "delete")
        source = await operate(client, repository, source_id, "start")
        assert (await docker("exec", source["containerId"], "sha256sum", probe)).decode().split()[0] == source_hash
        assert backup_hashes() == source_backup_hashes
        report.update(newRequestRestored=True, restoredProbeMatches=True, sourceProbePreserved=True, sourceBackupUnchanged=True)
    finally:
        try:
            if transfer is not None and not transfer.done():
                transfer.cancel()
                await asyncio.gather(transfer, return_exceptions=True)
            if monitor is not None and monitor.returncode is None:
                monitor.kill()
                await monitor.wait()
            if process is not None:
                await stop_server(process, client)
            for device in repository.list():
                if device.get("deleted"):
                    continue
                assert device["workspaceId"] == runtime.workspace_id
                manager = AndroidManagement(repository, runtime)
                if device.get("control") == "recovery_required":
                    manager.operate(device["deviceId"], {"requestId": str(uuid4()), "action": "recover", "deleteData": False})
                    await manager.task
                    assert repository.get(device["deviceId"])["operation"]["state"] == "succeeded"
                manager.operate(device["deviceId"], {"requestId": str(uuid4()), "action": "delete", "deleteData": True})
                await manager.task
                deleted = repository.get(device["deviceId"])
                assert deleted.get("deleted") and (await runtime.verify_deleted(deleted))["androidStatus"] == "missing"
            report["ownedResourcesDeleted"] = True
            resources = AndroidResourceRepository(sessions)
            backups = AndroidBackupService(resources, paths.workspace)
            for backup in resources.list("backup"):
                assert backup["workspaceId"] == str(paths.workspace.resolve())
                backups.delete(backup["id"])
            assert not resources.list("backup") and not list(backups.storage.final.glob("*"))
            report["ownedBackupsDeleted"] = True
            if report.get("sourceProbePreserved"):
                report["status"] = "passed"
        finally:
            sessions.dispose()
            (workspace / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-device-mutation", action="store_true")
    parser.add_argument("--interrupt-backup-first", action="store_true")
    args = parser.parse_args()
    if not args.allow_device_mutation:
        parser.error("--allow-device-mutation is required")
    asyncio.run(exercise(args.interrupt_backup_first))
