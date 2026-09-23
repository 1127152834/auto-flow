"""Opt-in real custom ReDroid image, immutable template and backup lifecycle."""

import argparse
import asyncio
import io
import json
import runpy
import tarfile
import tempfile
from pathlib import Path
from uuid import uuid4

from autoflow.application.android.backups import AndroidBackupService
from autoflow.bootstrap.android import android_service
from autoflow.domain.android.management_models import public_device_revision
from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.database.android_resources import AndroidResourceRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.filesystem.paths import AppPaths
from autoflow.providers.android.mac_runtime import docker

HELPERS = runpy.run_path(str(Path(__file__).with_name("restore-interruption-smoke.py")))
BASE = "/api/v1/android/management"
expect = HELPERS["expect"]
LABEL = "io.autoflow.qa.workspace"


async def build(base, tag, owner, version):
    context = io.BytesIO()
    with tarfile.open(fileobj=context, mode="w") as archive:
        for name, data in {"Dockerfile": f"FROM {base}\nLABEL {LABEL}={owner}\nCOPY marker /autoflow-qa-marker\n".encode(), "marker": version.encode()}.items():
            member = tarfile.TarInfo(name)
            member.size, member.mode = len(data), 0o644
            archive.addfile(member, io.BytesIO(data))
    await docker("build", "--network=none", "-t", tag, "-", input_data=context.getvalue(), timeout=120)
    result = json.loads(await docker("image", "inspect", tag))[0]
    assert result["Config"]["Labels"][LABEL] == owner and result["Id"] != base
    return result["Id"]


