from __future__ import annotations

import asyncio
import errno
import hashlib
import os
import stat
from pathlib import Path, PurePosixPath
from typing import Protocol
from uuid import uuid4

from autoflow.domain.workflows.execution import BinaryOutputSnapshot, CancellationToken
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
            cancellation=self._cancellation,
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

    async def write_binary_output(
        self,
        *,
        output_path: str,
        content: bytes,
        mime_type: str,
        expected_identity: str | None = None,
    ) -> str:
        return await asyncio.to_thread(
            self._store._write_binary_output_and_register,
            run_id=self._run_id,
            node_id=self._node_id,
            execution_id=self._execution_id,
            purpose=self._purpose,
            output_path=output_path,
            content=content,
            mime_type=mime_type,
            cancellation=self._cancellation,
            expected_identity=expected_identity,
        )

    async def read_binary_output(
        self,
        *,
        output_path: str,
        max_bytes: int,
    ) -> BinaryOutputSnapshot:
        return await asyncio.to_thread(
            self._store._read_binary_output,
            run_id=self._run_id,
            output_path=output_path,
            max_bytes=max_bytes,
            cancellation=self._cancellation,
        )


class WorkflowArtifactStore:
    def __init__(self, root: Path, repository: WorkflowArtifactRepository, *, execution_generation: int | None = None) -> None:
        if execution_generation is not None and (type(execution_generation) is not int or execution_generation < 0):
            raise ValueError("invalid execution generation")
        self._execution_generation = execution_generation
        self._root = root.resolve()
        self._repository = repository
        self._retry_pending_output_cleanups()

    def _run_root(self, run_id: str) -> Path:
        root = self._root / "runs" / run_id
        if self._execution_generation is not None:
            root /= f"generation-{self._execution_generation}"
        if root.resolve() != root or not root.is_relative_to(self._root):
            raise WorkflowRunError("ARTIFACT_PATH_INVALID", "产物目录不能是符号链接", 422)
        return root

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
        cancellation: CancellationToken | None,
    ) -> str:
        self._raise_if_cancelled(cancellation)
        relative_name = self._relative_name(name)
        run_root = self._run_root(run_id)
        target = run_root / "artifacts" / Path(*relative_name.parts)
        if target.resolve() != target or not target.is_relative_to(run_root):
            raise WorkflowRunError("ARTIFACT_PATH_INVALID", "产物路径超出运行目录", 422)
        relative_path = target.relative_to(self._root).as_posix()
        self._place_file(target, content)
        try:
            self._raise_if_cancelled(cancellation)
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
        output_root = self._run_root(run_id) / "outputs"
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
        suffix: str = ".txt",
    ) -> tuple[Path, int, str]:
        run_root = self._run_root(run_id)
        target = run_root / "artifacts" / "exports" / f"{uuid4().hex}{suffix}"
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

    @staticmethod
    def _output_identity(metadata: os.stat_result | None) -> str:
        if metadata is None:
            return "missing"
        return ":".join(
            str(value)
            for value in (
                metadata.st_dev,
                metadata.st_ino,
                metadata.st_size,
                metadata.st_mtime_ns,
            )
        )

    def _cleanup_root(self) -> Path:
        maintenance = self._root / "maintenance"
        if maintenance.is_symlink():
            raise WorkflowRunError(
                "ARTIFACT_PATH_INVALID", "产物维护目录不能是符号链接", 422
            )
        maintenance.mkdir(parents=True, exist_ok=True, mode=0o700)
        cleanup_root = maintenance / "workflow-output-backups"
        if cleanup_root.is_symlink():
            raise WorkflowRunError(
                "ARTIFACT_PATH_INVALID", "产物维护目录不能是符号链接", 422
            )
        cleanup_root.mkdir(exist_ok=True, mode=0o700)
        return cleanup_root

    def _output_lock_root(self) -> Path:
        maintenance = self._root / "maintenance"
        if maintenance.is_symlink():
            raise WorkflowRunError(
                "ARTIFACT_PATH_INVALID", "产物维护目录不能是符号链接", 422
            )
        maintenance.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_root = maintenance / "workflow-output-locks"
        if lock_root.is_symlink():
            raise WorkflowRunError(
                "ARTIFACT_PATH_INVALID", "产物锁目录不能是符号链接", 422
            )
        lock_root.mkdir(exist_ok=True, mode=0o700)
        return lock_root

    def _acquire_output_lock(self, target: Path) -> int:
        # Output publication only runs on POSIX (see _open_output_parent). Keep the
        # platform-specific lock local so importing the backend remains portable.
        import fcntl

        lock_root = self._output_lock_root()
        lock_name = hashlib.sha256(os.fsencode(str(target))).hexdigest() + ".lock"
        lock_root_fd = self._open_directory(lock_root)
        try:
            lock_fd = os.open(
                lock_name,
                os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
                0o600,
                dir_fd=lock_root_fd,
            )
        finally:
            os.close(lock_root_fd)
        try:
            if not stat.S_ISREG(os.fstat(lock_fd).st_mode):
                raise WorkflowRunError(
                    "ARTIFACT_PATH_INVALID", "产物锁文件不是普通文件", 422
                )
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            return lock_fd
        except BaseException:
            os.close(lock_fd)
            raise

    @staticmethod
    def _release_output_lock(lock_fd: int) -> None:
        import fcntl

        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)

    def _retry_pending_output_cleanups(self) -> None:
        maintenance = self._root / "maintenance"
        if maintenance.is_symlink():
            return
        cleanup_root = maintenance / "workflow-output-backups"
        if not cleanup_root.exists() or cleanup_root.is_symlink():
            return
        for backup in cleanup_root.glob("*.cleanup"):
            try:
                metadata = backup.lstat()
                if stat.S_ISREG(metadata.st_mode):
                    backup.unlink()
                    cleanup_fd = self._open_directory(cleanup_root)
                    try:
                        os.fsync(cleanup_fd)
                    finally:
                        os.close(cleanup_fd)
            except OSError:
                continue
        for marker in cleanup_root.glob("*.cleanup-marker"):
            try:
                marker_metadata = marker.lstat()
                if not stat.S_ISREG(marker_metadata.st_mode):
                    continue
                backup_name = marker.read_text(encoding="ascii").strip()
                if (
                    not backup_name.endswith(".pending")
                    or Path(backup_name).name != backup_name
                    or Path(backup_name).stem
                    != marker.name.removesuffix(".cleanup-marker")
                    or len(backup_name) > 128
                ):
                    continue
                backup = cleanup_root / backup_name
                try:
                    backup_metadata = backup.lstat()
                except FileNotFoundError:
                    backup_metadata = None
                if backup_metadata is not None:
                    if not stat.S_ISREG(backup_metadata.st_mode):
                        continue
                    backup.unlink()
                marker.unlink()
                cleanup_fd = self._open_directory(cleanup_root)
                try:
                    os.fsync(cleanup_fd)
                finally:
                    os.close(cleanup_fd)
            except (OSError, UnicodeError):
                continue

    def _backup_output(
        self,
        directory_fd: int,
        target_name: str,
        *,
        cancellation: CancellationToken | None,
        expected_identity: str | None = None,
    ) -> Path | None:
        try:
            source_fd = os.open(
                target_name,
                os.O_RDONLY | os.O_NOFOLLOW,
                dir_fd=directory_fd,
            )
        except FileNotFoundError:
            if expected_identity is not None and expected_identity != "missing":
                raise WorkflowRunError(
                    "ARTIFACT_WRITE_CONFLICT", "输出文件在生成期间发生变化", 409
                ) from None
            return None
        except OSError as error:
            if error.errno == errno.ELOOP:
                raise WorkflowRunError(
                    "ARTIFACT_PATH_INVALID", "输出文件不能是符号链接", 422
                ) from error
            raise

        cleanup_root = self._cleanup_root()
        backup = cleanup_root / f"{uuid4().hex}.pending"
        try:
            source_metadata = os.fstat(source_fd)
            if not stat.S_ISREG(source_metadata.st_mode):
                raise WorkflowRunError(
                    "ARTIFACT_PATH_INVALID", "输出文件不能是符号链接或特殊文件", 422
                )
            source_identity = self._output_identity(source_metadata)
            if expected_identity is not None and source_identity != expected_identity:
                raise WorkflowRunError(
                    "ARTIFACT_WRITE_CONFLICT", "输出文件在生成期间发生变化", 409
                )
            with backup.open("xb") as output:
                while chunk := os.read(source_fd, 1024 * 1024):
                    self._raise_if_cancelled(cancellation)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            final_metadata = os.fstat(source_fd)
            try:
                path_metadata = os.stat(
                    target_name, dir_fd=directory_fd, follow_symlinks=False
                )
            except FileNotFoundError as error:
                raise WorkflowRunError(
                    "ARTIFACT_WRITE_CONFLICT", "输出文件在生成期间发生变化", 409
                ) from error
            if source_identity != self._output_identity(
                final_metadata
            ) or source_identity != self._output_identity(path_metadata):
                raise WorkflowRunError(
                    "ARTIFACT_WRITE_CONFLICT", "输出文件在生成期间发生变化", 409
                )
            cleanup_fd = self._open_directory(cleanup_root)
            try:
                os.fsync(cleanup_fd)
            finally:
                os.close(cleanup_fd)
            return backup
        except BaseException:
            backup.unlink(missing_ok=True)
            raise
        finally:
            os.close(source_fd)

    def _restore_output(
        self,
        directory_fd: int,
        target_name: str,
        backup: Path | None,
        *,
        expected_current_identity: str | None,
    ) -> None:
        if expected_current_identity is not None:
            try:
                current_metadata = os.stat(
                    target_name, dir_fd=directory_fd, follow_symlinks=False
                )
            except FileNotFoundError as error:
                raise WorkflowRunError(
                    "ARTIFACT_ROLLBACK_CONFLICT",
                    "输出文件在回滚前发生变化",
                    409,
                ) from error
            if self._output_identity(current_metadata) != expected_current_identity:
                raise WorkflowRunError(
                    "ARTIFACT_ROLLBACK_CONFLICT",
                    "输出文件在回滚前发生变化",
                    409,
                )
        if backup is None:
            try:
                os.unlink(target_name, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
            os.fsync(directory_fd)
            return

        temporary_name = f".{target_name}.{uuid4().hex}.restore"
        source_fd = os.open(backup, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            source_metadata = os.fstat(source_fd)
            if not stat.S_ISREG(source_metadata.st_mode):
                raise WorkflowRunError(
                    "ARTIFACT_ROLLBACK_FAILED", "输出文件备份不是普通文件", 500
                )
            temporary_fd = os.open(
                temporary_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory_fd,
            )
            try:
                while chunk := os.read(source_fd, 1024 * 1024):
                    self._write_all(temporary_fd, chunk)
                os.fsync(temporary_fd)
            finally:
                os.close(temporary_fd)
            os.replace(
                temporary_name,
                target_name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
            )
            os.fsync(directory_fd)
            backup.unlink()
        except BaseException:
            try:
                os.unlink(temporary_name, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
            raise
        finally:
            os.close(source_fd)

    def _cleanup_registered_backup(self, backup: Path) -> None:
        cleanup = backup.with_suffix(".cleanup")
        try:
            os.replace(backup, cleanup)
            cleanup_fd = self._open_directory(cleanup.parent)
            try:
                os.fsync(cleanup_fd)
                cleanup.unlink()
                os.fsync(cleanup_fd)
            finally:
                os.close(cleanup_fd)
        except OSError as error:
            pending = cleanup if cleanup.exists() else backup
            if pending == backup:
                try:
                    backup.unlink()
                    cleanup_fd = self._open_directory(backup.parent)
                    try:
                        os.fsync(cleanup_fd)
                    finally:
                        os.close(cleanup_fd)
                    return
                except OSError:
                    marker = backup.with_suffix(".cleanup-marker")
                    try:
                        with marker.open("x", encoding="ascii") as output:
                            output.write(backup.name)
                            output.flush()
                            os.fsync(output.fileno())
                        cleanup_fd = self._open_directory(backup.parent)
                        try:
                            os.fsync(cleanup_fd)
                        finally:
                            os.close(cleanup_fd)
                        pending = marker
                    except OSError:
                        pending = backup
            relative = pending.relative_to(self._root).as_posix()
            raise WorkflowRunError(
                "ARTIFACT_CLEANUP_FAILED",
                f"产物已登记，但旧输出文件备份清理失败；责任记录: {relative}",
                500,
            ) from error

    def _write_binary_output_and_register(
        self,
        *,
        run_id: str,
        node_id: str,
        execution_id: str | None,
        purpose: str,
        output_path: str,
        content: bytes,
        mime_type: str,
        cancellation: CancellationToken | None,
        expected_identity: str | None,
    ) -> str:
        target, directory_fd = self._open_output_parent(run_id, output_path)
        try:
            lock_fd = self._acquire_output_lock(target)
        except BaseException:
            os.close(directory_fd)
            raise
        try:
            return self._write_binary_output_locked(
                run_id=run_id,
                node_id=node_id,
                execution_id=execution_id,
                purpose=purpose,
                content=content,
                mime_type=mime_type,
                cancellation=cancellation,
                expected_identity=expected_identity,
                target=target,
                directory_fd=directory_fd,
            )
        finally:
            self._release_output_lock(lock_fd)

    def _write_binary_output_locked(
        self,
        *,
        run_id: str,
        node_id: str,
        execution_id: str | None,
        purpose: str,
        content: bytes,
        mime_type: str,
        cancellation: CancellationToken | None,
        expected_identity: str | None,
        target: Path,
        directory_fd: int,
    ) -> str:
        temporary_name = f".{target.name}.{uuid4().hex}.tmp"
        snapshot_path: Path | None = None
        backup_path: Path | None = None
        published = False
        published_identity: str | None = None
        staged_identity: str | None = None
        try:
            self._raise_if_cancelled(cancellation)
            temporary_fd = os.open(
                temporary_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory_fd,
            )
            try:
                for start in range(0, len(content), 1024 * 1024):
                    self._raise_if_cancelled(cancellation)
                    self._write_all(temporary_fd, content[start : start + 1024 * 1024])
                os.fsync(temporary_fd)
                staged_identity = self._output_identity(os.fstat(temporary_fd))
            finally:
                os.close(temporary_fd)

            staged_fd = os.open(
                temporary_name,
                os.O_RDONLY | os.O_NOFOLLOW,
                dir_fd=directory_fd,
            )
            try:
                suffix = target.suffix.lower()
                if not suffix or len(suffix) > 16:
                    suffix = ".bin"
                snapshot_path, snapshot_size, snapshot_sha256 = (
                    self._snapshot_from_descriptor(
                        source_fd=staged_fd,
                        run_id=run_id,
                        cancellation=cancellation,
                        suffix=suffix,
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
            if expected_identity is not None and self._output_identity(
                current_stat
            ) != expected_identity:
                raise WorkflowRunError(
                    "ARTIFACT_WRITE_CONFLICT", "输出文件在生成期间发生变化", 409
                )

            self._raise_if_cancelled(cancellation)
            backup_path = self._backup_output(
                directory_fd,
                target.name,
                cancellation=cancellation,
                expected_identity=expected_identity,
            )
            os.replace(
                temporary_name,
                target.name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
            )
            published = True
            published_identity = staged_identity
            os.fsync(directory_fd)
        except BaseException:
            rollback_error: OSError | WorkflowRunError | None = None
            if published:
                try:
                    self._restore_output(
                        directory_fd,
                        target.name,
                        backup_path,
                        expected_current_identity=published_identity,
                    )
                    backup_path = None
                except (OSError, WorkflowRunError) as error:
                    rollback_error = error
            try:
                os.unlink(temporary_name, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
            if snapshot_path is not None:
                snapshot_path.unlink(missing_ok=True)
            if backup_path is not None and not published:
                backup_path.unlink(missing_ok=True)
            os.close(directory_fd)
            if rollback_error is not None:
                raise WorkflowRunError(
                    "ARTIFACT_ROLLBACK_FAILED",
                    self._rollback_failure_message(
                        "输出文件发布失败且回滚失败", backup_path
                    ),
                    500,
                ) from rollback_error
            raise

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
            registration_rollback_error: OSError | WorkflowRunError | None = None
            if published:
                try:
                    self._restore_output(
                        directory_fd,
                        target.name,
                        backup_path,
                        expected_current_identity=published_identity,
                    )
                    backup_path = None
                except (OSError, WorkflowRunError) as error:
                    registration_rollback_error = error
            self._remove_unowned(snapshot_path, self._run_root(run_id))
            if registration_rollback_error is not None:
                raise WorkflowRunError(
                    "ARTIFACT_ROLLBACK_FAILED",
                    self._rollback_failure_message(
                        "产物登记失败且输出文件回滚失败", backup_path
                    ),
                    500,
                ) from registration_rollback_error
            raise
        else:
            if backup_path is not None:
                self._cleanup_registered_backup(backup_path)
        finally:
            os.close(directory_fd)
        return str(target)

    def _rollback_failure_message(self, message: str, backup: Path | None) -> str:
        if backup is None:
            return message
        relative = backup.relative_to(self._root).as_posix()
        return f"{message}；责任记录: {relative}"

    def _read_binary_output(
        self,
        *,
        run_id: str,
        output_path: str,
        max_bytes: int,
        cancellation: CancellationToken | None,
    ) -> BinaryOutputSnapshot:
        if max_bytes <= 0:
            raise WorkflowRunError(
                "ARTIFACT_SIZE_INVALID", "读取容量限制必须为正数", 422
            )
        target, directory_fd = self._open_output_parent(run_id, output_path)
        try:
            self._raise_if_cancelled(cancellation)
            try:
                descriptor = os.open(
                    target.name,
                    os.O_RDONLY | os.O_NOFOLLOW,
                    dir_fd=directory_fd,
                )
            except FileNotFoundError:
                return BinaryOutputSnapshot(content=None, identity="missing")
            except OSError as error:
                if error.errno == errno.ELOOP:
                    raise WorkflowRunError(
                        "ARTIFACT_PATH_INVALID", "输出文件不能是符号链接", 422
                    ) from error
                raise
            try:
                metadata = os.fstat(descriptor)
                if not stat.S_ISREG(metadata.st_mode):
                    raise WorkflowRunError(
                        "ARTIFACT_PATH_INVALID", "输出路径不是普通文件", 422
                    )
                if metadata.st_size > max_bytes:
                    raise WorkflowRunError(
                        "ARTIFACT_TOO_LARGE", "已有输出文件超过读取限制", 422
                    )
                chunks: list[bytes] = []
                size = 0
                while chunk := os.read(descriptor, 1024 * 1024):
                    self._raise_if_cancelled(cancellation)
                    size += len(chunk)
                    if size > max_bytes:
                        raise WorkflowRunError(
                            "ARTIFACT_TOO_LARGE", "已有输出文件超过读取限制", 422
                        )
                    chunks.append(chunk)
                final_metadata = os.fstat(descriptor)
                try:
                    path_metadata = os.stat(
                        target.name, dir_fd=directory_fd, follow_symlinks=False
                    )
                except FileNotFoundError as error:
                    raise WorkflowRunError(
                        "ARTIFACT_READ_CONFLICT", "输出文件在读取期间发生变化", 409
                    ) from error

                if self._output_identity(metadata) != self._output_identity(
                    final_metadata
                ) or self._output_identity(metadata) != self._output_identity(
                    path_metadata
                ):
                    raise WorkflowRunError(
                        "ARTIFACT_READ_CONFLICT", "输出文件在读取期间发生变化", 409
                    )
                return BinaryOutputSnapshot(
                    content=b"".join(chunks),
                    identity=self._output_identity(metadata),
                )
            finally:
                os.close(descriptor)
        finally:
            os.close(directory_fd)

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
        try:
            lock_fd = self._acquire_output_lock(target)
        except BaseException:
            os.close(directory_fd)
            raise
        try:
            return self._write_text_locked(
                run_id=run_id,
                node_id=node_id,
                execution_id=execution_id,
                purpose=purpose,
                content=content,
                separator=separator,
                encoding=encoding,
                append=append,
                mime_type=mime_type,
                cancellation=cancellation,
                target=target,
                directory_fd=directory_fd,
            )
        finally:
            self._release_output_lock(lock_fd)

    def _write_text_locked(
        self,
        *,
        run_id: str,
        node_id: str,
        execution_id: str | None,
        purpose: str,
        content: str,
        separator: str,
        encoding: str,
        append: bool,
        mime_type: str,
        cancellation: CancellationToken | None,
        target: Path,
        directory_fd: int,
    ) -> str:
        temporary_name = f".{target.name}.{uuid4().hex}.tmp"
        snapshot_path: Path | None = None
        backup_path: Path | None = None
        published = False
        published_identity: str | None = None
        staged_identity: str | None = None
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
                    staged_identity = self._output_identity(
                        os.fstat(staged_text.fileno())
                    )
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
            backup_path = self._backup_output(
                directory_fd,
                target.name,
                cancellation=cancellation,
                expected_identity=(
                    self._output_identity(current_stat)
                    if target_identity is not None
                    else None
                ),
            )
            os.replace(
                temporary_name,
                target.name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
            )
            published = True
            published_identity = staged_identity
            os.fsync(directory_fd)
        except BaseException:
            rollback_error: OSError | WorkflowRunError | None = None
            if published:
                try:
                    self._restore_output(
                        directory_fd,
                        target.name,
                        backup_path,
                        expected_current_identity=published_identity,
                    )
                    backup_path = None
                except (OSError, WorkflowRunError) as error:
                    rollback_error = error
            try:
                os.unlink(temporary_name, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
            if snapshot_path is not None:
                snapshot_path.unlink(missing_ok=True)
            if backup_path is not None and not published:
                backup_path.unlink(missing_ok=True)
            os.close(directory_fd)
            if rollback_error is not None:
                raise WorkflowRunError(
                    "ARTIFACT_ROLLBACK_FAILED",
                    self._rollback_failure_message(
                        "输出文件发布失败且回滚失败", backup_path
                    ),
                    500,
                ) from rollback_error
            raise

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
            registration_rollback_error: OSError | WorkflowRunError | None = None
            if published:
                try:
                    self._restore_output(
                        directory_fd,
                        target.name,
                        backup_path,
                        expected_current_identity=published_identity,
                    )
                    backup_path = None
                except (OSError, WorkflowRunError) as error:
                    registration_rollback_error = error
            self._remove_unowned(snapshot_path, self._run_root(run_id))
            if registration_rollback_error is not None:
                raise WorkflowRunError(
                    "ARTIFACT_ROLLBACK_FAILED",
                    self._rollback_failure_message(
                        "产物登记失败且输出文件回滚失败", backup_path
                    ),
                    500,
                ) from registration_rollback_error
            raise
        else:
            if backup_path is not None:
                self._cleanup_registered_backup(backup_path)
        finally:
            os.close(directory_fd)
        return str(target)
