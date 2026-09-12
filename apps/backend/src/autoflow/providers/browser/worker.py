from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from contextlib import nullcontext, redirect_stderr, redirect_stdout, suppress
from pathlib import Path
from threading import Event, Thread
from typing import Any, TextIO

from autoflow.providers.browser.proxy_relay import BrowserProxyRelay

_FORBIDDEN_ARGS = (
    "--user-data-dir",
    "--fingerprint",
    "--proxy-server",
    "--load-extension",
)


def run_worker(
    stopped: Event,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
) -> int:
    try:
        command = _read_command(stdin)
        Thread(target=_watch_stdin, args=(stdin, stopped), daemon=True).start()
        return asyncio.run(_run(command, stopped, stdout))
    except BaseException:  # noqa: BLE001 -- browser and secret details stay isolated.
        _write(stdout, {"type": "error", "error": "Test browser worker failed"})
        return 1


async def _run(command: dict[str, Any], stopped: Event, stdout: TextIO) -> int:
    executable = Path(_required_string(os.environ, "CLOAKBROWSER_BINARY_PATH"))
    cache = Path(_required_string(os.environ, "CLOAKBROWSER_CACHE_DIR"))
    if not executable.is_absolute() or not executable.is_file() or not cache.is_absolute():
        raise ValueError("worker paths are invalid")
    session_id = _required_string(command, "sessionId")
    profile_id = _required_string(command, "profileId")
    seed = command.get("fingerprintSeed")
    if type(seed) is not int or not 10000 <= seed <= 99999:
        raise ValueError("fingerprintSeed is invalid")
    expert_args = _string_list(command, "expertArgs")
    if any(
        arg.split(maxsplit=1)[0].split("=", 1)[0] in _FORBIDDEN_ARGS
        for arg in expert_args
    ):
        raise ValueError("reserved browser argument")
    expert_args = [
        arg for arg in expert_args if arg.split("=", 1)[0] != "--headless"
    ]

    from cloakbrowser import launch_context_async  # type: ignore[import-untyped]

    upstream_proxy = _optional_proxy(command)
    relay_context = (
        BrowserProxyRelay(upstream_proxy) if upstream_proxy is not None else nullcontext()
    )
    launch: dict[str, Any] = {
        "headless": False,
        "args": [*expert_args, f"--fingerprint={seed}"],
        "stealth_args": True,
        "user_agent": _optional_string(command, "userAgent"),
        "locale": _optional_string(command, "locale"),
        "timezone": _optional_string(command, "timezone"),
        "color_scheme": _optional_string(command, "colorScheme"),
        "geoip": _boolean(command, "geoip"),
        "humanize": _boolean(command, "humanize"),
        "human_preset": _required_string(command, "humanPreset"),
        "extension_paths": _string_list(command, "extensionPaths"),
        "license_key": _optional_string(command, "licenseKey"),
        "browser_version": _required_string(command, "browserVersion"),
        "release_channel": _required_string(command, "releaseChannel"),
    }
    viewport = command.get("viewport")
    if viewport is not None:
        if (
            not isinstance(viewport, dict)
            or type(viewport.get("width")) is not int
            or type(viewport.get("height")) is not int
        ):
            raise ValueError("viewport is invalid")
        launch["viewport"] = viewport

    context = None
    try:
        with relay_context as relay:
            launch["proxy"] = {"server": relay.url} if relay is not None else None
            try:
                with (
                    open(os.devnull, "w", encoding="utf-8") as sink,  # noqa: ASYNC230
                    redirect_stdout(sink),
                    redirect_stderr(sink),
                ):
                    context = await launch_context_async(**launch)
                    page = await context.new_page()
                    warning = None
                    start_url = _required_string(command, "startUrl")
                    if start_url != "about:blank":
                        try:
                            await page.goto(
                                start_url,
                                wait_until="domcontentloaded",
                                timeout=15_000,
                            )
                        except Exception:  # noqa: BLE001 -- retain usable window.
                            warning = "起始网址加载失败，浏览器已保留，可手动重试"
                _write(
                    stdout,
                    {
                        "type": "ready",
                        "sessionId": session_id,
                        "profileId": profile_id,
                        "fingerprintSeed": seed,
                        "warning": warning,
                    },
                )
                while not stopped.is_set():
                    try:
                        if not context.pages:
                            break
                    except Exception:  # noqa: BLE001 -- closed context is normal.
                        break
                    await asyncio.sleep(0.1)
                return 0
            finally:
                if context is not None:
                    with suppress(BaseException):
                        await context.close()
    finally:
        shutil.rmtree(cache, ignore_errors=True)


def _read_command(stdin: TextIO) -> dict[str, Any]:
    line = stdin.readline()
    if not line:
        raise ValueError("worker expects one command")
    value = json.loads(line)
    if not isinstance(value, dict):
        raise TypeError("worker command must be an object")
    return value


def _watch_stdin(stdin: TextIO, stopped: Event) -> None:
    if stdin.read():
        os._exit(1)
    stopped.set()


def _required_string(values: dict[str, Any] | os._Environ[str], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{key} must be a string")
    return value


def _optional_string(values: dict[str, Any], key: str) -> str | None:
    value = values.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string")
    return value


def _optional_proxy(values: dict[str, Any]) -> dict[str, str] | None:
    value = values.get("proxy")
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError("proxy must be an object")
    proxy = {key: value.get(key) for key in ("server", "username", "password")}
    if not all(isinstance(item, str) for item in proxy.values()):
        raise TypeError("proxy values must be strings")
    return proxy  # type: ignore[return-value]


def _string_list(values: dict[str, Any], key: str) -> list[str]:
    value = values.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{key} must be a list of strings")
    return value


def _boolean(values: dict[str, Any], key: str) -> bool:
    value = values.get(key)
    if not isinstance(value, bool):
        raise TypeError(f"{key} must be a boolean")
    return value


def _write(stdout: TextIO, message: dict[str, object]) -> None:
    stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
    stdout.flush()
