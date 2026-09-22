import hashlib
import io
import json
import os
import tarfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from autoflow.domain.android.ports import AndroidError
from autoflow.providers.android.backup_storage import (
    BackupStorage,
    validate_archive_path,
)


class AndroidBackupService:
    def __init__(self, resources: Any, workspace: Path, operations: Any | None = None) -> None:
        self.resources, self.root = resources, workspace / "android-backups"
        self.storage = BackupStorage(self.root)
        self.operations = operations
        self.workspace_identity = str(workspace.resolve())

    @staticmethod
    def _digest(action: str, payload: dict[str, Any]) -> str:
        encoded = json.dumps({"action": action, **payload}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        return hashlib.sha256(encoded).hexdigest()

    def _accept(self, request_id: str | None, target_id: str, action: str, payload: dict[str, Any]) -> Any | None:
        if request_id is None or self.operations is None:
            return None
        return self.operations.accept(self.workspace_identity, request_id, target_id, action, self._digest(action, payload), payload)

    def _existing_request(self, request_id: str | None) -> dict[str, Any] | None:
        if request_id is None:
            return None
        return next((item for item in self.resources.list("backup") if item.get("workspaceId") == self.workspace_identity and item.get("requestId") == request_id), None)

    def _complete(self, record: Any | None, state: str, *, code: str | None = None, message: str | None = None) -> None:
        if record is None or self.operations is None or record.state != "running":
            return
        changes: dict[str, Any] = {"stage_code": state}
        if code is not None:
            changes["result_code"] = code
        if message is not None:
            changes["message"] = message[:480]
        self.operations.transition(record.operation_id, "running", state, changes)

    @contextmanager
    def _runtime_lock(self, runtime: Any):
        lock = getattr(runtime, "lock", None)
        unlock = getattr(runtime, "unlock", None)
        locked = False
        if callable(lock):
            lock()
            locked = True
        try:
            yield
        finally:
            if locked and callable(unlock):
                unlock()

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
        record = {"id": backup_id, "deviceId": device["deviceId"], "imageId": device["imageId"], "workspaceId": str(self.root.parent.resolve()), "formatVersion": 1, "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size, "createdAt": datetime.now(UTC).isoformat(), "state": "available"}
        self.resources.save("backup", record)
        return record

    async def create_with_runtime(self, device: dict[str, Any], observed: dict[str, Any] | None, runtime: Any, request_id: str | None = None, expected_revision: int | None = None) -> dict[str, Any]:
        payload = {"deviceId": device["deviceId"], "expectedRevision": expected_revision}
        existing = self._existing_request(request_id)
        if existing is not None:
            if existing.get("deviceId") != device["deviceId"] or existing.get("requestDigest") != self._digest("backup", payload):
                raise AndroidError("ANDROID_REQUEST_CONFLICT", "请求编号已用于不同备份", 409)
            return existing
        operation = self._accept(request_id, device["deviceId"], "backup", payload)
        if operation is not None:
            if operation.state == "succeeded":
                raise AndroidError("ANDROID_BACKUP_RESULT_UNKNOWN", "备份结果已记录但文件不可见，请核实后再操作", 503)
            if operation.state in {"running", "needs_verification", "failed", "cancelled"}:
                raise AndroidError("ANDROID_BACKUP_REQUEST_REPLAYED", "备份请求已处理，请先核实操作结果", 409)
            operation = self.operations.transition(operation.operation_id, "queued", "running", {"stage_code": "checking"})
        try:
            with self._runtime_lock(runtime):
                if observed is None and hasattr(runtime, "inspect"):
                    observed = await runtime.inspect(device)
                if (observed or {}).get("androidStatus") not in {"stopped", "retained"} or device.get("control") != "idle" or device.get("ownerRunId"):
                    raise AndroidError("ANDROID_BACKUP_REQUIRES_STOPPED", "备份前必须停止实例并释放控制会话", 409)
                if not hasattr(runtime, "backup_volume"):
                    raise AndroidError("ANDROID_BACKUP_UNAVAILABLE", "运行时尚未提供数据卷归档适配器", 503)
                data = await runtime.backup_volume(device)
                backup_id = str(uuid4())
                staged = self.storage.stage(backup_id)
                try:
                    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
                        for member in archive.getmembers():
                            kind = "link" if member.issym() or member.islnk() else "device" if member.isdev() or member.isfifo() else "file"
                            validate_archive_path(PurePosixPath(member.name), kind)
                    data_path = staged / "data.tar"
                    data_path.write_bytes(data)
                    os.chmod(data_path, 0o600)
                    manifest = {"formatVersion": 1, "deviceId": device["deviceId"], "imageId": device["imageId"], "config": device.get("creationConfig", {})}
                    manifest_path = staged / "manifest.json"
                    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
                    os.chmod(manifest_path, 0o600)
                    published = self.storage.finalize(backup_id)
                except BaseException:
                    self.storage.discard(backup_id)
                    raise
            digest = hashlib.sha256()
            size = 0
            for path in sorted(published.iterdir()):
                chunk = path.read_bytes()
                digest.update(chunk)
                size += len(chunk)
            record = {"id": backup_id, "deviceId": device["deviceId"], "imageId": device["imageId"], "workspaceId": str(self.root.parent.resolve()), "formatVersion": 1, "path": str(published), "sha256": digest.hexdigest(), "bytes": size, "createdAt": datetime.now(UTC).isoformat(), "state": "available", "config": device.get("creationConfig", {}), "requestId": request_id, "requestDigest": self._digest("backup", payload)}
            try:
                self.resources.save("backup", record)
            except BaseException as error:
                try:
                    self.storage.discard_final(backup_id)
                except (OSError, ValueError) as cleanup_error:
                    self._complete(operation, "needs_verification", code="BACKUP_RESULT_UNKNOWN", message=str(cleanup_error))
                    raise AndroidError("ANDROID_BACKUP_RESULT_UNKNOWN", "备份结果未知，请先核实后重试", 503) from cleanup_error
                self._complete(operation, "failed", code="BACKUP_RECORD_FAILED", message=str(error))
                raise
            self._complete(operation, "succeeded", code="BACKUP_CREATED")
            return record
        except (TimeoutError, OSError) as error:
            self._complete(operation, "needs_verification", code="BACKUP_RESULT_UNKNOWN", message=str(error))
            raise AndroidError("ANDROID_BACKUP_RESULT_UNKNOWN", "备份结果未知，请先核实后重试", 503) from error
        except Exception as error:
            self._complete(operation, "failed", code=getattr(error, "code", "ANDROID_BACKUP_FAILED"), message=str(error))
            raise

    def delete(self, backup_id: str) -> None:
        backup = next((item for item in self.resources.list("backup") if item.get("id") == backup_id), None)
        if backup is None:
            raise AndroidError("ANDROID_BACKUP_NOT_FOUND", "备份不存在", 404)
        raw_path = Path(backup.get("path", ""))
        if raw_path.is_symlink():
            raise AndroidError("ANDROID_CLEANUP_UNAVAILABLE", "备份路径不在受控目录内", 503)
        path = raw_path.resolve()
        root = self.storage.final.resolve()
        if not path.is_dir() or path.parent != root:
            raise AndroidError("ANDROID_CLEANUP_UNAVAILABLE", "备份路径不在受控目录内", 503)
        for child in path.iterdir():
            if child.is_symlink() or not child.is_file():
                raise AndroidError("ANDROID_CLEANUP_UNAVAILABLE", "备份目录包含不支持的条目", 503)
            child.unlink()
        path.rmdir()
        self.resources.delete("backup", backup_id)

    def restore(self, backup_id: str, image_id: str, new_device_id: str) -> dict[str, Any]:
        backup = next((item for item in self.resources.list("backup") if item["id"] == backup_id), None)
        if backup is None or backup.get("state") != "available":
            raise AndroidError("ANDROID_BACKUP_NOT_FOUND", "备份不存在或不可恢复", 404)
        if backup["imageId"] != image_id:
            raise AndroidError("ANDROID_BACKUP_IMAGE_MISMATCH", "备份必须使用完全相同的镜像摘要", 409)
        return {"deviceId": new_device_id, "backupId": backup_id, "state": "queued"}

    async def restore_data(self, backup_id: str, device: dict[str, Any], runtime: Any) -> dict[str, Any]:
        backup = next((item for item in self.resources.list("backup") if item["id"] == backup_id), None)
        if backup is None or backup.get("state") != "available":
            raise AndroidError("ANDROID_BACKUP_NOT_FOUND", "备份不存在或不可恢复", 404)
        if device.get("imageId") != backup.get("imageId"):
            raise AndroidError("ANDROID_BACKUP_IMAGE_MISMATCH", "备份必须使用完全相同的镜像摘要", 409)
        raw_backup_path = Path(backup.get("path", ""))
        backup_path = raw_backup_path.resolve()
        if raw_backup_path.is_symlink() or not hasattr(runtime, "restore_volume") or not backup_path.is_dir() or backup_path.parent != self.storage.final.resolve():
            raise AndroidError("ANDROID_BACKUP_UNAVAILABLE", "运行时尚未提供数据卷恢复适配器", 503)
        data_path = backup_path / "data.tar"
        if not data_path.is_file():
            raise AndroidError("ANDROID_BACKUP_INCOMPATIBLE", "备份缺少可恢复的数据卷归档", 409)
        digest = hashlib.sha256()
        size = 0
        for path in sorted(backup_path.iterdir()):
            if not path.is_file():
                raise AndroidError("ANDROID_BACKUP_INCOMPATIBLE", "备份目录包含不支持的条目", 409)
            chunk = path.read_bytes()
            digest.update(chunk)
            size += len(chunk)
        if backup.get("sha256") != digest.hexdigest() or backup.get("bytes") != size:
            raise AndroidError("ANDROID_BACKUP_CORRUPT", "备份摘要或字节数不匹配", 409)
        data = data_path.read_bytes()
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
            for member in archive.getmembers():
                kind = "link" if member.issym() or member.islnk() else "device" if member.isdev() or member.isfifo() else "file"
                validate_archive_path(PurePosixPath(member.name), kind)
        with self._runtime_lock(runtime):
            await runtime.restore_volume(device, data)
        return {"deviceId": device["deviceId"], "backupId": backup_id, "state": "restored"}
