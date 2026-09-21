"""Native named ownership for the existing kill-on-close Windows worker Job."""

from __future__ import annotations

import ctypes
import json
import os
import stat
import sys
import time
from pathlib import Path
from uuid import UUID

from .browser_processes import (
    _windows_handle_birth,
    _windows_process_api,
    process_identity_is_alive,
)


def create_run_job(name: str | None):
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    class BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("per_process_user_time_limit", ctypes.c_int64),
            ("per_job_user_time_limit", ctypes.c_int64),
            ("limit_flags", wintypes.DWORD),
            ("minimum_working_set_size", ctypes.c_size_t),
            ("maximum_working_set_size", ctypes.c_size_t),
            ("active_process_limit", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority_class", wintypes.DWORD),
            ("scheduling_class", wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_uint64)
            for name in (
                "read_operation_count",
                "write_operation_count",
                "other_operation_count",
                "read_transfer_count",
                "write_transfer_count",
                "other_transfer_count",
            )
        ]

    class ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("basic_limit_information", BasicLimitInformation),
            ("io_info", IoCounters),
            ("process_memory_limit", ctypes.c_size_t),
            ("job_memory_limit", ctypes.c_size_t),
            ("peak_process_memory_used", ctypes.c_size_t),
            ("peak_job_memory_used", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    ctypes.set_last_error(0)
    handle = kernel.CreateJobObjectW(None, name)
    if handle and ctypes.get_last_error() == 183:
        kernel.CloseHandle(handle)
        raise OSError("Worker Job identity already exists")
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    info = ExtendedLimitInformation()
    info.basic_limit_information.limit_flags = (
        0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    )
    if not kernel.SetInformationJobObject(
        handle, 9, ctypes.byref(info), ctypes.sizeof(info)
    ):
        error = ctypes.get_last_error()
        kernel.CloseHandle(handle)
        raise ctypes.WinError(error)
    return handle


def create_worker_job():
    if sys.platform != "win32":
        return None
    from ctypes import wintypes

    kernel = _api()
    name = os.environ.get("AUTOFLOW_WORKER_JOB_NAME")
    handle = kernel.OpenJobObjectW(0x0001 | 0x0004, False, name) if name else create_run_job(None)
    if not handle:
        raise OSError("Parent worker Job unavailable")
    try:
        current = kernel.GetCurrentProcess()
        member = wintypes.BOOL()
        if not kernel.IsProcessInJob(current, handle, ctypes.byref(member)):
            raise OSError("Worker Job membership unavailable")
        if not member.value and not kernel.AssignProcessToJobObject(handle, current):
            raise OSError("Worker could not join parent Job")
        return handle
    except BaseException:
        kernel.CloseHandle(handle)
        raise


def _api():
    from ctypes import wintypes

    kernel = _windows_process_api()
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.OpenJobObjectW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.OpenJobObjectW.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.IsProcessInJob.argtypes = [
        wintypes.HANDLE,
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.BOOL),
    ]
    kernel.IsProcessInJob.restype = wintypes.BOOL
    kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateJobObject.restype = wintypes.BOOL
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.QueryInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
    ]
    kernel.QueryInformationJobObject.restype = wintypes.BOOL
    return kernel


def _verified_process(kernel, job, pid: int, birth: int, *, owned_launcher: bool = False):
    from ctypes import wintypes

    access = 0x1000 | (0x0100 | 0x0001 if owned_launcher else 0)
    process = kernel.OpenProcess(access, False, pid)
    if not process:
        raise OSError("Worker process ownership unavailable")
    try:
        member = wintypes.BOOL()
        if _windows_handle_birth(kernel, process) != birth:
            raise OSError("Worker process does not own this Job: birth mismatch")
        if not kernel.IsProcessInJob(process, job, ctypes.byref(member)):
            raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]
        # Windows venv python.exe is a launcher outside its child's Job.
        # Only the live supervisor may attach its directly owned, birth-
        # verified launcher. Recovery never extends Job membership.
        if not member.value and (not owned_launcher or not kernel.AssignProcessToJobObject(job, process)):
            raise OSError("Worker process does not own this Job: not a member")
        return process
    except BaseException:
        kernel.CloseHandle(process)
        raise


def record_worker_job(
    directory: Path, run_id: str, generation: int, name: str, pid: int, birth: int
) -> int:
    kernel = _api()
    job = kernel.OpenJobObjectW(0x0001 | 0x0004 | 0x0008, False, name)  # JOB_OBJECT_QUERY
    if not job:
        raise OSError("Worker Job ownership unavailable")
    try:
        process = _verified_process(kernel, job, pid, birth, owned_launcher=True)
        kernel.CloseHandle(process)
        proof = {
            "runId": run_id,
            "generation": generation,
            "name": name,
            "pid": pid,
            "birth": birth,
        }
        with (directory / "worker-job.json").open("x", encoding="utf-8") as output:
            json.dump(proof, output)
            output.flush()
            os.fsync(output.fileno())
        return job
    except BaseException:
        kernel.CloseHandle(job)
        raise


