"""Opt-in real batch container disappearance and post-stop process interruption."""

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

import httpx
from autoflow.adapters.http.android_management import android_management_router
from autoflow.adapters.http.errors import install_error_handlers
from autoflow.application.android.bulk import AndroidBulkService
from autoflow.application.android.diagnostics import EnvironmentCheckService
from autoflow.bootstrap.android import android_service
from autoflow.domain.android.management_models import public_device_revision
from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.database.android_operations import (
    SqlAlchemyAndroidOperationRepository,
)
from autoflow.infrastructure.database.android_resources import AndroidResourceRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.filesystem.paths import AppPaths
from autoflow.providers.android import management as runtime_management
from autoflow.providers.android.mac_runtime import docker
from fastapi import FastAPI

HELPERS = runpy.run_path(str(Path(__file__).with_name("restore-interruption-smoke.py")))
BASE = "/api/v1/android/management/bulk-operations"
expect = HELPERS["expect"]


async def wait_batch(client, identifier):
    for _ in range(240):
        batch = expect(await client.get(f"{BASE}/{identifier}"), 200)
        if batch["state"] in {"succeeded", "failed", "partially_failed", "needs_verification", "cancelled"}:
            return batch
        await asyncio.sleep(.5)
    raise TimeoutError("Batch did not settle")


async def child(workspace, mode):
    paths = AppPaths.from_data_dir(workspace)
    sessions = create_session_factory(paths.database)
    resources = AndroidResourceRepository(sessions)
    operations = SqlAlchemyAndroidOperationRepository(sessions)
    devices = android_service(sessions, paths.workspace)
    devices.management.workspace_identity = str(paths.workspace.resolve())
    devices.management.operations = operations
    bulk = AndroidBulkService(resources, devices)
    body = json.loads((workspace / "batch-request.json").read_text())
    target = body["items"][1]["deviceId"]
    raw_mutation = runtime_management.mutation
    raw_manage = devices.runtime.manage

    async def disappear(device, save, *args, **kwargs):
        if device["deviceId"] == target and args[0] == "stop":
            containers, volumes = await runtime_management.verify(device, devices.runtime.workspace_id)
            assert len(containers) == len(volumes) == 1
            await docker("rm", "-f", containers[0]["Id"])
            (workspace / "disappearance.json").write_text(json.dumps({"deviceId": target, "containerId": containers[0]["Id"], "volumePreserved": True}))
        return await raw_mutation(device, save, *args, **kwargs)

    async def stop_then_kill(device, request, stage, save):
        await raw_manage(device, request, stage, save)
        if device["deviceId"] == target and request["action"] == "stop":
            assert (await devices.runtime.inspect(device))["androidStatus"] == "stopped"
            (workspace / "hard-kill.json").write_text(json.dumps({"deviceId": target, "actualState": "stopped", "beforeReceipt": operations.get(device["operation"]["id"]).state}))
            os.kill(os.getpid(), signal.SIGKILL)

    if mode == "disappear":
        runtime_management.mutation = disappear
    else:
        devices.runtime.manage = stop_then_kill
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(devices.runtime), operations, devices=devices, bulk=bulk))
    await bulk.start()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://qa") as client:
            batch = expect(await client.post(BASE, json=body), 202)
            (workspace / f"{mode}-batch.json").write_text(json.dumps(batch))
            batch = await wait_batch(client, batch["id"])
            assert mode == "disappear" and [item["state"] for item in batch["items"]] == ["succeeded", "failed"], batch
            failed = operations.get(batch["items"][1]["operationId"])
            assert failed.result_code == "ANDROID_COMMAND_FAILED", failed.result_code
            (workspace / "failure-result.json").write_text(json.dumps({"batch": batch, "resultCode": failed.result_code}))
    finally:
        await bulk.shutdown()
        await devices.management.shutdown()
        runtime_management.mutation = raw_mutation
        sessions.dispose()


