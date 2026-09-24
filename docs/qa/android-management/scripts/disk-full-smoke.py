"""Opt-in real Mac backup disk admission and cancellation on a private 64 MiB disk."""

import argparse
import asyncio
import errno
import json
import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from autoflow.application.android.backups import AndroidBackupService
from autoflow.application.android.management import AndroidManagement
from autoflow.bootstrap.android_prepare import prepare
from autoflow.domain.android.management_models import public_device_revision
from autoflow.domain.android.ports import AndroidError
from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.database.android_operations import (
    SqlAlchemyAndroidOperationRepository,
)
from autoflow.infrastructure.database.android_resources import AndroidResourceRepository
from autoflow.infrastructure.database.session import create_session_factory
from autoflow.infrastructure.filesystem.android_paths import android_runtime_root
from autoflow.infrastructure.filesystem.paths import AppPaths
from autoflow.providers.android.mac_runtime import MacAndroidRuntime, docker, run
from autoflow.providers.android.management import verify


async def operate(repository, runtime, device_id, action):
    manager = AndroidManagement(repository, runtime)
    manager.operate(device_id, {"requestId": str(uuid4()), "action": action, "deleteData": action == "delete"})
    await manager.task
    device = repository.get(device_id)
    assert device["operation"]["state"] == "succeeded", device["operation"]
    return device


