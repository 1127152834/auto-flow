from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict
from pathlib import Path
from typing import Any, TextIO, TypeVar

_INSTALL_DIRECTORY = re.compile(
    r"^chromium-(?P<version>[0-9]+(?:\.[0-9]+){3,4})(?P<pro>-pro)?$",
    re.IGNORECASE,
)
_COMMANDS = frozenset({"catalog", "license", "download"})
_T = TypeVar("_T")


def run_worker(
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
) -> int:
    try:
        command = _read_command(stdin)
        cache_dir = _cache_dir(command)
        os.environ["CLOAKBROWSER_CACHE_DIR"] = str(cache_dir)
        # The wrapper adapter is deliberately imported only after the task cache is set.
        from autoflow.providers.kernel.cloakbrowser import (
            download_with_wrapper,
            load_licensed_catalog,
            validate_license_with_wrapper,
        )

        kind = command["command"]
        if kind == "catalog":
            releases = _quiet_call(load_licensed_catalog)
            _write(stdout, {"type": "catalog", "releases": [_release(item) for item in releases]})
        elif kind == "license":
            key = _required_secret(command)
            status = _quiet_call(lambda: validate_license_with_wrapper(key))
            _write(stdout, {"type": "license", "status": asdict(status)})
        else:
            _write(stdout, {"type": "progress", "state": "downloading", "progress": None})
            executable = _quiet_call(
                lambda: download_with_wrapper(
                    license_key=_optional_secret(command),
                    browser_version=_required_string(command, "requestedVersion"),
                    release_channel=_required_string(command, "releaseChannel"),
                )
            )
            _write(stdout, {"type": "progress", "state": "verifying", "progress": None})
            result = _download_result(cache_dir, Path(executable))
            _write(stdout, {"type": "progress", "state": "extracting", "progress": None})
            _write(stdout, {"type": "completed", **result})
        return 0
    except Exception:  # noqa: BLE001 -- wrapper failures and secrets stay inside the worker.
        _write(stdout, {"type": "error", "error": "Kernel worker failed"})
        return 1


def _read_command(stdin: TextIO) -> dict[str, Any]:
    line = stdin.readline()
    if not line or stdin.readline():
        raise ValueError("worker expects one command")
    value = json.loads(line)
    if not isinstance(value, dict) or value.get("command") not in _COMMANDS:
        raise ValueError("unsupported worker command")
    return value


def _cache_dir(command: dict[str, Any]) -> Path:
    value = command.get("cacheDir")
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise ValueError("cacheDir must be absolute")
    path = Path(value)
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _required_secret(command: dict[str, Any]) -> str:
    value = _required_string(command, "licenseKey")
    if not value.strip():
        raise ValueError("license is required")
    return value


def _optional_secret(command: dict[str, Any]) -> str | None:
    value = command.get("licenseKey")
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("license must be a string")
    return value


def _required_string(command: dict[str, Any], key: str) -> str:
    value = command.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a string")
    return value


def _release(value: object) -> dict[str, object | None]:
    return {
        "version": _attribute(value, "version"),
        "releaseChannel": _attribute(value, "resolved_channel"),
    }


def _attribute(value: object, name: str) -> str | None:
    item = getattr(value, name, None)
    return str(item) if item is not None else None


def _download_result(cache_dir: Path, executable: Path) -> dict[str, str]:
    resolved_cache = cache_dir.resolve()
    resolved_executable = executable.resolve(strict=True)
    relative = resolved_executable.relative_to(resolved_cache)
    if len(relative.parts) < 2:
        raise ValueError("download is outside an install directory")
    match = _INSTALL_DIRECTORY.fullmatch(relative.parts[0])
    if match is None:
        raise ValueError("download directory is invalid")
    return {
        "resolvedVersion": match.group("version"),
        "executableRelativePath": relative.as_posix(),
    }


def _write(stdout: TextIO, message: dict[str, object]) -> None:
    stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
    stdout.flush()


def _quiet_call(call: Callable[[], _T]) -> _T:
    # Third-party wrapper output is neither trusted JSON nor safe for license logs.
    with (
        open(os.devnull, "w", encoding="utf-8") as sink,
        redirect_stdout(sink),
        redirect_stderr(sink),
    ):
        return call()
