import errno
import os
import sys
from pathlib import Path
from typing import BinaryIO


class ExclusiveFileLock:
    """A non-blocking cross-process lock backed by one file descriptor."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._handle: BinaryIO | None = None

    def acquire(self) -> bool:
        if self._handle is not None:
            return False
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = self._path.open("a+b")
        try:
            _lock(handle)
        except OSError as error:
            handle.close()
            if error.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                return False
            raise
        self._handle = handle
        return True

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return
        self._handle = None
        try:
            _unlock(handle)
        finally:
            handle.close()


def _lock(handle: BinaryIO) -> None:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(handle: BinaryIO) -> None:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
