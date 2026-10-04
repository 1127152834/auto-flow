from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import sys
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from autoflow.domain.environments.identity import request_from_identity
from autoflow.domain.workflows.runtime import WorkflowRuntimeError
from autoflow.infrastructure.process.browser_processes import process_identity_is_alive


def candidate_directory_name(save_operation_id: str) -> str:
    """Directory name for a staged save. ``environment:generation`` ids hold a colon, which
    Windows cannot use in a path; other platforms keep the historical name so staged
    candidates written by earlier builds are still found."""
    if sys.platform == "win32":
        return save_operation_id.replace(":", "~")
    return save_operation_id


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
        self, environment_id: str, generation: int, instance_id: str, *, identity_package: dict[str, Any] | None = None
    ) -> Path:
        source = self.generation_dir(environment_id, generation)
        if not source.is_dir():
            raise FileNotFoundError(environment_id)
        if identity_package is not None and self.generation_identity(environment_id, generation) != identity_package:
            raise WorkflowRuntimeError("ENVIRONMENT_IDENTITY_UNVERIFIED", "环境内容与身份资料不一致", 409)
        return self.prepare_instance(instance_id, source)

    def stage_candidate(
        self, save_operation_id: str, instance_id: str, *, identity_package: dict[str, Any] | None = None,
        keep_browser_cache: bool = False,
    ) -> str:
        """Stage an instance for saving; browser caches are left behind unless the environment keeps them."""
        return self._stage_candidate(
            save_operation_id, self.instance_dir(instance_id), identity_package,
            exclude=_RUNTIME_LOCK_NAMES if keep_browser_cache else _RUNTIME_LOCK_NAMES | BROWSER_CACHE_NAMES,
        )

    def stage_configuration(self, save_operation_id: str, environment_id: str, generation: int, identity_package: dict[str, Any]) -> str:
        return self._stage_candidate(save_operation_id, self.generation_dir(environment_id, generation), identity_package)

    def _stage_candidate(
        self, save_operation_id: str, source: Path, identity_package: dict[str, Any] | None,
        exclude: frozenset[str] | set[str] = frozenset(),
    ) -> str:
        candidate = self.root / "candidates" / candidate_directory_name(save_operation_id)
        if candidate.exists():
            shutil.rmtree(candidate)
        ignored = exclude | _RUNTIME_LOCK_NAMES
        shutil.copytree(source, candidate, ignore=lambda _directory, names: {name for name in names if name in ignored})
        _clear_runtime_locks(candidate)
        (candidate / ".digest-version").write_text("2", encoding="utf-8")
        # The host's database is authoritative, not a file a browser could alter.
        identity_path = candidate / ".autoflow-identity.json"
        identity_path.unlink(missing_ok=True)
        if identity_package is not None:
            request_from_identity(identity_package)
            identity_path.write_text(json.dumps(identity_package, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        publication = candidate / ".autoflow-publication"
        publication.unlink(missing_ok=True)
        publication.write_text(save_operation_id, encoding="utf-8")
        digest = self.digest(candidate)
        (candidate / ".digest").write_text(digest, encoding="utf-8")
        return digest

    def generation_identity(self, environment_id: str, generation: int) -> dict[str, Any] | None:
        path = self.generation_dir(environment_id, generation) / ".autoflow-identity.json"
        if not path.exists():
            return None
        try:
            if path.is_symlink() or self.digest(path.parent) != (path.parent / ".digest").read_text(encoding="utf-8").strip():
                raise ValueError
            identity = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            raise WorkflowRuntimeError("ENVIRONMENT_IDENTITY_UNVERIFIED", "保存环境的身份资料校验失败", 409) from None
        request_from_identity(identity)
        return cast(dict[str, Any], identity)

    def publish(
        self, environment_id: str, generation: int, save_operation_id: str
    ) -> str:
        candidate = self.root / "candidates" / candidate_directory_name(save_operation_id)
        if not candidate.is_dir():
            raise FileNotFoundError(save_operation_id)
        target = self.generation_dir(environment_id, generation)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            marker = target / ".autoflow-publication"
            if marker.is_symlink() or not marker.is_file() or marker.read_text(encoding="utf-8") != save_operation_id:
                raise WorkflowRuntimeError("SAVE_GENERATION_CONFLICT", "目标代次已被其他保存占用，请先核对原保存结果", 409)
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

    def generations(self, environment_id: str) -> list[int]:
        directory = self.root / "environments" / environment_id / "generations"
        if not directory.is_dir():
            return []
        return sorted(int(path.name) for path in directory.iterdir() if path.is_dir() and path.name.isdecimal())

    def trash_generation(self, environment_id: str, generation: int) -> None:
        """Take a generation out of the addressable store in one rename; ``purge_trash`` deletes it later."""
        trash = self.root / "trash"
        trash.mkdir(exist_ok=True)
        self.generation_dir(environment_id, generation).rename(trash / f"{environment_id}-{generation}-{uuid4().hex}")

    def purge_trash(self) -> None:
        trash = self.root / "trash"
        if trash.is_dir():
            for path in trash.iterdir():
                shutil.rmtree(path, ignore_errors=True)

    def generation_bytes(self, environment_id: str, generation: int) -> int:
        return sum(path.stat().st_size for path in self.generation_dir(environment_id, generation).rglob("*") if path.is_file())

    def discard_candidate(self, save_operation_id: str) -> None:
        candidate = self.root / "candidates" / candidate_directory_name(save_operation_id)
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
        version_file = directory / ".digest-version"
        version = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else "1"
        if version not in {"1", "2"}:
            raise ValueError("Unsupported environment digest version")
        digest = hashlib.sha256()
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.name in {".digest", ".digest-version"} or path.name in _RUNTIME_LOCK_NAMES:
                continue
            relative = path.relative_to(directory).as_posix().encode()
            digest.update(relative)
            digest.update(b"\0")
            digest.update(str(path.stat().st_size).encode())
            digest.update(b"\0")
            if version == "2":
                with path.open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
            elif path.name in {".autoflow-identity.json", ".autoflow-publication"}:
                digest.update(path.read_bytes())
        return digest.hexdigest()


_RUNTIME_LOCK_NAMES = {
    "SingletonLock",
    "SingletonCookie",
    "SingletonSocket",
    "DevToolsActivePort",
    "lockfile",
}


# Remediation M3 R3-09: rebuildable Chromium caches are not saved with an environment.
# Service Worker data stays (sites keep logins there); an environment may keep every cache instead.
BROWSER_CACHE_NAMES = frozenset({
    "Cache",
    "Code Cache",
    "GPUCache",
    "GrShaderCache",
    "GraphiteDawnCache",
    "ShaderCache",
    "DawnCache",
    "DawnGraphiteCache",
    "DawnWebGPUCache",
    "Crashpad",
    "component_crx_cache",
    "optimization_guide_model_store",
})


def _ignore_runtime_locks(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in _RUNTIME_LOCK_NAMES}


def _clear_runtime_locks(root: Path) -> None:
    for path in root.rglob("*"):
        if path.name in _RUNTIME_LOCK_NAMES:
            path.unlink(missing_ok=True)
