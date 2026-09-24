"""Opt-in real restore ENOSPC and request-task cancellation on owned Mac resources."""

import argparse
import asyncio
import hashlib
import json
import runpy
import shutil
import tempfile
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

import httpx
from autoflow.adapters.http.android_management import android_management_router
from autoflow.adapters.http.errors import install_error_handlers
from autoflow.application.android.backups import AndroidBackupService
from autoflow.application.android.diagnostics import EnvironmentCheckService
from autoflow.application.android.images import AndroidImageService
from autoflow.bootstrap.android import android_service
from autoflow.domain.android.management_models import public_device_revision
from autoflow.infrastructure.database.android_operations import (
    SqlAlchemyAndroidOperationRepository,
)
from autoflow.infrastructure.database.android_resources import AndroidResourceRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.filesystem.paths import AppPaths
from autoflow.providers.android.image_catalog import ImageCatalog
from autoflow.providers.android.mac_runtime import VM, docker, run
from fastapi import FastAPI

HELPERS = runpy.run_path(str(Path(__file__).with_name("restore-interruption-smoke.py")))


async def guest(*args, timeout=45):
    return await run(["limactl", "shell", "--workdir=/tmp", VM, "sudo", *args], timeout)


async def exercise():
    workspace = Path(tempfile.mkdtemp(prefix="autoflow-am4-restore-faults-"))
    paths = AppPaths.from_data_dir(workspace)
    paths.database.parent.mkdir(parents=True)
    migrate_database(paths.database)
    sessions = create_session_factory(paths.database)
    devices = android_service(sessions, paths.workspace)
    repository, runtime = devices.repository, devices.runtime
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    devices.management.operations = operations
    devices.management.workspace_identity = str(paths.workspace.resolve())
    runtime.image_catalog = AndroidImageService(resources, devices, ImageCatalog(runtime))
    backups = AndroidBackupService(resources, paths.workspace, operations)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(runtime), operations, backups=backups, devices=devices))
    report = {"workspace": str(workspace), "status": "started", "scenarios": []}
    process = client = transfer = None
    mounted = []
    original_restore = runtime.restore_volume_from_path
    expect, operate = HELPERS["expect"], HELPERS["operate"]
    try:
        assert shutil.disk_usage(workspace).free > 2 * 1024**3
        root = (await docker("info", "--format", "{{.DockerRootDir}}")).decode().strip()
        assert int(await guest("python3", "-c", "import shutil,sys;print(shutil.disk_usage(sys.argv[1]).free)", root)) > 2 * 1024**3
        image = json.loads(await docker("image", "inspect", "redroid/redroid:13.0.0_64only-latest"))[0]["Id"]
        process, client = await HELPERS["start_server"](workspace)
        expect(await client.post("/api/v1/android/management/images", json={"id": image, "name": "AM4 fault base", "reference": "redroid/redroid:13.0.0_64only-latest"}), 201)
        source_id = str(uuid4())
        created = expect(await client.post("/api/v1/android/devices", json={"deviceId": source_id, "name": "AM4 disk and cancel source", "imageId": image, "width": 720, "height": 1280, "dpi": 320, "cpu": 1, "memoryMb": 1536, "allowUnknownDiskEstimate": True, "start": True}), 202)
        source = await HELPERS["wait_device"](repository, source_id, created["operation"]["id"])
        probe = "/data/local/tmp/autoflow-restore-fault-probe"
        await docker("exec", source["containerId"], "dd", "if=/dev/urandom", f"of={probe}", "bs=1048576", "count=256", timeout=90)
        source_hash = (await docker("exec", source["containerId"], "sha256sum", probe)).decode().split()[0]
        source = await operate(client, repository, source_id, "stop")
        backup = expect(await client.post("/api/v1/android/management/backups", json={"requestId": str(uuid4()), "deviceId": source_id, "expectedRevision": public_device_revision(source["generation"])}), 201)
        damaged = expect(await client.post("/api/v1/android/management/backups", json={"requestId": str(uuid4()), "deviceId": source_id, "expectedRevision": public_device_revision(source["generation"])}), 201)
        damaged_path = Path(next(row for row in resources.list("backup") if row["id"] == damaged["id"])["path"]) / "data.tar"
        # Deliberately corrupt a second self-owned fixture; the valid backup stays unchanged.
        with damaged_path.open("ab") as stream:
            stream.write(b"intentional QA corruption")
        await HELPERS["stop_server"](process, client)
        process = client = None
        backup_path = Path(next(row for row in resources.list("backup") if row["id"] == backup["id"])["path"])

        def hashes():
            result = {}
            for path in backup_path.iterdir():
                with path.open("rb") as stream:
                    result[path.name] = hashlib.file_digest(stream, "sha256").hexdigest()
            return result

        before = hashes()
        report.update(sourceId=source_id, backupId=backup["id"], backupBytes=backup["bytes"], imageId=image, probeSha256=source_hash)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://qa-local") as local:
            corrupt_request = str(uuid4())
            corrupt_target = str(uuid5(NAMESPACE_URL, f"{paths.workspace.resolve()}/android-restore/{corrupt_request}"))
            corrupt_body = {"requestId": corrupt_request, "allowUnknownDiskEstimate": True, "newName": "AM4 deliberately corrupt fixture"}
            corrupt = await local.post(f"/api/v1/android/management/backups/{damaged['id']}/restore", json=corrupt_body)
            assert corrupt.status_code == 409 and "ANDROID_BACKUP_CORRUPT" in corrupt.text, (corrupt.status_code, corrupt.text)
            rejected = repository.get(corrupt_target)
            mount = await runtime._owned_volume_mount(rejected)
            assert json.loads(await guest("python3", "-c", "import json,os,sys;print(json.dumps(os.listdir(sys.argv[1])))", mount)) == []
            assert operations.by_request(str(paths.workspace.resolve()), corrupt_request).state == "failed"
            corrupt_replay = await local.post(f"/api/v1/android/management/backups/{damaged['id']}/restore", json=corrupt_body)
            assert corrupt_replay.status_code == 409 and "ANDROID_RESTORE_REQUEST_REPLAYED" in corrupt_replay.text
            report["scenarios"].append({"mode": "corrupt_backup", "requestId": corrupt_request, "targetId": corrupt_target, "backupId": damaged["id"], "httpStatus": corrupt.status_code, "operationState": "failed", "emptyTargetVolume": True, "replayProtected": True})
            for mode in ("disk_full", "cancel"):
                request_id = str(uuid4())
                target_id = str(uuid5(NAMESPACE_URL, f"{paths.workspace.resolve()}/android-restore/{request_id}"))
                entered = asyncio.Event()
                details = {"mode": mode, "requestId": request_id, "targetId": target_id}

                async def restore_with_real_fault(device, data_path, *, target_id=target_id, details=details, mode=mode, entered=entered):
                    assert device["deviceId"] == target_id and device["restoreState"] == "pending"
                    mount = await runtime._owned_volume_mount(device)
                    details["mount"] = mount
                    if mode == "disk_full":
                        source_name = "autoflow-qa-" + target_id
                        await guest("mount", "-t", "tmpfs", "-o", "size=16m,mode=0700", source_name, mount)
                        mounted.append((mount, source_name))
                        check = """import errno,json,os,sys
p=sys.argv[1]
assert os.stat(p).st_dev!=os.stat(os.path.dirname(p)).st_dev
f=os.path.join(p,'qa-enospc-probe')
try:
 with open(f,'wb') as out:
  for _ in range(32):out.write(bytes(1048576))
except OSError as e:
 assert e.errno==errno.ENOSPC,e
 print(json.dumps({'errno':e.errno,'limitBytes':os.statvfs(p).f_blocks*os.statvfs(p).f_frsize}))
else:raise AssertionError('No real ENOSPC')
finally:os.unlink(f)
"""
                        details.update(json.loads(await guest("python3", "-c", check, mount)))
                    entered.set()
                    await original_restore(device, data_path)

                runtime.restore_volume_from_path = restore_with_real_fault
                body = {"requestId": request_id, "allowUnknownDiskEstimate": True, "newName": f"AM4 real {mode}"}
                transfer = asyncio.create_task(local.post(f"/api/v1/android/management/backups/{backup['id']}/restore", json=body))
                await asyncio.wait_for(entered.wait(), 60)
                if mode == "cancel":
                    watch = """import os,sys,time
end=time.monotonic()+45
while time.monotonic()<end:
 try:n=os.stat(sys.argv[1]).st_size
 except FileNotFoundError:n=0
 if n>=1048576:
  print(n,flush=True)
  break
 time.sleep(.001)
else:raise TimeoutError('No in-flight write')
"""
                    target_probe = details["mount"] + "/local/tmp/autoflow-restore-fault-probe"
                    written = int(await guest("python3", "-c", watch, target_probe, timeout=50))
                    assert 0 < written < 256 * 1024**2 and not transfer.done()
                    details["bytesAtCancel"] = written
                    transfer.cancel()
                    try:
                        await transfer
                    except asyncio.CancelledError:
                        details["requestTaskCancelled"] = True
                    else:
                        raise AssertionError("Restore did not cancel")
                    await asyncio.sleep(1)
                    partial = int(await guest("stat", "--format=%s", target_probe))
                    await asyncio.sleep(1)
                    assert int(await guest("stat", "--format=%s", target_probe)) == partial
                    assert 0 < partial < 256 * 1024**2
                    details["stablePartialBytes"] = partial
                else:
                    response = await transfer
                    assert response.status_code == 503 and "ANDROID_BACKUP_RESTORE_RESULT_UNKNOWN" in response.text, (response.status_code, response.text)
                    stats = json.loads(await guest("python3", "-c", "import json,os,sys;v=os.statvfs(sys.argv[1]);print(json.dumps({'freeBytes':v.f_bavail*v.f_frsize,'usedBytes':(v.f_blocks-v.f_bfree)*v.f_frsize}))", details["mount"]))
                    assert stats["freeBytes"] == 0 and stats["usedBytes"] > 0, stats
                    details.update(httpStatus=response.status_code, **stats)
                runtime.restore_volume_from_path = original_restore
                target = repository.get(target_id)
                operation = operations.by_request(str(paths.workspace.resolve()), request_id)
                assert operation.state == "needs_verification" and target["restoreState"] == "pending"
                assert target["control"] == "recovery_required"
                assert not runtime._locked
                replay = await local.post(f"/api/v1/android/management/backups/{backup['id']}/restore", json=body)
                assert replay.status_code == 409 and "ANDROID_RESTORE_REQUEST_REPLAYED" in replay.text
                details.update(operationState=operation.state, restorePending=True, controlIsolated=True, runtimeLockReleased=True, replayProtected=True)
                report["scenarios"].append(details)
                if mounted:
                    mount, source_name = mounted[-1]
                    assert (await guest("findmnt", "-n", "-o", "SOURCE", "--target", mount)).decode().strip() == source_name
                    await guest("umount", mount)
                    mounted.pop()

        process, client = await HELPERS["start_server"](workspace)
        for scenario in report["scenarios"]:
            target_id = scenario["targetId"]
            record = expect(await client.get(f"/api/v1/android/management/operations/by-request/{scenario['requestId']}"), 200)
            assert record["state"] == scenario["operationState"]
            await operate(client, repository, target_id, "recover")
            denied = await client.post(f"/api/v1/android/devices/{target_id}/operations", json={"requestId": str(uuid4()), "action": "start"})
            assert denied.status_code == 409 and "ANDROID_RESTORE_INCOMPLETE" in denied.text
            target = await operate(client, repository, target_id, "delete")
            assert (await runtime.verify_deleted(target))["androidStatus"] == "missing"
            scenario.update(preservedAfterRestart=True, recoverCannotReleaseIncompleteRestore=True, targetDeleted=True)
        restored = expect(await client.post(f"/api/v1/android/management/backups/{backup['id']}/restore", json={"requestId": str(uuid4()), "allowUnknownDiskEstimate": True, "newName": "AM4 after disk and cancel"}), 202)
        target = await operate(client, repository, restored["deviceId"], "start")
        assert (await docker("exec", target["containerId"], "sha256sum", probe)).decode().split()[0] == source_hash
        await operate(client, repository, restored["deviceId"], "delete")
        source = await operate(client, repository, source_id, "start")
        assert (await docker("exec", source["containerId"], "sha256sum", probe)).decode().split()[0] == source_hash
        assert hashes() == before
        report.update(newRequestRestored=True, sourceAndTargetHashesMatch=True, sourceBackupUnchanged=True)
    finally:
        try:
            if transfer is not None and not transfer.done():
                transfer.cancel()
                await asyncio.gather(transfer, return_exceptions=True)
            runtime.restore_volume_from_path = original_restore
            for mount, source_name in reversed(mounted):
                assert (await guest("findmnt", "-n", "-o", "SOURCE", "--target", mount)).decode().strip() == source_name
                await guest("umount", mount)
            mounted.clear()
            if process is not None:
                await HELPERS["stop_server"](process, client)
            for device in repository.list():
                if device.get("deleted"):
                    continue
                assert device["workspaceId"] == runtime.workspace_id
                if device.get("control") == "recovery_required":
                    devices.operate(device["deviceId"], {"requestId": str(uuid4()), "action": "recover", "deleteData": False})
                    await devices.management.task
                    assert repository.get(device["deviceId"])["operation"]["state"] == "succeeded"
                devices.operate(device["deviceId"], {"requestId": str(uuid4()), "action": "delete", "deleteData": True})
                await devices.management.task
                deleted = repository.get(device["deviceId"])
                assert deleted.get("deleted") and (await runtime.verify_deleted(deleted))["androidStatus"] == "missing"
            for backup in resources.list("backup"):
                assert backup["workspaceId"] == str(paths.workspace.resolve())
                backups.delete(backup["id"])
            assert not resources.list("backup") and not list(backups.storage.final.glob("*"))
            report.update(ownedResourcesDeleted=True, ownedBackupsDeleted=True, privateMountsRemoved=True)
            if report.get("sourceAndTargetHashesMatch"):
                report["status"] = "passed"
        finally:
            sessions.dispose()
            (workspace / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-device-mutation", action="store_true")
    args = parser.parse_args()
    if not args.allow_device_mutation:
        parser.error("--allow-device-mutation is required")
    asyncio.run(exercise())
