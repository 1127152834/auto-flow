import hashlib
import json
import threading
from collections import Counter
from contextlib import nullcontext
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
            "filesystemFingerprint": item.get("filesystemFingerprint"),
        }
        projected["fingerprint"] = hashlib.sha256(
            json.dumps(fingerprint_input, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        result.append(projected)
    return result


class CleanupService:
    def __init__(self, resources: Any, devices: Any | None = None, backups: Any | None = None, operations: Any | None = None) -> None:
        self.resources, self.devices, self.backups, self.operations = resources, devices, backups, operations
        self.used: set[tuple[str, str]] = set()
        self.previews: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self.preview_ids: dict[tuple[str, str], str] = {}
        self.request_lock = threading.RLock()
        self.last_operation: dict[str, Any] | None = None

    def _reconcile(self, record: dict[str, Any]) -> dict[str, Any]:
        operations = self.operations or getattr(getattr(self.devices, "management", None), "operations", None)
        for item in record.get("items", []):
            # A persisted parent/item may have been marked terminal before the
            # child response was durably observed.  Always re-read a referenced
            # child on replay; trusting the cached item state could turn a
            # later child failure into a false successful parent operation.
            if not item.get("operationId"):
                continue
            if operations is None:
                item["state"] = "needs_verification"
                continue
            try:
                try:
                    child = operations.get(item["operationId"], record.get("workspaceId"))
                except TypeError:
                    child = operations.get(item["operationId"])
                if record.get("workspaceId") is not None and getattr(child, "workspace_identity", record["workspaceId"]) != record["workspaceId"]:
                    state = "needs_verification"
                else:
                    state = child.state
            except (AndroidError, AttributeError, KeyError, LookupError, TypeError):
                state = "needs_verification"
            if state in {"succeeded", "failed", "needs_verification", "cancelled"}:
                item["state"] = state
            elif state in {"queued", "running"}:
                item["state"] = "running"
            else:
                item["state"] = "needs_verification"
        states = {item.get("state") for item in record.get("items", [])}
        complete = "candidates" not in record or Counter(str(item.get("id")) for item in record["items"]) == Counter(str(item.get("id")) for item in record["candidates"])
        if complete and states and states <= {"succeeded"}:
            record["state"] = "succeeded"
        elif states & {"failed", "needs_verification", "cancelled"}:
            record["state"] = "needs_verification"
        elif states or not complete:
            record["state"] = "running"
        return record

    def reconcile_request(self, workspace_identity: str, request_id: str) -> None:
        if self.operations is None or not hasattr(self.resources, "list"):
            return
        with self.request_lock:
            stored = next((item for item in self.resources.list("cleanup-operation") if item.get("workspaceId") == workspace_identity and item.get("requestId") == request_id), None)
            if stored is None:
                return
            record = self._reconcile(deepcopy(stored))
            if record != stored:
                self.resources.save("cleanup-operation", record)
            desired = record.get("state")
            if desired not in {"succeeded", "needs_verification"}:
                return
            parent = self.operations.by_request(workspace_identity, request_id)
            if parent.state in {"running", "needs_verification"} and parent.state != desired:
                self.operations.transition(parent.operation_id, parent.state, desired, {"stage_code": "completed" if desired == "succeeded" else "verify", "result_code": "CLEANUP_COMPLETED" if desired == "succeeded" else "CLEANUP_RESULT_UNKNOWN"})

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
            owner = getattr(self.backups, "workspace_identity", None)
            if storage is not None and owner and owner == workspace_identity:
                registered = {item["id"] for item in items if item.get("kind") == "backup"}
                for item in items:
                    if item.get("kind") == "backup" and item.get("workspaceId") == owner:
                        path = Path(item.get("path", ""))
                        if path != storage.final / item["id"]:
                            raise AndroidError("ANDROID_CLEANUP_CHANGED", "备份路径与目录记录不一致", 409)
                        item.update(storage.snapshot(path))
                items.extend({**item, "workspaceId": owner} for item in storage.inventory(registered))
        if self.devices is not None:
            repository = getattr(self.devices, "repository", self.devices)
            runtime_workspace = getattr(getattr(self.devices, "runtime", None), "workspace_id", None)
            management_workspace = getattr(getattr(self.devices, "management", None), "workspace_identity", None)
            for device in repository.list():
                if device.get("dataRetained") and device.get("androidStatus") == "retained" and not device.get("deleted"):
                    device_workspace = device.get("workspaceId")
                    if (
                        workspace_identity
                        and device_workspace == runtime_workspace
                        and workspace_identity == management_workspace
                    ):
                        device_workspace = workspace_identity
                    items.append({**device, "id": device["deviceId"], "kind": "device", "purpose": "retained-data", "workspaceId": device_workspace})
        return items

    def inventory(self, workspace_identity: str) -> list[dict[str, Any]]:
        try:
            return preview_cleanup(self._items(workspace_identity), workspace_identity)
        except OSError as error:
            raise AndroidError("ANDROID_CLEANUP_CHANGED", "清理对象无法核实，请刷新后重新预览", 409) from error

    def preview(self, resource_ids: list[str], workspace_identity: str) -> list[dict[str, Any]]:
        candidates = [item for item in self.inventory(workspace_identity) if item["id"] in resource_ids]
        digest = hashlib.sha256(json.dumps(candidates, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        preview_id = str(uuid4())
        key = (workspace_identity, digest)
        self.previews[key] = deepcopy(candidates)
        self.preview_ids[key] = preview_id
        if hasattr(self.resources, "save"):
            self.resources.save("cleanup-preview", {"id": preview_id, "workspaceId": workspace_identity, "items": deepcopy(candidates), "confirmationDigest": digest, "state": "preview"})
        return deepcopy(candidates)

    def preview_id_for(self, workspace_identity: str, confirmation_digest: str) -> str | None:
        key = (workspace_identity, confirmation_digest)
        preview_id = self.preview_ids.get(key)
        if preview_id is not None:
            return preview_id
        if hasattr(self.resources, "list"):
            stored = next((item for item in self.resources.list("cleanup-preview") if item.get("workspaceId") == workspace_identity and item.get("confirmationDigest") == confirmation_digest), None)
            if stored is not None:
                self.preview_ids[key] = str(stored["id"])
                return str(stored["id"])
        return None

    def execute(self, workspace_identity: str, confirmation_digest: str, request_id: str | None = None, preview_id: str | None = None) -> list[dict[str, Any]]:
        storage = getattr(self.backups, "storage", None)
        with self.request_lock, storage.lock() if storage is not None else nullcontext():
            return self._execute(workspace_identity, confirmation_digest, request_id, preview_id)

    def _execute(self, workspace_identity: str, confirmation_digest: str, request_id: str | None = None, preview_id: str | None = None) -> list[dict[str, Any]]:
        key = (workspace_identity, confirmation_digest)
        candidates = self.previews.get(key)
        stored = None
        if hasattr(self.resources, "list"):
            stored = next((item for item in self.resources.list("cleanup-preview") if item.get("workspaceId") == workspace_identity and item.get("confirmationDigest") == confirmation_digest and (preview_id is None or item.get("id") == preview_id)), None)
        if candidates is None and stored is not None:
            candidates = stored.get("items")
        expected_preview_id = self.preview_id_for(workspace_identity, confirmation_digest)
        if preview_id is not None and expected_preview_id != preview_id:
            raise AndroidError("ANDROID_CLEANUP_CHANGED", "清理预览编号已变化，请重新确认", 409)
        preview_id = preview_id or expected_preview_id
        if candidates is None:
            raise AndroidError("ANDROID_CLEANUP_CHANGED", "清理预览已变化，请重新确认", 409)
        if request_id and hasattr(self.resources, "list"):
            previous = next((item for item in self.resources.list("cleanup-operation") if item.get("workspaceId") == workspace_identity and item.get("requestId") == request_id), None)
            if previous is not None:
                if previous.get("confirmationDigest") != confirmation_digest or (preview_id is not None and previous.get("previewId") != preview_id):
                    raise AndroidError("ANDROID_CLEANUP_REQUEST_CONFLICT", "请求编号已用于不同清理预览", 409)
                previous = self._reconcile(deepcopy(previous))
                if previous.get("state") != "running":
                    self.resources.save("cleanup-operation", deepcopy(previous))
                    if self.operations is not None:
                        try:
                            op = self.operations.by_request(workspace_identity, request_id)
                            desired = "succeeded" if previous["state"] == "succeeded" else "needs_verification"
                            if op.state in {"running", "needs_verification"} and op.state != desired:
                                op = self.operations.transition(op.operation_id, op.state, desired, {"stage_code": "completed" if desired == "succeeded" else "verify"})
                        except AndroidError:
                            pass
                parent_id = previous.get("operationId") or previous.get("id")
                self.last_operation = {"operationId": parent_id, "requestId": request_id, "state": previous.get("state"), "previewId": preview_id}
                return deepcopy(previous.get("candidates", candidates))
        current = {item["id"]: item for item in self.inventory(workspace_identity)}
        if any(current.get(item["id"]) != item for item in candidates):
            raise AndroidError("ANDROID_CLEANUP_CHANGED", "清理预览已变化，请重新确认", 409)
        digest = confirmation_digest
        if (workspace_identity, digest) in self.used:
            raise AndroidError("ANDROID_CLEANUP_CHANGED", "清理预览已使用，请重新生成", 409)
        operation = None
        if self.operations is not None and request_id:
            operation = self.operations.accept(workspace_identity, request_id, "cleanup", "cleanup", digest, {"previewId": preview_id})
            if operation.state == "queued":
                operation = self.operations.transition(operation.operation_id, "queued", "running", {"stage_code": "deleting"})
            elif operation.state != "running":
                self.last_operation = {"operationId": operation.operation_id, "requestId": operation.request_id, "state": operation.state, "previewId": preview_id}
                return deepcopy(candidates)
        record = {"id": str(uuid4()), "operationId": operation.operation_id if operation is not None else None, "requestId": request_id, "workspaceId": workspace_identity, "previewId": preview_id, "confirmationDigest": digest, "state": "running", "items": [], "candidates": deepcopy(candidates)}
        pending = False
        try:
            for item in candidates:
                if item.get("kind") == "device":
                    if self.devices is None:
                        raise AndroidError("ANDROID_CLEANUP_UNAVAILABLE", "设备清理服务未配置", 503)
                    result = self.devices.operate(item["id"], {"requestId": f"cleanup:{digest}:{item['id']}", "action": "delete", "deleteData": True})
                    child = result.get("operation") or {}
                    child_id = child.get("id")
                    child_state = child.get("state")
                    if child_state in {"failed", "cancelled", "needs_verification"}:
                        record["items"].append({"id": item["id"], "state": child_state, "operationId": child_id})
                        if hasattr(self.resources, "save"):
                            self.resources.save("cleanup-operation", deepcopy(record))
                        continue
                    if child_state not in {"succeeded"}:
                        pending = True
                        record["items"].append({"id": item["id"], "state": "running", "operationId": child_id})
                        if hasattr(self.resources, "save"):
                            self.resources.save("cleanup-operation", deepcopy(record))
                        continue
                    record["items"].append({"id": item["id"], "state": "succeeded", "operationId": child_id})
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
                elif item.get("kind") == "backup-orphan":
                    self.backups.storage.discard_final(str(item["id"])[len("orphan:"):])
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
            states = {item.get("state") for item in record["items"]}
            if states & {"failed", "cancelled", "needs_verification"}:
                record["state"] = "needs_verification"
            else:
                record["state"] = "running" if pending else "succeeded"
            if hasattr(self.resources, "save"):
                self.resources.save("cleanup-operation", deepcopy(record))
            if operation is not None and not pending:
                if record["state"] == "needs_verification":
                    operation = self.operations.transition(operation.operation_id, "running", "needs_verification", {"stage_code": "verify", "result_code": "CLEANUP_RESULT_UNKNOWN"})
                else:
                    operation = self.operations.transition(operation.operation_id, "running", "succeeded", {"stage_code": "completed"})
        except BaseException as error:
            record["state"] = "needs_verification"
            if hasattr(self.resources, "save"):
                self.resources.save("cleanup-operation", deepcopy(record))
            if operation is not None and operation.state in {"running", "needs_verification"}:
                self.operations.transition(operation.operation_id, operation.state, "needs_verification", {"stage_code": "verify", "result_code": "CLEANUP_RESULT_UNKNOWN", "message": str(error)[:480]})
            if isinstance(error, AndroidError):
                raise
            raise AndroidError("ANDROID_CLEANUP_RESULT_UNKNOWN", "清理结果未知，请核实后重试", 503) from error
        self.last_operation = {"operationId": operation.operation_id if operation is not None else record["id"], "requestId": request_id, "state": record["state"], "previewId": preview_id}
        if not pending:
            self.used.add((workspace_identity, digest))
            self.previews.pop(key, None)
        return candidates
