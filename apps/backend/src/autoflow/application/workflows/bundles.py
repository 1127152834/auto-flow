from __future__ import annotations

import base64
import binascii
import copy
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from autoflow.application.workflows.image_assets import ImageAssetStore
from autoflow.application.workflows.modules import CustomModuleService
from autoflow.domain.workflows.models import WorkflowError
from autoflow.domain.workflows.modules import custom_module_reference


class WorkflowBundleService:
    def __init__(
        self, modules: CustomModuleService, images: ImageAssetStore
    ) -> None:
        self._modules = modules
        self._images = images

    def export(self, name: str, workflow: Mapping[str, Any]) -> dict[str, Any]:
        document = self._workflow(workflow)
        closure = self._modules.freeze_closure(self._dependencies(document))
        serialized = json.dumps([document, *closure.values()], ensure_ascii=False)
        images = []
        for asset in self._images.list_assets():
            if str(asset["id"]) not in serialized:
                continue
            path, content_type = self._images.file(str(asset["id"]))
            images.append(
                {
                    "id": asset["id"],
                    "name": asset["name"],
                    "originalName": asset["originalName"],
                    "folder": asset["folder"],
                    "ext": asset["extension"],
                    "contentType": content_type,
                    "dataB64": base64.b64encode(path.read_bytes()).decode("ascii"),
                }
            )
        return {
            "type": "webrpa-workflow-bundle",
            "version": 1,
            "name": name.strip() or "未命名流程",
            "exportedAt": datetime.now(UTC).isoformat(),
            "workflow": document,
            "customModules": list(closure.values()),
            "images": images,
        }

    def import_bundle(self, raw: object) -> dict[str, Any]:
        if not isinstance(raw, Mapping) or raw.get("type") != "webrpa-workflow-bundle":
            raise WorkflowError("WORKFLOW_BUNDLE_INVALID", "工作流整包格式无效", 422)
        if raw.get("version") != 1:
            raise WorkflowError("WORKFLOW_BUNDLE_VERSION_UNSUPPORTED", "不支持该整包版本", 422)
        workflow = self._workflow(raw.get("workflow"))
        modules = raw.get("customModules", [])
        images = raw.get("images", [])
        if not isinstance(modules, list) or not all(isinstance(item, Mapping) for item in modules):
            raise WorkflowError("WORKFLOW_BUNDLE_INVALID", "整包模块列表无效", 422)
        if not isinstance(images, list) or not all(isinstance(item, Mapping) for item in images):
            raise WorkflowError("WORKFLOW_BUNDLE_INVALID", "整包图片列表无效", 422)

        mapping: dict[str, str] = {}
        pending = {str(item.get("id") or ""): dict(item) for item in modules}
        if "" in pending or len(pending) != len(modules):
            raise WorkflowError("WORKFLOW_BUNDLE_INVALID", "整包模块标识无效", 422)
        restored_modules = 0
        while pending:
            progressed = False
            for old_id, module in list(pending.items()):
                if self._modules.exists(old_id):
                    mapping[old_id] = old_id
                    del pending[old_id]
                    progressed = True
                    continue
                module_workflow = self._workflow(module.get("workflow"))
                dependencies = self._dependencies(module_workflow)
                missing = [
                    dependency
                    for dependency in dependencies
                    if dependency not in mapping
                    and dependency not in pending
                    and not self._modules.exists(dependency)
                ]
                if missing:
                    raise WorkflowError(
                        "WORKFLOW_BUNDLE_DEPENDENCY_MISSING",
                        f"自定义模块依赖不存在: {missing[0]}",
                        422,
                    )
                if any(
                    dependency in pending and dependency not in mapping
                    for dependency in dependencies
                ):
                    continue
                module["workflow"] = self._remap(module_workflow, mapping)
                module.pop("dependencyIds", None)
                module.pop("snapshotDigest", None)
                saved = self._modules.import_module(
                    module,
                    client_request_id=f"bundle:{self._digest(raw)}:{old_id}",
                )
                mapping[old_id] = saved.id
                del pending[old_id]
                restored_modules += 1
                progressed = True
            if not progressed:
                raise WorkflowError(
                    "WORKFLOW_BUNDLE_DEPENDENCY_CYCLE",
                    "整包中的自定义模块存在循环依赖",
                    422,
                )

        restored_images = 0
        for image in images:
            restored_images += int(self._restore_image(image))
        return {
            "success": True,
            "name": str(raw.get("name") or "未命名流程"),
            "workflow": self._remap(workflow, mapping),
            "restored": {
                "customModules": restored_modules,
                "images": restored_images,
            },
        }

    def _restore_image(self, image: Mapping[str, Any]) -> bool:
        try:
            content = base64.b64decode(str(image.get("dataB64") or ""), validate=True)
        except (binascii.Error, ValueError) as error:
            raise WorkflowError(
                "WORKFLOW_BUNDLE_IMAGE_INVALID", "整包图片内容损坏", 422
            ) from error
        return self._images.restore(
            asset_id=str(image.get("id") or ""),
            name=str(image.get("name") or ""),
            original_name=str(image.get("originalName") or image.get("name") or ""),
            folder=str(image.get("folder") or ""),
            content=content,
            content_type=str(image.get("contentType") or ""),
        )

    @staticmethod
    def _workflow(value: object) -> dict[str, Any]:
        if not isinstance(value, Mapping) or not isinstance(value.get("nodes"), list):
            raise WorkflowError("WORKFLOW_BUNDLE_INVALID", "整包工作流格式无效", 422)
        return copy.deepcopy(dict(value))

    @staticmethod
    def _dependencies(workflow: Mapping[str, Any]) -> tuple[str, ...]:
        result: list[str] = []
        for node in workflow.get("nodes", []):
            if not isinstance(node, Mapping):
                continue
            module_id = custom_module_reference(node)
            if module_id and module_id not in result:
                result.append(module_id)
        return tuple(result)

    @staticmethod
    def _remap(workflow: Mapping[str, Any], mapping: Mapping[str, str]) -> dict[str, Any]:
        result = copy.deepcopy(dict(workflow))
        for node in result.get("nodes", []):
            if not isinstance(node, dict):
                continue
            data = node.get("data")
            config = data.get("config") if isinstance(data, dict) else None
            for container in (node, data, config):
                if not isinstance(container, dict):
                    continue
                for key in ("customModuleId", "custom_module_id"):
                    value = container.get(key)
                    if isinstance(value, str) and value in mapping:
                        container[key] = mapping[value]
        return result

    @staticmethod
    def _digest(value: object) -> str:
        import hashlib

        return hashlib.sha256(
            json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()
        ).hexdigest()[:24]
