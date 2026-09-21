from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from autoflow.domain.workflows.models import WorkflowError

from .webdav import WebDavWorkflowService


class LocalWorkflowFiles:
    def __init__(
        self,
        workspace: Path,
        remote: WebDavWorkflowService | None = None,
        ensure_unreferenced: Callable[[str], None] | None = None,
    ) -> None:
        self._default = (workspace / "local-workflows").resolve()
        self._settings = workspace / "local-workflows.json"
        self._remote = remote
        self._ensure_unreferenced = ensure_unreferenced
        self._lock = RLock()

    @property
    def default_folder(self) -> Path | str:
        return "WebDAV" if self._active_remote() else self._default

    def active_folder(self) -> Path:
        try:
            value = json.loads(self._settings.read_text("utf-8")).get("activeFolder")
        except (FileNotFoundError, OSError, ValueError, AttributeError):
            value = None
        return self._folder(value)

    def set_active_folder(self, value: str) -> Path:
        folder = self._default if not value.strip() else self._absolute_folder(value)
        folder.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._write_json(self._settings, {"activeFolder": str(folder)})
        return folder

    def list(self, folder: str | None = None) -> list[dict[str, Any]]:
        if remote := self._active_remote():
            return remote.list_workflows()
        root = self._folder(folder)
        root.mkdir(parents=True, exist_ok=True)
        rows: list[dict[str, Any]] = []
        for path in root.glob("*.json"):
            try:
                content = self._read(path)
                stat = path.stat()
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                continue
            rows.append(
                {
                    "filename": path.name,
                    "name": str(content.get("name") or path.stem),
                    "modifiedTime": datetime.fromtimestamp(
                        stat.st_mtime, UTC
                    ).isoformat(),
                    "size": stat.st_size,
                }
            )
        return sorted(rows, key=lambda row: row["modifiedTime"], reverse=True)

    def save(
        self, filename: str, content: dict[str, Any], folder: str | None = None
    ) -> str:
        if not isinstance(content.get("nodes"), list):
            raise WorkflowError(
                "LOCAL_WORKFLOW_INVALID",
                "工作流缺少 nodes",
                422,
                details={"path": ["content", "nodes"]},
            )
        if remote := self._active_remote():
            return remote.save(filename, content)
        path = self._path(filename, folder)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            if "selfHeal" not in content and path.exists():
                existing = self._read(path)
                if "selfHeal" in existing:
                    content = {**content, "selfHeal": existing["selfHeal"]}
            self._write_json(path, content)
        return path.name

    def load(self, filename: str, folder: str | None = None) -> dict[str, Any]:
        if remote := self._active_remote():
            value = remote.read(filename)
            if value is None:
                raise self._not_found(filename)
            return value
        path = self._existing_path(filename, folder)
        try:
            return self._read(path)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise WorkflowError(
                "LOCAL_WORKFLOW_INVALID", "工作流文件格式无效", 422
            ) from error

    def exists(self, filename: str, folder: str | None = None) -> tuple[bool, str]:
        if remote := self._active_remote():
            value = filename if filename.lower().endswith(".json") else f"{filename}.json"
            return remote.exists(value), value
        path = self._path(filename, folder)
        return path.is_file(), path.name

    def delete(self, filename: str, folder: str | None = None) -> None:
        if self._ensure_unreferenced is not None:
            self._ensure_unreferenced(filename)
        if remote := self._active_remote():
            remote.delete(filename)
            return
        path = self._existing_path(filename, folder)
        with self._lock:
            try:
                path.unlink()
            except FileNotFoundError as error:
                raise self._not_found(filename) from error

    def self_heal(
        self,
        filename: str,
        folder: str | None = None,
        *,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        if remote := self._active_remote():
            content = self.load(filename, folder)
            value = dict(content.get("selfHeal") or {})
            if enabled is not None:
                value["enabled"] = enabled
                remote.save(filename, {**content, "selfHeal": value})
            return value
        path = self._existing_path(filename, folder)
        with self._lock:
            content = self._read(path)
            value = dict(content.get("selfHeal") or {})
            if enabled is not None:
                value["enabled"] = enabled
                self._write_json(path, {**content, "selfHeal": value})
        return value

    def resolve_folder(self, folder: str | None = None) -> Path:
        if self._active_remote():
            raise WorkflowError(
                "WEB_DAV_FOLDER_REMOTE",
                "当前工作流存储在 WebDAV 远程目录，无法打开本地文件夹",
                409,
            )
        root = self._folder(folder)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _active_remote(self) -> WebDavWorkflowService | None:
        return self._remote if self._remote is not None and self._remote.enabled() else None

    def _folder(self, value: str | None) -> Path:
        if value is None or not value.strip():
            if self._settings.exists():
                try:
                    active = json.loads(self._settings.read_text("utf-8")).get(
                        "activeFolder"
                    )
                except (OSError, ValueError, AttributeError):
                    active = None
                if isinstance(active, str) and active.strip():
                    return self._absolute_folder(active)
            return self._default
        return self._absolute_folder(value)

    @staticmethod
    def _absolute_folder(value: str) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise WorkflowError(
                "LOCAL_WORKFLOW_FOLDER_INVALID", "工作流目录必须是绝对路径", 422
            )
        return path.resolve()

    def _path(self, filename: str, folder: str | None) -> Path:
        value = filename.strip()
        if (
            not value
            or value in {".", ".."}
            or Path(value).name != value
            or "\\" in value
        ):
            raise WorkflowError(
                "LOCAL_WORKFLOW_FILENAME_INVALID", "工作流文件名无效", 422
            )
        if not value.lower().endswith(".json"):
            value += ".json"
        return self._folder(folder) / value

    def _existing_path(self, filename: str, folder: str | None) -> Path:
        path = self._path(filename, folder)
        if not path.is_file():
            raise self._not_found(filename)
        return path

    @staticmethod
    def _not_found(filename: str) -> WorkflowError:
        return WorkflowError(
            "LOCAL_WORKFLOW_NOT_FOUND",
            "工作流不存在",
            404,
            details={"filename": filename},
        )

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text("utf-8"))
        if not isinstance(value, dict):
            raise TypeError("workflow must be an object")
        return value

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except BaseException:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
