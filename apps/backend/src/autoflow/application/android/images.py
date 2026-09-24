import asyncio
import re
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from autoflow.domain.android.image_verification import (
    REQUIRED_CHECKS,
    summarize_verification,
)
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
        fields = {"id", "imageId", "name", "reference", "revision", "state", "verification", "validation", "createdAt", "sourceDigest", "architecture", "os", "androidVersion", "googleComponents", "references"}
        public = {key: value for key, value in image.items() if key in fields}
        public.setdefault("validation", "not_tested")
        return public

    @staticmethod
    def _metadata_value(metadata: Any, *keys: str, default: Any = None) -> Any:
        for key in keys:
            if isinstance(metadata, Mapping):
                value = metadata.get(key)
            else:
                value = getattr(metadata, key, None)
            if value is not None:
                return value
        return default

    def _normalise_metadata(self, metadata: Any) -> dict[str, Any]:
        architecture = self._metadata_value(metadata, "architecture")
        return {
            "imageId": self._metadata_value(metadata, "imageId", "image_id"),
            "sourceDigest": self._metadata_value(metadata, "sourceDigest", "source_digest"),
            "architecture": "arm64" if architecture == "aarch64" else architecture,
            "os": self._metadata_value(metadata, "os"),
            "androidVersion": self._metadata_value(metadata, "androidVersion", "android_version"),
            "googleComponents": self._metadata_value(
                metadata, "googleComponents", "google_components", default="unknown"
            ),
        }

    @staticmethod
    def _validate_metadata(metadata: dict[str, Any]) -> None:
        if not _IMAGE_ID.fullmatch(str(metadata.get("imageId") or "")):
            raise AndroidError("ANDROID_IMAGE_ID_INVALID", "镜像未返回固定摘要", 502)
        if metadata.get("architecture") not in {"arm64", "aarch64"} or metadata.get("os") != "linux":
            raise AndroidError(
                "ANDROID_IMAGE_UNTRUSTED",
                "镜像不是兼容的 Linux ARM64 镜像",
                409,
            )

    async def _inspect_reference(self, reference: str) -> dict[str, Any]:
        runtime = getattr(self.devices, "runtime", None)
        inspector = getattr(self.catalog, "inspect", None)
        if not callable(inspector):
            inspector = getattr(runtime, "inspect_image", None)
        if not callable(inspector):
            raise AndroidError(
                "ANDROID_IMAGE_CATALOG_UNAVAILABLE",
                "镜像目录不可访问，不能登记镜像",
                503,
            )
        metadata = await inspector(reference)
        normalised = self._normalise_metadata(metadata)
        self._validate_metadata(normalised)
        return normalised

    def _persist_registered(
        self, request: dict[str, Any], metadata: dict[str, Any], receipt: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        image_id = request["id"]
        existing = next((item for item in self.list() if item["imageId"] == image_id), None)
        if existing is not None:
            if any(existing.get(key) != request.get(key) for key in ("name", "reference")):
                raise AndroidError("ANDROID_IMAGE_CONFLICT", "镜像摘要已登记为其他内容", 409)
            if existing.get("state") in {"delete_pending", "delete_needs_verification", "delete_blocked"}:
                raise AndroidError("ANDROID_IMAGE_DELETE_RESULT_UNKNOWN", "镜像删除结果未核实，不能重新登记", 503)
            metadata_fields = (
                "sourceDigest",
                "architecture",
                "os",
                "androidVersion",
                "googleComponents",
            )
            changed = any(existing.get(key) != metadata.get(key) for key in metadata_fields)
            if existing.get("state") in {"deleted", "unregistered"}:
                existing.update(state="verified" if (existing.get("verification") or {}).get("state") == "passed" else "registered", revision=int(existing.get("revision", 0)) + 1)
                changed = True
            if changed:
                existing.update({key: metadata.get(key) for key in metadata_fields})
                self._save_registration(existing, receipt)
            elif receipt is not None:
                self.resources.save("image_pull_receipt", receipt)
            return self._public(existing)
        image = {
            "id": str(uuid4()),
            "imageId": image_id,
            "name": request["name"],
            "reference": str(request["reference"]),
            "revision": 1,
            "state": "registered",
            "verification": {"state": "unknown", "evidence": None},
            "validation": "not_tested",
            "sourceDigest": metadata["sourceDigest"],
            "architecture": metadata["architecture"],
            "os": metadata["os"],
            "androidVersion": metadata["androidVersion"],
            "googleComponents": metadata["googleComponents"],
            "references": [{"kind": "source", "id": image_id, "name": str(request["reference"])}],
            "requestId": request.get("requestId"),
            "allowUnknownDiskEstimate": bool(request.get("allowUnknownDiskEstimate", False)),
            "createdAt": datetime.now(UTC).isoformat(),
            "workspaceId": self._workspace(),
        }
        self._save_registration(image, receipt)
        return self._public(image)

    def _save_registration(self, image: dict[str, Any], receipt: dict[str, Any] | None) -> None:
        if receipt is None:
            self.resources.save("image", image)
        elif callable(writer := getattr(self.resources, "save_many", None)):
            writer([("image", image), ("image_pull_receipt", receipt)])
        else:
            # In-memory test stores expose only save; production repository commits both rows together.
            self.resources.save("image", image)
            self.resources.save("image_pull_receipt", receipt)

    @staticmethod
    def _pull_receipt(workspace: str | None, request_id: str, reference: str, image_id: str, *, allow_unknown_disk_estimate: bool = False) -> dict[str, Any]:
        receipt: dict[str, Any] = {
            "id": str(uuid5(NAMESPACE_URL, f"{workspace}/android-image-pull/{request_id}")),
            "workspaceId": workspace,
            "requestId": request_id,
            "reference": reference,
            "imageId": image_id,
            "createdAt": datetime.now(UTC).isoformat(),
        }
        if allow_unknown_disk_estimate:
            receipt["allowUnknownDiskEstimate"] = True
        return receipt

    async def register(self, request: dict[str, Any]) -> dict[str, Any]:
        image_id = request["id"]
        if not _IMAGE_ID.fullmatch(image_id):
            raise AndroidError("ANDROID_IMAGE_ID_INVALID", "镜像摘要格式无效", 422)
        reference = str(request.get("reference", ""))
        if not _REFERENCE.fullmatch(reference):
            raise AndroidError("ANDROID_IMAGE_REFERENCE_INVALID", "镜像引用格式无效", 422)
        with self._runtime_lock():
            metadata = await self._inspect_reference(reference)
            if metadata["imageId"] != image_id:
                raise AndroidError(
                    "ANDROID_IMAGE_METADATA_MISMATCH",
                    "服务端核实的镜像摘要与请求不一致",
                    409,
                )
            return self._persist_registered(request, metadata)

    async def pull(self, request_id: str, reference: str, *, allow_unknown_disk_estimate: bool = False) -> dict[str, Any]:
        if self.catalog is None:
            raise AndroidError("ANDROID_IMAGE_PULL_UNAVAILABLE", "镜像拉取适配器尚未配置", 503)
        with self._runtime_lock():
            workspace = self._workspace()
            receipt = next((item for item in self.resources.list("image_pull_receipt") if item.get("requestId") == request_id and item.get("workspaceId") == workspace), None)
            if receipt is not None:
                if receipt["reference"] != reference or bool(receipt.get("allowUnknownDiskEstimate", False)) != allow_unknown_disk_estimate:
                    raise AndroidError("ANDROID_REQUEST_CONFLICT", "请求编号已用于其他镜像拉取", 409)
                image = next((item for item in self.list() if item["imageId"] == receipt["imageId"]), None)
                if image is None:
                    raise AndroidError("ANDROID_IMAGE_PULL_RESULT_UNKNOWN", "拉取回执对应的镜像目录不存在", 503)
                return self._public(image)
            existing = next((item for item in self.list() if item.get("requestId") == request_id), None)
            if existing is not None:
                if existing.get("reference") != reference or bool(existing.get("allowUnknownDiskEstimate", False)) != allow_unknown_disk_estimate:
                    raise AndroidError("ANDROID_REQUEST_CONFLICT", "请求编号已用于其他镜像拉取", 409)
                self.resources.save("image_pull_receipt", self._pull_receipt(workspace, request_id, reference, existing["imageId"], allow_unknown_disk_estimate=allow_unknown_disk_estimate))
                return self._public(existing)
            metadata = await (self.catalog.pull(reference, allow_unknown_disk_estimate=allow_unknown_disk_estimate) if hasattr(self.catalog, "pull") else self.catalog.inspect(reference))
            metadata = self._normalise_metadata(metadata)
            self._validate_metadata(metadata)
            receipt = self._pull_receipt(workspace, request_id, reference, metadata["imageId"], allow_unknown_disk_estimate=allow_unknown_disk_estimate)
            image = self._persist_registered({
                "id": metadata["imageId"],
                "name": reference,
                "reference": reference,
                "requestId": request_id,
                "allowUnknownDiskEstimate": allow_unknown_disk_estimate,
                "sourceDigest": metadata["sourceDigest"],
                "architecture": metadata["architecture"],
                "os": metadata["os"],
                "androidVersion": metadata["androidVersion"],
                "googleComponents": metadata["googleComponents"],
            }, metadata, receipt)
            return image

    async def verify_pull(self, request_id: str, reference: str, on_verified: Callable[[], Any] | None = None) -> Any:
        with self._runtime_lock():
            receipt = next((item for item in self.resources.list("image_pull_receipt") if item.get("requestId") == request_id and item.get("workspaceId") == self._workspace() and item.get("reference") == reference), None)
            if receipt is None:
                legacy = next((item for item in self.list() if item.get("requestId") == request_id and item.get("reference") == reference and item.get("state") not in {"deleted", "unregistered"}), None)
                if legacy is None:
                    return False
                receipt = self._pull_receipt(self._workspace(), request_id, reference, legacy["imageId"])
            image = next((item for item in self.list() if item.get("imageId") == receipt["imageId"] and item.get("state") not in {"deleted", "unregistered"}), None)
            if image is None:
                return False
            runtime = getattr(self.devices, "runtime", None)
            inspector = getattr(runtime, "inspect_image", None)
            observed = await (inspector(receipt["imageId"]) if callable(inspector) else self.catalog.inspect(reference))
            metadata = self._normalise_metadata(observed)
            verified = metadata["imageId"] == receipt["imageId"] and metadata["architecture"] == "arm64" and metadata["os"] == "linux"
            if verified and not any(item.get("id") == receipt["id"] for item in self.resources.list("image_pull_receipt")):
                self.resources.save("image_pull_receipt", receipt)
            return on_verified() if verified and on_verified is not None else verified

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
        runtime_workspace = getattr(getattr(self.devices, "runtime", None), "workspace", None)
        backup_workspace = str(runtime_workspace.resolve()) if runtime_workspace is not None else workspace
        refs = [
            device.get("deviceId")
            for device in self.devices.list()
            if not device.get("deleted")
            and device.get("imageId") == image_id
            and (workspace is None or device.get("workspaceId") in {None, workspace})
        ]
        refs.extend(item.get("id") for item in self.resources.list("profile") if not item.get("archived") and item.get("imageId") == image_id and (workspace is None or item.get("workspaceId") in {None, workspace}))
        refs.extend(item.get("id") for item in self.resources.list("backup") if item.get("imageId") == image_id and (backup_workspace is None or item.get("workspaceId") in {None, backup_workspace}))
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

    async def _server_probe(self, image: dict[str, Any]) -> dict[str, Any]:
        runtime = getattr(self.devices, "runtime", None)
        inspector = getattr(self.catalog, "inspect", None)
        reference = image.get("reference")
        if not callable(inspector):
            inspector = getattr(runtime, "inspect_image", None)
            reference = image["imageId"]
        if not callable(inspector):
            raise AndroidError("ANDROID_IMAGE_VERIFICATION_UNAVAILABLE", "运行时尚未提供镜像核实适配器", 503)
        metadata = await inspector(reference)
        return {
            "imageId": self._metadata_value(metadata, "imageId", "image_id"),
            "sourceDigest": self._metadata_value(metadata, "sourceDigest", "source_digest"),
            "architecture": self._metadata_value(metadata, "architecture"),
            "os": self._metadata_value(metadata, "os"),
            "androidVersion": self._metadata_value(metadata, "androidVersion", "android_version"),
            "googleComponents": self._metadata_value(metadata, "googleComponents", "google_components", default="unknown"),
        }

    async def verify_server(self, identifier: str, observation: dict[str, Any]) -> dict[str, Any]:
        """Record verification only from a runtime/catalog probe.

        The client observation remains a check label and explanation.  Its result
        is deliberately ignored so a caller cannot manufacture a passed image.
        """
        with self._runtime_lock():
            image = self.resources.get("image", identifier)
            if image.get("state") not in {"registered", "verified"}:
                raise AndroidError("ANDROID_IMAGE_STATE_CONFLICT", "镜像未登记或删除结果待核实，请先处理原操作", 409)
            check = str(observation.get("check", ""))
            evidence: dict[str, Any] = {"source": "server", "reference": image.get("reference")}
            if check not in {"image_metadata", "runtime_image"}:
                result = "blocked"
                evidence["code"] = "ANDROID_IMAGE_CHECK_UNSUPPORTED"
            else:
                try:
                    observed = await self._server_probe(image)
                except AndroidError as error:
                    result = "failed" if error.status == 404 or error.code in {"ANDROID_IMAGE_UNTRUSTED", "ANDROID_IMAGE_ID_INVALID"} else "blocked"
                    evidence.update(code=error.code, message=error.message[:240])
                except (TimeoutError, OSError) as error:
                    result = "blocked"
                    evidence.update(code="ANDROID_IMAGE_VERIFICATION_UNKNOWN", message=str(error)[:240])
                else:
                    evidence.update({key: value for key, value in observed.items() if value is not None})
                    required = (observed.get("imageId"), observed.get("architecture"), observed.get("os"))
                    source_known = bool(observed.get("sourceDigest")) or str(image.get("reference", "")).startswith("local:")
                    if not source_known:
                        result = "blocked"
                        evidence["code"] = "ANDROID_IMAGE_SOURCE_UNKNOWN"
                    elif required[0] != image.get("imageId") or required[1] not in {"arm64", "aarch64"} or required[2] != "linux":
                        result = "failed"
                        evidence["code"] = "ANDROID_IMAGE_METADATA_MISMATCH"
                    else:
                        result = "passed"
            verification = deepcopy(image.get("verification") or {"state": "not_tested", "records": []})
            records = list(verification.get("records") or [])
            records.append({"check": check, "result": result, "source": "server", "evidence": evidence, "recordedAt": datetime.now(UTC).isoformat()})
            verification["records"] = records
            results = {record.get("result") for record in records if record.get("check") in {"image_metadata", "runtime_image"}}
            verification["state"] = "failed" if "failed" in results else "blocked" if "blocked" in results else "passed" if results and results == {"passed"} else "not_tested"
            image["verification"] = verification
            image["validation"] = summarize_verification([
                {"checkId": record["check"], "status": record["result"]}
                for record in records if record.get("check") in REQUIRED_CHECKS
            ]).status
            image["state"] = "verified" if verification["state"] == "passed" else "registered"
            self.resources.save("image", image)
            return self._public(image)

    async def verify_delete_content(self, identifier: str, request_id: str) -> dict[str, Any]:
        """Reconcile an interrupted image deletion without issuing another delete."""
        with self._runtime_lock() as runtime:
            image = self.resources.get("image", identifier)
            if image.get("deleteRequestId") != request_id:
                raise AndroidError("ANDROID_REQUEST_CONFLICT", "核实请求编号与镜像删除请求不一致", 409)
            if image.get("state") == "deleted":
                return self._public(image)
            inspector = getattr(runtime, "inspect_image", None)
            reference = image["imageId"]
            catalog_probe = False
            if not callable(inspector):
                inspector = getattr(self.catalog, "inspect", None)
                reference = image.get("reference")
                catalog_probe = True
            if not callable(inspector):
                raise AndroidError("ANDROID_IMAGE_VERIFICATION_UNAVAILABLE", "运行时尚未提供镜像核实适配器", 503)
            try:
                observed = await inspector(reference)
            except AndroidError as error:
                if error.status != 404:
                    raise AndroidError("ANDROID_IMAGE_DELETE_RESULT_UNKNOWN", "镜像内容删除结果仍未知，请稍后核实", 503) from error
                result = deepcopy(image)
                result.update(state="deleted", revision=int(image.get("revision", 0)) + 1, deletedAt=datetime.now(UTC).isoformat())
                self.resources.save("image", result)
                return self._public(result)
            except (TimeoutError, OSError) as error:
                raise AndroidError("ANDROID_IMAGE_DELETE_RESULT_UNKNOWN", "镜像内容删除结果仍未知，请稍后核实", 503) from error
            if catalog_probe:
                observed_id = observed.get("imageId", observed.get("image_id")) if isinstance(observed, dict) else getattr(observed, "image_id", None)
                if observed_id != image.get("imageId"):
                    result = deepcopy(image)
                    result.update(state="deleted", revision=int(image.get("revision", 0)) + 1, deletedAt=datetime.now(UTC).isoformat())
                    self.resources.save("image", result)
                    return self._public(result)
            pending = deepcopy(image)
            pending["state"] = "delete_blocked"
            pending["deleteVerifiedAt"] = datetime.now(UTC).isoformat()
            self.resources.save("image", pending)
            return self._public(pending)

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
