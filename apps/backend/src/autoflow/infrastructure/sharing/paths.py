"""Filesystem boundary for one share; never open a checked pathname a second time.

POSIX walks with directory descriptors and O_NOFOLLOW. Windows keeps directory
handles without FILE_SHARE_DELETE and rejects reparse points. Uploads publish
complete private staging files exclusively, without replacing any public name.
Symlinks/junctions inside a share are deliberately not traversed on either OS.
"""

from __future__ import annotations

import errno
import importlib
import os
import shutil
import stat
import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from threading import Lock
from typing import BinaryIO, Protocol
from uuid import uuid4


class _WindowsHandle(Protocol):
    def Close(self) -> None: ...

    def Detach(self) -> int: ...


_UPLOAD_PREFIX = ".autoflow-upload-"


def parts(value: str) -> tuple[str, ...]:
    # URL decoding belongs to the HTTP adapter, exactly once. Also reject Windows
    # ADS/device/drive syntax on POSIX so shared links have portable semantics.
    if "\\" in value or ":" in value or "\x00" in value:
        raise PermissionError("无效的共享路径")
    result = tuple(part for part in value.split("/") if part)
    for part in result:
        if part in {".", ".."} or part.endswith((".", " ")) or part.casefold().startswith(_UPLOAD_PREFIX):
            raise PermissionError("无效的共享路径")
        if part.split(".")[0].upper() in {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10)),
        }:
            raise PermissionError("无效的共享路径")
    return result


