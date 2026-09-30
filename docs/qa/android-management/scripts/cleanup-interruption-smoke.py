"""Opt-in real multi-object cleanup SIGKILL after the first durable deletion."""

import argparse
import asyncio
import json
import os
import runpy
import signal
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

from autoflow.adapters.http.android_management import android_management_router
from autoflow.adapters.http.errors import install_error_handlers
from autoflow.application.android.backups import AndroidBackupService
from autoflow.application.android.cleanup import CleanupService
from autoflow.application.android.diagnostics import EnvironmentCheckService
from autoflow.bootstrap.android import android_service
from autoflow.infrastructure.database.android_operations import (
    SqlAlchemyAndroidOperationRepository,
)
from autoflow.infrastructure.database.android_resources import AndroidResourceRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.filesystem.paths import AppPaths
from fastapi import FastAPI
from fastapi.testclient import TestClient

HELPERS = runpy.run_path(str(Path(__file__).with_name("restore-interruption-smoke.py")))
BASE = "/api/v1/android/management"


def crash_child(workspace):
    paths = AppPaths.from_data_dir(workspace)
    sessions = create_session_factory(paths.database)
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    devices = android_service(sessions, paths.workspace)
    devices.management.workspace_identity = str(paths.workspace.resolve())
    backups = AndroidBackupService(resources, paths.workspace, operations)
    cleanup = CleanupService(resources, devices=devices, backups=backups, operations=operations)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(devices.runtime), operations, devices=devices, backups=backups, cleanup=cleanup))
    raw_save = resources.save

    def save_then_crash(kind, record):
        raw_save(kind, record)
        if kind == "cleanup-operation" and len(record["items"]) == 1:
            assert len(record["candidates"]) == 2 and record["items"][0]["state"] == "succeeded"
            os.kill(os.getpid(), signal.SIGKILL)

    resources.save = save_then_crash
    payload = json.loads((workspace / "request.json").read_text())
    with TestClient(app) as client:
        response = client.post(BASE + "/cleanup", json=payload)
    raise AssertionError((response.status_code, response.text))


async def exercise():
    workspace = Path(tempfile.mkdtemp(prefix="autoflow-am4-cleanup-interrupt-"))
    paths = AppPaths.from_data_dir(workspace)
    paths.database.parent.mkdir(parents=True)
    migrate_database(paths.database)
    sessions = create_session_factory(paths.database)
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    backups = AndroidBackupService(resources, paths.workspace, operations)
    first = backups.storage.stage(str(uuid4()))
    second = backups.storage.stage(str(uuid4()))
    (first / "data.tar").write_bytes(b"first owned unpublished archive")
    (second / "data.tar").write_bytes(b"second owned unpublished archive")
    peer = workspace / "outside-backup-root-probe"
    peer.write_bytes(b"keep unselected external data")
    selected = ["staging:" + first.name, "staging:" + second.name]
    report = {"workspace": str(workspace), "status": "started", "resourceIds": selected}
    process = client = None
    expect = HELPERS["expect"]
    try:
        process, client = await HELPERS["start_server"](workspace)
        preview = expect(await client.post(BASE + "/cleanup/previews", json={"resourceIds": selected}), 200)
        assert {row["id"] for row in preview["items"]} == set(selected)
        payload = {"requestId": str(uuid4()), "previewId": preview["previewId"], "confirmationDigest": preview["confirmationDigest"]}
        (workspace / "request.json").write_text(json.dumps(payload))
        await HELPERS["stop_server"](process, client)
        process = client = None
        child = await asyncio.create_subprocess_exec(sys.executable, __file__, "--allow-device-mutation", "--crash-child", str(workspace), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, errors = await asyncio.wait_for(child.communicate(), 45)
        assert child.returncode == -signal.SIGKILL, errors.decode(errors="replace")
        record = next(item for item in resources.list("cleanup-operation") if item["requestId"] == payload["requestId"])
        assert len(record["items"]) == 1 and len(record["candidates"]) == 2
        deleted_id = record["items"][0]["id"]
        remaining_id = next(identifier for identifier in selected if identifier != deleted_id)
        deleted_path = backups.storage.staging / deleted_id.removeprefix("staging:")
        remaining_path = backups.storage.staging / remaining_id.removeprefix("staging:")
        assert not deleted_path.exists() and remaining_path.is_dir()
        remaining_bytes = (remaining_path / "data.tar").read_bytes()
        process, client = await HELPERS["start_server"](workspace)
        operation = expect(await client.get(BASE + f"/operations/by-request/{payload['requestId']}"), 200)
        assert operation["state"] == "needs_verification", operation
        replay = expect(await client.post(BASE + "/cleanup", json=payload), 200)
        assert replay["state"] != "succeeded", replay
        assert (remaining_path / "data.tar").read_bytes() == remaining_bytes
        verified = await client.post(BASE + f"/operations/{operation['operationId']}/verify", json={"requestId": payload["requestId"]})
        assert verified.status_code == 503 and "ANDROID_VERIFICATION_UNAVAILABLE" in verified.text, (verified.status_code, verified.text)
        assert (remaining_path / "data.tar").read_bytes() == remaining_bytes
        refreshed = expect(await client.post(BASE + "/cleanup/previews", json={"resourceIds": [remaining_id]}), 200)
        completed = expect(await client.post(BASE + "/cleanup", json={"requestId": str(uuid4()), "previewId": refreshed["previewId"], "confirmationDigest": refreshed["confirmationDigest"]}), 200)
        assert completed["state"] == "succeeded" and not remaining_path.exists()
        assert peer.read_bytes() == b"keep unselected external data"
        report.update(status="passed", requestId=payload["requestId"], processExit=child.returncode, deletedBeforeCrash=deleted_id, unexecutedAfterCrash=remaining_id, parentState=operation["state"], replayState=replay["state"], verificationHttpStatus=verified.status_code, noAutomaticReplay=True, explicitNewPreviewSucceeded=True, externalProbePreserved=True)
    finally:
        try:
            if process is not None:
                await HELPERS["stop_server"](process, client)
            for directory in (first, second):
                if directory.exists():
                    backups.storage.discard(directory.name)
            assert not list(backups.storage.staging.iterdir())
            report["ownedTemporaryFilesDeleted"] = True
        finally:
            sessions.dispose()
            (workspace / "result.json").write_text(json.dumps(report, indent=2))
            print(json.dumps(report), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-device-mutation", action="store_true")
    parser.add_argument("--crash-child", type=Path)
    args = parser.parse_args()
    if not args.allow_device_mutation:
        parser.error("--allow-device-mutation is required")
    if args.crash_child:
        crash_child(args.crash_child)
    else:
        asyncio.run(exercise())
