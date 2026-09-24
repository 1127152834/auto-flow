from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, RLock
from typing import Any

from autoflow.domain.workflows.models import WorkflowError
from autoflow.infrastructure.database.studio_retention import (
    SqlAlchemyStudioRetention,
)

DEFAULT_RETENTION: dict[str, Any] = {
    "enabled": False,
    "recordings_max_days": 30,
    "recordings_max_total_mb": 0,
    "data_max_days": 30,
    "data_max_total_mb": 0,
    "cleanup_interval_hours": 24,
}
_MAX_SAFE_INTEGER = 9_007_199_254_740_991
logger = logging.getLogger(__name__)


class StudioRetentionService:
    def __init__(
        self, repository: SqlAlchemyStudioRetention, workspace: Path
    ) -> None:
        self._repository = repository
        self._workspace = workspace.resolve()
        self._settings = self._workspace / "studio-retention.json"
        self._lock = RLock()
        self._wake = Event()
        self._stopping = False
        self._task: asyncio.Task[None] | None = None

    async def startup(self) -> None:
        if self._task is None:
            self._stopping = False
            self._task = asyncio.create_task(
                self._periodic_cleanup(), name="studio-retention"
            )

    async def shutdown(self) -> None:
        self._stopping = True
        self._wake.set()
        if self._task is not None:
            await self._task
            self._task = None

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self._settings.exists():
                return dict(DEFAULT_RETENTION)
            try:
                stored = json.loads(self._settings.read_text("utf-8"))
            except (OSError, UnicodeDecodeError, ValueError) as error:
                raise WorkflowError(
                    "RETENTION_CONFIG_INVALID", "留存策略文件无法读取", 500
                ) from error
            if not isinstance(stored, dict):
                raise WorkflowError(
                    "RETENTION_CONFIG_INVALID", "留存策略文件格式无效", 500
                )
            try:
                return self._validate({**DEFAULT_RETENTION, **stored})
            except WorkflowError as error:
                raise WorkflowError(
                    "RETENTION_CONFIG_INVALID", "留存策略文件格式无效", 500
                ) from error

    def save(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            config = self._validate({**self.load(), **updates})
            try:
                self._write_json(config)
            except OSError as error:
                raise WorkflowError(
                    "RETENTION_CONFIG_WRITE_FAILED", "留存策略无法写入", 507
                ) from error
            self._wake.set()
            return config

    def usage(self) -> dict[str, dict[str, float | int]]:
        values = self._repository.usage()
        return {
            name: {
                "count": value["count"],
                "sizeMB": round(value["bytes"] / 1024 / 1024, 2),
            }
            for name, value in values.items()
        }

    def cleanup(self) -> dict[str, Any]:
        with self._lock:
            config = self.load()
            recordings = self._select(
                self._repository.recordings(),
                days=config["recordings_max_days"],
                megabytes=config["recordings_max_total_mb"],
            )
            artifacts = self._select(
                self._repository.artifacts(),
                days=config["data_max_days"],
                megabytes=config["data_max_total_mb"],
            )
            paths = [self._artifact_path(item["relativePath"]) for item in artifacts]
            self._repository.delete_recordings([item["id"] for item in recordings])
            self._repository.delete_artifacts([item["key"] for item in artifacts])
            freed = 0
            for path in paths:
                try:
                    size = path.stat().st_size
                    path.unlink()
                except OSError as error:
                    raise WorkflowError(
                        "RETENTION_DELETE_FAILED", "运行产物文件删除失败", 507
                    ) from error
                freed += size
            return {
                "success": True,
                "recordings": self._result(recordings),
                "data": {
                    "removed": len(artifacts),
                    "freedMB": round(freed / 1024 / 1024, 2),
                },
            }

    async def _periodic_cleanup(self) -> None:
        while not self._stopping:
            try:
                config = self.load()
            except Exception:
                logger.exception("Studio retention configuration could not be loaded")
                config = dict(DEFAULT_RETENTION)
            changed = await asyncio.to_thread(
                self._wake.wait, config["cleanup_interval_hours"] * 3600
            )
            self._wake.clear()
            if self._stopping:
                return
            if changed:
                continue
            if config["enabled"]:
                try:
                    await asyncio.to_thread(self.cleanup)
                except Exception:
                    logger.exception("scheduled Studio retention cleanup failed")

    def _artifact_path(self, relative_path: Any) -> Path:
        if not isinstance(relative_path, str) or not relative_path:
            raise WorkflowError(
                "RETENTION_ARTIFACT_PATH_INVALID", "运行产物路径无效", 500
            )
        path = (self._workspace / relative_path).resolve()
        if not path.is_relative_to(self._workspace) or not path.is_file():
            raise WorkflowError(
                "RETENTION_ARTIFACT_PATH_INVALID", "运行产物路径无效或文件不存在", 500
            )
        return path

    @staticmethod
    def _select(
        entries: list[dict[str, Any]], *, days: int, megabytes: int
    ) -> list[dict[str, Any]]:
        now = datetime.now(UTC)
        selected: list[dict[str, Any]] = []
        remaining: list[dict[str, Any]] = []
        cutoff = now - timedelta(days=days) if days else None
        for entry in entries:
            timestamp = entry["timestamp"]
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            if cutoff is not None and timestamp < cutoff:
                selected.append(entry)
            else:
                remaining.append(entry)
        limit = megabytes * 1024 * 1024
        total = sum(item["size"] for item in remaining)
        if limit and total > limit:
            for entry in sorted(remaining, key=lambda item: item["timestamp"]):
                if total <= limit:
                    break
                selected.append(entry)
                total -= entry["size"]
        return selected

    @staticmethod
    def _result(entries: list[dict[str, Any]]) -> dict[str, float | int]:
        return {
            "removed": len(entries),
            "freedMB": round(sum(item["size"] for item in entries) / 1024 / 1024, 2),
        }

    @staticmethod
    def _validate(value: dict[str, Any]) -> dict[str, Any]:
        if set(value) != set(DEFAULT_RETENTION) or type(value["enabled"]) is not bool:
            raise WorkflowError(
                "RETENTION_CONFIG_INVALID", "留存策略包含无效字段", 422
            )
        for key in DEFAULT_RETENTION:
            if key == "enabled":
                continue
            item = value[key]
            minimum = 1 if key == "cleanup_interval_hours" else 0
            if type(item) is not int or not minimum <= item <= _MAX_SAFE_INTEGER:
                raise WorkflowError(
                    "RETENTION_CONFIG_INVALID", "留存策略必须使用合法整数", 422
                )
        return dict(value)

    def _write_json(self, value: dict[str, Any]) -> None:
        self._settings.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{self._settings.name}.", suffix=".tmp", dir=self._settings.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._settings)
        except BaseException:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
