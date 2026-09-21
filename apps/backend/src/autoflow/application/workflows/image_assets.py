from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from autoflow.domain.workflows.models import WorkflowError

_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "webp", "svg", "ico"}


class ImageAssetStore:
    def __init__(self, workspace: Path) -> None:
        self._root = workspace / "image-assets"
        self._files = self._root / "files"
        self._index = self._root / "index.json"
        self._lock = RLock()

    def list_assets(self) -> list[dict[str, Any]]:
        return list(self._load()["assets"])

    def folders(self) -> list[str]:
        return list(self._load()["folders"])

    def get(self, asset_id: str) -> dict[str, Any]:
        for asset in self._load()["assets"]:
            if asset["id"] == asset_id:
                return dict(asset)
        raise self._missing(asset_id)

    def upload(
        self, name: str, content: bytes, folder: str = "", content_type: str = ""
    ) -> dict[str, Any]:
        extension = self._extension(name)
        folder = self._folder(folder)
        with self._lock:
            state = self._load()
            self._assert_unique(state, name, folder)
            self._add_folder_tree(state, folder)
            asset_id = str(uuid4())
            path = self._files / f"{asset_id}.{extension}"
            self._write_bytes(path, content)
            asset = {
                "id": asset_id,
                "name": name,
                "originalName": name,
                "size": len(content),
                "uploadedAt": datetime.now(UTC).isoformat(),
                "folder": folder,
                "extension": extension,
                "path": str(path.resolve()),
                "contentType": content_type,
            }
            state["assets"].append(asset)
            try:
                self._save(state)
            except BaseException:
                path.unlink(missing_ok=True)
                raise
            return dict(asset)

    def restore(
        self,
        *,
        asset_id: str,
        name: str,
        original_name: str,
        folder: str,
        content: bytes,
        content_type: str = "",
    ) -> bool:
        if not asset_id.strip() or "/" in asset_id or "\\" in asset_id:
            raise WorkflowError("IMAGE_ASSET_ID_INVALID", "图像资源标识无效", 422)
        extension = self._extension(name)
        folder = self._folder(folder)
        with self._lock:
            state = self._load()
            if any(asset["id"] == asset_id for asset in state["assets"]):
                return False
            self._assert_unique(state, name, folder)
            self._add_folder_tree(state, folder)
            path = self._files / f"{asset_id}.{extension}"
            self._write_bytes(path, content)
            state["assets"].append(
                {
                    "id": asset_id,
                    "name": name,
                    "originalName": self._name(original_name),
                    "size": len(content),
                    "uploadedAt": datetime.now(UTC).isoformat(),
                    "folder": folder,
                    "extension": extension,
                    "path": str(path.resolve()),
                    "contentType": content_type,
                }
            )
            try:
                self._save(state)
            except BaseException:
                path.unlink(missing_ok=True)
                raise
        return True

    def file(self, asset_id: str) -> tuple[Path, str]:
        asset = self.get(asset_id)
        path = self._stored_path(asset)
        if not path.is_file():
            raise WorkflowError(
                "IMAGE_ASSET_FILE_MISSING", "图像资源文件不存在", 404
            )
        return path, str(asset.get("contentType") or "application/octet-stream")

    def delete(self, asset_id: str) -> None:
        with self._lock:
            state = self._load()
            asset = self._pop_asset(state, asset_id)
            self._save(state)
            try:
                self._stored_path(asset).unlink(missing_ok=True)
            except OSError:
                state["assets"].append(asset)
                self._save(state)
                raise

    def rename(self, asset_id: str, new_name: str) -> dict[str, Any]:
        self._extension(new_name)
        self._name(new_name)
        with self._lock:
            state = self._load()
            asset = self._find(state, asset_id)
            self._assert_unique(state, new_name, str(asset["folder"]), asset_id)
            asset["name"] = new_name
            self._save(state)
            return dict(asset)

    def move(self, asset_id: str, target_folder: str = "") -> str:
        target_folder = self._folder(target_folder)
        with self._lock:
            state = self._load()
            asset = self._find(state, asset_id)
            self._assert_unique(state, str(asset["name"]), target_folder, asset_id)
            self._add_folder_tree(state, target_folder)
            asset["folder"] = target_folder
            self._save(state)
        return target_folder

    def create_folder(self, name: str, parent: str = "") -> str:
        name = self._name(name)
        parent = self._folder(parent)
        folder = f"{parent}/{name}" if parent else name
        with self._lock:
            state = self._load()
            if folder in state["folders"]:
                raise WorkflowError(
                    "IMAGE_ASSET_FOLDER_EXISTS", "文件夹已存在", 409
                )
            self._add_folder_tree(state, folder)
            self._save(state)
        return folder

    def rename_folder(self, old_path: str, new_name: str) -> str:
        old_path = self._folder(old_path)
        if not old_path:
            raise WorkflowError("IMAGE_ASSET_FOLDER_INVALID", "不能重命名根目录", 422)
        new_name = self._name(new_name)
        parent = old_path.rpartition("/")[0]
        new_path = f"{parent}/{new_name}" if parent else new_name
        with self._lock:
            state = self._load()
            if old_path not in state["folders"]:
                raise WorkflowError(
                    "IMAGE_ASSET_FOLDER_NOT_FOUND", "文件夹不存在", 404
                )
            if new_path in state["folders"]:
                raise WorkflowError(
                    "IMAGE_ASSET_FOLDER_EXISTS", "目标文件夹已存在", 409
                )

            def renamed(value: str) -> str:
                return (
                    new_path + value[len(old_path) :]
                    if value == old_path or value.startswith(f"{old_path}/")
                    else value
                )

            state["folders"] = sorted(renamed(value) for value in state["folders"])
            for asset in state["assets"]:
                asset["folder"] = renamed(str(asset["folder"]))
            self._save(state)
        return new_path

    def delete_folder(self, folder: str) -> int:
        folder = self._folder(folder)
        if not folder:
            raise WorkflowError("IMAGE_ASSET_FOLDER_INVALID", "不能删除根目录", 422)
        with self._lock:
            state = self._load()
            if folder not in state["folders"]:
                raise WorkflowError(
                    "IMAGE_ASSET_FOLDER_NOT_FOUND", "文件夹不存在", 404
                )
            removed = [
                asset
                for asset in state["assets"]
                if asset["folder"] == folder
                or str(asset["folder"]).startswith(f"{folder}/")
            ]
            state["assets"] = [asset for asset in state["assets"] if asset not in removed]
            state["folders"] = [
                value
                for value in state["folders"]
                if value != folder and not value.startswith(f"{folder}/")
            ]
            self._save(state)
            for asset in removed:
                self._stored_path(asset).unlink(missing_ok=True)
            return len(removed)

    def _load(self) -> dict[str, list[Any]]:
        try:
            value = json.loads(self._index.read_text("utf-8"))
        except FileNotFoundError:
            return {"assets": [], "folders": []}
        except (OSError, ValueError) as error:
            raise WorkflowError(
                "IMAGE_ASSET_INDEX_INVALID", "图像资源索引损坏", 500
            ) from error
        if (
            not isinstance(value, dict)
            or not isinstance(value.get("assets"), list)
            or not isinstance(value.get("folders"), list)
        ):
            raise WorkflowError("IMAGE_ASSET_INDEX_INVALID", "图像资源索引损坏", 500)
        return value

    def _save(self, value: dict[str, list[Any]]) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=".index.", suffix=".tmp", dir=self._root
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._index)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    @staticmethod
    def _write_bytes(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    @staticmethod
    def _name(value: str) -> str:
        value = value.strip()
        if not value or value in {".", ".."} or "/" in value or "\\" in value:
            raise WorkflowError("IMAGE_ASSET_NAME_INVALID", "文件名无效", 422)
        return value

    @classmethod
    def _extension(cls, name: str) -> str:
        name = cls._name(name)
        extension = Path(name).suffix.lower().lstrip(".")
        if extension not in _EXTENSIONS:
            raise WorkflowError(
                "IMAGE_ASSET_TYPE_INVALID", "不支持该图像文件格式", 422
            )
        return extension

    @classmethod
    def _folder(cls, value: str) -> str:
        value = value.strip().strip("/")
        if not value:
            return ""
        if "\\" in value:
            raise WorkflowError("IMAGE_ASSET_FOLDER_INVALID", "文件夹路径无效", 422)
        return "/".join(cls._name(part) for part in value.split("/"))

    @staticmethod
    def _find(state: dict[str, list[Any]], asset_id: str) -> dict[str, Any]:
        for asset in state["assets"]:
            if asset["id"] == asset_id:
                return asset
        raise ImageAssetStore._missing(asset_id)

    @staticmethod
    def _pop_asset(state: dict[str, list[Any]], asset_id: str) -> dict[str, Any]:
        asset = ImageAssetStore._find(state, asset_id)
        state["assets"].remove(asset)
        return asset

    @staticmethod
    def _missing(asset_id: str) -> WorkflowError:
        return WorkflowError(
            "IMAGE_ASSET_NOT_FOUND",
            "图像资源不存在",
            404,
            details={"assetId": asset_id},
        )

    def _stored_path(self, asset: dict[str, Any]) -> Path:
        path = Path(str(asset.get("path") or "")).resolve()
        try:
            path.relative_to(self._files.resolve())
        except ValueError as error:
            raise WorkflowError(
                "IMAGE_ASSET_INDEX_INVALID", "图像资源索引包含越界路径", 500
            ) from error
        return path

    @staticmethod
    def _assert_unique(
        state: dict[str, list[Any]], name: str, folder: str, except_id: str = ""
    ) -> None:
        if any(
            asset["id"] != except_id
            and asset["name"] == name
            and asset["folder"] == folder
            for asset in state["assets"]
        ):
            raise WorkflowError("IMAGE_ASSET_EXISTS", "同名图像资源已存在", 409)

    @staticmethod
    def _add_folder_tree(state: dict[str, list[Any]], folder: str) -> None:
        parts = folder.split("/") if folder else []
        for index in range(1, len(parts) + 1):
            value = "/".join(parts[:index])
            if value not in state["folders"]:
                state["folders"].append(value)
        state["folders"].sort()