async def exercise():
    workspace = Path(tempfile.mkdtemp(prefix="autoflow-am2-custom-image-"))
    paths = AppPaths.from_data_dir(workspace)
    paths.database.parent.mkdir(parents=True)
    migrate_database(paths.database)
    sessions = create_session_factory(paths.database)
    repository = SqlAlchemyDeviceRepository(sessions)
    resources = AndroidResourceRepository(sessions)
    service = android_service(sessions, paths.workspace)
    owner = service.runtime.workspace_id
    prefix = "autoflow-qa-" + uuid4().hex
    tags = [prefix + ":candidate", prefix + ":next"]
    report = {"workspace": str(workspace), "status": "started", "tags": tags}
    process = client = None
    created_images = []
    operate = HELPERS["operate"]
    try:
        base = json.loads(await docker("image", "inspect", "redroid/redroid:13.0.0_64only-latest"))[0]["Id"]
        image_a = await build(base, tags[0], owner, "candidate-v1")
        created_images.append(image_a)
        image_b = await build(base, tags[1], owner, "candidate-v2")
        created_images.append(image_b)
        assert image_a != image_b
        report.update(baseImage=base, candidateImage=image_a, nextImage=image_b)
        process, client = await HELPERS["start_server"](workspace)
        for image_id, reference in [(base, "redroid/redroid:13.0.0_64only-latest"), (image_a, tags[0]), (image_b, tags[1])]:
            registered = expect(await client.post(BASE + "/images", json={"id": image_id, "name": reference, "reference": reference}), 201)
            assert registered["validation"] == "not_tested"
            if image_id == image_a:
                record_a = registered
        profile_id = str(uuid4())
        profile = expect(await client.put(f"/api/v1/android/profiles/{profile_id}", json={"id": profile_id, "revision": 0, "name": "Real custom Android", "imageId": image_a, "cpu": 1, "memoryMb": 1536}), 200)

        async def blocked_delete(reference_kind):
            response = await client.request("DELETE", BASE + "/images/" + record_a["id"], json={"requestId": str(uuid4()), "expectedRevision": record_a["revision"], "deleteContent": True})
            assert response.status_code == 409 and "ANDROID_IMAGE_REFERENCED" in response.text, response.text
            assert json.loads(await docker("image", "inspect", image_a))[0]["Id"] == image_a
            report.setdefault("deleteBlockedBy", []).append(reference_kind)

        await blocked_delete("template")
        batch = expect(await client.post("/api/v1/android/batches", json={"batchId": str(uuid4()), "name": "Real custom candidate", "profileId": profile_id, "profileRevision": profile["revision"], "quantity": 1, "start": True}), 202)
        candidate_id = batch["items"][0]["deviceId"]
        for _ in range(480):
            batches = expect(await client.get("/api/v1/android/batches"), 200)
            current = next(item for item in batches if item["id"] == batch["id"])
            if current["state"] == "succeeded":
                break
            assert current["state"] not in {"failed", "cancelled"}, current
            await asyncio.sleep(.5)
        else:
            raise TimeoutError("Template creation batch")
        candidate = repository.get(candidate_id)
        assert candidate["androidStatus"] == "ready" and candidate["imageId"] == image_a, candidate
        assert (await docker("exec", candidate["containerId"], "cat", "/autoflow-qa-marker")).decode() == "candidate-v1"
        base_id = str(uuid4())
        created = expect(await client.post("/api/v1/android/devices", json={"deviceId": base_id, "name": "Unmodified base peer", "imageId": base, "width": 720, "height": 1280, "dpi": 320, "cpu": 1, "memoryMb": 1536, "start": True}), 202)
        peer = await HELPERS["wait_device"](repository, base_id, created["operation"]["id"])
        assert peer["androidStatus"] == "ready"
        await docker("exec", peer["containerId"], "test", "!", "-e", "/autoflow-qa-marker")
        report.update(candidateDeviceId=candidate_id, baseDeviceId=base_id, candidateAndBaseReady=True)
        await docker("tag", image_b, tags[0])
        edited = expect(await client.put(f"/api/v1/android/profiles/{profile_id}", json={**profile, "imageId": image_b}), 200)
        conflict = await client.put(f"/api/v1/android/profiles/{profile_id}", json=profile)
        assert conflict.status_code == 409
        candidate = await operate(client, repository, candidate_id, "restart")
        assert candidate["imageId"] == candidate["creationConfig"]["imageId"] == image_a
        assert json.loads(await docker("inspect", candidate["containerId"]))[0]["Image"] == image_a
        assert (await docker("exec", candidate["containerId"], "cat", "/autoflow-qa-marker")).decode() == "candidate-v1"
        assert json.loads(await docker("image", "inspect", tags[0]))[0]["Id"] == image_b
        await blocked_delete("device")
        await docker("exec", candidate["containerId"], "sh", "-c", "printf custom-data > /data/local/tmp/autoflow-custom-probe")
        candidate = await operate(client, repository, candidate_id, "stop")
        backup = expect(await client.post(BASE + "/backups", json={"requestId": str(uuid4()), "deviceId": candidate_id, "expectedRevision": public_device_revision(candidate["generation"])}), 201)
        restored = expect(await client.post(BASE + f"/backups/{backup['id']}/restore", json={"requestId": str(uuid4()), "newName": "Custom image restored"}), 202)
        restored_row = await operate(client, repository, restored["deviceId"], "start")
        assert (await docker("exec", restored_row["containerId"], "cat", "/autoflow-qa-marker")).decode() == "candidate-v1"
        assert (await docker("exec", restored_row["containerId"], "cat", "/data/local/tmp/autoflow-custom-probe")).decode() == "custom-data"
        await operate(client, repository, restored["deviceId"], "delete")
        await operate(client, repository, candidate_id, "delete")
        await blocked_delete("backup")
        preview = expect(await client.post(BASE + "/cleanup/previews", json={"resourceIds": [backup["id"]]}), 200)
        assert [item["id"] for item in preview["items"]] == [backup["id"]], preview
        cleaned = expect(await client.post(BASE + "/cleanup", json={"requestId": str(uuid4()), "previewId": preview["previewId"], "confirmationDigest": preview["confirmationDigest"]}), 200)
        assert cleaned["state"] == "succeeded", cleaned
        assert not resources.list("backup")
        deleted = expect(await client.request("DELETE", BASE + "/images/" + record_a["id"], json={"requestId": str(uuid4()), "expectedRevision": record_a["revision"], "deleteContent": True}), 200)
        assert deleted["state"] == "deleted"
        assert image_a not in (await docker("image", "ls", "-a", "--no-trunc", "-q")).decode().split()
        archived = expect(await client.post(BASE + f"/profiles/{profile_id}/archive", json={"requestId": str(uuid4()), "expectedRevision": edited["revision"]}), 200)
        assert archived["archived"]
        assert (await service.runtime.inspect(repository.get(base_id)))["androidStatus"] == "ready"
        assert json.loads(await docker("image", "inspect", "redroid/redroid:13.0.0_64only-latest"))[0]["Id"] == base
        report.update(tagDriftPreservesFrozenImage=True, profileRevisionConflict=True, customBackupRestored=True, backupId=backup["id"], restoredDeviceId=restored["deviceId"], candidateContentDeleted=True, baseUnchanged=True, googleValidation="not_tested")
    finally:
        try:
            if process is None and repository.list():
                process, client = await HELPERS["start_server"](workspace)
            for row in repository.list():
                if row.get("deleted"):
                    continue
                assert row["workspaceId"] == owner
                if row["control"] == "recovery_required":
                    await operate(client, repository, row["deviceId"], "recover")
                await operate(client, repository, row["deviceId"], "delete")
            for row in repository.list():
                assert (await service.runtime.verify_deleted(row))["androidStatus"] == "missing"
            backups = AndroidBackupService(resources, paths.workspace)
            for backup in resources.list("backup"):
                assert backup["workspaceId"] == str(paths.workspace.resolve())
                backups.delete(backup["id"])
            available = set((await docker("image", "ls", "-a", "--no-trunc", "-q")).decode().split())
            for image_id in created_images:
                if image_id not in available:
                    continue
                obj = json.loads(await docker("image", "inspect", image_id))[0]
                assert obj["Config"]["Labels"][LABEL] == owner and image_id != report["baseImage"]
                owned_tags = obj.get("RepoTags") or []
                assert set(owned_tags) <= set(tags)
                await docker("image", "rm", "--no-prune", *(owned_tags or [image_id]))
            remaining = set((await docker("image", "ls", "-a", "--no-trunc", "-q")).decode().split())
            assert not remaining.intersection(created_images)
            report["ownedDevicesBackupsImagesDeleted"] = True
            if report.get("baseUnchanged"):
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
    args = parser.parse_args()
    if not args.allow_device_mutation:
        parser.error("--allow-device-mutation is required")
    asyncio.run(exercise())
