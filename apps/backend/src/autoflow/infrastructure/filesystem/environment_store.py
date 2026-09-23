from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import sys
from pathlib import Path

from autoflow.infrastructure.process.browser_processes import process_identity_is_alive


class EnvironmentStore:
    """Generation-addressed browser work copies. File contents are never logged."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).absolute()
        self.root.mkdir(parents=True, exist_ok=True)

    def instance_dir(self, instance_id: str) -> Path:
        path = self.root / "instances" / instance_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def generation_dir(self, environment_id: str, generation: int) -> Path:
        return self.root / "environments" / environment_id / "generations" / str(generation)

    def prepare_instance(self, instance_id: str, source: Path | None = None) -> Path:
        target = self.instance_dir(instance_id)
        if source is None:
            return target
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target, ignore=_ignore_runtime_locks)
        _clear_runtime_locks(target)
        return target

    def restore_generation(
        self, environment_id: str, generation: int, instance_id: str
    ) -> Path:
        source = self.generation_dir(environment_id, generation)
        if not source.is_dir():
            raise FileNotFoundError(environment_id)
        return self.prepare_instance(instance_id, source)

    def stage_candidate(self, save_operation_id: str, instance_id: str) -> str:
        source = self.instance_dir(instance_id)
        candidate = self.root / "candidates" / save_operation_id
        if candidate.exists():
            shutil.rmtree(candidate)
        shutil.copytree(source, candidate, ignore=_ignore_runtime_locks)
        _clear_runtime_locks(candidate)
        digest = self.digest(candidate)
        (candidate / ".digest").write_text(digest, encoding="utf-8")
        return digest

    def publish(
        self, environment_id: str, generation: int, save_operation_id: str
    ) -> str:
        candidate = self.root / "candidates" / save_operation_id
        if not candidate.is_dir():
            raise FileNotFoundError(save_operation_id)
        target = self.generation_dir(environment_id, generation)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError(target)
        candidate.rename(target)
        digest = (target / ".digest").read_text(encoding="utf-8").strip()
        pointer = self.root / "environments" / environment_id / "current.json"
        pointer.write_text(
            json.dumps(
                {"contentGeneration": generation, "digest": digest},
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        return digest

    def discard_candidate(self, save_operation_id: str) -> None:
        candidate = self.root / "candidates" / save_operation_id
        if candidate.exists():
            shutil.rmtree(candidate)

    def close_instance(self, instance_id: str) -> None:
        path = self.root / "instances" / instance_id
        if path.exists():
            shutil.rmtree(path)

    def runtime_lock_present(self, instance_id: str) -> bool:
        """True while a Chromium process still holds this work copy open.

        Copying a profile out from under a live browser produces a torn login
        state, so callers must refuse instead of reporting a clean close.
        """

        directory = self.root / "instances" / instance_id
        if not directory.is_dir():
            return False
        if sys.platform == "darwin":
            lock = directory / "SingletonLock"
            try:
                target = os.readlink(lock)
            except OSError:
                pass
            else:
                host, separator, pid_text = target.rpartition("-")
                if (separator and not lock.exists() and host == socket.gethostname() and pid_text.isascii()
                    and pid_text.isdecimal() and len(pid_text) <= 10
                    and 0 < int(pid_text) < 2**31
                    and not process_identity_is_alive(int(pid_text), None)):
                    # A killed Chromium can leave a live socket pathname behind.
                    # A changed lock or any uncertain owner remains busy.
                    try:
                        return os.readlink(lock) != target
                    except OSError:
                        return True
        return any(os.path.lexists(directory / name) for name in _RUNTIME_LOCK_NAMES)

    def digest(self, directory: Path) -> str:
        digest = hashlib.sha256()
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.name == ".digest" or path.name in _RUNTIME_LOCK_NAMES:
                continue
            relative = path.relative_to(directory).as_posix().encode()
            digest.update(relative)
            digest.update(b"\0")
            digest.update(str(path.stat().st_size).encode())
            digest.update(b"\0")
        return digest.hexdigest()


_RUNTIME_LOCK_NAMES = {
    "SingletonLock",
    "SingletonCookie",
    "SingletonSocket",
    "DevToolsActivePort",
    "lockfile",
}


def _ignore_runtime_locks(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in _RUNTIME_LOCK_NAMES}


def _clear_runtime_locks(root: Path) -> None:
    for path in root.rglob("*"):
        if path.name in _RUNTIME_LOCK_NAMES:
            path.unlink(missing_ok=True)
