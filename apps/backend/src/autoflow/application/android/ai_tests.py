"""AI test use cases: start/cancel ARTEMIS runs on managed or external devices and track them."""

import asyncio
import contextlib
import hashlib
import json
import logging
from collections import deque
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from autoflow.application.android.devices import AndroidDeviceService
from autoflow.application.models.service import ModelExecutionBinding, ModelService
from autoflow.domain.android.ai_test import (
    TERMINAL_STATES,
    AiTestRequest,
    AiTestState,
    redact,
    transition,
    validate_request,
)
from autoflow.domain.android.ports import AndroidError
from autoflow.domain.models.errors import ModelError
from autoflow.domain.models.validation import DEFAULT_URLS
from autoflow.infrastructure.database.android_ai_tests import AiTestRepository
from autoflow.providers.android.artemis_tool import (
    ARTEMIS_COMMIT,
    ArtemisTool,
    ModelEnv,
    ToolStatus,
)
from autoflow.providers.android.external_devices import list_external_devices

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDER_KINDS = frozenset({"openai", "openai-compatible", "gemini", "anthropic"})
_FIXED_URL_KINDS = frozenset({"gemini", "anthropic"})  # ARTEMIS cannot point these at another endpoint
_INTERRUPTED = "程序中断，无法确定测试是否完成"
_PASSTHROUGH_CODES = frozenset({"AI_TEST_TIMEOUT", "AI_TEST_PROCESS_FAILED"})
_SCREEN_TIMEOUT = 5


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _digest(fields: dict[str, Any]) -> str:
    canonical = json.dumps(fields, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _model_env(binding: ModelExecutionBinding) -> ModelEnv:
    kind = binding.connection.provider_kind
    base_url = (binding.connection.base_url or "").strip().rstrip("/") or None
    if base_url is not None and base_url == DEFAULT_URLS.get(kind):
        base_url = None  # saved providers store the normalized default URL
    if kind not in SUPPORTED_PROVIDER_KINDS or (kind in _FIXED_URL_KINDS and base_url):
        raise AndroidError("AI_TEST_MODEL_UNSUPPORTED", "所选模型暂不支持 AI 测试", 409)
    return ModelEnv(kind, base_url, binding.model_key, binding.secret)


class AiTestService:
    def __init__(
        self,
        repository: AiTestRepository,
        tool: ArtemisTool,
        devices: AndroidDeviceService,
        models: ModelService,
        console_serials: Callable[[], set[str]],
        close_console: Callable[[str], Awaitable[None]],
        artifacts_root: Path,
    ) -> None:
        self.repository, self.tool, self.devices, self.models = repository, tool, devices, models
        self.console_serials = console_serials
        self.close_console = close_console  # ends the device's console session so the test can claim it
        self.artifacts_root = artifacts_root
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._cancels: dict[str, asyncio.Event] = {}
        self._managed_serials: dict[str, str] = {}  # run id -> adb serial while a managed run holds it
        self._contexts: dict[str, AndroidDeviceService] = {}  # run id -> held managed device context
        self._external_busy: set[str] = set()
        self._install_task: asyncio.Task[None] | None = None
        self._install_error: str | None = None
        self._install_output: deque[str] = deque(maxlen=50)
        self._starting: dict[str, asyncio.Event] = {}  # request id -> set when that start() returns
        self._shutting_down = False

    # -- tool -------------------------------------------------------------

    async def tool_status(self) -> ToolStatus:
        status = await asyncio.to_thread(self.tool.status)
        if self._install_error and status.state == "not_installed":
            return ToolStatus("failed", None, self._install_error)
        return status

    async def install_tool(self, request_id: str) -> dict[str, Any]:
        if self._install_task is None or self._install_task.done():
            status = await self.tool_status()
            if status.state != "installing":
                self._install_task = asyncio.create_task(self._install(request_id))
                await asyncio.sleep(0)  # let install() flag itself as installing before reporting
        return asdict(await self.tool_status())

    async def _install(self, request_id: str) -> None:
        self._install_error = None
        self._install_output.clear()
        try:
            await self.tool.install(self._install_output.append)
        except AndroidError as exc:  # the tool already reports its own failures in status()
            logger.warning("AI test tool install %s failed: %s", request_id, exc.message)
        except Exception as exc:  # noqa: BLE001 -- any failure must reach the user-visible status.
            self._install_output.append(f"{type(exc).__name__}: {exc}")
            self._install_error = redact("\n".join(self._install_output), [])
            logger.warning("AI test tool install %s failed: %s", request_id, self._install_error)

    async def _require_tool(self) -> None:
        if (await self.tool_status()).state != "ready":
            raise AndroidError("AI_TOOL_NOT_READY", "测试工具尚未安装或不可用", 409)

    # -- devices ----------------------------------------------------------

    def _managed_set(self) -> set[str]:
        return set(self.console_serials()) | set(self._managed_serials.values())

    async def external_devices(self) -> list[dict[str, Any]]:
        return await list_external_devices(self._managed_set())

    async def _check_external(self, serial: str) -> None:
        if serial in self._managed_set():
            raise AndroidError("AI_TEST_DEVICE_MANAGED", "该设备由 AutoFlow 管理，请从设备工作台运行", 409)
        devices = await self.external_devices()
        if not any(d["serial"] == serial and d["state"] == "device" for d in devices):
            raise AndroidError("AI_TEST_DEVICE_OFFLINE", "设备不在线或未授权", 409)

    @contextlib.contextmanager
    def _external_lock(self, serial: str) -> Iterator[None]:
        if serial in self._external_busy:
            raise AndroidError("AI_TEST_DEVICE_BUSY", "该设备正在运行另一个测试", 409)
        self._external_busy.add(serial)
        try:
            yield
        except BaseException:
            self._external_busy.discard(serial)
            raise

    async def _open_managed(self, device_id: str, run_id: str) -> tuple[AndroidDeviceService, str]:
        await self.close_console(device_id)
        context = self.devices.context(device_id)
        claim = asyncio.ensure_future(asyncio.to_thread(context.claim, device_id, run_id, "ai_test"))
        try:
            await asyncio.shield(claim)
        except asyncio.CancelledError:
            await asyncio.wait({claim})  # the thread still finishes; release what it took
            if not claim.cancelled() and claim.exception() is None:
                await context.cleanup()
            raise
        try:
            await context.connect()
            serial = getattr(context.runtime, "serial", None)
            if not serial:
                raise AndroidError("AI_TEST_DEVICE_OFFLINE", "设备不在线或未授权", 409)
            return context, serial
        except BaseException:
            await context.cleanup()
            raise

    async def install_helper(self, device_kind: str, device_id: str | None, serial: str | None) -> bool:
        await self._require_tool()
        if device_kind == "managed" and device_id:
            context, adb_serial = await self._open_managed(device_id, str(uuid4()))
            try:
                return await self.tool.helper(adb_serial, install=True)
            finally:
                await context.cleanup()
        if device_kind == "external" and serial:
            await self._check_external(serial)
            with self._external_lock(serial):
                try:
                    return await self.tool.helper(serial, install=True)
                finally:
                    self._external_busy.discard(serial)
        raise AndroidError("AI_TEST_DEVICE_INVALID", "请选择要测试的设备", 422)

    # -- runs -------------------------------------------------------------

    async def start(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = request.get("requestId")
        if not isinstance(request_id, str) or not request_id.strip():
            raise AndroidError("AI_TEST_REQUEST_INVALID", "缺少请求编号", 422)
        # Serialize starts of one request so a double submit claims the device once and replays.
        while (busy := self._starting.get(request_id)) is not None:
            await busy.wait()
        done = self._starting[request_id] = asyncio.Event()
        try:
            return await self._start(request_id, request)
        finally:
            del self._starting[request_id]
            done.set()

    async def _start(self, request_id: str, request: dict[str, Any]) -> dict[str, Any]:
        parsed = validate_request(request)
        kind, device_id, serial = request.get("deviceKind"), request.get("deviceId"), request.get("serial")
        if not (kind == "managed" and isinstance(device_id, str) and device_id) and not (
            kind == "external" and isinstance(serial, str) and serial
        ):
            raise AndroidError("AI_TEST_DEVICE_INVALID", "请选择要测试的设备", 422)
        if kind == "managed":
            serial = None
        else:
            device_id = None
        digest = _digest({
            "deviceKind": kind, "deviceId": device_id, "serial": serial, "instruction": parsed.instruction,
            "mode": parsed.mode, "modelId": parsed.model_id, "maxSteps": parsed.max_steps,
            "timeoutSeconds": parsed.timeout_seconds,
        })
        existing = await asyncio.to_thread(self.repository.get_by_request, request_id)
        if existing is not None:
            if existing.get("requestDigest") != digest:
                raise AndroidError("ANDROID_REQUEST_CONFLICT", "请求编号已用于不同的测试", 409)
            return existing

        await self._require_tool()
        try:
            binding = await asyncio.to_thread(self.models.execution_binding, parsed.model_id)
        except ModelError as exc:
            raise AndroidError(exc.code, exc.message, exc.status) from None
        model = _model_env(binding)

        run_id = uuid4().hex
        context: AndroidDeviceService | None = None
        if kind == "managed":
            assert device_id is not None
            context, adb_serial = await self._open_managed(device_id, run_id)
            self._managed_serials[run_id] = adb_serial
            self._contexts[run_id] = context
        else:
            assert serial is not None
            await self._check_external(serial)
            adb_serial = serial
        try:
            with contextlib.ExitStack() as stack:
                if context is None:
                    stack.enter_context(self._external_lock(adb_serial))
                if not await self.tool.helper(adb_serial, install=False):
                    raise AndroidError("AI_TEST_HELPER_REQUIRED", "需要在该设备安装测试辅助组件", 409)
                artifacts = self.artifacts_root / run_id
                record = await self._create({
                    "id": run_id, "requestId": request_id, "deviceKind": kind, "deviceId": device_id,
                    "serial": serial, "state": "queued", "createdAt": _now(), "startedAt": None, "finishedAt": None,
                    "instruction": parsed.instruction, "mode": parsed.mode, "modelId": parsed.model_id,
                    "modelKey": binding.model_key, "maxSteps": parsed.max_steps,
                    "timeoutSeconds": parsed.timeout_seconds, "requestDigest": digest,
                    "artifactsDir": str(artifacts), "toolVersion": ARTEMIS_COMMIT, "steps": [],
                    "succeeded": None, "traceId": None, "artifacts": [], "errorCode": None, "errorMessage": None,
                }, run_id)
                if record["id"] != run_id:  # lost a race with the same request: the other start owns the run
                    raise _Duplicate(record)
        except _Duplicate as dup:
            await self._release(run_id, context, None)
            return dup.record
        except BaseException:
            await self._release(run_id, context, None)
            raise
        cancel = asyncio.Event()
        self._cancels[run_id] = cancel
        self._tasks[run_id] = asyncio.create_task(
            self._execute(record, parsed, model, adb_serial, artifacts, context, cancel)
        )
        return record

    async def _create(self, run: dict[str, Any], run_id: str) -> dict[str, Any]:
        create = asyncio.ensure_future(asyncio.to_thread(self.repository.create, run))
        try:
            return await asyncio.shield(create)
        except asyncio.CancelledError:
            await asyncio.wait({create})
            if not create.cancelled() and create.exception() is None and create.result()["id"] == run_id:
                await asyncio.to_thread(  # no task will ever run it: close the row instead of leaving it queued
                    self.repository.update, run_id, state="failed", finishedAt=_now(), succeeded=False,
                    errorCode="AI_TEST_INTERNAL", errorMessage="启动被取消",
                )
            raise

    async def _release(self, run_id: str, context: AndroidDeviceService | None, serial: str | None) -> None:
        self._managed_serials.pop(run_id, None)
        self._contexts.pop(run_id, None)
        if serial is not None:
            self._external_busy.discard(serial)
        if context is not None:
            await context.cleanup()

    async def _execute(
        self,
        record: dict[str, Any],
        request: AiTestRequest,
        model: ModelEnv,
        serial: str,
        artifacts: Path,
        context: AndroidDeviceService | None,
        cancel: asyncio.Event,
    ) -> None:
        run_id = record["id"]
        state: AiTestState = "queued"
        released = False

        async def release() -> None:
            nonlocal released
            if released:
                return
            released = True
            try:
                await self._release(run_id, context, None if context else serial)
            except Exception:  # cleanup marks the device for recovery itself
                logger.exception("AI test %s device cleanup failed", run_id)

        async def finish(target: AiTestState, **changes: Any) -> None:
            nonlocal state
            if state not in ("queued", "running"):
                return  # already finalized (e.g. cancelled while the terminal write was in flight)
            state = transition(state, target)
            # Free the device first: whoever sees the final state may immediately rerun or take over.
            await release()
            await asyncio.to_thread(self.repository.update, run_id, state=state, finishedAt=_now(), **changes)

        async def on_event(event: dict[str, Any]) -> None:
            if event.get("type") == "step":
                step = {k: event.get(k) for k in ("index", "summary", "screenshot")}
                await asyncio.to_thread(self.repository.append_step, run_id, step)

        try:
            try:
                state = transition(state, "running")
                await asyncio.to_thread(self.repository.update, run_id, state=state, startedAt=_now())
                await asyncio.to_thread(artifacts.mkdir, parents=True, exist_ok=True)
                result = await self.tool.run(
                    serial=serial, instruction=request.instruction, mode=request.mode,
                    max_steps=request.max_steps, timeout_seconds=request.timeout_seconds,
                    artifacts=artifacts, model=model, on_event=on_event, cancel=cancel,
                )
                succeeded = bool(result.get("succeeded"))
                error = result.get("error")
                await finish(
                    "succeeded" if succeeded else "failed", succeeded=succeeded,
                    traceId=result.get("traceId"), artifacts=list(result.get("artifacts") or []),
                    errorMessage=None if succeeded else redact(str(error or "测试未通过"), [model.secret]),
                )
            except AndroidError as exc:
                if exc.code == "AI_TEST_CANCELLED":
                    await finish("cancelled", succeeded=False)
                elif exc.code in _PASSTHROUGH_CODES:
                    await finish("failed", succeeded=False, errorCode=exc.code,
                                 errorMessage=redact(exc.message, [model.secret]))
                else:
                    raise
            except asyncio.CancelledError:
                if self._shutting_down and state == "running":
                    # The user did not stop it: the app is closing, so the outcome is unknown (spec §6.7).
                    await finish("needs_verification", errorMessage=_INTERRUPTED)
                else:
                    await finish("cancelled", succeeded=False)
                raise
        except Exception as exc:  # noqa: BLE001 -- a run must never stay "running" after its task ends
            message = redact(str(exc) or type(exc).__name__, [model.secret])
            # No traceback: the raw exception text may carry the model secret.
            logger.error("AI test %s failed unexpectedly: %s: %s", run_id, type(exc).__name__, message)
            await finish("failed", succeeded=False, errorCode="AI_TEST_INTERNAL", errorMessage=message)
        finally:
            self._tasks.pop(run_id, None)
            self._cancels.pop(run_id, None)
            await release()

    async def cancel(self, run_id: str) -> dict[str, Any]:
        record = await asyncio.to_thread(self.repository.get, run_id)
        if record["state"] in TERMINAL_STATES:
            return record
        event = self._cancels.get(run_id)
        if event is not None:
            event.set()
        return record

    async def screen(self, run_id: str) -> bytes:
        """Read-only live view (spec §6.4): one PNG through the running managed test's own connection."""
        record = await asyncio.to_thread(self.repository.get, run_id)
        context = self._contexts.get(run_id)
        if record["state"] != "running" or context is None:
            raise AndroidError("AI_TEST_STATE_CONFLICT", "测试未在设备工作台中运行，无法查看实时画面", 409)
        try:  # adb exec-out screencap -p runs as a subprocess, off the event loop
            return cast(bytes, await context.runtime.command("android_screenshot", {}, _SCREEN_TIMEOUT))
        except TimeoutError:
            raise AndroidError("AI_TEST_SCREEN_TIMEOUT", "读取实时画面超时", 504) from None

    async def recover(self) -> None:
        """Mark runs interrupted by a restart; their devices are recovered by AndroidDeviceService.recover."""
        for run in await asyncio.to_thread(self.repository.unfinished):
            # Direct marking: the run's process is gone, so no normal transition applies.
            await asyncio.to_thread(
                self.repository.update, run["id"], state="needs_verification", errorMessage=_INTERRUPTED,
            )

    async def shutdown(self) -> None:
        self._shutting_down = True
        tasks: list[asyncio.Task[None]] = list(self._tasks.values())
        if self._install_task is not None:
            tasks.append(self._install_task)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


class _Duplicate(Exception):
    def __init__(self, record: dict[str, Any]) -> None:
        super().__init__(record["id"])
        self.record = record
