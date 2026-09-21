from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import FileResponse

from autoflow.adapters.http.schemas import ApiModel
from autoflow.adapters.http.workflow_studio_schemas import (
    StudioImageAsset,
    StudioImageFolderCreated,
    StudioImageFolderDeleted,
    StudioImageFolderRenamed,
    StudioImageMoved,
    StudioImageMutationResult,
    StudioImageRenameResult,
    StudioImageUploadResult,
)
from autoflow.application.workflows.image_assets import ImageAssetStore


class FolderCreate(ApiModel):
    name: str
    parent_path: str = ""


class FolderRename(ApiModel):
    old_path: str
    new_name: str


class FolderDelete(ApiModel):
    folder_path: str


class AssetMove(ApiModel):
    asset_id: str
    target_folder: str = ""


def image_assets_router(service: ImageAssetStore) -> APIRouter:
    router = APIRouter(prefix="/api/image-assets", tags=["studio-image-assets"])

    @router.get("", response_model=list[StudioImageAsset])
    def list_assets() -> list[dict[str, Any]]:
        return service.list_assets()

    @router.get("/folders", response_model=list[str])
    def list_folders() -> list[str]:
        return service.folders()

    @router.post("/folders", response_model=StudioImageFolderCreated)
    def create_folder(request: FolderCreate) -> dict[str, Any]:
        return {
            "success": True,
            "path": service.create_folder(request.name, request.parent_path),
        }

    @router.put("/folders/rename", response_model=StudioImageFolderRenamed)
    def rename_folder(request: FolderRename) -> dict[str, Any]:
        return {
            "success": True,
            "newPath": service.rename_folder(request.old_path, request.new_name),
        }

    @router.delete("/folders", response_model=StudioImageFolderDeleted)
    def delete_folder(request: FolderDelete) -> dict[str, Any]:
        return {
            "success": True,
            "deletedCount": service.delete_folder(request.folder_path),
        }

    @router.post("/upload", response_model=StudioImageUploadResult)
    async def upload_asset(
        file: Annotated[UploadFile, File()], folder: Annotated[str, Form()] = ""
    ) -> dict[str, Any]:
        content = await file.read()
        return {
            "asset": service.upload(
                file.filename or "", content, folder, file.content_type or ""
            )
        }

    @router.put("/move", response_model=StudioImageMoved)
    def move_asset(request: AssetMove) -> dict[str, Any]:
        return {
            "success": True,
            "newFolder": service.move(request.asset_id, request.target_folder),
        }

    @router.get("/{asset_id}/thumbnail")
    @router.get("/{asset_id}/file")
    def read_asset(asset_id: str) -> FileResponse:
        path, content_type = service.file(asset_id)
        return FileResponse(path, media_type=content_type)

    @router.put("/{asset_id}/rename", response_model=StudioImageRenameResult)
    def rename_asset(
        asset_id: str, new_name: str = Query(alias="newName")
    ) -> dict[str, Any]:
        return {"success": True, "asset": service.rename(asset_id, new_name)}

    @router.get("/{asset_id}", response_model=StudioImageAsset)
    def get_asset(asset_id: str) -> dict[str, Any]:
        return service.get(asset_id)

    @router.delete("/{asset_id}", response_model=StudioImageMutationResult)
    def delete_asset(asset_id: str) -> dict[str, bool]:
        service.delete(asset_id)
        return {"success": True}

    return router
