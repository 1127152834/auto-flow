"""Explicit preparation command; creates a new, owned integration device only."""
import argparse
import asyncio
import hashlib
import json
import shutil
import tarfile
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4

from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.filesystem.android_paths import android_runtime_root
from autoflow.infrastructure.filesystem.paths import AppPaths
from autoflow.providers.android.mac_runtime import (
    ARCHIVE_SHA,
    LABEL,
    VENDOR,
    VM,
    MacAndroidRuntime,
    docker,
)


def install_client(root: Path, archive: Path | None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    cached = root / (VENDOR + ".tar.gz")
    if archive:
        if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA:
            raise ValueError("scrcpy checksum mismatch")
        if archive.resolve() != cached.resolve():
            shutil.copyfile(archive, cached)
    if not cached.exists():
        with urlopen("https://github.com/Genymobile/scrcpy/releases/download/v3.3.4/" + VENDOR + ".tar.gz", timeout=120) as response:
            data = response.read(100 * 1024 * 1024)
        if hashlib.sha256(data).hexdigest() != ARCHIVE_SHA:
            raise ValueError("scrcpy checksum mismatch")
        cached.write_bytes(data)
    if hashlib.sha256(cached.read_bytes()).hexdigest() != ARCHIVE_SHA:
        raise ValueError("scrcpy checksum mismatch")
    with tarfile.open(cached) as source:
        # Fixed distribution contains ordinary files only; reject links/devices.
        for member in source.getmembers():
            target = root / member.name
            if not target.resolve().is_relative_to(root.resolve()) or not (member.isfile() or member.isdir()):
                raise ValueError("Unsafe client archive")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                stream = source.extractfile(member)
                assert stream is not None
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(stream.read())
                target.chmod(member.mode & 0o777)


async def prepare(data_dir: Path, archive: Path | None, recover: bool) -> dict:
    paths = AppPaths.from_data_dir(data_dir.resolve())
    paths.database.parent.mkdir(parents=True, exist_ok=True)
    migrate_database(paths.database)
    sessions = create_session_factory(paths.database)
    repo = SqlAlchemyDeviceRepository(sessions)
    root = android_runtime_root()
    runtime = MacAndroidRuntime(root, paths.data_dir)
    runtime.lock()
    try:
        if recover:
            for device in repo.list():
                await runtime.recover(device)
                device.update(ownerRunId=None, control="idle", lastError=None)
                repo.save(device)
            return {"recovered": True}
        install_client(root, archive)
        if repo.list():
            return repo.list()[0]
        image = "redroid/redroid:13.0.0_64only-latest"
        image_info = json.loads(await docker("image", "inspect", image))[0]
        if image_info["Os"] != "linux" or image_info["Architecture"] != "arm64":
            raise ValueError("Requires cached Linux arm64 image")
        device_id = str(uuid4())
        name = "autoflow-android-" + device_id
        volume = name + "-data"
        record = {"deviceId": device_id, "name": "安卓工作流测试", "runtimeId": VM,
                  "workspaceId": runtime.workspace_id, "volumeId": volume, "containerId": name,
                  "imageId": image_info["Id"], "imageDigests": image_info.get("RepoDigests", []),
                  "width": 720, "height": 1280, "androidStatus": "unknown", "ownerRunId": None,
                  "control": "recovery_required", "generation": 0, "lastError": "正在准备设备"}
        # Record intended names before provisioning so partial creation remains reviewable.
        paths.logs.mkdir(parents=True, exist_ok=True)
        journal = paths.logs / (name + ".json")
        journal.write_text(json.dumps(record, ensure_ascii=False, indent=2))
        await docker("volume", "create", "--label", LABEL + "=" + runtime.workspace_id, "--label", "io.autoflow.android.device=" + device_id, volume)
        container = await docker("create", "--name", name, "--privileged", "--cpus", "1", "--memory", "1536m", "--label", LABEL + "=" + runtime.workspace_id, "--label", "io.autoflow.android.device=" + device_id, "-v", volume + ":/data", "-p", "127.0.0.1::5555", image, "androidboot.redroid_gpu_mode=guest", "androidboot.redroid_width=720", "androidboot.redroid_height=1280", "androidboot.redroid_dpi=320")
        record["containerId"] = container.decode().strip()
        repo.save(record)
        await runtime.connect(record, lambda: repo.save(record))
        await runtime.disconnect()
        record.update(control="idle", lastError=None)
        repo.save(record)
        journal.write_text(json.dumps(record, ensure_ascii=False, indent=2))
        return record
    finally:
        await runtime.disconnect()
        runtime.unlock()
        sessions.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--scrcpy-archive", type=Path)
    parser.add_argument("--recover", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(prepare(args.data_dir, args.scrcpy_archive, args.recover)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
