import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import uuid4

from autoflow.domain.android.ports import AndroidError


def _path_summary(raw_path: Any) -> dict[str, str] | None:
    if not isinstance(raw_path, str) or not raw_path:
        return None
    path = Path(raw_path)
    parents = [part for part in path.parent.parts if part not in {"/", "\\"}]
    return {"basename": path.name, "parent": "/".join(parents[-2:])}


def _references(item: dict[str, Any]) -> list[dict[str, Any]]:
    value = item.get("references")
    if isinstance(value, list):
        return deepcopy(value)
    if isinstance(value, str) and value:
        return [{"kind": "reference", "id": value}]
    refs = []
    for key, kind in (("deviceId", "device"), ("imageId", "image"), ("profileId", "profile")):
        if item.get(key):
            refs.append({"kind": kind, "id": str(item[key])})
    return refs


def _revision(item: dict[str, Any]) -> int:
    try:
        return max(1, int(item.get("revision", item.get("generation", 1)) or 1))
    except (TypeError, ValueError):
        return 1


def preview_cleanup(resources: list[dict[str, Any]], workspace_identity: str) -> list[dict[str, Any]]:
    result = []
    for item in resources:
        if item.get("workspaceId") != workspace_identity:
            continue
        path_summary = _path_summary(item.get("path"))
        sha256 = item.get("sha256")
        references = _references(item)
        revision = _revision(item)
        ownership = {"workspaceId": workspace_identity, "ownerId": item.get("ownerId", item.get("ownerRunId"))}
        summary = {"sha256": sha256, "path": path_summary}
        projected = {
            "id": item["id"],
            "kind": item.get("kind", "cleanup"),
            "purpose": item.get("purpose", "android"),
            "revision": revision,
            "references": references,
            "workspaceId": workspace_identity,
            "ownership": ownership,
            "size": item.get("size", item.get("bytes", 0)),
            "irreversibleImpact": "删除后无法恢复此本地资源及其数据",
            "sha256": sha256,
            "pathSummary": path_summary,
            "summary": summary,
            "reversible": False,
        }
        fingerprint_input = {
            **projected,
            # Keep the complete path out of the response while still fencing it.
            "pathDigest": hashlib.sha256(str(item.get("path", "")).encode()).hexdigest(),
        }
        projected["fingerprint"] = hashlib.sha256(
            json.dumps(fingerprint_input, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        result.append(projected)
    return result


class CleanupService:
    def __init__(self, resources: Any, devices: Any | None = None, backups: Any | None = None, operations: Any | None = None) -> None:
        self.resources, self.devices, self.backups, self.operations = resources, devices, backups, operations
        self.used: set[str] = set()
        self.previews: dict[str, list[dict[str, Any]]] = {}
        self.last_operation: dict[str, Any] | None = None

    def _reconcile(self, record: dict[str, Any]) -> dict[str, Any]:
        operations = getattr(getattr(self.devices, "management", None), "operations", None)
        for item in record.get("items", []):
            if item.get("state") != "running" or not item.get("operationId"):
                continue
            try:
                state = operations.get(item["operationId"]).state if operations is not None else None
            except AndroidError:
                state = None
            if state in {"succeeded", "failed", "needs_verification", "cancelled"}:
                item["state"] = state
        states = {item.get("state") for item in record.get("items", [])}
        if states and states <= {"succeeded"}:
            record["state"] = "succeeded"
        elif states & {"failed", "needs_verification", "cancelled"}:
            record["state"] = "needs_verification"
        return record

    def _items(self, workspace_identity: str | None = None) -> list[dict[str, Any]]:
        if isinstance(self.resources, list):
            items = self.resources
        else:
            items = [{**item, "kind": "cleanup"} for item in self.resources.list("cleanup")]
            for item in self.resources.list("backup"):
                workspace_id = item.get("workspaceId")
                if workspace_id is None and item.get("path"):
                    workspace_id = str(Path(item["path"]).resolve().parent.parent)
                items.append({**item, "kind": "backup", "workspaceId": workspace_id})
            storage = getattr(self.backups, "storage", None)
            staging = getattr(storage, "staging", None)
            staging_workspace = getattr(self.backups, "workspace_identity", None)
            if isinstance(staging, Path) and staging_workspace and staging.exists() and staging.is_dir() and not staging.is_symlink():
                for candidate in staging.iterdir():
                    if candidate.is_symlink() or not candidate.is_dir() or candidate.parent.resolve() != staging.resolve():
                        continue
                    size = sum(
                        child.stat().st_size
                        for child in candidate.rglob("*")
                        if child.is_file() and not child.is_symlink()
                    )
                    items.append({
                        "id": f"staging:{candidate.name}",
                        "kind": "backup-staging",
                        "purpose": "backup-staging",
                        "workspaceId": staging_workspace,
                        "path": str(candidate),
                        "size": size,
                    })
        if self.devices is not None:
            repository = getattr(self.devices, "repository", self.devices)
            runtime_workspace = getattr(getattr(self.devices, "runtime", None), "workspace_id", None)
            management_workspace = getattr(getattr(self.devices, "management", None), "workspace_identity", None)
            for device in repository.list():
                if device.get("dataRetained") and not device.get("deleted"):
                    device_workspace = device.get("workspaceId")
                    if (
                        workspace_identity
                        and device_workspace == runtime_workspace
                        and workspace_identity == management_workspace
                    ):
                        device_workspace = workspace_identity
                    items.append({**device, "id": device["deviceId"], "kind": "device", "purpose": "retained-data", "workspaceId": device_workspace})
        return items

    def preview(self, resource_ids: list[str], workspace_identity: str) -> list[dict[str, Any]]:
        candidates = preview_cleanup([item for item in self._items(workspace_identity) if item.get("id") in resource_ids], workspace_identity)
        digest = hashlib.sha256(json.dumps(candidates, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.previews[digest] = deepcopy(candidates)
        if hasattr(self.resources, "save"):
            self.resources.save("cleanup-preview", {"id": str(uuid4()), "workspaceId": workspace_identity, "items": deepcopy(candidates), "confirmationDigest": digest, "state": "preview"})
        return deepcopy(candidates)

    def execute(self, workspace_identity: str, confirmation_digest: str, request_id: str | None = None) -> list[dict[str, Any]]:
        candidates = self.previews.get(confirmation_digest)
        if candidates is None and hasattr(self.resources, "list"):
            stored = next((item for item in self.resources.list("cleanup-preview") if item.get("confirmationDigest") == confirmation_digest), None)
            if stored and stored.get("workspaceId") == workspace_identity and stored.get("confirmationDigest") == confirmation_digest:
                candidates = stored.get("items")
        if candidates is None:
            raise AndroidError("ANDROID_CLEANUP_CHANGED", "清理预览已变化，请重新确认", 409)
        if request_id and hasattr(self.resources, "list"):
            previous = next((item for item in self.resources.list("cleanup-operation") if item.get("workspaceId") == workspace_identity and item.get("requestId") == request_id), None)
            if previous is not None:
                previous = self._reconcile(deepcopy(previous))
                if previous.get("state") != "running":
                    self.resources.save("cleanup-operation", deepcopy(previous))
                    if self.operations is not None:
                        try:
                            op = self.operations.by_request(workspace_identity, request_id)
                            if op.state == "running":
                                self.operations.transition(op.operation_id, "running", "succeeded" if previous["state"] == "succeeded" else "needs_verification", {"stage_code": "completed" if previous["state"] == "succeeded" else "verify"})
                        except AndroidError:
                            pass
                self.last_operation = {"operationId": previous.get("id"), "requestId": request_id, "state": previous.get("state"), "previewId": confirmation_digest}
                return deepcopy(previous.get("candidates", candidates))
        current = {item["id"]: item for item in preview_cleanup(self._items(workspace_identity), workspace_identity)}
        if any(current.get(item["id"]) != item for item in candidates):
            raise AndroidError("ANDROID_CLEANUP_CHANGED", "清理预览已变化，请重新确认", 409)
        digest = confirmation_digest
        if digest in self.used:
            raise AndroidError("ANDROID_CLEANUP_CHANGED", "清理预览已使用，请重新生成", 409)
        operation = None
        if self.operations is not None and request_id:
            operation = self.operations.accept(workspace_identity, request_id, "cleanup", "cleanup", digest, {"previewId": digest})
            if operation.state == "queued":
                operation = self.operations.transition(operation.operation_id, "queued", "running", {"stage_code": "deleting"})
            elif operation.state != "running":
                self.last_operation = {"operationId": operation.operation_id, "requestId": operation.request_id, "state": operation.state}
                return deepcopy(candidates)
        record = {"id": str(uuid4()), "requestId": request_id, "workspaceId": workspace_identity, "confirmationDigest": digest, "state": "running", "items": [], "candidates": deepcopy(candidates)}
        pending = False
        try:
            for item in candidates:
                if item.get("kind") == "device":
                    if self.devices is None:
                        raise AndroidError("ANDROID_CLEANUP_UNAVAILABLE", "设备清理服务未配置", 503)
                    result = self.devices.operate(item["id"], {"requestId": f"cleanup:{digest}:{item['id']}", "action": "delete", "deleteData": True})
                    child = result.get("operation") or {}
                    if child.get("state") not in {"succeeded", "failed", "cancelled"}:
                        pending = True
                        record["items"].append({"id": item["id"], "state": "running", "operationId": child.get("id")})
                        if hasattr(self.resources, "save"):
                            self.resources.save("cleanup-operation", deepcopy(record))
                        continue
                elif item.get("kind") == "backup":
                    if self.backups is None:
                        raise AndroidError("ANDROID_CLEANUP_UNAVAILABLE", "备份清理服务未配置", 503)
                    self.backups.delete(item["id"])
                elif item.get("kind") == "backup-staging":
                    storage = getattr(self.backups, "storage", None)
                    discard = getattr(storage, "discard", None)
                    if not callable(discard):
                        raise AndroidError("ANDROID_CLEANUP_UNAVAILABLE", "备份暂存区不支持受控清理", 503)
                    discard(str(item["id"])[len("staging:"):])
                elif isinstance(self.resources, list):
                    self.resources[:] = [stored for stored in self.resources if not (stored.get("id") == item["id"] and stored.get("workspaceId") == workspace_identity)]
                else:
                    delete = getattr(self.resources, "delete", None)
                    if delete is None:
                        raise AndroidError("ANDROID_CLEANUP_UNAVAILABLE", "清理仓储不支持安全删除", 503)
                    delete(str(item.get("kind", "cleanup")), item["id"])
                record["items"].append({"id": item["id"], "state": "succeeded"})
                if hasattr(self.resources, "save"):
                    self.resources.save("cleanup-operation", deepcopy(record))
            record["state"] = "running" if pending else "succeeded"
            if operation is not None and not pending:
                operation = self.operations.transition(operation.operation_id, "running", "succeeded", {"stage_code": "completed"})
        except BaseException as error:
            record["state"] = "needs_verification"
            if hasattr(self.resources, "save"):
                self.resources.save("cleanup-operation", deepcopy(record))
            if operation is not None:
                self.operations.transition(operation.operation_id, "running", "needs_verification", {"stage_code": "verify", "result_code": "CLEANUP_RESULT_UNKNOWN", "message": str(error)[:480]})
            if isinstance(error, AndroidError):
                raise
            raise AndroidError("ANDROID_CLEANUP_RESULT_UNKNOWN", "清理结果未知，请核实后重试", 503) from error
        self.last_operation = {"operationId": operation.operation_id if operation is not None else record["id"], "requestId": request_id, "state": record["state"], "previewId": digest}
        if not pending:
            self.used.add(digest)
            self.previews.pop(digest, None)
        return candidates
