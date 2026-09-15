from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path, PurePosixPath
from typing import Protocol
from uuid import uuid4

from autoflow.domain.workflows.runs import WorkflowArtifact, WorkflowRunError


class WorkflowArtifactRepository(Protocol):
    def register_artifact(
        self,
        *,
        run_id: str,
        artifact_id: str,
        node_id: str,
        execution_id: str | None,
        relative_path: str,
        size: int,
        sha256: str,
        mime_type: str,
        purpose: str,
    ) -> WorkflowArtifact: ...


class _BoundArtifactWriter:
    def __init__(
        self,
        store: WorkflowArtifactStore,
        *,
        run_id: str,
        node_id: str,
        execution_id: str | None,
        purpose: str,
    ) -> None:
        self._store = store
        self._run_id = run_id
        self._node_id = node_id
        self._execution_id = execution_id
        self._purpose = purpose

    async def write_bytes(
        self, *, name: str, content: bytes, mime_type: str
    ) -> str:
        return await asyncio.to_thread(
            self._store._write_and_register,
            run_id=self._run_id,
            node_id=self._node_id,
            execution_id=self._execution_id,
            purpose=self._purpose,
            name=name,
            content=content,
            mime_type=mime_type,
        )


class WorkflowArtifactStore:
    def __init__(self, root: Path, repository: WorkflowArtifactRepository) -> None:
        self._root = root.resolve()
        self._repository = repository

    def writer(
        self,
        *,
        run_id: str,
        node_id: str,
        execution_id: str | None,
        purpose: str,
    ) -> _BoundArtifactWriter:
        if not run_id or Path(run_id).name != run_id:
            raise WorkflowRunError("ARTIFACT_PATH_INVALID", "运行标识不能用于产物路径", 422)
        return _BoundArtifactWriter(
            self,
            run_id=run_id,
            node_id=node_id,
            execution_id=execution_id,
            purpose=purpose,
        )

    @staticmethod
    def _relative_name(name: str) -> PurePosixPath:
        normalized = name.replace("\\", "/")
        path = PurePosixPath(normalized)
        if (
            not normalized
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise WorkflowRunError("ARTIFACT_PATH_INVALID", "产物路径无效", 422)
        return path

    @staticmethod
    def _place_file(target: Path, content: bytes) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.parent / f".{target.name}.{uuid4().hex}.tmp"
        try:
            with temporary.open("xb") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError as error:
                raise WorkflowRunError(
                    "ARTIFACT_ALREADY_EXISTS", "产物文件已存在", 409
                ) from error
            finally:
                temporary.unlink(missing_ok=True)
            directory_fd = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    def _remove_unowned(self, target: Path, run_root: Path) -> None:
        target.unlink(missing_ok=True)
        current = target.parent
        while current != self._root and current.is_relative_to(self._root):
            try:
                current.rmdir()
            except OSError:
                break
            if current == run_root:
                break
            current = current.parent

    def _write_and_register(
        self,
        *,
        run_id: str,
        node_id: str,
        execution_id: str | None,
        purpose: str,
        name: str,
        content: bytes,
        mime_type: str,
    ) -> str:
        relative_name = self._relative_name(name)
        run_root = self._root / "runs" / run_id
        target = run_root / "artifacts" / Path(*relative_name.parts)
        target = target.resolve()
        if not target.is_relative_to(run_root.resolve()):
            raise WorkflowRunError("ARTIFACT_PATH_INVALID", "产物路径超出运行目录", 422)
        self._place_file(target, content)
        relative_path = target.relative_to(self._root).as_posix()
        try:
            self._repository.register_artifact(
                run_id=run_id,
                artifact_id=str(uuid4()),
                node_id=node_id,
                execution_id=execution_id,
                relative_path=relative_path,
                size=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                mime_type=mime_type,
                purpose=purpose,
            )
        except BaseException:
            self._remove_unowned(target, run_root)
            raise
        return str(target)
