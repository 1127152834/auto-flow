from __future__ import annotations

import asyncio
import hashlib
import json
import os
import queue
import sys
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from threading import Event, Thread
from typing import Any, Protocol, TextIO
from uuid import uuid4

from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.project_runs.worker_commands import project_command_id
from autoflow.infrastructure.filesystem.project_workflow_artifacts import (
    ProjectArtifactWriter,
)
from autoflow.providers.browser.project_graph import (
    ProjectGraphExecutor,
    _ProjectRegistry,
)
from autoflow.providers.browser.proxy_relay import BrowserProxyRelay
from autoflow.providers.browser.worker import _optional_proxy, browser_launch_options
from autoflow.providers.browser.workflow_worker import (
    _WorkerCommandBus,
    _WorkerCredentialReader,
)
from autoflow.providers.integrations.gateway import WorkflowIntegrationGateway
from autoflow.providers.model import WorkflowModelGateway

PROTOCOL_VERSION = 1
MAX_JSONL_BYTES = 1024 * 1024
MAX_EVENT_JSONL_BYTES = 16 * 1024 * 1024
MAX_SCREENSHOT_BYTES = 20 * 1024 * 1024
FAILURE_SCREENSHOT_TIMEOUT_SECONDS = 5.0


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
        self.credentials: _WorkerCredentialReader | None = None
        self.generation: int | None = None

    def first(self) -> dict[str, Any]:
        return _read_jsonl(self.stdin)

    def start(self) -> None:
        Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        try:
            while True:
                message = _read_jsonl(self.stdin)
                if self.credentials is not None:
                    if type(message.get("executionGeneration")) is not int or message.get("executionGeneration") != self.generation:
                        raise ProtocolFailure
                    if message.get("type") == "credential:result":
                        self.credentials.receive(message)
                        continue
                    if message.get("type") == "stop":
                        self.credentials.close()
                self.messages.put(message)
        except BaseException as exc:  # noqa: BLE001
            if self.credentials is not None:
                self.credentials.close()
            self.messages.put(exc)

    async def next(self) -> dict[str, Any]:
        # The stdin reader remains the only blocking thread. Cancelling a
        # to_thread(queue.get) would leave an abandoned consumer stealing ACKs.
        while True:
            try:
                item = self.messages.get_nowait()
                break
            except queue.Empty:
                await asyncio.sleep(0.01)
        if isinstance(item, BaseException):
            raise ProtocolFailure from item
        return item


class _Incoming(Protocol):
    async def next(self) -> dict[str, Any]: ...


class _Control:
    """One async reader dispatches control and ACKs independently of actions."""

    def __init__(self, incoming: _Incoming, generation: int, stopped: Event, command_bus: _WorkerCommandBus | None = None) -> None:
        self.incoming, self.generation, self.stopped = incoming, generation, stopped
        self.stop_requested = False
        self.command_bus = command_bus
        self.failure: ProtocolFailure | None = None
        self.pending: dict[str, asyncio.Future[None]] = {}
        self.capabilities: dict[str, asyncio.Future[dict[str, Any]]] = {}

    @property
    def cancelled(self) -> bool:
        return self.stop_requested or self.stopped.is_set() or self.failure is not None

    async def read(self) -> None:
        try:
            while True:
                message = await self.incoming.next()
                if message.get("executionGeneration") != self.generation:
                    raise ProtocolFailure
                if message.get("type") == "stop":
                    self.stop_requested = True
                    if self.command_bus is not None:
                        self.command_bus.close()
                    continue
                if message.get("type") in {"input_prompt_result", "js_script_result", "webhook_result", "proxy:result"} and self.command_bus is not None:
                    self.command_bus.receive(message)
                    continue
                if message.get("type") == "capability_result":
                    command_id = message.get("commandId")
                    if command_id not in self.capabilities or ("result" in message) == ("error" in message):
                        raise ProtocolFailure
                    capability_waiter = self.capabilities.pop(command_id)
                    if not capability_waiter.done():
                        capability_waiter.set_result(message)
                    continue
                event_id = message.get("eventId")
                if message.get("type") != "event_committed" or event_id not in self.pending:
                    raise ProtocolFailure
                waiter = self.pending.pop(event_id)
                if not waiter.done():
                    waiter.set_result(None)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 -- EOF and invalid control fail closed.
            self.failure = error if isinstance(error, ProtocolFailure) else ProtocolFailure()
            for waiter in self.pending.values():
                if not waiter.done():
                    waiter.set_result(None)
            self.pending.clear()
            for capability_waiter in self.capabilities.values():
                if not capability_waiter.done():
                    capability_waiter.set_exception(self.failure)
            self.capabilities.clear()

    async def wait_cancelled(self) -> None:
        while not self.cancelled:
            await asyncio.sleep(0.01)

    def check_parent(self) -> None:
        if self.failure is not None:
            raise self.failure


