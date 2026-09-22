"""One input lease per device, shared by the embedded and native consoles."""

import asyncio
from copy import deepcopy
from time import monotonic
from typing import Any

from autoflow.domain.android.ports import AndroidError


class AndroidConsole:
    def __init__(
        self, devices: Any, runs: Any, resources: Any, stream_factory: Any
    ) -> None:
        self.devices, self.runs, self.resources, self.stream_factory = (
            devices,
            runs,
            resources,
            stream_factory,
        )
        self.sessions: dict[str, dict[str, Any]] = {}
        self.lock = asyncio.Lock()
        self.operations = asyncio.Semaphore(2)
        self.reaper: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self.reaper = asyncio.create_task(self._expire())

    async def _expire(self) -> None:
        while True:
            await asyncio.sleep(5)
            for session in list(self.sessions.values()):
                if (
                    session["view"]["state"] == "closed"
                    or monotonic() - session["seen"] < 30
                ):
                    continue
                async with session["lock"]:
                    if monotonic() - session["seen"] < 30:
                        continue
                    try:
                        await self._close_stream(session)
                        if session["owned"]:
                            await session["context"].cleanup()
                        else:
                            context = session["context"]
                            if context.device and session["view"]["access"] == "manual":
                                await context.runtime.close_window()
                                context.device["control"] = "workflow"
                                context._save()
                    except (AndroidError, OSError, TimeoutError):
                        session["view"]["state"] = "recovery_required"

    def busy(self) -> bool:
        return any(s["view"]["state"] != "closed" for s in self.sessions.values())

    def get(self, identifier: str) -> dict[str, Any]:
        session = self.sessions.get(identifier)
        if session is None:
            raise AndroidError(
                "ANDROID_SESSION_EXPIRED", "控制会话已结束，请重新打开设备", 410
            )
        if (
            session["view"]["endpoint"] == "native"
            and session["view"]["state"] == "connected"
            and not session["context"].runtime.window_open()
        ):
            session["view"]["state"] = "native_closed"
        return session

    async def heartbeat(self, identifier: str, client_session_id: str, generation: int) -> dict[str, Any]:
        session = self.sessions.get(identifier)
        if session is None or session["view"]["state"] == "closed":
            raise AndroidError("ANDROID_SESSION_EXPIRED", "控制会话已结束，请重新打开设备", 410)
        if session.get("clientSessionId") != client_session_id or session["view"]["generation"] != generation:
            raise AndroidError("ANDROID_SESSION_STALE", "控制会话身份已变化，请刷新会话", 409)
        session["seen"] = monotonic()
        return session["view"]

    async def create(self, request: dict[str, Any]) -> dict[str, Any]:
        async with self.lock:
            identifier = request["requestId"]
            if identifier in self.sessions:
                session = self.sessions[identifier]
                if session["request"] != request:
                    raise AndroidError(
                        "ANDROID_REQUEST_CONFLICT", "请求编号已用于不同会话"
                    )
                return session["view"]
            try:
                self.resources.get("session", identifier)
            except AndroidError as error:
                if error.status != 404:
                    raise
            else:
                raise AndroidError(
                    "ANDROID_SESSION_EXPIRED",
                    "此请求对应的旧会话已结束，请重新打开设备",
                    410,
                )
            if any(
                s["view"]["deviceId"] == request["deviceId"]
                and s["view"]["state"] != "closed"
                for s in self.sessions.values()
            ):
                raise AndroidError(
                    "ANDROID_CONSOLE_BUSY", "此设备已有控制台，请回到已打开的控制台"
                )
            context = self.runs.device_context(request["deviceId"])
            owned = context is None
            if owned:
                context = self.devices.context(request["deviceId"])
                context.claim(request["deviceId"], identifier)
                try:
                    await context.connect()
                except BaseException:
                    await context.cleanup()
                    raise
            elif request["access"] == "manual":
                raise AndroidError(
                    "ANDROID_WORKFLOW_OWNS_DEVICE",
                    "工作流正在使用设备，请先只读预览并申请接管",
                )
            assert context.device
            access = request["access"]
            view = {
                "id": identifier,
                "deviceId": request["deviceId"],
                "generation": context.device["generation"],
                "access": access,
                "endpoint": "embedded",
                "state": "connected",
                "width": context.device["width"],
                "height": context.device["height"],
                "latestOperation": None,
            }
            session = {
                "view": view,
                "request": request,
                "context": context,
                "owned": owned,
                "stream": None,
                "sequence": 0,
                "lock": asyncio.Lock(),
                "keys": set(),
                "touch": None,
                "seen": monotonic(),
                "clientSessionId": request.get("clientSessionId") or identifier,
            }
            view["clientSessionId"] = session["clientSessionId"]
            self.resources.save(
                "session",
                {"id": identifier, "deviceId": request["deviceId"], "request": request},
            )
            self.sessions[identifier] = session
            context.close_console = lambda: self._close_stream(session)
            try:
                await self._start_stream(session)
                if access == "manual":
                    context.device["control"] = "manual"
                    context._save()
            except BaseException:
                view["state"] = "closed"
                if owned:
                    await context.cleanup()
                raise
            return view

    async def _start_stream(self, session: dict[str, Any]) -> None:
        stream = self.stream_factory(session["context"].runtime)
        session["stream"] = stream
        await stream.start()
        session["view"].update(
            width=stream.width,
            height=stream.height,
            state="connected",
            endpoint="embedded",
        )

    async def _close_stream(self, session: dict[str, Any]) -> None:
        if session["stream"]:
            await self._release(session)
            await session["stream"].close()
            session["stream"] = None
        session["view"]["state"] = "closed"

    def _check(
        self, session: dict[str, Any], generation: int, manual: bool = False
    ) -> Any:
        view, context = session["view"], session["context"]
        if (
            not context.device
            or context.stopping
            or view["state"] == "closed"
            or generation != view["generation"]
            or (
                view["access"] == "manual"
                and generation != context.device["generation"]
            )
        ):
            raise AndroidError("ANDROID_SESSION_STALE", "控制权已变化，请刷新会话")
        if manual and context.device.get("pendingCommand"):
            raise AndroidError(
                "ANDROID_OPERATION_UNKNOWN",
                "上一操作结果尚未确认，请结束控制并核实设备",
                409,
            )
        if manual and (
            view["state"] != "connected"
            or session["stream"] is None
            or view["access"] != "manual"
            or view["endpoint"] != "embedded"
            or context.device["control"] != "manual"
            or context.runtime.window_open()
        ):
            raise AndroidError(
                "ANDROID_INPUT_FORBIDDEN", "当前设备未授予页面输入控制权", 409
            )
        return context

    async def command(self, identifier: str, command: dict[str, Any]) -> dict[str, Any]:
        session = self.get(identifier)
        async with session["lock"]:
            self._check(session, command["generation"], True)
            if command["sequence"] <= session["sequence"]:
                raise AndroidError(
                    "ANDROID_INPUT_STALE", "过期或重复的输入已被拒绝", 409
                )
            # Consume before sending. An unknown write is never replayed by the server.
            session["sequence"] = command["sequence"]
            if command["kind"] == "release":
                await self._release(session)
            else:
                await session["stream"].command(command)
                if command["kind"] == "key":
                    if command["action"] == 0:
                        session["keys"].add(command["keycode"])
                    else:
                        session["keys"].discard(command["keycode"])
                if command["kind"] == "touch":
                    session["touch"] = command if command["action"] in {0, 2} else None
            session["view"]["latestOperation"] = {
                "text": "文本已发送",
                "key": "按键已发送",
                "touch": "触控已发送",
                "rotate": "旋转已发送",
                "release": "输入已释放",
            }[command["kind"]]
            return session["view"]

    async def _release(self, session: dict[str, Any]) -> None:
        if not session["stream"] or session["stream"].error:
            session["keys"].clear()
            session["touch"] = None
            return
        for key in session["keys"]:
            await session["stream"].command(
                {"kind": "key", "keycode": key, "action": 1}
            )
        if session["touch"]:
            await session["stream"].command({**session["touch"], "action": 3})
        session["keys"].clear()
        session["touch"] = None

    async def action(self, identifier: str, request: dict[str, Any]) -> dict[str, Any]:
        session = self.get(identifier)
        async with session["lock"]:
            receipts = session.setdefault("receipts", {})
            if request["requestId"] in receipts:
                if receipts[request["requestId"]] != request:
                    raise AndroidError(
                        "ANDROID_REQUEST_CONFLICT", "请求编号已用于其他操作"
                    )
                return session["view"]
            action = request["action"]
            if action == "end" and session["view"]["state"] == "recovery_required":
                context = session["context"]
                if session["owned"]:
                    await context.cleanup()
                else:
                    await self._close_stream(session)
                    await context.runtime.close_window()
                    if context.device:
                        context.device["control"] = "workflow"
                        context._save()
                session["view"]["state"] = "closed"
                return session["view"]
            context = self._check(session, request["generation"])
            try:
                if action == "takeover":
                    self.runs.request_takeover(session["view"]["deviceId"])
                    session["view"]["state"] = "waiting_pause"
                elif action == "native" and session["view"]["access"] == "readonly":
                    await self._close_stream(session)
                    await context.runtime.open_window(
                        "AutoFlow · 只读 · " + context.device["name"], readonly=True
                    )
                    session["view"].update(endpoint="native", state="connected")
                elif (
                    action == "embedded"
                    and session["view"]["access"] == "readonly"
                    and session["view"]["endpoint"] == "native"
                ):
                    await context.runtime.close_window()
                    await self._start_stream(session)
                elif (
                    action == "embedded"
                    and session["view"]["access"] == "readonly"
                    and session["owned"]
                ):
                    context.device["generation"] += 1
                    context.device["control"] = "manual"
                    context._save()
                    session["view"].update(
                        access="manual", generation=context.device["generation"]
                    )
                elif action == "embedded" and session["view"]["access"] == "readonly":
                    if (
                        not context.handoff
                        or context.continued.is_set()
                        or context.resuming
                    ):
                        raise AndroidError(
                            "ANDROID_PAUSE_PENDING", "当前动作尚未完成，请等待暂停确认"
                        )
                    await context.runtime.close_window()
                    context.device["control"] = "manual"
                    context._save()
                    session["view"].update(
                        access="manual",
                        generation=context.device["generation"],
                        state="connected",
                        endpoint="embedded",
                    )
                    if session["stream"] is None:
                        await self._start_stream(session)
                elif action in {"embedded", "native"}:
                    if session["view"]["access"] != "manual":
                        raise AndroidError("ANDROID_INPUT_FORBIDDEN", "请先取得控制权")
                    await self._close_stream(session)
                    await context.runtime.close_window()
                    context.device["generation"] += 1
                    context._save()
                    session["view"]["generation"] = context.device["generation"]
                    if action == "native":
                        await context.runtime.open_window(
                            "AutoFlow · " + context.device["name"]
                        )
                        session["view"].update(endpoint="native", state="connected")
                    else:
                        await self._start_stream(session)
                elif action in {"end", "resume"}:
                    await self._close_stream(session)
                    if session["owned"]:
                        try:
                            await context.cleanup()
                        except BaseException:
                            session["view"]["state"] = "recovery_required"
                            raise
                    elif action == "resume":
                        await context.control(
                            context.handoff["handoffId"],
                            request["requestId"],
                            "continue",
                        )
                    else:
                        # Leaving a readonly view does not stop its workflow.
                        if (
                            session["view"]["endpoint"] == "native"
                            or session["view"]["access"] == "manual"
                        ):
                            await context.runtime.close_window()
                            context.device["control"] = "workflow"
                            context._save()
                    session["view"]["state"] = "closed"
            except BaseException:
                if session["view"]["state"] == "closed" and context.device:
                    session["view"]["state"] = "recovery_required"
                raise
            receipts[request["requestId"]] = request
            return session["view"]

    async def apps(self, identifier: str) -> dict[str, Any]:
        session = self.get(identifier)
        async with session["lock"]:
            context = self._check(session, session["view"]["generation"])
            return await context.runtime.app_info()

    def _persist_session(self, session: dict[str, Any]) -> None:
        """Persist app-operation receipts before and after the runtime call."""
        request = session.get(
            "request",
            {
                "requestId": session["view"]["id"],
                "deviceId": session["view"]["deviceId"],
                "access": session["view"].get("access", "manual"),
            },
        )
        self.resources.save(
            "session",
            {
                "id": session["view"]["id"],
                "deviceId": session["view"]["deviceId"],
                "request": request,
                "appReceipts": deepcopy(session.get("appReceipts", {})),
                "latestOperation": session["view"].get("latestOperation"),
            },
        )

    def _app_operation_unknown(
        self, session: dict[str, Any], request_id: str | None, error: BaseException
    ) -> None:
        receipt = session.get("appReceipts", {}).get(request_id) if request_id else None
        if receipt is not None:
            receipt.update(
                state="needs_verification",
                error={
                    "code": "ANDROID_OPERATION_UNKNOWN",
                    "message": str(error)[:480] or "应用操作结果未知",
                },
            )
        session["view"]["latestOperation"] = "应用操作结果待核实"
        if request_id:
            self._persist_session(session)

    def _app_operation_failed(
        self, session: dict[str, Any], request_id: str | None, error: AndroidError
    ) -> None:
        receipt = session.get("appReceipts", {}).get(request_id) if request_id else None
        if receipt is not None:
            receipt.update(
                state="failed",
                error={
                    "code": error.code,
                    "message": error.message[:480],
                    "status": error.status,
                },
            )
        session["view"]["latestOperation"] = "应用操作失败"
        if request_id:
            self._persist_session(session)

    async def app_operation(
        self, identifier: str, generation: int, operation: str, value: Any, request_id: str | None = None
    ) -> dict[str, Any]:
        session = self.get(identifier)
        async with session["lock"], self.operations:
            context = self._check(session, generation, True)
            receipts = session.setdefault("appReceipts", {})
            current = {
                "generation": generation,
                "operation": operation,
                "value": value if isinstance(value, str) else "bytes",
            }
            if request_id:
                previous = receipts.get(request_id)
                if previous is not None:
                    prior_request = previous.get("request", previous)
                    if prior_request != current:
                        raise AndroidError("ANDROID_REQUEST_CONFLICT", "请求编号已用于其他应用操作", 409)
                    state = previous.get("state", "succeeded")
                    if state == "succeeded":
                        return session["view"]
                    if state == "failed":
                        error = previous.get("error", {})
                        raise AndroidError(
                            error.get("code", "ANDROID_APP_OPERATION_FAILED"),
                            error.get("message", "应用操作失败"),
                            error.get("status", 502),
                        )
                    raise AndroidError(
                        "ANDROID_OPERATION_UNKNOWN",
                        "应用操作结果尚未核实，请先核实设备状态",
                        503,
                    )
            if operation not in {"install", "launch", "stop", "uninstall", "clearData"}:
                raise AndroidError("ANDROID_OPERATION_INVALID", "不支持的应用操作", 422)
            if operation in {"uninstall", "clearData"} and str(value).startswith(
                ("com.android.", "com.google.android.")
            ):
                raise AndroidError("ANDROID_PROTECTED_APP", "系统应用不能作为普通应用移除或清除", 409)
            if request_id:
                receipts[request_id] = {"request": current, "state": "running"}
                session["view"]["latestOperation"] = "应用操作执行中"
                self._persist_session(session)
            if operation == "install":
                try:
                    await context.runtime.install_apk(value)
                except asyncio.CancelledError:
                    self._app_operation_unknown(session, request_id, asyncio.CancelledError())
                    raise
                except (TimeoutError, OSError) as error:
                    self._app_operation_unknown(session, request_id, error)
                    raise AndroidError("ANDROID_OPERATION_UNKNOWN", "应用操作结果未知，请先核实后重试", 503) from error
                except AndroidError as error:
                    self._app_operation_failed(session, request_id, error)
                    raise
                except Exception as error:
                    self._app_operation_unknown(session, request_id, error)
                    raise AndroidError("ANDROID_OPERATION_UNKNOWN", "应用操作结果未知，请先核实后重试", 503) from error
            else:
                command = {"launch": "android_launch_app", "stop": "android_stop_app", "uninstall": "android_uninstall_app", "clearData": "android_clear_app_data"}[operation]
                try:
                    await context.runtime.command(command, {"packageName": value}, 30)
                except asyncio.CancelledError:
                    self._app_operation_unknown(session, request_id, asyncio.CancelledError())
                    raise
                except (TimeoutError, OSError) as error:
                    self._app_operation_unknown(session, request_id, error)
                    raise AndroidError("ANDROID_OPERATION_UNKNOWN", "应用操作结果未知，请先核实后重试", 503) from error
                except AndroidError as error:
                    self._app_operation_failed(session, request_id, error)
                    raise
                except Exception as error:
                    self._app_operation_unknown(session, request_id, error)
                    raise AndroidError("ANDROID_OPERATION_UNKNOWN", "应用操作结果未知，请先核实后重试", 503) from error
            session["view"]["latestOperation"] = (
                "APK 已安装" if operation == "install" else {"launch": "应用已启动", "stop": "应用已停止", "uninstall": "应用已卸载", "clearData": "应用数据已清除"}[operation]
            )
            if request_id:
                receipts[request_id]["state"] = "succeeded"
                self._persist_session(session)
            return session["view"]

    async def shutdown(self) -> None:
        if self.reaper and not self.reaper.done():
            self.reaper.cancel()
            await asyncio.gather(self.reaper, return_exceptions=True)
        for session in self.sessions.values():
            async with session["lock"]:
                await self._close_stream(session)
                if session["owned"]:
                    await session["context"].cleanup()
