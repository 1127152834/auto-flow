import asyncio
import re
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from autoflow.domain.android.ports import AndroidError

_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_REFERENCE = re.compile(r"^(?:[A-Za-z0-9._/-]+:[A-Za-z0-9._-]+|sha256:[0-9a-f]{64}|local:[A-Za-z0-9._/-]+)$")


class AndroidImageService:
    def __init__(self, resources: Any, devices: Any, catalog: Any | None = None) -> None:
        self.resources, self.devices, self.catalog = resources, devices, catalog

    def _workspace(self) -> str | None:
        return getattr(getattr(self.devices, "runtime", None), "workspace_id", None)

    def list(self) -> list[dict[str, Any]]:
        workspace = self._workspace()
        return [
            item for item in self.resources.list("image")
            if workspace is None or item.get("workspaceId") in {None, workspace}
        ]

    @contextmanager
    def _runtime_lock(self):
        runtime = getattr(self.devices, "runtime", None)
        lock = getattr(runtime, "lock", None)
        unlock = getattr(runtime, "unlock", None)
        locked = False
        if callable(lock):
            lock()
            locked = True
        try:
            yield runtime
        finally:
            if locked and callable(unlock):
                unlock()

    @staticmethod
    def _public(image: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in image.items() if not key.startswith("_") and key not in {"deleteRequestId", "deleteRequestDigest"}}

    def register(self, request: dict[str, Any]) -> dict[str, Any]:
        image_id = request["id"]
        if not _IMAGE_ID.fullmatch(image_id):
            raise AndroidError("ANDROID_IMAGE_ID_INVALID", "镜像摘要格式无效", 422)
        if not _REFERENCE.fullmatch(str(request.get("reference", ""))):
            raise AndroidError("ANDROID_IMAGE_REFERENCE_INVALID", "镜像引用格式无效", 422)
        existing = next((item for item in self.list() if item["imageId"] == image_id), None)
        if existing is not None:
            if any(existing.get(key) != request.get(key) for key in ("name", "reference")):
                raise AndroidError("ANDROID_IMAGE_CONFLICT", "镜像摘要已登记为其他内容", 409)
            return existing
        image = {
            "id": str(uuid4()),
            "imageId": image_id,
            "name": request["name"],
            "reference": request["reference"],
            "revision": 1,
            "state": "registered",
            "verification": {"state": "unknown", "evidence": None},
            "sourceDigest": request.get("sourceDigest"),
            "architecture": request.get("architecture"),
            "os": request.get("os"),
            "androidVersion": request.get("androidVersion"),
            "googleComponents": request.get("googleComponents", "unknown"),
            "references": [{"kind": "source", "id": image_id, "name": request["reference"]}],
            "requestId": request.get("requestId"),
            "createdAt": datetime.now(UTC).isoformat(),
            "workspaceId": self._workspace(),
        }
        self.resources.save("image", image)
        return self._public(image)

    async def pull(self, request_id: str, reference: str) -> dict[str, Any]:
        if self.catalog is None:
            raise AndroidError("ANDROID_IMAGE_PULL_UNAVAILABLE", "镜像拉取适配器尚未配置", 503)
        existing = next((item for item in self.list() if item.get("requestId") == request_id), None)
        if existing is not None:
            if existing.get("reference") != reference:
                raise AndroidError("ANDROID_REQUEST_CONFLICT", "请求编号已用于其他镜像拉取", 409)
            return existing
        metadata = await (self.catalog.pull(reference) if hasattr(self.catalog, "pull") else self.catalog.inspect(reference))
        image = self.register({
            "id": metadata.image_id,
            "name": reference,
            "reference": reference,
            "requestId": request_id,
            "sourceDigest": metadata.source_digest,
            "architecture": metadata.architecture,
            "os": metadata.os,
            "androidVersion": metadata.android_version,
            "googleComponents": metadata.google_components,
        })
        return image

    def delete(self, identifier: str, delete_content: bool = False, request_id: str | None = None, expected_revision: int | None = None) -> dict[str, Any]:
        if delete_content:
            raise AndroidError("ANDROID_IMAGE_DELETE_UNAVAILABLE", "镜像内容删除尚未启用", 503)
        with self._runtime_lock():
            image = self.resources.get("image", identifier)
            if request_id and image.get("deleteRequestId") == request_id:
                return self._public(image)
            if expected_revision is not None and int(image.get("revision", 0)) != expected_revision:
                raise AndroidError("ANDROID_IMAGE_CONFLICT", "镜像目录已更新，请重新加载", 409)
            refs = self._references(image["imageId"])
            if refs:
                raise AndroidError("ANDROID_IMAGE_REFERENCED", "镜像仍被资源引用，不能删除内容", 409)
            result = deepcopy(image)
            result["state"] = "unregistered"
            result["revision"] = int(image.get("revision", 0)) + 1
            result["deletedAt"] = datetime.now(UTC).isoformat()
            if request_id:
                result["deleteRequestId"] = request_id
            self.resources.save("image", result)
            return self._public(result)

    def _references(self, image_id: str) -> list:
        workspace = self._workspace()
        refs = [
            device.get("deviceId")
            for device in self.devices.list()
            if not device.get("deleted")
            and device.get("imageId") == image_id
            and (workspace is None or device.get("workspaceId") in {None, workspace})
        ]
        refs.extend(item.get("id") for item in self.resources.list("profile") if not item.get("archived") and item.get("imageId") == image_id and (workspace is None or item.get("workspaceId") in {None, workspace}))
        refs.extend(item.get("id") for item in self.resources.list("backup") if item.get("imageId") == image_id and (workspace is None or item.get("workspaceId") in {None, workspace}))
        return refs

    async def delete_content(self, identifier: str, request_id: str | None = None, expected_revision: int | None = None) -> dict[str, Any]:
        with self._runtime_lock() as runtime:
            image = self.resources.get("image", identifier)
            if request_id and image.get("deleteRequestId") == request_id:
                if image.get("state") in {"delete_pending", "delete_needs_verification", "delete_blocked"}:
                    raise AndroidError("ANDROID_IMAGE_DELETE_RESULT_UNKNOWN", "镜像内容删除结果未知，请先核实运行时", 503)
                return self._public(image)
            if expected_revision is not None and int(image.get("revision", 0)) != expected_revision:
                raise AndroidError("ANDROID_IMAGE_CONFLICT", "镜像目录已更新，请重新加载", 409)
            if self._references(image["imageId"]):
                raise AndroidError("ANDROID_IMAGE_REFERENCED", "镜像仍被资源引用，不能删除内容", 409)
            if runtime is None or not hasattr(runtime, "delete_image"):
                raise AndroidError("ANDROID_IMAGE_DELETE_UNAVAILABLE", "运行时尚未提供镜像内容删除适配器", 503)
            pending = deepcopy(image)
            pending.update(state="delete_pending", deleteRequestId=request_id, deleteRequestDigest=str(expected_revision))
            self.resources.save("image", pending)
            try:
                await runtime.delete_image(image["imageId"])
            except asyncio.CancelledError:
                pending["state"] = "delete_blocked"
                self.resources.save("image", pending)
                raise
            except (TimeoutError, OSError) as error:
                pending["state"] = "delete_blocked"
                self.resources.save("image", pending)
                raise AndroidError("ANDROID_IMAGE_DELETE_RESULT_UNKNOWN", "镜像内容删除结果未知，请先核实运行时", 503) from error
            result = deepcopy(image)
            result.update(state="deleted", revision=int(image.get("revision", 0)) + 1, deletedAt=datetime.now(UTC).isoformat())
            if request_id:
                result["deleteRequestId"] = request_id
            self.resources.save("image", result)
            return self._public(result)

    def verify(self, identifier: str, observation: dict[str, Any]) -> dict[str, Any]:
        image = self.resources.get("image", identifier)
        if observation.get("result") not in {"passed", "failed", "blocked"} or not observation.get("check"):
            raise AndroidError("ANDROID_IMAGE_VERIFICATION_INVALID", "验证观察结果无效", 422)
        verification = deepcopy(image.get("verification") or {"state": "not_tested", "records": []})
        records = list(verification.get("records") or [])
        records.append({"check": observation["check"], "result": observation["result"], "evidence": {"message": str((observation.get("evidence") or {}).get("message", ""))[:500]}, "recordedAt": datetime.now(UTC).isoformat()})
        verification["records"] = records
        results = {record["result"] for record in records}
        verification["state"] = "failed" if "failed" in results else "blocked" if "blocked" in results else "passed" if results and results == {"passed"} else "not_tested"
        image["verification"] = verification
        image["state"] = "verified" if verification["state"] == "passed" else "registered"
        self.resources.save("image", image)
        return image
