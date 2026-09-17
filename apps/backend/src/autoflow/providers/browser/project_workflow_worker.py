from __future__ import annotations

import asyncio
import hashlib
import json
import os
import queue
import sys
from contextlib import nullcontext, redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from threading import Event, Thread
from typing import Any, TextIO
from uuid import uuid4

from autoflow.providers.browser.proxy_relay import BrowserProxyRelay
from autoflow.providers.browser.worker import _optional_proxy, browser_launch_options
from autoflow.providers.browser.workflow_executor import WorkflowExecutor

PROTOCOL_VERSION = 1
MAX_JSONL_BYTES = 1024 * 1024
MAX_SCREENSHOT_BYTES = 20 * 1024 * 1024


class ProtocolFailure(Exception):
    def __init__(self, code: str = "WORKFLOW_PARENT_UNAVAILABLE") -> None:
        super().__init__(code)
        self.code = code


class _CleanupGuard:
    def __init__(self, context_manager: Any) -> None:
        self.context_manager = context_manager
        self.failed = False

    def __enter__(self) -> Any:
        return self.context_manager.__enter__()

    def __exit__(self, *error: object) -> object:
        try:
            return self.context_manager.__exit__(*error)
        except BaseException:
            self.failed = True
            raise


class _Input:
    def __init__(self, stdin: TextIO) -> None:
        self.stdin = stdin
        self.messages: queue.Queue[dict[str, Any] | BaseException] = queue.Queue()

    def first(self) -> dict[str, Any]:
        return _read_jsonl(self.stdin)

    def start(self) -> None:
        Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        try:
            while True:
                self.messages.put(_read_jsonl(self.stdin))
        except BaseException as exc:  # noqa: BLE001
            self.messages.put(exc)

    async def next(self) -> dict[str, Any]:
        item = await asyncio.to_thread(self.messages.get)
        if isinstance(item, BaseException):
            raise ProtocolFailure from item
        return item


def run_worker(stopped: Event, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    input_stream = _Input(stdin)
    try:
        command = input_stream.first()
        input_stream.start()
        return asyncio.run(_run(command, stopped, input_stream, stdout))
    except BaseException:  # noqa: BLE001 -- stdout is a secret-free protocol.
        _write(stdout, {"type": "error", "code": "WORKFLOW_WORKER_FAILED", "message": "工作流执行进程失败"})
        return 1


async def _run(command: dict[str, Any], stopped: Event, incoming: _Input, stdout: TextIO) -> int:
    run_id, generation = _validate_start(command)
    executable = Path(_required_env("CLOAKBROWSER_BINARY_PATH"))
    cache = Path(_required_env("CLOAKBROWSER_CACHE_DIR"))
    if not executable.is_absolute() or not executable.is_file() or not cache.is_absolute():
        raise ProtocolFailure
    browser = command["browser"]
    launch = browser_launch_options(browser, headless=_boolean(browser, "headless"))
    relay_context = BrowserProxyRelay(proxy) if (proxy := _optional_proxy(browser)) else nullcontext()
    stop_requested = stopped.is_set()
    context = None
    relay_guard = _CleanupGuard(relay_context)

    async def emit(kind: str, node_id: str, visit: str, payload: dict[str, object]) -> None:
        nonlocal stop_requested
        event_id = uuid4().hex
        event = {
            "eventId": event_id, "runId": run_id, "executionGeneration": generation,
            "kind": kind, "nodeId": node_id, "nodeVisitId": visit, "attempt": 1,
            "occurredAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"), "payload": payload,
        }
        message = _envelope(command, "event", event=event)
        output_too_large = _jsonl_size(message) > MAX_JSONL_BYTES
        if output_too_large:
            event["kind"] = "nodeAttempt"
            event["payload"] = {
                "status": "failed",
                "error": {
                    "code": "WORKFLOW_OUTPUT_TOO_LARGE",
                    "message": "工作流输出超过协议限制",
                },
            }
            message = _envelope(command, "event", event=event)
        _write(stdout, message)
        while True:
            message = await incoming.next()
            if message.get("type") == "stop" and message.get("executionGeneration") == generation:
                stop_requested = True
                continue
            if (
                message.get("type") != "event_committed"
                or message.get("eventId") != event_id
                or message.get("executionGeneration") != generation
            ):
                raise ProtocolFailure
            if output_too_large:
                raise ProtocolFailure("WORKFLOW_OUTPUT_TOO_LARGE")
            return

    result: dict[str, object] = {"status": "failed", "error": {"code": "WORKFLOW_WORKER_FAILED", "message": "工作流执行进程失败"}}
    cleanup_failed = False
    try:
        with relay_guard as relay:
            launch["proxy"] = {"server": relay.url} if relay is not None else None
            with open(os.devnull, "w", encoding="utf-8") as sink, redirect_stdout(sink), redirect_stderr(sink):  # noqa: ASYNC230
                from cloakbrowser import (  # type: ignore[import-untyped]
                    launch_context_async,
                )
                context = await launch_context_async(**launch)
                context.set_default_timeout(0)
                context.set_default_navigation_timeout(0)
                _write(stdout, _envelope(command, "ready"))
                variables = dict(command.get("variables", {}))
                variables.update(command.get("parameters", {}))
                executor = WorkflowExecutor(
                    context,
                    variables,
                    emit,
                    lambda: stop_requested or stopped.is_set(),
                    lambda page, node_id, visit: _capture_failure_screenshot(
                        command, page, node_id, visit
                    ),
                )
                result = await executor.run(command["executionPlan"])
    except asyncio.CancelledError:
        result = {"status": "cancelled", "error": None}
    except ProtocolFailure as exc:
        message = "工作流输出超过协议限制" if exc.code == "WORKFLOW_OUTPUT_TOO_LARGE" else "父进程通信中断"
        result = {"status": "failed", "error": {"code": exc.code, "message": message}}
    except Exception:  # noqa: BLE001
        result = {"status": "failed", "error": {"code": "WORKFLOW_WORKER_FAILED", "message": "工作流执行进程失败"}}
    finally:
        try:
            if context is not None:
                with open(os.devnull, "w", encoding="utf-8") as sink, redirect_stdout(sink), redirect_stderr(sink):  # noqa: ASYNC230
                    await context.close()
            cleanup_failed = relay_guard.failed
        except Exception:  # noqa: BLE001
            cleanup_failed = True
    if cleanup_failed:
        _write(
            stdout,
            _envelope(
                command,
                "error",
                code="WORKFLOW_CLEANUP_FAILED",
                message="工作流资源清理失败",
            ),
        )
    else:
        _write(stdout, _envelope(command, "finished", status=result["status"], error=result["error"], cleanupConfirmed=True))
    return 0 if not cleanup_failed and result["status"] in {"succeeded", "cancelled"} else 1


