"""Use the shared artifact store, then confirm the durable project event separately."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import Any

from autoflow.domain.workflows.execution import BinaryOutputSnapshot
from autoflow.domain.workflows.runs import WorkflowArtifact, WorkflowRunError

from .workflow_artifacts import WorkflowArtifactStore


class _WriteCancellation:
    def __init__(self) -> None:
        self.event = Event()

    @property
    def cancelled(self) -> bool:
        return self.event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise asyncio.CancelledError


class ProjectArtifactWriter:
    def __init__(
        self,
        root: Path,
        run_id: str,
        generation: int,
        node_id: str,
        execution_id: str,
        kind: str,
        emit: Callable[[str, str, str, dict[str, object]], Awaitable[None]],
    ) -> None:
        self._node_id, self._execution_id, self._emit = node_id, execution_id, emit
        self._kind = kind
        self._pending: WorkflowArtifact | None = None
        self._cancellation = _WriteCancellation()
        self._run_id = run_id
        self._store = WorkflowArtifactStore(root, self, execution_generation=generation)
        self._writer = self._store.writer(
            run_id=run_id,
            node_id=node_id,
            execution_id=execution_id,
            purpose="result",
            cancellation=self._cancellation,
        )

    def register_artifact(self, **values: Any) -> WorkflowArtifact:
        # This is an in-worker receipt only. The parent still owns SQL commit.
        artifact = WorkflowArtifact(**values, ordinal=0, event_sequence=0)
        self._pending = artifact
        return artifact

    async def write_bytes(self, *, name: str, content: bytes, mime_type: str) -> str:
        valid_media = (
            mime_type == "image/png" if self._kind == "screenshot"
            else mime_type.startswith("image/") if self._kind == "image"
            else mime_type == "application/octet-stream" if self._kind == "file"
            else False
        )
        limit = 20 * 1024 * 1024 if self._kind == "screenshot" else 64 * 1024 * 1024
        if not valid_media or not content or len(content) > limit or len(mime_type) > 120:
            raise WorkflowRunError(
                "RUN_ARTIFACT_INVALID", "项目产物的类型或大小无效", 422
            )
        writing = asyncio.create_task(
            self._writer.write_bytes(name=name, content=content, mime_type=mime_type)
        )
        try:
            target = await asyncio.shield(writing)
        except asyncio.CancelledError:
            self._cancellation.event.set()
            target = await writing
            # No event has been sent, so this file cannot have a SQL owner yet.
            await asyncio.to_thread(
                self._store._remove_unowned,
                Path(target),
                self._store._run_root(self._run_id),
            )
            raise
        artifact = self._pending
        assert artifact is not None
        self._pending = None
        # Do not let an uncertain ACK roll back a file that SQL may have committed.
        # The dispatcher checks durable facts before removing an uncommitted file.
        await self._emit(
            "artifact",
            self._node_id,
            self._execution_id,
            {
                "artifactId": artifact.artifact_id,
                "kind": self._kind,
                "purpose": "result",
                "availability": "available",
                "relativePath": artifact.relative_path,
                "mediaType": artifact.mime_type,
                "byteSize": artifact.size,
                "sha256": artifact.sha256,
                "createdAt": datetime.now(UTC).isoformat(),
                "unavailableReason": None,
            },
        )
        return target

    async def write_text(
        self,
        *,
        output_path: str,
        content: str,
        separator: str,
        encoding: str,
        append: bool,
        mime_type: str,
    ) -> str:
        raise WorkflowRunError("WORKFLOW_NOT_RUNNABLE", "项目任务尚未接入文本产物", 422)

    async def write_binary_output(
        self,
        *,
        output_path: str,
        content: bytes,
        mime_type: str,
        expected_identity: str | None = None,
    ) -> str:
        raise WorkflowRunError(
            "WORKFLOW_NOT_RUNNABLE", "项目任务尚未接入二进制输出", 422
        )

    async def read_binary_output(
        self, *, output_path: str, max_bytes: int
    ) -> BinaryOutputSnapshot:
        raise WorkflowRunError(
            "WORKFLOW_NOT_RUNNABLE", "项目任务尚未接入二进制输出", 422
        )
