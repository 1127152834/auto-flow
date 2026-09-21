from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Query, Response
from pydantic import ConfigDict, Field

from autoflow.adapters.http.schemas import ApiModel
from autoflow.application.workflows.local_files import LocalWorkflowFiles
from autoflow.application.workflows.webdav import WebDavWorkflowService


class FolderRequest(ApiModel):
    folder: str | None = None


class LocalWorkflowSave(FolderRequest):
    model_config = ConfigDict(alias_generator=None, populate_by_name=True, extra="forbid")

    filename: str = Field(min_length=1, max_length=255)
    content: dict[str, Any]


class LocalWorkflowExists(FolderRequest):
    filename: str = Field(min_length=1, max_length=255)


class ActiveFolder(ApiModel):
    folder: str


class SelfHealWrite(LocalWorkflowExists):
    enabled: bool


class WebDavConfig(ApiModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    enabled: bool = False
    url: str = ""
    username: str = ""
    password: str = ""
    remote_dir: str = Field(default="", alias="remoteDir")


def local_workflows_router(
    service: LocalWorkflowFiles, webdav: WebDavWorkflowService
) -> APIRouter:
    router = APIRouter(prefix="/api/local-workflows", tags=["studio-local-workflows"])

    @router.get("/default-folder")
    def default_folder() -> dict[str, Any]:
        return {"success": True, "folder": str(service.default_folder)}

    @router.get("/active-folder")
    def active_folder() -> dict[str, Any]:
        return {
            "success": True,
            "folder": str(service.active_folder()),
            "default": str(service.default_folder),
        }

    @router.post("/active-folder")
    def set_active_folder(request: ActiveFolder) -> dict[str, Any]:
        return {"success": True, "folder": str(service.set_active_folder(request.folder))}

    @router.get("/webdav-config")
    def get_webdav_config() -> dict[str, Any]:
        return {"success": True, "config": webdav.config()}

    @router.post("/webdav-config")
    def save_webdav_config(request: WebDavConfig) -> dict[str, Any]:
        config = webdav.save_config(request.model_dump(by_alias=True))
        return {"success": True, "config": config}

    @router.post("/webdav-test")
    def test_webdav(request: WebDavConfig) -> dict[str, bool]:
        return webdav.test(request.model_dump(by_alias=True))

    @router.post("/list")
    def list_workflows(request: FolderRequest) -> dict[str, Any]:
        return {"workflows": service.list(request.folder)}

    @router.post("/check-exists")
    def check_exists(request: LocalWorkflowExists) -> dict[str, Any]:
        exists, filename = service.exists(request.filename, request.folder)
        return {"exists": exists, "filename": filename}

    @router.post("/save-to-folder")
    @router.post("/import")
    def save_workflow(request: LocalWorkflowSave) -> dict[str, Any]:
        filename = service.save(request.filename, request.content, request.folder)
        return {"success": True, "filename": filename}

    @router.get("/load/{filename}")
    def load_workflow(filename: str, folder: str | None = None) -> dict[str, Any]:
        return {"success": True, "content": service.load(filename, folder)}

    @router.post("/delete")
    def delete_workflow_query(
        filename: str = Query(min_length=1, max_length=255),
        folder: str | None = None,
    ) -> dict[str, bool]:
        service.delete(filename, folder)
        return {"success": True}

    @router.post("/open-folder")
    def open_folder(request: FolderRequest) -> dict[str, Any]:
        return {"success": True, "folder": str(service.resolve_folder(request.folder))}

    @router.get("/self-heal/{filename}")
    def get_self_heal(filename: str, folder: str | None = None) -> dict[str, Any]:
        value = service.self_heal(filename, folder)
        return {
            "success": True,
            "enabled": value.get("enabled") is True,
            "selfHeal": value,
        }

    @router.post("/self-heal")
    def set_self_heal(request: SelfHealWrite) -> dict[str, Any]:
        value = service.self_heal(
            request.filename, request.folder, enabled=request.enabled
        )
        return {"success": True, "enabled": value["enabled"], "selfHeal": value}

    @router.get("/{filename}/export")
    def export_workflow(filename: str, folder: str | None = None) -> Response:
        content = json.dumps(service.load(filename, folder), ensure_ascii=False).encode()
        return Response(
            content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.delete("/{filename}")
    def delete_workflow(filename: str, folder: str | None = None) -> dict[str, bool]:
        service.delete(filename, folder)
        return {"success": True}

    return router
