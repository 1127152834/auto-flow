from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from autoflow.application.profiles.service import ProfileService
from autoflow.application.workflows.node_browser_resources import (
    freeze_node_browser_resources,
)
from autoflow.domain.environments.identity import profile_from_request
from autoflow.domain.kernels.errors import LicenseInvalid
from autoflow.domain.kernels.models import InstalledKernel, KernelEdition, KernelRef
from autoflow.domain.profiles.errors import KernelNotInstalled
from autoflow.domain.profiles.models import Profile, ProfileBrowserProxy
from autoflow.domain.workflows.browser import WorkflowBrowserBusy
from autoflow.domain.workflows.browser_environment import node_browser_environments
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
    project_id: str | None = None
    browser_environment: dict[str, Any] | None = None
    phase: str = "starting"
    picker_session_id: str | None = None
    picker_fingerprint: tuple[str | None, str] | None = None
    recorder_session_id: str | None = None
    recorder_paused: bool = False
    recorder_pending: list[dict[str, Any]] = field(default_factory=list)


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
        self._node_browser_resources: Any = None
        self._node_environments: Any = None
        self._profiles = profiles
        self._installed = installed_kernels
        self._resolve_proxy = resolve_proxy
        self._read_license = read_license
        self._resources = resources
        self._workers = workers
        self._recordings = recordings
        self._state: _BrowserState | None = None
        self._starting_task: asyncio.Task[Any] | None = None
        self._retired_pickers: set[str] = set()
        self._waiters: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._lock = asyncio.Lock()
        self._picker_lock = asyncio.Lock()
        self._recording_command_lock = asyncio.Lock()

    def configure_node_browser_environments(self, resources, environments) -> None:
        self._node_browser_resources = resources
        self._node_environments = environments

    def busy(self) -> bool:
        return self._state is not None or self._workers.busy()

    def project_blockers(self, project_id: str) -> list[dict[str, Any]]:
        state = self._state
        if state is None or state.project_id != project_id:
            return []
        return [{"code": "STUDIO_INSPECTION_ACTIVE", "resource": {"type": "project", "projectId": project_id},
                 "state": state.phase, "message": "拾取或录制浏览器尚未清理，请先结束会话"}]

    def check_project_access(self, project_id: str | None, *, writable: bool = False,
                             browser: bool = True) -> None:
        if project_id is not None:
            self._require_recordings().check_project(project_id, writable=writable)
        if browser and self._state is not None and self._state.project_id != project_id:
            raise WorkflowRunError("INSPECTION_NOT_FOUND", "浏览器会话不属于当前项目", 404)

    async def open(self, *, profile_id: str | None, url: str | None = None,
                   project_id: str | None = None, browser_environment: dict[str, Any] | None = None) -> dict[str, Any]:
        async with self._lock:
            self.check_project_access(project_id, writable=True)
            if self._state is not None:
                self._require_browser()
                if (profile_id is not None and self._state.profile_id != profile_id) or (browser_environment is not None and self._state.browser_environment != browser_environment):
                    raise _conflict("当前浏览器使用其他 Profile，请先关闭")
                if url:
                    await self._command("navigate", url=url)
                return await self.status()
            frozen = None
            if browser_environment is not None:
                declarations = node_browser_environments({'schemaVersion':3, 'browserEnvironmentVersion':1, 'nodes':[{'id':'inspection','data':{'moduleType':'open_page','browserEnvironment':browser_environment}}]})
                if browser_environment.get('source') not in {'profile','newFromProfile','fixedEnvironment'} or self._node_browser_resources is None:
                    raise WorkflowRunError('BROWSER_INITIALIZATION_REQUIRED', '请选择新建实例或固定环境的打开网页节点', 422)
                defaults = self._node_environments.projects.get(project_id).default_resources if project_id else {}
                frozen = freeze_node_browser_resources(self._node_browser_resources, self._node_environments, project_id, declarations, defaults or {})['inspection']
                profile = profile_from_request(frozen)
                profile_id = profile.id
            else:
                if not profile_id:
                    raise WorkflowRunError('INSPECTION_PROFILE_REQUIRED', '请选择浏览器初始化节点', 422)
                profile = self._profiles.get(profile_id)
            kernel = self._kernel(profile)
            session_id = str(uuid4())
            acquired = False
            state = _BrowserState(session_id, profile_id, project_id=project_id, browser_environment=browser_environment)
            if self._recordings is not None:
                self._recordings.admit_browser(project_id, lambda: setattr(self, "_state", state))
            else:
                self._state = state
            self._starting_task = asyncio.current_task()
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
                if frozen is not None:
                    def prepare(directory):
                        target = directory / 'preview' / 'instances' / 'browser'
                        payload['userDataDir'] = str(target)
                        if frozen.get('environmentRef'):
                            self._node_environments.prepare_studio_copy(frozen, target)
                    await self._workers.start(session_id, profile_id, kernel.executable_path, payload, prepare_directory=prepare)
                else:
                    await self._workers.start(session_id, profile_id, kernel.executable_path, payload)
                state.phase = "ready"
                return await self.status()
            except BaseException as error:
                state.phase = "closing"
                if self._workers.busy():
                    await self._workers.stop(session_id)
                if self._workers.busy():
                    raise WorkflowRunError("INSPECTION_CLEANUP_PENDING", "浏览器清理尚未确认", 503) from error
                if acquired and self._resources.owner_id == session_id:
                    await self._resources.release(session_id)
                if self._state is state:
                    self._state = None
                if isinstance(error, asyncio.CancelledError):
                    raise
                if isinstance(error, WorkflowRunError):
                    raise
                if isinstance(error, WorkflowBrowserBusy):
                    raise _conflict("当前工作区已有活跃浏览器会话") from error
                raise WorkflowRunError(
                    "INSPECTION_START_FAILED", "拾取浏览器启动失败", 503
                ) from error

            finally:
                if self._starting_task is asyncio.current_task():
                    self._starting_task = None

    async def close(self, session_id: str | None = None, *, project_id: str | None = None) -> dict[str, Any]:
        self.check_project_access(project_id)
        state = self._state
        if state is not None and session_id is not None and state.session_id != session_id:
            raise _conflict("浏览器会话已变化")
        if self._starting_task is not None and self._starting_task is not asyncio.current_task():
            self._starting_task.cancel()
        async with self._picker_lock:
            return await self._close(session_id, project_id=project_id)

    async def _close(self, session_id: str | None = None, *, project_id: str | None = None) -> dict[str, Any]:
        async with self._lock:
            self.check_project_access(project_id)
            state = self._state
            if state is None:
                return {"success": True}
            if session_id is not None and session_id != state.session_id:
                raise _conflict("浏览器会话已变化")
            if state.recorder_session_id is not None:
                raise _conflict("请先停止录制，再关闭浏览器")
            state.phase = "closing"
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
                    state.recorder_session_id, after_seq=0, project_id=state.project_id
                )
            state = self._state
            if state is not None:
                await self.close(state.session_id, project_id=state.project_id)
        finally:
            await self._workers.shutdown()
            state = self._state
            if state is not None:
                await self.on_worker_exit(state.session_id, -1)

    async def status(self) -> dict[str, Any]:
        state = self._state
        return {
            "isOpen": state is not None,
            "projectId": state.project_id if state else None,
            "phase": state.phase if state else "closed",
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
        self, *, session_id: str, profile_id: str | None, url: str | None, project_id: str | None = None, browser_environment: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        async with self._picker_lock:
            return await self._start_picker(
                session_id=session_id, profile_id=profile_id, url=url, project_id=project_id, browser_environment=browser_environment
            )

    async def _start_picker(
        self, *, session_id: str, profile_id: str | None, url: str | None, project_id: str | None = None, browser_environment: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.check_project_access(project_id, writable=True)
        fingerprint = (url, json.dumps([profile_id,browser_environment], sort_keys=True))
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
            await self.open(profile_id=profile_id, url=url, project_id=project_id, browser_environment=browser_environment)
            state = self._require_browser()
        elif (profile_id is not None and state.profile_id != profile_id) or (browser_environment is not None and state.browser_environment != browser_environment):
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

    async def start_recording(self, session_id: str, *, project_id: str | None = None, document_id: str | None = None) -> dict[str, Any]:
        self.check_project_access(project_id, writable=True)
        state = self._require_browser()
        repository = self._require_recordings()
        if state.picker_session_id is not None:
            raise _conflict("元素拾取期间不能开始录制")
        if state.recorder_session_id is not None:
            if state.recorder_session_id != session_id:
                raise _conflict("当前已有活跃录制会话")
            return {
                "success": True,
                **repository.start(session_id, now=datetime.now(UTC), project_id=project_id, document_id=document_id),
                "paused": state.recorder_paused,
            }
        try:
            receipt = repository.start(session_id, now=datetime.now(UTC), project_id=project_id, document_id=document_id)
        except ValueError as error:
            raise _conflict(str(error)) from error
        try:
            await self._command("recorder_start")
        except BaseException:
            repository.stop(session_id, now=datetime.now(UTC))
            raise
        state.recorder_session_id = session_id
        state.recorder_paused = False
        state.recorder_pending.clear()
        return {"success": True, **receipt, "paused": False}

    async def recording_command(
        self,
        command_id: str,
        *,
        action: str,
        session_id: str,
        after_seq: int = 0,
        project_id: str | None = None,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        if action not in {"start", "pause", "resume", "stop"}:
            raise WorkflowRunError("RECORDING_COMMAND_INVALID", "录制命令无效", 422)
        self.check_project_access(project_id, writable=action in {"start", "resume"}, browser=action in {"start", "resume", "pause"})
        repository = self._require_recordings()
        identity: dict[str, Any] = {"action": action, "sessionId": session_id, "afterSeq": after_seq}
        if project_id is not None:
            identity["projectId"] = project_id
        if document_id is not None:
            identity["documentId"] = document_id
        fingerprint = hashlib.sha256(
            json.dumps(
                identity,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        async with self._recording_command_lock:
            previous = repository.begin_command(
                command_id,
                session_id=session_id,
                action=action,
                request_hash=fingerprint,
                project_id=project_id,
                now=datetime.now(UTC),
            )
            if previous is not None:
                if previous["requestHash"] != fingerprint:
                    raise _conflict("commandId 已用于不同录制命令")
                return self._recording_command_result(previous)
            try:
                if action == "start":
                    result = await self.start_recording(session_id, project_id=project_id, document_id=document_id)
                elif action == "pause":
                    result = await self.pause_recording(session_id, after_seq=after_seq, project_id=project_id)
                elif action == "resume":
                    result = await self.resume_recording(session_id, after_seq=after_seq, project_id=project_id)
                else:
                    result = await self.stop_recording(session_id, after_seq=after_seq, project_id=project_id)
            except WorkflowRunError as error:
                repository.finish_command(
                    command_id,
                    status="failed",
                    payload={
                        "code": error.code,
                        "message": error.message,
                        "details": error.details,
                    },
                    http_status=error.status,
                    now=datetime.now(UTC),
                )
                raise
            result = {**result, "commandId": command_id}
            repository.finish_command(
                command_id,
                status="completed",
                payload=result,
                http_status=200,
                now=datetime.now(UTC),
            )
            return result

    def recording_command_status(self, command_id: str, *, project_id: str | None = None) -> dict[str, Any]:
        command = self._require_recordings().command(command_id, project_id=project_id)
        if command is None:
            raise WorkflowRunError(
                "RECORDING_COMMAND_NOT_FOUND", "录制命令不存在", 404
            )
        payload = command["payload"]
        failed = command["status"] == "failed"
        return {
            "success": True,
            "commandId": command["commandId"],
            "sessionId": command["sessionId"],
            "action": command["action"],
            "status": command["status"],
            "result": payload if command["status"] == "completed" else None,
            "error": payload.get("message") if failed else None,
            "errorCode": payload.get("code") if failed else None,
            "httpStatus": command["httpStatus"],
        }

    @staticmethod
    def _recording_command_result(command: Mapping[str, Any]) -> dict[str, Any]:
        if command["status"] == "completed":
            return dict(command["payload"])
        if command["status"] == "failed":
            payload = command["payload"]
            raise WorkflowRunError(
                str(payload.get("code") or "RECORDING_COMMAND_FAILED"),
                str(payload.get("message") or "录制命令失败"),
                int(command["httpStatus"]),
                dict(payload.get("details") or {}),
            )
        raise WorkflowRunError(
            "RECORDING_COMMAND_PENDING", "录制命令尚未确认，请查询原 commandId", 503
        )

    async def recording_events(
        self, session_id: str, *, after_seq: int, project_id: str | None = None
    ) -> dict[str, Any]:
        repository = self._require_recordings()
        repository.status(session_id, project_id=project_id)
        state = self._state
        if state is not None and state.recorder_session_id == session_id:
            response = await self._command("recorder_events")
            await self._append_recording_events(session_id, response.get("events"))
        else:
            current = repository.current(project_id=project_id)
            if current is None or current["sessionId"] != session_id:
                raise _conflict("录制会话不存在或已过期")
        try:
            return {"success": True, **repository.events(session_id, after_seq=after_seq, project_id=project_id)}
        except ValueError as error:
            raise _conflict(str(error)) from error

    async def stop_recording(
        self, session_id: str, *, after_seq: int, project_id: str | None = None
    ) -> dict[str, Any]:
        repository = self._require_recordings()
        state = self._state
        current = repository.current(project_id=project_id)
        if current is None or current["sessionId"] != session_id:
            raise _conflict("录制会话不存在或已过期")
        if state is not None and state.recorder_session_id == session_id:
            response = await self._command("recorder_stop")
            await self._append_recording_events(session_id, response.get("events"))
            repository.stop(session_id, now=datetime.now(UTC))
            state.recorder_session_id = None
            state.recorder_paused = False
        elif current["recording"]:
            raise _conflict("录制会话浏览器已失效")
        batch = repository.events(session_id, after_seq=after_seq, project_id=project_id)
        return {
            "success": True,
            "sessionId": session_id,
            "recording": False,
            "paused": False,
            "nextSeq": batch["nextSeq"],
            "hasMore": batch["hasMore"],
            "data": {"events": batch["data"]},
        }

    def recording_status(self, session_id: str | None, *, project_id: str | None = None) -> dict[str, Any]:
        repository = self._require_recordings()
        current = repository.current(project_id=project_id)
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
        paused = bool(recording and state and state.recorder_paused)
        return {"success": True, **current, "recording": recording, "paused": paused}

    async def pause_recording(
        self, session_id: str, *, after_seq: int, project_id: str | None = None
    ) -> dict[str, Any]:
        state = self._require_recording(session_id, project_id=project_id)
        if not state.recorder_paused:
            response = await self._command("recorder_pause")
            await self._append_recording_events(session_id, response.get("events"))
            state.recorder_paused = True
        return self._recording_control(session_id, after_seq=after_seq, paused=True, project_id=project_id)

    async def resume_recording(
        self, session_id: str, *, after_seq: int, project_id: str | None = None
    ) -> dict[str, Any]:
        state = self._require_recording(session_id, project_id=project_id)
        if state.recorder_paused:
            await self._command("recorder_resume")
            state.recorder_paused = False
        return self._recording_control(session_id, after_seq=after_seq, paused=False, project_id=project_id)

    def _require_recording(self, session_id: str, *, project_id: str | None = None) -> _BrowserState:
        current = self._require_recordings().current(project_id=project_id)
        state = self._state
        if (
            current is None
            or current["sessionId"] != session_id
            or not current["recording"]
            or state is None
            or state.recorder_session_id != session_id
        ):
            raise _conflict("录制会话不存在或已过期")
        return state

    def _recording_control(
        self, session_id: str, *, after_seq: int, paused: bool, project_id: str | None = None
    ) -> dict[str, Any]:
        batch = self._require_recordings().events(session_id, after_seq=after_seq, project_id=project_id)
        return {
            "success": True,
            "sessionId": session_id,
            "recording": True,
            "paused": paused,
            "nextSeq": batch["nextSeq"],
            "hasMore": batch["hasMore"],
            "data": {"events": batch["data"]},
        }

    def read_recording_review(self, document_id: str, *, project_id: str | None = None) -> dict[str, Any]:
        review = self._require_recordings().read_review(document_id, project_id=project_id)
        if review is None:
            raise WorkflowRunError(
                "RECORDING_REVIEW_NOT_FOUND", "录制审查不存在", 404
            )
        return review

    def save_recording_review(
        self, document_id: str, request: Mapping[str, Any], *, project_id: str | None = None
    ) -> dict[str, Any]:
        try:
            return self._require_recordings().save_review(
                document_id,
                project_id=project_id,
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
        if not isinstance(raw_events, list):
            raise WorkflowRunError(
                "RECORDING_EVENT_INVALID", "录制浏览器返回了无效步骤", 500
            )
        events = [dict(event) for event in raw_events if isinstance(event, dict)]
        if len(events) != len(raw_events):
            raise WorkflowRunError(
                "RECORDING_EVENT_INVALID", "录制浏览器返回了无效步骤", 500
            )
        state = self._require_browser()
        events = [*state.recorder_pending, *events]
        if not events:
            return
        try:
            self._require_recordings().append(
                session_id, events, now=datetime.now(UTC)
            )
        except ValueError as error:
            await self._command("recorder_stop")
            self._require_recordings().stop(session_id, now=datetime.now(UTC))
            state.recorder_session_id = None
            state.recorder_paused = False
            state.recorder_pending.clear()
            raise WorkflowRunError("RECORDING_LIMIT_REACHED", str(error), 413) from error
        except Exception as error:
            state.recorder_pending = events
            raise WorkflowRunError(
                "RECORDING_PERSIST_FAILED",
                "录制步骤暂未写入工作区，请重试",
                503,
            ) from error
        state.recorder_pending.clear()

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
        if self._state.phase != "ready":
            raise _conflict("浏览器正在启动或清理，请稍后重试")
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
