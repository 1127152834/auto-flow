from __future__ import annotations

import asyncio
import hashlib
import os
import stat
from pathlib import Path, PurePosixPath
from typing import Protocol
from uuid import uuid4

from autoflow.domain.workflows.execution import CancellationToken
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
        cancellation: CancellationToken | None,
    ) -> None:
        self._store = store
        self._run_id = run_id
        self._node_id = node_id
        self._execution_id = execution_id
        self._purpose = purpose
        self._cancellation = cancellation

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
        return await asyncio.to_thread(
            self._store._write_text_and_register,
            run_id=self._run_id,
            node_id=self._node_id,
            execution_id=self._execution_id,
            purpose=self._purpose,
            output_path=output_path,
            content=content,
            separator=separator,
            encoding=encoding,
            append=append,
            mime_type=mime_type,
            cancellation=self._cancellation,
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
        cancellation: CancellationToken | None = None,
    ) -> _BoundArtifactWriter:
        if not run_id or Path(run_id).name != run_id:
            raise WorkflowRunError("ARTIFACT_PATH_INVALID", "运行标识不能用于产物路径", 422)
        return _BoundArtifactWriter(
            self,
            run_id=run_id,
            node_id=node_id,
            execution_id=execution_id,
            purpose=purpose,
            cancellation=cancellation,
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

    @staticmethod
    def _raise_if_cancelled(cancellation: CancellationToken | None) -> None:
        if cancellation is not None:
            cancellation.raise_if_cancelled()

    def _open_output_parent(self, run_id: str, output_path: str) -> tuple[Path, int]:
        if not isinstance(output_path, str) or not output_path:
            raise WorkflowRunError("ARTIFACT_PATH_INVALID", "输出文件路径无效", 422)
        if os.name == "nt":
            raise WorkflowRunError(
                "ARTIFACT_PLATFORM_UNSUPPORTED",
                "Windows 安全文件输出尚未完成实机验收",
                501,
            )
        raw = Path(output_path)
        if raw.is_absolute():
            raw.parent.mkdir(parents=True, exist_ok=True)
            parent = raw.parent.resolve()
            return parent / raw.name, self._open_directory(parent)

        relative = self._relative_name(output_path)
        output_root = self._root / "runs" / run_id / "outputs"
        output_root.mkdir(parents=True, exist_ok=True)
        output_root = output_root.resolve()
        directory_fd = self._open_directory(output_root)
        parent = output_root
        try:
            for part in relative.parts[:-1]:
                try:
                    os.mkdir(part, dir_fd=directory_fd)
                except FileExistsError:
                    pass
                try:
                    child_fd = os.open(
                        part,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=directory_fd,
                    )
                except OSError as error:
                    raise WorkflowRunError(
                        "ARTIFACT_PATH_INVALID", "输出目录不能是符号链接", 422
                    ) from error
                os.close(directory_fd)
                directory_fd = child_fd
                parent /= part
            return parent / relative.name, directory_fd
        except BaseException:
            os.close(directory_fd)
            raise

    @staticmethod
    def _open_directory(path: Path) -> int:
        return os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    @staticmethod
    def _write_all(file_descriptor: int, content: bytes) -> None:
        view = memoryview(content)
        while view:
            written = os.write(file_descriptor, view)
            view = view[written:]

    def _snapshot_from_descriptor(
        self,
        *,
        source_fd: int,
        run_id: str,
        cancellation: CancellationToken | None,
    ) -> tuple[Path, int, str]:
        run_root = self._root / "runs" / run_id
        target = run_root / "artifacts" / "exports" / f"{uuid4().hex}.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.parent / f".{target.name}.{uuid4().hex}.tmp"
        digest = hashlib.sha256()
        size = 0
        try:
            os.lseek(source_fd, 0, os.SEEK_SET)
            with temporary.open("xb") as output:
                while chunk := os.read(source_fd, 1024 * 1024):
                    self._raise_if_cancelled(cancellation)
                    output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                output.flush()
                os.fsync(output.fileno())
            os.link(temporary, target)
            temporary.unlink()
        except BaseException:
            temporary.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            raise
        return target, size, digest.hexdigest()

    def _write_text_and_register(
        self,
        *,
        run_id: str,
        node_id: str,
        execution_id: str | None,
        purpose: str,
        output_path: str,
        content: str,
        separator: str,
        encoding: str,
        append: bool,
        mime_type: str,
        cancellation: CancellationToken | None,
    ) -> str:
        target, directory_fd = self._open_output_parent(run_id, output_path)
        temporary_name = f".{target.name}.{uuid4().hex}.tmp"
        snapshot_path: Path | None = None
        try:
            self._raise_if_cancelled(cancellation)
            target_identity: tuple[int, int] | None = None
            flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
            flags |= os.O_NOFOLLOW
            temporary_fd = os.open(
                temporary_name, flags, 0o600, dir_fd=directory_fd
            )
            try:
                if append:
                    try:
                        source_fd = os.open(
                            target.name,
                            os.O_RDONLY | os.O_NOFOLLOW,
                            dir_fd=directory_fd,
                        )
                    except FileNotFoundError:
                        source_fd = None
                    if source_fd is not None:
                        try:
                            source_stat = os.fstat(source_fd)
                            target_identity = (source_stat.st_dev, source_stat.st_ino)
                            while chunk := os.read(source_fd, 1024 * 1024):
                                self._raise_if_cancelled(cancellation)
                                self._write_all(temporary_fd, chunk)
                        finally:
                            os.close(source_fd)
                size_before_text = os.lseek(temporary_fd, 0, os.SEEK_CUR)
                text_fd = temporary_fd
                temporary_fd = -1
                with os.fdopen(text_fd, "a", encoding=encoding) as staged_text:
                    if append and size_before_text > 0:
                        staged_text.write(separator)
                    if not content:
                        staged_text.write("")
                    for start in range(0, len(content), 64 * 1024):
                        self._raise_if_cancelled(cancellation)
                        staged_text.write(content[start : start + 64 * 1024])
                    staged_text.flush()
                    os.fsync(staged_text.fileno())
            finally:
                if temporary_fd >= 0:
                    os.close(temporary_fd)

            staged_fd = os.open(
                temporary_name,
                os.O_RDONLY | os.O_NOFOLLOW,
                dir_fd=directory_fd,
            )
            try:
                snapshot_path, snapshot_size, snapshot_sha256 = (
                    self._snapshot_from_descriptor(
                        source_fd=staged_fd,
                        run_id=run_id,
                        cancellation=cancellation,
                    )
                )
            finally:
                os.close(staged_fd)

            opened_parent = os.fstat(directory_fd)
            current_parent = os.stat(target.parent, follow_symlinks=False)
            if stat.S_ISLNK(current_parent.st_mode) or (
                current_parent.st_dev,
                current_parent.st_ino,
            ) != (opened_parent.st_dev, opened_parent.st_ino):
                raise WorkflowRunError(
                    "ARTIFACT_WRITE_CONFLICT", "输出目录在写入期间发生变化", 409
                )
            try:
                current_stat = os.stat(
                    target.name, dir_fd=directory_fd, follow_symlinks=False
                )
            except FileNotFoundError:
                current_stat = None
            if current_stat is not None and stat.S_ISLNK(current_stat.st_mode):
                raise WorkflowRunError(
                    "ARTIFACT_PATH_INVALID", "输出文件不能是符号链接", 422
                )
            if target_identity is not None and (
                current_stat is None
                or (current_stat.st_dev, current_stat.st_ino) != target_identity
            ):
                raise WorkflowRunError(
                    "ARTIFACT_WRITE_CONFLICT", "追加期间输出文件已被修改", 409
                )

            self._raise_if_cancelled(cancellation)
            os.replace(
                temporary_name,
                target.name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
            )
            os.fsync(directory_fd)
        except BaseException:
            try:
                os.unlink(temporary_name, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
            if snapshot_path is not None:
                snapshot_path.unlink(missing_ok=True)
            raise
        finally:
            os.close(directory_fd)

        assert snapshot_path is not None
        relative_path = snapshot_path.relative_to(self._root).as_posix()
        try:
            self._repository.register_artifact(
                run_id=run_id,
                artifact_id=str(uuid4()),
                node_id=node_id,
                execution_id=execution_id,
                relative_path=relative_path,
                size=snapshot_size,
                sha256=snapshot_sha256,
                mime_type=mime_type,
                purpose=purpose,
            )
        except BaseException:
            self._remove_unowned(snapshot_path, self._root / "runs" / run_id)
            raise
        return str(target)