def _validate_start(command: dict[str, Any]) -> tuple[str, int]:
    if command.get("type") != "start" or command.get("protocolVersion") != PROTOCOL_VERSION:
        raise ProtocolFailure
    run_id, generation = command.get("runId"), command.get("executionGeneration")
    if not isinstance(run_id, str) or not run_id or type(generation) is not int:
        raise ProtocolFailure
    if not isinstance(command.get("executionPlan"), dict) or not isinstance(command.get("browser"), dict):
        raise ProtocolFailure
    return run_id, generation


async def _capture_failure_screenshot(
    command: dict[str, Any], page: Any, _node_id: str, _visit: str
) -> dict[str, object]:
    artifact_id = str(uuid4())
    unavailable = {
        "artifactId": artifact_id,
        "kind": "screenshot",
        "purpose": "error",
        "availability": "unavailable",
        "relativePath": None,
        "mediaType": None,
        "byteSize": None,
        "sha256": None,
        "createdAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    temporary: Path | None = None
    try:
        if page is None or page.is_closed() or not hasattr(page, "screenshot"):
            return {**unavailable, "unavailableReason": "SCREENSHOT_PAGE_UNAVAILABLE"}
        directory, relative_directory = _artifact_directory(command)
        content = await page.screenshot(type="png")
        if not isinstance(content, bytes) or not content or len(content) > MAX_SCREENSHOT_BYTES:
            raise ValueError
        directory.mkdir(parents=True, exist_ok=True)
        directory = directory.resolve(strict=True)
        filename = f"{artifact_id}.png"
        temporary = directory / f".{artifact_id}.tmp"
        destination = directory / filename
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        return {
            **unavailable,
            "availability": "available",
            "relativePath": str(relative_directory / filename),
            "mediaType": "image/png",
            "byteSize": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "unavailableReason": None,
        }
    except Exception:  # noqa: BLE001 -- screenshot failures become safe evidence.
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        return {**unavailable, "unavailableReason": "SCREENSHOT_CAPTURE_FAILED"}


def _artifact_directory(command: dict[str, Any]) -> tuple[Path, PurePosixPath]:
    directory_value = os.environ.get("AUTOFLOW_WORKFLOW_ARTIFACT_DIR")
    relative_value = os.environ.get("AUTOFLOW_WORKFLOW_ARTIFACT_RELATIVE_DIR")
    if not directory_value or not relative_value:
        raise ValueError
    directory = Path(directory_value)
    relative = PurePosixPath(relative_value)
    expected = (
        "runs",
        str(command["runId"]),
        f"generation-{command['executionGeneration']}",
    )
    if (
        not directory.is_absolute()
        or relative.is_absolute()
        or "." in relative.parts
        or ".." in relative.parts
        or relative.parts != expected
        or "\\" in relative_value
    ):
        raise ValueError
    return directory, relative


def _envelope(command: dict[str, Any], kind: str, **values: object) -> dict[str, object]:
    return {"type": kind, "protocolVersion": PROTOCOL_VERSION, "runId": command["runId"], "executionGeneration": command["executionGeneration"], **values}


def _read_jsonl(stdin: TextIO) -> dict[str, Any]:
    line = stdin.readline(MAX_JSONL_BYTES + 1)
    if not line or len(line.encode("utf-8")) > MAX_JSONL_BYTES or not line.endswith("\n"):
        raise ProtocolFailure
    value = json.loads(line)
    if not isinstance(value, dict):
        raise ProtocolFailure
    return value


def _write(stdout: TextIO, message: dict[str, object]) -> None:
    raw = json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n"
    if len(raw.encode("utf-8")) > MAX_JSONL_BYTES:
        raise ProtocolFailure("WORKFLOW_OUTPUT_TOO_LARGE")
    stdout.write(raw)
    stdout.flush()


def _jsonl_size(message: dict[str, object]) -> int:
    return len(
        (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
    )


def _required_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise ProtocolFailure
    return value


def _boolean(values: dict[str, Any], key: str) -> bool:
    value = values.get(key)
    if not isinstance(value, bool):
        raise ProtocolFailure
    return value
