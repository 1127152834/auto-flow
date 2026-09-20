"""POSIX browser ownership without trusting ps command text or recycled PIDs."""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

# PID -> (process group, kernel process-start identifier).
OwnedProcesses = dict[int, tuple[int, int]]


@lru_cache(maxsize=1)
def _libproc() -> ctypes.CDLL:
    library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    library.proc_pid_rusage.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
    library.proc_pid_rusage.restype = ctypes.c_int
    library.proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    library.proc_pidpath.restype = ctypes.c_int
    return library


@lru_cache(maxsize=1)
def _sysctl_library() -> ctypes.CDLL:
    libc = ctypes.CDLL(None, use_errno=True)
    libc.sysctl.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_uint,
                           ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
                           ctypes.c_void_p, ctypes.c_size_t]
    libc.sysctl.restype = ctypes.c_int
    return libc


def process_birth(pid: int) -> int | None:
    try:
        if sys.platform == "darwin":
            # macOS SDK sys/resource.h: rusage_info_v0 has UUID + ten uint64 fields;
            # ri_proc_start_abstime is field 8 after the UUID (offset 80).
            library = _libproc()
            buffer = ctypes.create_string_buffer(96)
            if library.proc_pid_rusage(pid, 0, buffer) != 0:
                return None
            return int.from_bytes(buffer.raw[80:88], sys.byteorder)
        raw = Path(f"/proc/{pid}/stat").read_text()
        return int(raw[raw.rfind(")") + 2:].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _native_arguments(pid: int) -> tuple[Path, list[str], dict[str, str]] | None:
    try:
        if sys.platform == "darwin":
            library = _libproc()
            path = ctypes.create_string_buffer(4096)
            if library.proc_pidpath(pid, path, len(path)) <= 0:
                return None
            executable = Path(os.fsdecode(path.value))
            libc = _sysctl_library()
            mib = (ctypes.c_int * 3)(1, 49, pid)  # CTL_KERN, KERN_PROCARGS2, pid.
            size = ctypes.c_size_t()
            if libc.sysctl(mib, 3, None, ctypes.byref(size), None, 0) != 0:
                return None
            buffer = ctypes.create_string_buffer(size.value)
            if libc.sysctl(mib, 3, buffer, ctypes.byref(size), None, 0) != 0:
                return None
            raw = buffer.raw[:size.value]
            count = int.from_bytes(raw[:4], sys.byteorder)
            start = raw.index(b"\0", 4) + 1  # Skip the kernel's executable path and padding.
            while raw[start:start + 1] == b"\0":
                start += 1
            values = raw[start:].split(b"\0")
            arguments = [os.fsdecode(value) for value in values[:count]]
            environment = values[count:]
        else:
            executable = Path(os.readlink(f"/proc/{pid}/exe"))
            arguments = [os.fsdecode(value) for value in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0") if value]
            environment = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
        env = {os.fsdecode(key): os.fsdecode(value) for entry in environment if b"=" in entry
               for key, value in [entry.split(b"=", 1)]}
        return executable, arguments, env
    except (OSError, ValueError):
        return None


def _belongs_to_run(pid: int, directory: Path, executable: Path) -> bool | None:
    native = _native_arguments(pid)
    if native is None:
        return None
    actual, arguments, environment = native
    if environment.get("CLOAKBROWSER_CACHE_DIR") != str(directory):
        return False
    # The worker and Playwright driver also retain the unique inherited run marker.
    if actual.resolve() == Path(sys.executable).resolve():
        return True
    # Framework Python launches Python.app; sys.executable names its launcher.
    current = _native_arguments(os.getpid())
    if current is not None and actual.resolve() == current[0].resolve():
        return True
    if actual.parts[-3:] == ("playwright", "driver", "node") and any(
        arg.endswith("/playwright/driver/package/cli.js") for arg in arguments
    ) and "run-driver" in arguments:
        return True
    bundle = next((parent for parent in executable.parents if parent.suffix == ".app"), executable.parent)
    if actual != executable and not actual.is_relative_to(bundle):
        return False
    return any(
        arg.startswith("--user-data-dir=")
        and Path(arg.removeprefix("--user-data-dir=")).is_relative_to(directory)
        for arg in arguments
    )


def capture_processes(
    pid: int, birth: int | None, directory: Path | None, executable: Path | None,
    previous: OwnedProcesses | None = None, *, strict_ownership: bool = False,
) -> OwnedProcesses:
    output = subprocess.check_output(["ps", "-ax", "-o", "pid=,ppid=,pgid=,command="], text=True)
    rows = [line.split(None, 3) for line in output.splitlines()]
    identities = {int(row[0]): process_birth(int(row[0])) for row in rows}
    uncertain = {
        item: identity for item, identity in (previous or {}).items()
        if identities.get(item) is None and _process_exists(item)
    }
    if birth is not None and identities.get(pid) is None and _process_exists(pid):
        uncertain[pid] = (pid, birth)  # The worker was launched as this session/group leader.
    owned = {item for item, (_, started) in (previous or {}).items() if identities.get(item) == started}
    if birth is not None and identities.get(pid) == birth:
        owned.add(pid)
    if directory is not None and executable is not None:
        directory, executable = directory.resolve(), executable.resolve()
        for row in rows:
            item = int(row[0])
            # Text is only a cheap candidate filter. Native executable, argv and the
            # inherited per-run marker make the ownership decision below.
            command = row[3] if len(row) == 4 else ""
            if (str(directory) in command or "--test-browser-worker" in command
                or "--workflow-worker" in command or "/playwright/driver/" in command):
                belongs = _belongs_to_run(item, directory, executable)
                if belongs is None and strict_ownership and _process_exists(item):
                    raise RuntimeError("Candidate browser process ownership is unavailable")
                if belongs:
                    owned.add(item)
    old: set[int] = set()
    while old != owned:
        old = owned.copy()
        owned.update(int(row[0]) for row in rows if int(row[1]) in owned)
    result = dict(uncertain)
    for row in rows:
        item = int(row[0])
        started = identities[item]
        if item in owned:
            if started is None and _process_exists(item):
                raise RuntimeError("Owned browser process identity is unavailable")
            if started is not None:
                confirmed = process_birth(item)
                if confirmed == started or (confirmed is None and _process_exists(item)):
                    result[item] = (int(row[2]), started)
    return result


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def living_processes(owned: OwnedProcesses) -> OwnedProcesses:
    live = {}
    for pid, identity in owned.items():
        birth = process_birth(pid)
        if birth == identity[1] or (birth is None and _process_exists(pid)):
            live[pid] = identity
    return live


def signal_processes(owned: OwnedProcesses, number: int) -> None:
    if sys.platform == "win32":
        raise RuntimeError("POSIX process groups are unavailable on Windows")
    # A still-live original member proves that its group has not been recycled.
    live = living_processes(owned)
    groups = {group for group, _ in live.values()}
    for group in sorted(groups, key=lambda item: item == os.getpgrp()):
        if not any(identity[0] == group and process_birth(pid) == identity[1] for pid, identity in live.items()):
            continue
        try:
            os.killpg(group, number)
        except ProcessLookupError:
            pass
        except PermissionError:
            if any(identity[0] == group for identity in living_processes(live).values()):
                raise
