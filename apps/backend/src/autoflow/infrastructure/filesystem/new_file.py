"""Publish a flushed sibling temporary file without replacing an existing file."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def publish_new_file(temporary: Path, target: Path) -> None:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        move = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
        move.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
        move.restype = wintypes.BOOL
        # WRITE_THROUGH only: no overwrite and no cross-volume copy fallback.
        if not move(str(temporary), str(target), 0x8):
            raise ctypes.WinError(ctypes.get_last_error())
        return
    os.link(temporary, target)
    directory = os.open(target.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