def run_worker(stopped: Event, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    input_stream = _Input(stdin)
    try:
        command = input_stream.first()
        run_id, generation = _validate_start(command)
        input_stream.generation = generation
        input_stream.credentials = _WorkerCredentialReader(
            stopped, stdout, run_id,
            protocol_metadata={"protocolVersion": PROTOCOL_VERSION, "executionGeneration": generation},
        )
        input_stream.start()
        return asyncio.run(_run(command, stopped, input_stream, stdout))
    except BaseException:  # noqa: BLE001 -- stdout is a secret-free protocol.
        _write(stdout, {"type": "error", "code": "WORKFLOW_WORKER_FAILED", "message": "工作流执行进程失败"})
        return 1
    finally:
        if input_stream.credentials is not None:
            input_stream.credentials.close()


async def _run(command: dict[str, Any], stopped: Event, incoming: _Incoming, stdout: TextIO) -> int:
    run_id, generation = _validate_start(command)
    plan = command["executionPlan"]
    document = plan.get("document")
    if not isinstance(document, dict):
        document = {"nodes": [{"data": {**node["data"], "moduleType": node["moduleType"]}}
                              for node in plan["nodes"]]}
    browser_runtime = WorkflowRuntime(_ProjectRegistry(None))
    requires_browser = browser_runtime.requires_browser(document)
    for snapshot in plan.get("customModuleDependencies", {}).values():
        if isinstance(snapshot, dict) and isinstance(snapshot.get("workflow"), dict):
            requires_browser = requires_browser or browser_runtime.requires_browser(snapshot["workflow"])
    for snapshot in plan.get("workflowDependencies", {}).values():
        if isinstance(snapshot, dict):
            requires_browser = requires_browser or browser_runtime.requires_browser(snapshot)
    from autoflow.domain.workflows.browser_environment import node_browser_environments
    node_mode = node_browser_environments(document) is not None
    requires_browser = requires_browser and not node_mode
    browser = command["browser"]
    launch = {}
    proxy = None
    if requires_browser:
        executable = Path(_required_env("CLOAKBROWSER_BINARY_PATH"))
        cache = Path(_required_env("CLOAKBROWSER_CACHE_DIR"))
        if not executable.is_absolute() or not executable.is_file() or not cache.is_absolute():
            raise ProtocolFailure
        launch = browser_launch_options(browser, headless=_boolean(browser, "headless"))
        proxy = _optional_proxy(browser)
    relay_context = ExitStack()
    command_bus = _WorkerCommandBus(
        asyncio.get_running_loop(), stopped, stdout, command,
        protocol_metadata={"protocolVersion": PROTOCOL_VERSION, "executionGeneration": generation},
    )
    if isinstance(incoming, _Input) and incoming.credentials is not None:
        command_bus.credentials = incoming.credentials
    control = _Control(incoming, generation, stopped, command_bus)
    control_task = asyncio.create_task(control.read())
    context = None
    integrations = WorkflowIntegrationGateway()
    relay_guard = _CleanupGuard(relay_context)
    exchange_lock = asyncio.Lock()

    async def send_event(kind: str, node_id: str, visit: str, payload: dict[str, object]) -> None:
        event_id = uuid4().hex
        event = {
            "eventId": event_id, "runId": run_id, "executionGeneration": generation,
            "kind": kind, "nodeId": node_id, "nodeVisitId": visit, "attempt": 1,
            "occurredAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"), "payload": payload,
        }
        message = _envelope(command, "event", event=event)
        output_too_large = _jsonl_size(message) > MAX_EVENT_JSONL_BYTES
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
        control.check_parent()
        waiter = asyncio.get_running_loop().create_future()
        control.pending[event_id] = waiter
        _write(stdout, message)
        # A timed-out artifact may still be committed. Keep its ACK identity
        # until the sole reader confirms it; it must never satisfy a newer event.
        await asyncio.shield(waiter)
        control.check_parent()
        if output_too_large:
            raise ProtocolFailure("WORKFLOW_OUTPUT_TOO_LARGE")

    async def emit(kind: str, node_id: str, visit: str, payload: dict[str, object]) -> None:
        async with exchange_lock:
            await send_event(kind, node_id, visit, payload)

    async def capability(node_id: str, visit: str, operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
        command_id = project_command_id(run_id, generation, visit)
        async with exchange_lock:
            if control.cancelled:
                raise asyncio.CancelledError
            closed = False
            if operation in {'end', 'manualComplete'}:
                if context is not None:
                    await context.close()
                closed = True
            waiter = asyncio.get_running_loop().create_future()
            control.capabilities[command_id] = waiter
            _write(stdout, _envelope(command, 'capability', commandId=command_id, nodeId=node_id, nodeVisitId=visit, attempt=1, operation=operation, arguments=arguments, browserClosed=closed))
            cancelled = asyncio.create_task(control.wait_cancelled())
            try:
                done, _ = await asyncio.wait({waiter, cancelled}, return_when=asyncio.FIRST_COMPLETED)
                control.check_parent()
                if waiter not in done:
                    raise asyncio.CancelledError
                reply = waiter.result()
                if reply.get('runId') != run_id:
                    raise ProtocolFailure
            finally:
                cancelled.cancel()
                await asyncio.gather(cancelled, return_exceptions=True)
        if operation == 'manual' and 'result' in reply:
            action = reply['result'].get('action')
            if action == 'cancel':
                raise asyncio.CancelledError
            if action in {'finish', 'expired'}:
                return await capability(node_id, visit, 'manualComplete', {})
        return reply

    session = None
    initialized_visit = None
    initialized_configuration = None

    async def launch_browser(payload, options):
        nonlocal context
        browser, launch = payload, options
        from cloakbrowser import (  # type: ignore[import-untyped]
            launch_context_async,
            launch_persistent_context_async,
        )
        user_data_dir = browser.get("userDataDir")
        launching = asyncio.create_task(
            launch_persistent_context_async(user_data_dir=user_data_dir, **launch)
            if isinstance(user_data_dir, str) and user_data_dir
            else launch_context_async(**launch)
        )
        launch_cancel = asyncio.create_task(control.wait_cancelled())
        try:
            done, _ = await asyncio.wait(
                {launching, launch_cancel}, return_when=asyncio.FIRST_COMPLETED
            )
            if launching not in done:
                launching.cancel()
            context = await launching
            control.check_parent()
            if control.cancelled:
                raise asyncio.CancelledError
        finally:
            launch_cancel.cancel()
            if not launching.done():
                launching.cancel()
            await asyncio.gather(launch_cancel, launching, return_exceptions=True)
        context.set_default_timeout(0)
        context.set_default_navigation_timeout(0)

    async def initialize_browser(execution, declaration):
        nonlocal session, initialized_visit, initialized_configuration
        from autoflow.domain.workflows.browser_environment import same_shared_browser
        from autoflow.domain.workflows.runtime import WorkflowRuntimeError
        from autoflow.providers.browser.workflow_session import (
            CloakBrowserWorkflowSession,
        )
        if declaration.get('source') == 'current':
            if session is None:
                raise WorkflowRuntimeError('BROWSER_INSTANCE_REQUIRED', '请先执行创建或加载环境的打开网页节点', 409)
            return session
        if session is not None and same_shared_browser(declaration, initialized_configuration):
            return session
        if session is not None and declaration.get('source') == 'profile':
            raise WorkflowRuntimeError('BROWSER_CONFIGURATION_MISMATCH', '本次运行已打开浏览器，请保持浏览器配置、代理和内核一致', 409)
        if initialized_visit is not None and initialized_visit != execution.current_execution_id:
            raise WorkflowRuntimeError('BROWSER_INSTANCE_ALREADY_INITIALIZED', '任务已有浏览器实例，请使用当前实例', 409)
        if session is not None:
            return session
        initialized_visit = execution.current_execution_id
        reply = await capability(execution.current_node_id, initialized_visit, 'initializeBrowser', {})
        if 'error' in reply:
            raise WorkflowRuntimeError(reply['error']['code'], '浏览器环境初始化失败', 409)
        granted = reply['result']
        executable = Path(granted['executablePath'])
        if not executable.is_absolute() or not executable.is_file():
            raise ProtocolFailure
        os.environ['CLOAKBROWSER_BINARY_PATH'] = str(executable)
        payload = granted['browser']
        options = browser_launch_options(payload, headless=_boolean(payload, 'headless'))
        selected_proxy = _optional_proxy(payload)
        relay = relay_context.enter_context(BrowserProxyRelay(selected_proxy)) if selected_proxy else None
        options['proxy'] = {'server': relay.url} if relay else None
        await launch_browser(payload, options)
        session = CloakBrowserWorkflowSession(context)
        session.proxy_relay = relay
        initialized_configuration = declaration.copy()
        return session

    result: dict[str, object] = {"status": "failed", "error": {"code": "WORKFLOW_WORKER_FAILED", "message": "工作流执行进程失败"}}
    cleanup_failed = False
    try:
        with relay_guard as stack:
            relay = stack.enter_context(BrowserProxyRelay(proxy)) if proxy else None
            launch["proxy"] = {"server": relay.url} if relay is not None else None
            with open(os.devnull, "w", encoding="utf-8") as sink, redirect_stdout(sink), redirect_stderr(sink):  # noqa: ASYNC230
                if requires_browser:
                    await launch_browser(browser, launch)
                _write(stdout, _envelope(command, "ready"))
                variables = dict(command.get("variables", {}))
                variables.update(command.get("parameters", {}))
                executor = ProjectGraphExecutor(
                    context,
                    variables,
                    emit,
                    lambda: control.cancelled,
                    lambda page, node_id, visit: _capture_failure_screenshot(
                        command, page, node_id, visit, control=control
                    ),
                    lambda node_id, visit, module_type: ProjectArtifactWriter(
                        _artifact_directory(command)[0].parents[2], run_id, generation,
                        node_id, visit,
                        {"screenshot": "screenshot", "download_file": "file", "save_image": "image", "list_export": "file", "export_log": "file", "table_export": "file", "extract_table_data": "file", "allure_generate_report": "file", "ssh_connect": "file", "ssh_upload_file": "file", "ssh_download_file": "file", "base64": "file", "firecrawl_scrape": "screenshot", "face_recognition": "file", "image_ocr": "file"}[module_type],
                        emit,
                    ),
                    credentials=incoming.credentials if isinstance(incoming, _Input) else None,
                    models=WorkflowModelGateway(command.pop("modelBindings", [])),
                    external_integrations=integrations,
                    command_bus=command_bus,
                    capability=capability,
                    browser_initializer=initialize_browser if node_mode else None,

                    proxy_probe=relay.probe if relay is not None else None,
                )
                result = await executor.run(command["executionPlan"])
                control.check_parent()
    except asyncio.CancelledError:
        if control.failure is not None:
            result = {"status": "failed", "error": {"code": control.failure.code, "message": "父进程通信中断"}}
        else:
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
        except Exception:  # noqa: BLE001
            cleanup_failed = True
        try:
            await integrations.close()
        except Exception:  # noqa: BLE001 -- retained as unconfirmed cleanup.
            cleanup_failed = True
        cleanup_failed = cleanup_failed or relay_guard.failed
    command_bus.close()
    control_task.cancel()
    await asyncio.gather(control_task, return_exceptions=True)
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
    command: dict[str, Any], page: Any, _node_id: str, _visit: str,
    *, control: _Control | None = None,
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
        capture = asyncio.create_task(page.screenshot(type="png"))
        cancellation = asyncio.create_task(control.wait_cancelled()) if control is not None else None
        tasks = {capture, cancellation} if cancellation is not None else {capture}
        try:
            done, _ = await asyncio.wait(
                tasks, timeout=FAILURE_SCREENSHOT_TIMEOUT_SECONDS,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if control is not None:
                control.check_parent()
            if capture not in done or (control is not None and control.cancelled):
                return {**unavailable, "unavailableReason": "SCREENSHOT_CAPTURE_FAILED"}
            content = capture.result()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
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
    except ProtocolFailure:
        raise
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
    if len(raw.encode("utf-8")) > MAX_EVENT_JSONL_BYTES:
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