class ShareDirectory:
    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)
        self._stack = ExitStack()
        self._lifecycle = Lock()
        self._closed = False
        self._active = 0
        try:
            if sys.platform == "win32":
                # Pin ancestors too: replacing an ancestor must not redirect a later
                # CreateFile pathname while a directory handle remains open.
                self._win = importlib.import_module("win32file")
                parent = Path(self.root.anchor)
                self._stack.callback(self._windows_open(parent, directory=True).Close)
                for component in self.root.parts[1:]:
                    parent /= component
                    self._stack.callback(
                        self._windows_open(parent, directory=True).Close
                    )
                self._fd = -1
            else:
                self._fd = os.open(
                    self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                )
                self._stack.callback(os.close, self._fd)
        except BaseException:
            self._stack.close()
            raise

    def close(self) -> None:
        with self._lifecycle:
            self._closed = True
            if self._active == 0:
                self._stack.close()

    @contextmanager
    def _operation(self) -> Iterator[None]:
        with self._lifecycle:
            if self._closed:
                raise PermissionError("共享已关闭")
            self._active += 1
        try:
            yield
        finally:
            with self._lifecycle:
                self._active -= 1
                if self._closed and self._active == 0:
                    self._stack.close()

    def _windows_open(self, path: Path, *, directory: bool = False, private: bool = False) -> _WindowsHandle:
        if sys.platform != "win32":
            raise RuntimeError("Windows file handles require Windows")
        try:
            handle: _WindowsHandle = self._win.CreateFile(
                str(path),
                0 if directory else 0x80000000,
                1 | 2,
                None,
                3,
                0x00200000 | (0x02000000 if directory else 0),
                None,
            )
        except OSError as error:
            import ctypes

            raise ctypes.WinError(error.args[0]) from error
        try:
            attributes = self._win.GetFileInformationByHandle(handle)[0]
            if attributes & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
                raise PermissionError("共享路径不能经过链接")
            # Inspect the normalized opened object, including Windows short-name
            # aliases, rather than relying only on the caller's spelling.
            actual = Path(self._win.GetFinalPathNameByHandle(handle, 0))
            if not private and actual.name.casefold().startswith(_UPLOAD_PREFIX):
                raise PermissionError("共享路径不能访问上传暂存")
            return handle
        except BaseException:
            handle.Close()
            raise

    @contextmanager
    def directory(self, value: str, *, create: bool = False) -> Iterator[int | Path]:
        components = parts(value)
        with self._operation(), ExitStack() as stack:
            if sys.platform == "win32":
                path = self.root
                for component in components:
                    path /= component
                    if create:
                        try:
                            path.mkdir()
                        except FileExistsError:
                            pass
                    stack.callback(self._windows_open(path, directory=True).Close)
                yield path
            else:
                fd = os.dup(self._fd)
                stack.callback(os.close, fd)
                for component in components:
                    if create:
                        try:
                            os.mkdir(component, dir_fd=fd)
                        except FileExistsError:
                            pass
                    try:
                        fd = os.open(
                            component,
                            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=fd,
                        )
                    except (NotADirectoryError, PermissionError) as error:
                        raise PermissionError("共享路径不能经过链接") from error
                    stack.callback(os.close, fd)
                yield fd

    @contextmanager
    def open_file(self, value: str) -> Iterator[BinaryIO]:
        components = parts(value)
        if not components:
            raise FileNotFoundError(value)
        with self.directory("/".join(components[:-1])) as parent:
            if isinstance(parent, Path):
                if sys.platform != "win32":
                    raise RuntimeError("Windows file handles require Windows")
                import msvcrt

                handle = self._windows_open(parent / components[-1])
                fd = msvcrt.open_osfhandle(handle.Detach(), os.O_RDONLY | os.O_BINARY)
            else:
                if sys.platform == "win32":
                    raise RuntimeError("POSIX directory descriptors require POSIX")
                try:
                    fd = os.open(
                        components[-1],
                        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                        dir_fd=parent,
                    )
                except OSError as error:
                    if error.errno == errno.ELOOP:
                        raise PermissionError("共享路径不能经过链接") from error
                    raise
            with os.fdopen(fd, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise PermissionError("共享对象必须是普通文件")
                yield stream

    @contextmanager
    def _upload_stage(self, parent: int | Path) -> Iterator[int | Path]:
        # A private, API-inaccessible staging directory keeps failed writes away
        # from final names. No check-then-unlink cleanup of public paths.
        name = _UPLOAD_PREFIX + uuid4().hex
        options = {} if isinstance(parent, Path) else {"dir_fd": parent}
        path = parent / name if isinstance(parent, Path) else name
        os.mkdir(path, 0o700, **options)
        try:
            with ExitStack() as stack:
                stage: int | Path
                if isinstance(parent, Path):
                    stage = parent / name
                    stack.callback(self._windows_open(stage, directory=True, private=True).Close)
                else:
                    if sys.platform == "win32":
                        raise RuntimeError("POSIX directory descriptors require POSIX")
                    stage = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                    stack.callback(os.close, stage)
                try:
                    yield stage
                finally:
                    try:
                        if isinstance(stage, Path):
                            (stage / "content").unlink(missing_ok=True)
                        else:
                            os.unlink("content", dir_fd=stage)
                    except FileNotFoundError:
                        pass
        finally:
            os.rmdir(path, **options)

    def upload(self, directory: str, filename: str, content: bytes) -> str:
        if parts(filename) != (filename,):
            raise PermissionError("无效的文件名")
        with self.directory(directory, create=True) as parent, self._upload_stage(parent) as stage:
            fd = os.open(
                stage / "content" if isinstance(stage, Path) else "content",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL
                | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0),
                0o600,
                **({} if isinstance(stage, Path) else {"dir_fd": stage}),
            )
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            counter = 0
            while True:
                name = filename if not counter else f"{Path(filename).stem}_{counter}{Path(filename).suffix}"
                try:
                    if isinstance(parent, Path) and isinstance(stage, Path):
                        # Windows rename refuses existing targets, including links.
                        os.rename(stage / "content", parent / name)
                    elif isinstance(parent, int) and isinstance(stage, int):
                        # POSIX link is an atomic exclusive publication; never replace
                        # an existing file/link. Filesystems without links fail closed.
                        os.link("content", name, src_dir_fd=stage, dst_dir_fd=parent, follow_symlinks=False)
                    else:
                        raise TypeError("共享路径平台不一致")
                    return name
                except FileExistsError:
                    counter += 1

    def mkdir(self, directory: str, name: str) -> None:
        if parts(name) != (name,):
            raise PermissionError("无效的目录名")
        with self.directory(directory) as parent:
            if isinstance(parent, Path):
                (parent / name).mkdir()
            else:
                os.mkdir(name, dir_fd=parent)

    def delete(self, value: str) -> None:
        components = parts(value)
        if not components:
            raise PermissionError("不能删除共享根目录")
        with self.directory("/".join(components[:-1])) as parent:
            target = (
                parent / components[-1] if isinstance(parent, Path) else components[-1]
            )
            options = {} if isinstance(parent, Path) else {"dir_fd": parent}
            info = os.stat(target, follow_symlinks=False, **options)
            if (
                stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & 0x400
            ):
                raise PermissionError("共享路径不能经过链接")
            if isinstance(parent, Path):
                # The final segment may be a short-name alias of private staging.
                # Release this target handle before deleting; the parent stays pinned.
                self._windows_open(
                    parent / components[-1], directory=stat.S_ISDIR(info.st_mode)
                ).Close()
            if stat.S_ISDIR(info.st_mode):
                # Python's fd-based rmtree refuses symlink swaps; on Windows it
                # removes junctions without recursing into their targets.
                if isinstance(parent, Path):
                    shutil.rmtree(parent / components[-1])
                else:
                    shutil.rmtree(components[-1], dir_fd=parent)
            else:
                os.unlink(target, **options)

    def entries(self, directory: str) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        with self.directory(directory) as parent, os.scandir(parent) as iterator:
            for entry in iterator:
                if entry.name.casefold().startswith(_UPLOAD_PREFIX):
                    continue
                info = entry.stat(follow_symlinks=False)
                if (
                    stat.S_ISLNK(info.st_mode)
                    or getattr(info, "st_file_attributes", 0) & 0x400
                ):
                    continue
                if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                    continue
                result.append(
                    {
                        "name": entry.name,
                        "type": "folder" if stat.S_ISDIR(info.st_mode) else "file",
                        "size": info.st_size if stat.S_ISREG(info.st_mode) else 0,
                        "modified": info.st_mtime,
                        "path": "/".join((*parts(directory), entry.name)),
                    }
                )
        return sorted(
            result,
            key=lambda item: (item["type"] != "folder", str(item["name"]).lower()),
        )
