"""Windows new-file publication: pin every directory and publish the owned handle.

Existing-file replacement remains refused: Windows cannot atomically replace a
file while its identity is protected by a handle denying delete sharing.
"""

from __future__ import annotations

import ctypes
import os
import re
from contextlib import contextmanager
from pathlib import Path, PureWindowsPath
from uuid import uuid4

from autoflow.domain.workflows.runs import WorkflowRunError


def _api():
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.GetFileInformationByHandleEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
    kernel.GetFinalPathNameByHandleW.argtypes = [
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    kernel.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    kernel.SetFileInformationByHandle.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    kernel.SetFileInformationByHandle.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    return kernel


def _invalid():
    return WorkflowRunError(
        "ARTIFACT_PATH_INVALID", "输出路径包含不支持的 Windows 文件名或重解析点", 422
    )


def output_target(root: Path, output_path: str) -> Path:
    if not isinstance(output_path, str) or not output_path:
        raise _invalid()
    raw = Path(output_path)
    if raw.drive and (
        not re.fullmatch("[A-Za-z]:", raw.drive) or not raw.is_absolute()
    ):
        raise _invalid()
    if raw.root and not raw.drive:
        raise _invalid()
    parts = output_path.replace("\\", "/").split("/")
    if raw.drive:
        parts = parts[1:]
    for part in parts:
        if (
            not part
            or part in {".", ".."}
            or part[-1] in " ."
            or any(ord(char) < 32 or char in '<>:"|?*' for char in part)
            or PureWindowsPath(part).is_reserved()
        ):
            raise _invalid()
    target = raw if raw.is_absolute() else root / raw
    if not target.is_absolute() or not re.fullmatch("[A-Za-z]:", target.drive):
        raise _invalid()
    return target


def _open(kernel, path: Path, access: int, share: int, creation: int, flags: int):
    from ctypes import wintypes

    handle = kernel.CreateFileW(str(path), access, share, None, creation, flags, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]
    return handle


@contextmanager
def pinned_parent(target: Path):
    kernel = _api()
    handles = []
    try:
        path = Path(target.anchor)
        for part in [None, *target.parts[1:-1]]:
            if part is not None:
                path /= part
                path.mkdir(exist_ok=True)
            handle = _open(kernel, path, 0x80, 1, 3, 0x02000000 | 0x00200000)
            handles.append(handle)
            # FILE_ATTRIBUTE_TAG_INFO: reject every reparse point, including junctions.
            info = (ctypes.c_uint32 * 2)()
            if not kernel.GetFileInformationByHandleEx(
                handle, 9, info, ctypes.sizeof(info)
            ):
                raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]
            if info[0] & 0x400 or not info[0] & 0x10:
                raise _invalid()
            final = ctypes.create_unicode_buffer(32768)
            length = kernel.GetFinalPathNameByHandleW(handle, final, len(final), 0)
            if (
                not length
                or length >= len(final)
                or final.value.removeprefix("\\\\?\\").rstrip("\\").casefold()
                != str(path).rstrip("\\").casefold()
            ):
                raise _invalid()
        yield
    finally:
        for handle in reversed(handles):
            kernel.CloseHandle(handle)


@contextmanager
def staged_output(target: Path):
    import msvcrt

    kernel = _api()
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    handle = _open(
        kernel, temporary, 0x80000000 | 0x40000000 | 0x10000, 0, 1, 0x00200000
    )
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDWR | os.O_BINARY)  # type: ignore[attr-defined]
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    committed = False
    try:
        yield descriptor
        committed = True
    finally:
        try:
            if not committed:
                delete = ctypes.c_ubyte(1)
                if not kernel.SetFileInformationByHandle(
                    handle, 4, ctypes.byref(delete), ctypes.sizeof(delete)
                ):
                    raise WorkflowRunError(
                        "ARTIFACT_CLEANUP_FAILED",
                        f"输出暂存文件清理失败: {temporary.name}",
                        500,
                    )
        finally:
            os.close(descriptor)


def publish(descriptor: int, target: Path) -> None:
    import msvcrt
    from ctypes import wintypes

    name = str(target)

    class Rename(ctypes.Structure):
        _fields_ = [
            ("replace", wintypes.BOOL),
            ("root", wintypes.HANDLE),
            ("length", wintypes.DWORD),
            ("name", wintypes.WCHAR * (len(name.encode("utf-16-le")) // 2 + 1)),
        ]

    info = Rename()
    info.name = name
    info.length = len(name.encode("utf-16-le"))
    kernel = _api()
    if not kernel.SetFileInformationByHandle(
        msvcrt.get_osfhandle(descriptor),  # type: ignore[attr-defined]
        3,
        ctypes.byref(info),
        Rename.name.offset + info.length,
    ):
        raise WorkflowRunError(
            "ARTIFACT_WRITE_CONFLICT",
            "输出文件已存在或无法安全发布；没有覆盖已有文件",
            409,
        )
