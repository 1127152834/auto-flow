from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from autoflow.application.profiles.service import ProfileService
from autoflow.domain.kernels.errors import LicenseInvalid
from autoflow.domain.kernels.models import InstalledKernel, KernelEdition, KernelRef
from autoflow.domain.profiles.errors import KernelNotInstalled
from autoflow.domain.profiles.models import Profile, ProfileBrowserProxy
from autoflow.domain.workflows.browser import WorkflowBrowserBusy
from autoflow.domain.workflows.runs import WorkflowRunError
from autoflow.infrastructure.process.project_test_browser_worker import (
    browser_worker_payload,
)
from autoflow.infrastructure.process.workflow_worker import (
    WorkflowResourceCoordinator,
    WorkflowWorkerManager,
)


@dataclass(slots=True)
class _BrowserState:
    session_id: str
    profile_id: str
    picker_session_id: str | None = None
    picker_fingerprint: tuple[str | None, str] | None = None
    recorder_session_id: str | None = None


class WorkflowInspectionService:
    """Own one visible CloakBrowser inspection session for the Studio workspace."""

    def __init__(
        self,
        *,
        profiles: ProfileService,
        installed_kernels: Callable[[], Sequence[InstalledKernel]],
        resolve_proxy: Callable[[Profile, str], Awaitable[ProfileBrowserProxy | None]],
        read_license: Callable[[], str | None],
        resources: WorkflowResourceCoordinator,
        workers: WorkflowWorkerManager,
        recordings: Any | None = None,
    ) -> None:
        self._profiles = profiles
        self._installed = installed_kernels
        self._resolve_proxy = resolve_proxy
        self._read_license = read_license
        self._resources = resources
        self._workers = workers
        self._recordings = recordings
        self._state: _BrowserState | None = None
        self._retired_pickers: set[str] = set()
        self._waiters: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._lock = asyncio.Lock()
        self._picker_lock = asyncio.Lock()

    def busy(self) -> bool:
        return self._state is not None or self._workers.busy()

    async def open(self, *, profile_id: str, url: str | None = None) -> dict[str, Any]:
        async with self._lock:
            if self._state is not None:
                if self._state.profile_id != profile_id:
                    raise _conflict("当前浏览器使用其他 Profile，请先关闭")
                if url:
                    await self._command("navigate", url=url)
                return await self.status()
            profile = self._profiles.get(profile_id)
            kernel = self._kernel(profile)
            session_id = str(uuid4())
            acquired = False
            try:
                await self._resources.acquire(
                    session_id,
                    profile_id,
                    KernelRef(
                        cast(KernelEdition, profile.spec.browser_edition),
                        profile.spec.browser_version,
                    ),
                )
                acquired = True
                proxy = await self._resolve_proxy(profile, session_id)
                license_key = (
                    self._read_license()
                    if profile.spec.browser_edition == "licensed"
                    else None
                )
                if profile.spec.browser_edition == "licensed" and not license_key:
                    raise LicenseInvalid
                payload = browser_worker_payload(session_id, profile, proxy, license_key)
                payload.update(
                    {
                        "runId": session_id,
                        "headless": False,
                        "inspectionUrl": url,
                    }
                )
                await self._workers.start(
                    session_id, profile_id, kernel.executable_path, payload
                )
                self._state = _BrowserState(session_id, profile_id)
                return await self.status()
            except BaseException as error:
                if self._workers.busy():
                    await self._workers.stop(session_id)
                if acquired and self._resources.owner_id == session_id:
                    await self._resources.release(session_id)
                if isinstance(error, WorkflowRunError):
                    raise
                if isinstance(error, WorkflowBrowserBusy):
                    raise _conflict("当前工作区已有活跃浏览器会话") from error
                raise WorkflowRunError(
                    "INSPECTION_START_FAILED", "拾取浏览器启动失败", 503
                ) from error

    async def close(self, session_id: str | None = None) -> dict[str, Any]:
        async with self._picker_lock:
            return await self._close(session_id)

    async def _close(self, session_id: str | None = None) -> dict[str, Any]:
        async with self._lock:
            state = self._state
            if state is None:
                return {"success": True}
            if session_id is not None and session_id != state.session_id:
                raise _conflict("浏览器会话已变化")
            if state.recorder_session_id is not None:
                raise _conflict("请先停止录制，再关闭浏览器")
            await self._workers.stop(state.session_id)
            if self._workers.busy():
                raise WorkflowRunError(
                    "INSPECTION_CLEANUP_PENDING", "浏览器清理尚未确认", 503
                )
            if self._resources.owner_id == state.session_id:
                await self._resources.release(state.session_id)
            if state.picker_session_id:
                self._retired_pickers.add(state.picker_session_id)
            self._state = None
            return {"success": True}

    async def shutdown(self) -> None:
        try:
            state = self._state
            if state is not None and state.recorder_session_id is not None:
                await self.stop_recording(
                    state.recorder_session_id, after_seq=0
                )
            state = self._state
            if state is not None:
                await self.close(state.session_id)
        finally:
            await self._workers.shutdown()
            state = self._state
            if state is not None:
                await self.on_worker_exit(state.session_id, -1)

    async def status(self) -> dict[str, Any]:
        state = self._state
        return {
            "isOpen": state is not None,
            "pickerActive": bool(state and state.picker_session_id),
            "sessionId": state.session_id if state else None,
            "profileId": state.profile_id if state else None,
            "pickerSessionId": state.picker_session_id if state else None,
        }

    async def pages(self) -> dict[str, Any]:
        state = self._require_browser()
        data = await self._command("pages")
        return {"sessionId": state.session_id, **data}

    async def page(self, request: Mapping[str, Any]) -> dict[str, Any]:
        state = self._require_browser()
        if request.get("sessionId") != state.session_id:
            raise _conflict("浏览器页面命令属于其他会话")
        data = await self._command(
            "page",
            expectedRevision=request.get("expectedRevision"),
            pageId=request.get("pageId"),
            action=request.get("action"),
            url=request.get("url"),
        )
        return {"sessionId": state.session_id, **data}

    async def navigate(self, url: str) -> dict[str, Any]:
        self._require_browser()
        return await self._command("navigate", url=url)

    async def current_url(self) -> dict[str, Any]:
        self._require_browser()
        return await self._command("url")

    async def start_picker(
        self, *, session_id: str, profile_id: str, url: str | None
    ) -> dict[str, Any]:
        async with self._picker_lock:
            return await self._start_picker(
                session_id=session_id, profile_id=profile_id, url=url
            )

    async def _start_picker(
        self, *, session_id: str, profile_id: str, url: str | None
    ) -> dict[str, Any]:
        fingerprint = (url, profile_id)
        state = self._state
        if state and state.picker_session_id == session_id:
            if state.picker_fingerprint != fingerprint:
                raise _conflict("拾取会话 ID 已用于不同的启动参数")
            return self._picker_state(True)
        if session_id in self._retired_pickers:
            raise _conflict("拾取会话已结束")
        if state and state.picker_session_id:
            raise _conflict("当前已有活跃拾取会话")
        if state and state.recorder_session_id:
            raise _conflict("录制期间不能启动元素拾取")
        if state is None:
            await self.open(profile_id=profile_id, url=url)
            state = self._require_browser()
        elif state.profile_id != profile_id:
            raise _conflict("拾取请求与浏览器 Profile 不一致")
        elif url:
            await self.navigate(url)
        await self._command("start_picker")
        state.picker_session_id = session_id
        state.picker_fingerprint = fingerprint
        return self._picker_state(True)

    async def stop_picker(self, session_id: str) -> dict[str, Any]:
        async with self._picker_lock:
            return await self._stop_picker(session_id)

    async def _stop_picker(self, session_id: str) -> dict[str, Any]:
        state = self._state
        if state is None or state.picker_session_id is None:
            if session_id in self._retired_pickers:
                return {
                    "success": True,
                    "sessionId": session_id,
                    "active": False,
                    "selected": False,
                }
            raise _conflict("拾取会话不存在或已失效")
        if state.picker_session_id != session_id:
            raise _conflict("拾取会话已变化")
        await self._command("stop_picker")
        self._retired_pickers.add(session_id)
        state.picker_session_id = None
        state.picker_fingerprint = None
        return {
            "success": True,
            "sessionId": session_id,
            "active": False,
            "selected": False,
        }

    def picker_status(self, session_id: str | None) -> dict[str, Any]:
        state = self._state
        if state and state.picker_session_id:
            if session_id and session_id != state.picker_session_id:
                raise _conflict("拾取状态属于其他会话")
            return self._picker_state(True)
        if session_id and session_id not in self._retired_pickers:
            raise _conflict("拾取会话不存在或已失效")
        return {
            "success": True,
            "sessionId": session_id or "none",
            "active": False,
            "selected": False,
        }

    async def picker_result(self, session_id: str, *, similar: bool) -> dict[str, Any]:
        state = self._require_picker(session_id)
        key = "__elementPickerSimilar" if similar else "__elementPickerResult"
        result = await self._command("picker_result", key=key)
        value = result.get("value")
        payload = self._picker_state(True)
        payload["selected"] = bool(result.get("selected"))
        if isinstance(value, dict):
            if similar:
                payload["similar"] = value
            else:
                payload.update(value)
                payload["data"] = value
                payload["element"] = value
        assert state.picker_session_id == session_id
        return payload

    async def test_selector(self, request: Mapping[str, Any]) -> dict[str, Any]:
        state = self._require_browser()
        session_id = request.get("sessionId")
        if session_id is not None and session_id != state.picker_session_id:
            raise _conflict("定位测试不属于当前拾取会话")
        return await self._command(
            "test_selector",
            selector=request.get("selector"),
            hints=request.get("hints"),
            highlight=request.get("highlight", True),
        )

    async def start_recording(self, session_id: str) -> dict[str, Any]:
        state = self._require_browser()
        repository = self._require_recordings()
        if state.picker_session_id is not None:
            raise _conflict("元素拾取期间不能开始录制")
        if state.recorder_session_id is not None:
            if state.recorder_session_id != session_id:
                raise _conflict("当前已有活跃录制会话")
            return {"success": True, **repository.status(session_id)}
        try:
            receipt = repository.start(session_id, now=datetime.now(UTC))
        except ValueError as error:
            raise _conflict(str(error)) from error
        try:
            await self._command("recorder_start")
        except BaseException:
            repository.stop(session_id, now=datetime.now(UTC))
            raise
        state.recorder_session_id = session_id
        return {"success": True, **receipt}

    async def recording_events(
        self, session_id: str, *, after_seq: int
    ) -> dict[str, Any]:
        repository = self._require_recordings()
        state = self._state
        if state is not None and state.recorder_session_id == session_id:
            response = await self._command("recorder_events")
            await self._append_recording_events(session_id, response.get("events"))
        else:
            current = repository.current()
            if current is None or current["sessionId"] != session_id:
                raise _conflict("录制会话不存在或已过期")
        try:
            return {"success": True, **repository.events(session_id, after_seq=after_seq)}
        except ValueError as error:
            raise _conflict(str(error)) from error

    async def stop_recording(
        self, session_id: str, *, after_seq: int
    ) -> dict[str, Any]:
        repository = self._require_recordings()
        state = self._state
        current = repository.current()
        if current is None or current["sessionId"] != session_id:
            raise _conflict("录制会话不存在或已过期")
        if state is not None and state.recorder_session_id == session_id:
            response = await self._command("recorder_stop")
            await self._append_recording_events(session_id, response.get("events"))
            repository.stop(session_id, now=datetime.now(UTC))
            state.recorder_session_id = None
        elif current["recording"]:
            raise _conflict("录制会话浏览器已失效")
        batch = repository.events(session_id, after_seq=after_seq)
        return {
            "success": True,
            "sessionId": session_id,
            "recording": False,
            "nextSeq": batch["nextSeq"],
            "hasMore": batch["hasMore"],
            "data": {"events": batch["data"]},
        }

    def recording_status(self, session_id: str | None) -> dict[str, Any]:
        repository = self._require_recordings()
        current = repository.current()
        if current is None:
            if session_id is not None:
                raise _conflict("录制会话不存在或已过期")
            return {
                "success": True,
                "sessionId": None,
                "recording": False,
                "nextSeq": 0,
            }
        if session_id is not None and current["sessionId"] != session_id:
            raise _conflict("录制会话不存在或已过期")
        state = self._state
        recording = bool(
            current["recording"]
            and state is not None
            and state.recorder_session_id == current["sessionId"]
        )
        return {"success": True, **current, "recording": recording}

    def read_recording_review(self, document_id: str) -> dict[str, Any]:
        review = self._require_recordings().read_review(document_id)
        if review is None:
            raise WorkflowRunError(
                "RECORDING_REVIEW_NOT_FOUND", "录制审查不存在", 404
            )
        return review

    def save_recording_review(
        self, document_id: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        try:
            return self._require_recordings().save_review(
                document_id,
                expected_revision=int(request["expectedRevision"]),
                auto_wait=bool(request["autoWait"]),
                events=[dict(event) for event in request["events"]],
                now=datetime.now(UTC),
            )
        except ValueError as error:
            code = (
                "RECORDING_REVIEW_CONFLICT"
                if "已修改" in str(error)
                else "RECORDING_REVIEW_INVALID"
            )
            status = 409 if code.endswith("CONFLICT") else 413
            raise WorkflowRunError(code, str(error), status) from error

    async def _append_recording_events(
        self, session_id: str, raw_events: object
    ) -> None:
        if not isinstance(raw_events, list) or not raw_events:
            return
        events = [dict(event) for event in raw_events if isinstance(event, dict)]
        if len(events) != len(raw_events):
            raise WorkflowRunError(
                "RECORDING_EVENT_INVALID", "录制浏览器返回了无效步骤", 500
            )
        try:
            self._require_recordings().append(
                session_id, events, now=datetime.now(UTC)
            )
        except ValueError as error:
            state = self._require_browser()
            await self._command("recorder_stop")
            self._require_recordings().stop(session_id, now=datetime.now(UTC))
            state.recorder_session_id = None
            raise WorkflowRunError("RECORDING_LIMIT_REACHED", str(error), 413) from error

    def _require_recordings(self) -> Any:
        if self._recordings is None:
            raise WorkflowRunError(
                "RECORDING_NOT_READY", "录制持久化服务尚未装配", 503
            )
        return self._recordings

    async def on_worker_event(self, event: dict[str, object]) -> None:
        if event.get("type") != "inspection:response":
            return
        request_id = event.get("requestId")
        if not isinstance(request_id, str):
            return
        waiter = self._waiters.pop(request_id, None)
        if waiter is not None and not waiter.done():
            waiter.set_result(dict(event))

    async def on_worker_exit(self, session_id: str, _return_code: int) -> None:
        state = self._state
        if state is None or state.session_id != session_id:
            return
        for waiter in self._waiters.values():
            if not waiter.done():
                waiter.set_exception(RuntimeError("inspection worker exited"))
        self._waiters.clear()
        if self._resources.owner_id == session_id:
            await self._resources.release(session_id)
        if state.picker_session_id:
            self._retired_pickers.add(state.picker_session_id)
        if state.recorder_session_id and self._recordings is not None:
            self._recordings.interrupt(
                state.recorder_session_id, now=datetime.now(UTC)
            )
        self._state = None

    async def _command(self, command: str, **values: Any) -> dict[str, Any]:
        state = self._require_browser()
        request_id = str(uuid4())
        future = asyncio.get_running_loop().create_future()
        self._waiters[request_id] = future
        try:
            await self._workers.send_command(
                state.session_id,
                {"command": command, "requestId": request_id, **values},
            )
            response = await asyncio.wait_for(future, 20)
        except BaseException:
            self._waiters.pop(request_id, None)
            raise
        if response.get("success") is not True or not isinstance(
            response.get("data"), dict
        ):
            raise WorkflowRunError(
                "INSPECTION_COMMAND_FAILED",
                str(response.get("error") or "浏览器操作失败"),
                409,
            )
        return dict(response["data"])

    def _require_browser(self) -> _BrowserState:
        if self._state is None:
            raise WorkflowRunError(
                "INSPECTION_BROWSER_CLOSED", "浏览器未打开，请先启动浏览器", 409
            )
        return self._state

    def _require_picker(self, session_id: str) -> _BrowserState:
        state = self._require_browser()
        if state.picker_session_id != session_id:
            raise _conflict("拾取结果不属于当前会话")
        return state

    def _picker_state(self, active: bool) -> dict[str, Any]:
        state = self._state
        session_id = state.picker_session_id if state else None
        return {
            "success": True,
            "sessionId": session_id or "none",
            "active": active,
            "selected": False,
        }

    def _kernel(self, profile: Profile) -> InstalledKernel:
        for kernel in self._installed():
            if (
                kernel.edition == profile.spec.browser_edition
                and kernel.version == profile.spec.browser_version
            ):
                return kernel
        raise KernelNotInstalled


def _conflict(message: str) -> WorkflowRunError:
    return WorkflowRunError("INSPECTION_SESSION_CONFLICT", message, 409)