async def exercise():
    workspace = Path(tempfile.mkdtemp(prefix="autoflow-am3-runtime-fault-"))
    paths = AppPaths.from_data_dir(workspace)
    paths.database.parent.mkdir(parents=True)
    migrate_database(paths.database)
    sessions = create_session_factory(paths.database)
    repository = SqlAlchemyDeviceRepository(sessions)
    devices = android_service(sessions, paths.workspace)
    ids = [str(uuid4()), str(uuid4())]
    report = {"workspace": str(workspace), "deviceIds": ids, "status": "started"}
    process = client = fault = None
    operate = HELPERS["operate"]
    probe = "/data/local/tmp/autoflow-bulk-fault-probe"
    hashes = {}
    try:
        process, client = await HELPERS["start_server"](workspace)
        image = json.loads(await docker("image", "inspect", "redroid/redroid:13.0.0_64only-latest"))[0]["Id"]
        report["imageId"] = image
        expect(await client.post("/api/v1/android/management/images", json={"id": image, "name": "Bulk QA base", "reference": "redroid/redroid:13.0.0_64only-latest"}), 201)
        for identifier in ids:
            result = expect(await client.post("/api/v1/android/devices", json={"deviceId": identifier, "name": "Bulk runtime QA " + identifier[:8], "imageId": image, "width": 720, "height": 1280, "dpi": 320, "cpu": 1, "memoryMb": 1536, "start": True}), 202)
            row = await HELPERS["wait_device"](repository, identifier, result["operation"]["id"])
            await docker("exec", row["containerId"], "sh", "-c", f"printf %s {identifier} > {probe}")
            hashes[identifier] = (await docker("exec", row["containerId"], "sha256sum", probe)).decode().split()[0]
        for mode in ("disappear", "kill"):
            body = {"requestId": str(uuid4()), "action": "stop", "items": [{"deviceId": identifier, "expectedRevision": public_device_revision(repository.get(identifier)["generation"])} for identifier in ids]}
            (workspace / "batch-request.json").write_text(json.dumps(body))
            await HELPERS["stop_server"](process, client)
            process = client = None
            with (workspace / "fault-child.log").open("ab") as log:
                fault = await asyncio.create_subprocess_exec(sys.executable, __file__, "--allow-device-mutation", "--child", mode, "--workspace", str(workspace), stdout=log, stderr=log, start_new_session=True)
            assert await asyncio.wait_for(fault.wait(), 150) == (0 if mode == "disappear" else -signal.SIGKILL), (workspace / "fault-child.log").read_text()[-3000:]
            identifier = json.loads((workspace / f"{mode}-batch.json").read_text())["id"]
            process, client = await HELPERS["start_server"](workspace)
            batch = await wait_batch(client, identifier)
            failed_id = batch["items"][1]["operationId"]
            expected = "failed" if mode == "disappear" else "needs_verification"
            assert [item["state"] for item in batch["items"]] == ["succeeded", expected], batch
            before = repository.get(ids[1])["generation"]
            replay = expect(await client.post(BASE, json=body), 202)
            assert replay["id"] == identifier
            blocked_retry = expect(await client.post(f"{BASE}/{identifier}/actions", json={"requestId": str(uuid4()), "action": "retryFailed"}), 200)
            assert blocked_retry["items"][1]["operationId"] == failed_id
            assert repository.get(ids[1])["generation"] == before
            if mode == "disappear":
                failure = json.loads((workspace / "failure-result.json").read_text())
                assert failure["resultCode"] == "ANDROID_COMMAND_FAILED"
                recovered = await operate(client, repository, ids[1], "recover")
                assert recovered["dataRetained"]
                await operate(client, repository, ids[1], "restore")
                expect(await client.post(f"{BASE}/{identifier}/actions", json={"requestId": str(uuid4()), "action": "retryFailed"}), 200)
                done = await wait_batch(client, identifier)
                assert done["state"] == "succeeded" and done["items"][1]["retryOf"] == failed_id, done
                report["runtimeFailure"] = {"batchId": identifier, "statesBefore": ["succeeded", "failed"], "resultCode": failure["resultCode"], "retryBlockedUntilRecovery": True, "retryOf": failed_id, "finalState": done["state"]}
            else:
                marker = json.loads((workspace / "hard-kill.json").read_text())
                assert marker["beforeReceipt"] == "running"
                done = expect(await client.post(f"{BASE}/{identifier}/actions", json={"requestId": str(uuid4()), "action": "verify"}), 200)
                assert done["state"] == "succeeded" and repository.get(ids[1])["generation"] == before, done
                report["hardKill"] = {"batchId": identifier, "exitCode": fault.returncode, "statesBefore": ["succeeded", "needs_verification"], "retryDidNotReplay": True, "verificationState": done["state"], "verificationDidNotAdvanceGeneration": True, **marker}
            for device_id in ids:
                row = await operate(client, repository, device_id, "start")
                assert (await docker("exec", row["containerId"], "sha256sum", probe)).decode().split()[0] == hashes[device_id]
        report["bothDataProbesPreserved"] = True
    finally:
        try:
            if fault is not None and fault.returncode is None:
                await HELPERS["kill_owned_tree"](fault)
            if process is None:
                process, client = await HELPERS["start_server"](workspace)
            for row in repository.list():
                if row.get("deleted"):
                    continue
                assert row["workspaceId"] == devices.runtime.workspace_id
                if row["control"] == "recovery_required":
                    await operate(client, repository, row["deviceId"], "recover")
                deleted = await operate(client, repository, row["deviceId"], "delete")
                assert (await devices.runtime.verify_deleted(deleted))["androidStatus"] == "missing"
            report["ownedResourcesDeleted"] = True
            if report.get("bothDataProbesPreserved"):
                report["status"] = "passed"
        finally:
            if process is not None:
                await HELPERS["stop_server"](process, client)
            sessions.dispose()
            (workspace / "result.json").write_text(json.dumps(report, indent=2))
            print(json.dumps(report), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-device-mutation", action="store_true")
    parser.add_argument("--child", choices=("disappear", "kill"))
    parser.add_argument("--workspace", type=Path)
    args = parser.parse_args()
    if not args.allow_device_mutation:
        parser.error("--allow-device-mutation is required")
    if args.child:
        if args.workspace is None:
            parser.error("--workspace is required for --child")
        asyncio.run(child(args.workspace, args.child))
    else:
        asyncio.run(exercise())
