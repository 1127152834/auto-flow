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


def test_cleanup_maps_runtime_workspace_hash_to_management_identity():
    service = CleanupService(_ResourceRepository(), _HashedDevices())

    preview = service.preview(["d1"], "/workspace")

    assert [item["id"] for item in preview] == ["d1"]


def test_cleanup_deletes_backup_through_backup_service():
    resources = _ResourceRepository()
    resources.backup["bytes"] = 19
    backups = _Backups()
    service = CleanupService(resources, backups=backups)
    preview = service.preview(["b1"], "w")
    assert preview[0]["kind"] == "backup"
    assert preview[0]["size"] == 19
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


def test_cleanup_preview_freezes_public_ownership_revision_and_summary():
    service = CleanupService([
        {
            "id": "v1",
            "workspaceId": "w",
            "ownerId": "workspace-w",
            "revision": 7,
            "kind": "volume",
            "purpose": "android-data",
            "size": 12,
            "path": "/private/root/v1.tar",
            "sha256": "a" * 64,
            "references": [{"kind": "device", "id": "d1", "name": "测试设备"}],
        }
    ])

    preview = service.preview(["v1"], "w")

    item = preview[0]
    assert item["revision"] == 7
    assert item["workspaceId"] == "w"
    assert item["ownership"] == {"workspaceId": "w", "ownerId": "workspace-w"}
    assert item["references"] == [{"kind": "device", "id": "d1", "name": "测试设备"}]
    assert item["sha256"] == "a" * 64
    assert item["pathSummary"] == {"basename": "v1.tar", "parent": "private/root"}
    assert item["summary"]["sha256"] == "a" * 64
    assert item["summary"]["path"] == {"basename": "v1.tar", "parent": "private/root"}
    assert item["irreversibleImpact"]
    assert item["fingerprint"]


def test_cleanup_rejects_revision_reference_size_or_path_changes_before_delete():
    resources = [{
        "id": "v1",
        "workspaceId": "w",
        "revision": 1,
        "size": 12,
        "path": "/private/root/v1.tar",
        "sha256": "a" * 64,
        "references": [{"kind": "device", "id": "d1"}],
    }]
    service = CleanupService(resources)
    preview = service.preview(["v1"], "w")
    digest = hashlib.sha256(json.dumps(preview, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    resources[0]["revision"] = 2
    resources[0]["references"] = [{"kind": "device", "id": "d2"}]
    resources[0]["size"] = 13
    resources[0]["path"] = "/private/root/other.tar"
    with pytest.raises(AndroidError, match="变化"):
        service.execute("w", digest)


def test_cleanup_lists_owned_orphan_backup_staging_and_uses_controlled_discard(tmp_path):
    staging = tmp_path / "android-backups" / "staging" / "stale-1"
    staging.mkdir(parents=True)
    (staging / "partial.tar").write_bytes(b"partial")
    backups = _StagingBackups(tmp_path / "android-backups", "w")
    service = CleanupService(_ResourceRepository(), backups=backups)

    preview = service.preview(["staging:stale-1"], "w")

    assert preview[0]["kind"] == "backup-staging"
    assert preview[0]["size"] == 7
    digest = hashlib.sha256(json.dumps(preview, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    service.execute("w", digest)
    assert backups.discarded == ["stale-1"]


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


class _HashedDevices(_Devices):
    def __init__(self):
        super().__init__()
        self.runtime = type("Runtime", (), {"workspace_id": "runtime-hash"})()
        self.management = type("Management", (), {"workspace_identity": "/workspace"})()

    def list(self):
        return [{"deviceId": "d1", "workspaceId": "runtime-hash", "dataRetained": True, "deleted": False}]


class _StagingBackups:
    def __init__(self, root, workspace_identity):
        self.workspace_identity = workspace_identity
        self.storage = type("Storage", (), {"root": root, "staging": root / "staging"})()
        self.storage.discard = self.discard
        self.discarded = []

    def delete(self, identifier):
        raise AssertionError(f"final backup deletion not expected for {identifier}")

    def discard(self, identifier):
        self.discarded.append(identifier)
