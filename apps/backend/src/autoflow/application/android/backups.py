import hashlib
import json
import os
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from autoflow.domain.android.ports import AndroidError


class AndroidBackupService:
    def __init__(self, resources: Any, workspace: Path) -> None:
        self.resources, self.root = resources, workspace / "android-backups"

    def create(self, device: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
        if observed.get("androidStatus") not in {"stopped", "retained"} or device.get("control") != "idle" or device.get("ownerRunId"):
            raise AndroidError("ANDROID_BACKUP_REQUIRES_STOPPED", "备份前必须停止实例并释放控制会话", 409)
        backup_id = str(uuid4())
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self.root / f"{backup_id}.tar"
        payload = json.dumps({"formatVersion": 1, "deviceId": device["deviceId"], "imageId": device["imageId"], "config": device.get("creationConfig", {})}, ensure_ascii=False).encode()
        with tarfile.open(path, "w") as archive:
            info = tarfile.TarInfo("manifest.json")
            info.size = len(payload)
            archive.addfile(info, __import__("io").BytesIO(payload))
        os.chmod(path, 0o600)
        record = {"id": backup_id, "deviceId": device["deviceId"], "imageId": device["imageId"], "formatVersion": 1, "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size, "createdAt": datetime.now(UTC).isoformat(), "state": "available"}
        self.resources.save("backup", record)
        return record

    def restore(self, backup_id: str, image_id: str, new_device_id: str) -> dict[str, Any]:
        backup = next((item for item in self.resources.list("backup") if item["id"] == backup_id), None)
        if backup is None or backup.get("state") != "available":
            raise AndroidError("ANDROID_BACKUP_NOT_FOUND", "备份不存在或不可恢复", 404)
        if backup["imageId"] != image_id:
            raise AndroidError("ANDROID_BACKUP_IMAGE_MISMATCH", "备份必须使用完全相同的镜像摘要", 409)
        return {"deviceId": new_device_id, "backupId": backup_id, "state": "queued"}
