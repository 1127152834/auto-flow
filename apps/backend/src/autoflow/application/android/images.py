import re
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from autoflow.domain.android.ports import AndroidError

_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")


class AndroidImageService:
    def __init__(self, resources: Any, devices: Any) -> None:
        self.resources, self.devices = resources, devices

    def list(self) -> list[dict[str, Any]]:
        return self.resources.list("image")

    def register(self, request: dict[str, Any]) -> dict[str, Any]:
        image_id = request["id"]
        if not _IMAGE_ID.fullmatch(image_id):
            raise AndroidError("ANDROID_IMAGE_ID_INVALID", "镜像摘要格式无效", 422)
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
            "createdAt": datetime.now(UTC).isoformat(),
        }
        self.resources.save("image", image)
        return image

    def delete(self, identifier: str, delete_content: bool = False) -> dict[str, Any]:
        if delete_content:
            raise AndroidError("ANDROID_IMAGE_DELETE_UNAVAILABLE", "镜像内容删除尚未启用", 503)
        image = self.resources.get("image", identifier)
        image_id = image["imageId"]
        refs = [device.get("deviceId") for device in self.devices.list() if not device.get("deleted") and device.get("imageId") == image_id]
        refs.extend(item.get("id") for item in self.resources.list("profile") if not item.get("archived") and item.get("imageId") == image_id)
        refs.extend(item.get("id") for item in self.resources.list("backup") if item.get("imageId") == image_id)
        if refs:
            raise AndroidError("ANDROID_IMAGE_REFERENCED", "镜像仍被资源引用，不能删除内容", 409)
        result = deepcopy(image)
        result["state"] = "unregistered"
        result["deletedAt"] = datetime.now(UTC).isoformat()
        self.resources.save("image", result)
        return result
