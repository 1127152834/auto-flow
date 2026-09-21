import re
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

    def list(self) -> list[dict[str, Any]]:
        return self.resources.list("image")

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
        }
        self.resources.save("image", image)
        return image

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

    def delete(self, identifier: str, delete_content: bool = False) -> dict[str, Any]:
        if delete_content:
            raise AndroidError("ANDROID_IMAGE_DELETE_UNAVAILABLE", "镜像内容删除尚未启用", 503)
        image = self.resources.get("image", identifier)
        image_id = image["imageId"]
        refs = self._references(image_id)
        if refs:
            raise AndroidError("ANDROID_IMAGE_REFERENCED", "镜像仍被资源引用，不能删除内容", 409)
        result = deepcopy(image)
        result["state"] = "unregistered"
        result["deletedAt"] = datetime.now(UTC).isoformat()
        self.resources.save("image", result)
        return result

    def _references(self, image_id: str) -> list:
        refs = [device.get("deviceId") for device in self.devices.list() if not device.get("deleted") and device.get("imageId") == image_id]
        refs.extend(item.get("id") for item in self.resources.list("profile") if not item.get("archived") and item.get("imageId") == image_id)
        refs.extend(item.get("id") for item in self.resources.list("backup") if item.get("imageId") == image_id)
        return refs

    async def delete_content(self, identifier: str) -> dict[str, Any]:
        image = self.resources.get("image", identifier)
        if self._references(image["imageId"]):
            raise AndroidError("ANDROID_IMAGE_REFERENCED", "镜像仍被资源引用，不能删除内容", 409)
        runtime = getattr(self.devices, "runtime", None)
        if runtime is None or not hasattr(runtime, "delete_image"):
            raise AndroidError("ANDROID_IMAGE_DELETE_UNAVAILABLE", "运行时尚未提供镜像内容删除适配器", 503)
        await runtime.delete_image(image["imageId"])
        result = deepcopy(image)
        result.update(state="deleted", deletedAt=datetime.now(UTC).isoformat())
        self.resources.save("image", result)
        return result

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