async def exercise(archive: Path):
    workspace = Path(tempfile.mkdtemp(prefix="autoflow-am4-disk-full-"))
    paths = AppPaths.from_data_dir(workspace)
    report = {"workspace": str(workspace), "status": "started"}
    image = workspace / "backup-capacity.dmg"
    mount = paths.workspace / "android-backups"
    mounted = False
    sessions = None
    device = None
    try:
        device = await prepare(workspace, archive, False)
        sessions = create_session_factory(paths.database)
        repository = SqlAlchemyDeviceRepository(sessions)
        resources = AndroidResourceRepository(sessions)
        operations = SqlAlchemyAndroidOperationRepository(sessions)
        runtime = MacAndroidRuntime(android_runtime_root(), paths.workspace)
        service = AndroidBackupService(resources, paths.workspace, operations)
        estimates = []
        archive_calls = 0
        original_estimate = runtime.estimate_backup_bytes
        original_archive = runtime.backup_volume_to_path

        async def counted_estimate(device):
            size = await original_estimate(device)
            estimates.append(size)
            return size

        async def counted_archive(device, path):
            nonlocal archive_calls
            archive_calls += 1
            await original_archive(device, path)

        runtime.estimate_backup_bytes = counted_estimate
        runtime.backup_volume_to_path = counted_archive
        report.update(deviceId=device["deviceId"], imageId=device["imageId"])
        containers, volumes = await verify(device, runtime.workspace_id)
        assert len(containers) == len(volumes) == 1
        probe = b"autoflow-private-disk-full-probe"
        await docker("exec", device["containerId"], "sh", "-c", "printf %s autoflow-private-disk-full-probe > /data/local/tmp/autoflow-disk-full-probe")
        device = await operate(repository, runtime, device["deviceId"], "stop")

        mount.mkdir(parents=True)
        await run(["hdiutil", "create", "-size", "64m", "-fs", "HFS+", "-volname", "AutoFlowPrivateBackupQA", "-type", "UDIF", str(image)], 60)
        await run(["hdiutil", "attach", "-nobrowse", "-mountpoint", str(mount), str(image)], 60)
        mounted = True
        assert os.stat(mount).st_dev != os.stat(mount.parent).st_dev
        filler = mount / "qa-capacity-reservation"
        free = shutil.disk_usage(mount).free
        with filler.open("wb") as stream:
            remaining = free - 2 * 1024 * 1024
            while remaining > 0:
                written = stream.write(bytes(min(remaining, 1024 * 1024)))
                remaining -= written
            stream.flush()
            os.fsync(stream.fileno())
        # Prove real filesystem ENOSPC, then restore the small transfer budget.
        overflow = mount / "qa-enospc-probe"
        try:
            with overflow.open("wb") as stream:
                for _ in range(8):
                    stream.write(bytes(1024 * 1024))
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as error:
            assert error.errno == errno.ENOSPC, error
            report["filesystemErrno"] = error.errno
        else:
            raise AssertionError("Private disk did not reach ENOSPC")
        finally:
            overflow.unlink(missing_ok=True)
        report["freeBytesBeforeBackup"] = shutil.disk_usage(mount).free
        request_id = str(uuid4())
        revision = public_device_revision(device["generation"])
        try:
            await service.create_with_runtime(device, None, runtime, request_id, revision)
        except AndroidError as error:
            report["backupFailureCode"] = error.code
            assert error.code == "ANDROID_DISK_SPACE_INSUFFICIENT", error.code
        else:
            raise AssertionError("Backup unexpectedly succeeded on the full private disk")
        operation = operations.by_request(service.workspace_identity, request_id)
        assert operation.state == "failed", operation.state
        assert archive_calls == 0 and len(estimates) == 1
        report.update(archiveCallsBeforeAdmission=archive_calls, requiredArchiveBytes=estimates[0])
        assert resources.list("backup") == []
        assert not list(service.storage.final.glob("*"))
        assert not list(service.storage.staging.glob("*"))
        report.update(failedOperationState=operation.state, noPublishedBackup=True, noStaging=True)
        filler.unlink()
        try:
            await service.create_with_runtime(device, None, runtime, request_id, revision)
        except AndroidError as error:
            assert error.code == "ANDROID_BACKUP_REQUEST_REPLAYED", error.code
        else:
            raise AssertionError("Failed request replay was not protected")
        assert len(estimates) == 1 and archive_calls == 0
        backup = await service.create_with_runtime(device, None, runtime, str(uuid4()), revision)
        actual = (Path(backup["path"]) / "data.tar").stat().st_size
        assert actual == estimates[-1] and archive_calls == 1
        report.update(estimatedArchiveBytes=estimates[-1], actualArchiveBytes=actual, admissionThenArchiveCalls=archive_calls)
        assert backup["state"] == "available" and backup["bytes"] > report["freeBytesBeforeBackup"]
        report.update(replayProtected=True, newRequestBackupBytes=backup["bytes"], backupId=backup["id"])
        service.delete(backup["id"])
        cancel_request = str(uuid4())
        transfer = asyncio.create_task(service.create_with_runtime(device, None, runtime, cancel_request, revision))
        try:
            for _ in range(30000):
                if transfer.done():
                    raise AssertionError("Transfer finished before cancellation; cancellation is not verified")
                partials = list(service.storage.staging.glob("*/data.tar"))
                transferred = partials[0].stat().st_size if partials else 0
                if 0 < transferred < backup["bytes"] - 10240:
                    report["bytesAtTransferCancel"] = transferred
                    transfer.cancel()
                    break
                await asyncio.sleep(.001)
            else:
                raise TimeoutError("No archive transfer observed")
            try:
                await transfer
            except asyncio.CancelledError:
                pass
            else:
                raise AssertionError("In-flight transfer did not report cancellation")
        finally:
            if not transfer.done():
                transfer.cancel()
                await asyncio.gather(transfer, return_exceptions=True)
        cancelled = operations.by_request(service.workspace_identity, cancel_request)
        assert cancelled.state == "needs_verification", cancelled.state
        assert not resources.list("backup") and not list(service.storage.staging.glob("*"))
        assert not list(service.storage.final.glob("*"))
        report.update(cancelledOperationState=cancelled.state, cancelNoPublishedBackup=True, cancelNoStaging=True)
        try:
            await service.create_with_runtime(device, None, runtime, cancel_request, revision)
        except AndroidError as error:
            assert error.code == "ANDROID_BACKUP_REQUEST_REPLAYED", error.code
        else:
            raise AssertionError("Cancelled request replay was not protected")
        device = await operate(repository, runtime, device["deviceId"], "start")
        containers, _ = await verify(device, runtime.workspace_id)
        assert len(containers) == 1
        assert await docker("exec", device["containerId"], "cat", "/data/local/tmp/autoflow-disk-full-probe") == probe
        report["sourceProbePreserved"] = True
    finally:
        try:
            if device is not None and sessions is not None:
                device = await operate(repository, runtime, device["deviceId"], "delete")
                assert (await runtime.verify_deleted(device))["androidStatus"] == "missing"
                report["ownedResourcesDeleted"] = True
        finally:
            if sessions is not None:
                sessions.dispose()
            if mounted:
                await run(["hdiutil", "detach", str(mount)], 30)
                report["privateDiskDetached"] = True
                image.unlink()
            if report.get("sourceProbePreserved") and report.get("ownedResourcesDeleted") and report.get("privateDiskDetached"):
                report["status"] = "passed"
            (workspace / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-device-mutation", action="store_true")
    parser.add_argument("--scrcpy-archive", type=Path, required=True)
    args = parser.parse_args()
    if not args.allow_device_mutation:
        parser.error("--allow-device-mutation is required")
    asyncio.run(exercise(args.scrcpy_archive))