def cleanup_worker_job(
    directory: Path, run_id: str, generation: int, timeout: float
) -> None:
    path = directory / "worker-job.json"
    try:
        metadata = path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_size > 4096
            or getattr(metadata, "st_file_attributes", 0) & 0x400
        ):
            raise ValueError("Invalid ownership file")
        proof = json.loads(path.read_text(encoding="utf-8"))
        prefix = f"Local\\AutoFlow-{run_id}-{generation}-"
        if (
            set(proof) != {"runId", "generation", "name", "pid", "birth"}
            or proof["runId"] != run_id
            or type(proof["generation"]) is not int
            or proof["generation"] != generation
            or not isinstance(proof["name"], str)
            or not proof["name"].startswith(prefix)
            or str(UUID(hex=proof["name"][len(prefix) :])).replace("-", "")
            != proof["name"][len(prefix) :]
            or any(
                type(proof[key]) is not int or proof[key] <= 0
                for key in ["pid", "birth"]
            )
        ):
            raise ValueError("Invalid Job identity")
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise RuntimeError(
            "Windows workflow restart cleanup needs native ownership verification"
        ) from error
    kernel = _api()
    job = kernel.OpenJobObjectW(
        0x0004 | 0x0008, False, proof["name"]
    )  # QUERY | TERMINATE
    if not job:
        if ctypes.get_last_error() == 2 and not process_identity_is_alive(  # type: ignore[attr-defined]
            proof["pid"], proof["birth"]
        ):
            return  # Verified kill-on-close Job and its original owner are gone.
        raise OSError("Worker Job exit is unconfirmed")
    process = None
    try:
        process = _verified_process(kernel, job, proof["pid"], proof["birth"])
        terminate_worker_job(job, timeout)
    finally:
        if process:
            kernel.CloseHandle(process)
        kernel.CloseHandle(job)


def _job_member_handles(kernel, job: int, deadline: float) -> list[int]:
    """Pin Job members before termination can remove them from accounting."""
    from ctypes import wintypes

    capacity = 16
    while True:
        class ProcessIds(ctypes.Structure):
            _fields_ = [("assigned", wintypes.DWORD), ("count", wintypes.DWORD),
                        ("pids", ctypes.c_size_t * capacity)]
        info = ProcessIds()
        ok = kernel.QueryInformationJobObject(job, 3, ctypes.byref(info), ctypes.sizeof(info), None)
        if not ok and ctypes.get_last_error() != 234:  # type: ignore[attr-defined]
            raise OSError("Owned Job process list unavailable")
        if ok and info.count == info.assigned and info.count <= capacity:
            break
        if time.monotonic() >= deadline:
            raise TimeoutError("Owned Job member snapshot unconfirmed")
        capacity = max(capacity * 2, info.assigned)
    handles = []
    try:
        for pid in info.pids[:info.count]:
            process = kernel.OpenProcess(0x00100000 | 0x1000, False, pid)  # SYNCHRONIZE | QUERY_LIMITED
            if not process:
                if ctypes.get_last_error() == 87:  # type: ignore[attr-defined]
                    continue  # Process exited before OpenProcess.
                raise OSError("Owned Job member exit unavailable")
            member = wintypes.BOOL()
            if not kernel.IsProcessInJob(process, job, ctypes.byref(member)):
                kernel.CloseHandle(process)
                raise OSError("Owned Job member identity unavailable")
            if member.value:
                handles.append(process)
            else:
                kernel.CloseHandle(process)  # PID was reused outside this Job.
        return handles
    except BaseException:
        for process in handles:
            kernel.CloseHandle(process)
        raise


def terminate_worker_job(job: int, timeout: float) -> None:
    """Wait for native process exit, not just the earlier accounting decrement."""
    from ctypes import wintypes

    kernel = _api()
    deadline = time.monotonic() + timeout
    handles = _job_member_handles(kernel, job, deadline)
    try:
        if not kernel.TerminateJobObject(job, 1):
            raise OSError("Owned Job termination denied")
        class Accounting(ctypes.Structure):
            _fields_ = [
                (name, ctypes.c_int64)
                for name in ["user", "kernel", "period_user", "period_kernel"]
            ] + [
                (name, wintypes.DWORD)
                for name in ["faults", "total", "active", "terminated"]
            ]
        while True:
            info = Accounting()
            if not kernel.QueryInformationJobObject(
                job, 1, ctypes.byref(info), ctypes.sizeof(info), None
            ):
                raise OSError("Owned Job accounting unavailable")
            if not info.active:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("Owned Job cleanup unconfirmed")
            time.sleep(0.02)
        for process in handles:
            remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
            result = kernel.WaitForSingleObject(process, remaining_ms)
            if result == 258:
                raise TimeoutError("Owned Job member exit unconfirmed")
            if result != 0:
                raise OSError("Owned Job member exit unavailable")
    finally:
        for process in handles:
            kernel.CloseHandle(process)


def close_worker_job(job: int) -> None:
    _api().CloseHandle(job)
