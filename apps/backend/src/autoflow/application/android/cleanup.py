import hashlib
import json
from pathlib import Path
from typing import Any

from autoflow.domain.android.ports import AndroidError


def preview_cleanup(resources: list[dict[str, Any]], workspace_identity: str) -> list[dict[str, Any]]:
    return [
        {
            "id": item["id"],
            "kind": item.get("kind", "cleanup"),
            "purpose": item.get("purpose", "android"),
            "size": item.get("size", 0),
            "fingerprint": hashlib.sha256(
                json.dumps(
                    {
                        key: item.get(key)
                        for key in ("id", "kind", "workspaceId", "path", "sha256", "generation")
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest(),
            "reversible": False,
        }
        for item in resources
        if item.get("workspaceId") == workspace_identity
    ]


class CleanupService:
    def __init__(self, resources: Any, devices: Any | None = None, backups: Any | None = None) -> None:
        self.resources, self.devices, self.backups = resources, devices, backups
        self.used: set[str] = set()
        self.previews: dict[str, list[dict[str, Any]]] = {}

    def _items(self) -> list[dict[str, Any]]:
        if isinstance(self.resources, list):
            items = self.resources
        else:
            items = [{**item, "kind": "cleanup"} for item in self.resources.list("cleanup")]
            for item in self.resources.list("backup"):
                workspace_id = item.get("workspaceId")
                if workspace_id is None and item.get("path"):
                    workspace_id = str(Path(item["path"]).resolve().parent.parent)
                items.append({**item, "kind": "backup", "workspaceId": workspace_id})
        if self.devices is not None:
            repository = getattr(self.devices, "repository", self.devices)
            for device in repository.list():
                if device.get("dataRetained") and not device.get("deleted"):
                    items.append({**device, "id": device["deviceId"], "kind": "device", "purpose": "retained-data"})
        return items

    def preview(self, resource_ids: list[str], workspace_identity: str) -> list[dict[str, Any]]:
        candidates = preview_cleanup([item for item in self._items() if item.get("id") in resource_ids], workspace_identity)
        digest = hashlib.sha256(json.dumps(candidates, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.previews[digest] = candidates
        return candidates

    def execute(self, workspace_identity: str, confirmation_digest: str) -> list[dict[str, Any]]:
        candidates = self.previews.get(confirmation_digest)
        if candidates is None:
            raise AndroidError("ANDROID_CLEANUP_CHANGED", "清理预览已变化，请重新确认", 409)
        current = {item["id"]: item for item in preview_cleanup(self._items(), workspace_identity)}
        if any(current.get(item["id"]) != item for item in candidates):
            raise AndroidError("ANDROID_CLEANUP_CHANGED", "清理预览已变化，请重新确认", 409)
        digest = confirmation_digest
        if digest in self.used:
            raise AndroidError("ANDROID_CLEANUP_CHANGED", "清理预览已使用，请重新生成", 409)
        for item in candidates:
            if item.get("kind") == "device":
                if self.devices is None:
                    raise AndroidError("ANDROID_CLEANUP_UNAVAILABLE", "设备清理服务未配置", 503)
                self.devices.operate(item["id"], {"requestId": f"cleanup:{digest}:{item['id']}", "action": "delete", "deleteData": True})
            elif item.get("kind") == "backup":
                if self.backups is None:
                    raise AndroidError("ANDROID_CLEANUP_UNAVAILABLE", "备份清理服务未配置", 503)
                self.backups.delete(item["id"])
            elif isinstance(self.resources, list):
                self.resources[:] = [stored for stored in self.resources if stored.get("id") != item["id"]]
            else:
                delete = getattr(self.resources, "delete", None)
                if delete is None:
                    raise AndroidError("ANDROID_CLEANUP_UNAVAILABLE", "清理仓储不支持安全删除", 503)
                delete(str(item.get("kind", "cleanup")), item["id"])
        self.used.add(digest)
        self.previews.pop(digest, None)
        return candidates
