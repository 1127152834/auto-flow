import hashlib
import json

import pytest

from autoflow.application.android.cleanup import CleanupService
from autoflow.domain.android.ports import AndroidError


def test_cleanup_requires_unchanged_preview_digest():
    service = CleanupService([{"id": "v1", "workspaceId": "w", "size": 12}, {"id": "v2", "workspaceId": "w", "size": 8}])
    preview = service.preview(["v1"], "w")
    digest = hashlib.sha256(json.dumps(preview, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert service.execute("w", digest)[0]["id"] == "v1"
    with pytest.raises(AndroidError):
        service.execute("w", digest)


def test_cleanup_does_not_recompute_a_different_resource_set():
    service = CleanupService([
        {"id": "v1", "workspaceId": "w", "size": 12},
        {"id": "v2", "workspaceId": "w", "size": 8},
    ])
    preview = service.preview(["v1"], "w")
    digest = hashlib.sha256(json.dumps(preview, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert [item["id"] for item in service.execute("w", digest)] == ["v1"]


def test_cleanup_execution_removes_the_frozen_resource():
    resources = [{"id": "v1", "workspaceId": "w", "size": 12}]
    service = CleanupService(resources)
    preview = service.preview(["v1"], "w")
    digest = hashlib.sha256(json.dumps(preview, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    service.execute("w", digest)
    assert service.preview(["v1"], "w") == []


def test_cleanup_includes_retained_devices_and_submits_scoped_delete():
    resources = _ResourceRepository()
    devices = _Devices()
    service = CleanupService(resources, devices)
    preview = service.preview(["d1"], "w")
    assert preview[0]["kind"] == "device"
    digest = hashlib.sha256(json.dumps(preview, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    service.execute("w", digest)
    assert devices.calls == [("d1", {"requestId": f"cleanup:{digest}:d1", "action": "delete", "deleteData": True})]


def test_cleanup_deletes_backup_through_backup_service():
    resources = _ResourceRepository()
    backups = _Backups()
    service = CleanupService(resources, backups=backups)
    preview = service.preview(["b1"], "w")
    assert preview[0]["kind"] == "backup"
    digest = hashlib.sha256(json.dumps(preview, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    service.execute("w", digest)
    assert backups.calls == ["b1"]


def test_cleanup_rejects_changed_backup_reference_after_preview():
    resources = _ResourceRepository()
    service = CleanupService(resources, backups=_Backups())
    preview = service.preview(["b1"], "w")
    digest = hashlib.sha256(json.dumps(preview, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    resources.backup["path"] = "/other/backup"
    with pytest.raises(AndroidError, match="变化"):
        service.execute("w", digest)


class _ResourceRepository:
    def __init__(self):
        self.backup = {"id": "b1", "workspaceId": "w", "kind": "backup", "path": "/w/b1", "sha256": "a"}

    def list(self, kind):
        return [self.backup] if kind == "backup" else []


class _Backups:
    def __init__(self):
        self.calls = []

    def delete(self, identifier):
        self.calls.append(identifier)


class _Devices:
    def __init__(self):
        self.repository = self
        self.calls = []

    def list(self):
        return [{"deviceId": "d1", "workspaceId": "w", "dataRetained": True, "deleted": False}]

    def operate(self, device_id, request):
        self.calls.append((device_id, request))
        return {"deviceId": device_id}
