from __future__ import annotations

import asyncio
import copy
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast

from autoflow.adapters.events.workflows import StudioEventJournal
from autoflow.application.models.service import ModelExecutionBinding
from autoflow.application.profiles.service import ProfileService
from autoflow.domain.kernels.errors import LicenseInvalid
from autoflow.domain.kernels.models import InstalledKernel, KernelRef
from autoflow.domain.models.errors import ModelError
from autoflow.domain.profiles.errors import KernelNotInstalled
from autoflow.domain.profiles.models import Profile, ProfileBrowserProxy
from autoflow.domain.workflows.browser import WorkflowBrowserBusy
from autoflow.domain.workflows.document import WorkflowDraft
from autoflow.domain.workflows.errors import WorkflowDocumentError
from autoflow.domain.workflows.modules import custom_module_reference
from autoflow.domain.workflows.runs import (
    TerminalRunStatus,
    WorkflowRun,
    WorkflowRunError,
    WorkflowRunStart,
)
from autoflow.domain.workflows.variables import resolve_value

from .documents import WorkflowDocumentService
from .modules import CustomModuleService
from .runs import WorkflowRunRepository, WorkflowRunService
from .runtime import WorkflowRuntime


class WorkflowWorkers(Protocol):
    async def start(
        self,
        run_id: str,
        profile_id: str,
        executable: Path | None,
        payload: dict[str, Any],
    ) -> object: ...

    async def stop(self, run_id: str) -> None: ...

    async def send_command(self, run_id: str, command: dict[str, Any]) -> None: ...

    def busy(self) -> bool: ...


class WorkflowResources(Protocol):
    @property
    def owner_id(self) -> str | None: ...

    async def acquire(
        self, owner_id: str, profile_id: str, kernel: KernelRef
    ) -> None: ...

    async def release(self, owner_id: str) -> None: ...


class ProfileReader(Protocol):
    def get(self, profile_id: str) -> Profile: ...


class WorkflowRunCoordinator:
    def __init__(
        self,
        *,
        documents: WorkflowDocumentService,
        runs: WorkflowRunService,
        run_repository: WorkflowRunRepository,
        runtime: WorkflowRuntime,
        profiles: ProfileService | ProfileReader,
        installed_kernels: Callable[[], Sequence[InstalledKernel]],
        resolve_proxy: Callable[[Profile, str], Awaitable[ProfileBrowserProxy | None]],
        read_license: Callable[[], str | None],
        workers: WorkflowWorkers,
        resources: WorkflowResources,
        events: StudioEventJournal,
        artifact_root: Path,
        modules: CustomModuleService | None = None,
        resolve_model: Callable[[str], ModelExecutionBinding] | None = None,
    ) -> None:
        self._documents = documents
        self._runs = runs
        self._repository = run_repository
        self._runtime = runtime
        self._profiles = profiles
        self._installed_kernels = installed_kernels
        self._resolve_proxy = resolve_proxy
        self._read_license = read_license
        self._workers = workers
        self._resources = resources
        self._events = events
        self._artifact_root = artifact_root.resolve()
        self._modules = modules
        self._resolve_model = resolve_model
        self._terminal_intents: dict[str, dict[str, Any]] = {}
        self._command_lock = asyncio.Lock()
        self._event_command_lock = asyncio.Lock()
        self._input_prompts: dict[str, dict[str, str]] = {}
        self._js_requests: dict[str, dict[str, str]] = {}
        self._speech_requests: dict[str, dict[str, str]] = {}
        self._command_receipts: dict[str, tuple[str, dict[str, Any], int]] = {}
        self._command_waiters: dict[str, asyncio.Future[None]] = {}

    async def start(
        self, workflow_id: str, request: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        run_id = _required_string(request, "runId")
        document_id = _required_string(request, "documentId")
        profile_id = _required_string(request, "profileId")
        mode = (
            "debug" if bool(request.get("debug") or request.get("stepMode")) else "run"
        )
        headless = request.get("headless", False)
        if not isinstance(headless, bool):
            raise WorkflowRunError("RUN_REQUEST_INVALID", "headless 必须是布尔值", 422)

        async with self._command_lock:
            supplied_document = request.get("document")
            if supplied_document is None:
                saved = self._documents.get(workflow_id)
                draft = WorkflowDraft(
                    saved.id,
                    saved.name,
                    copy.deepcopy(saved.document),
                    copy.deepcopy(saved.layout),
                )
            elif isinstance(supplied_document, Mapping):
                draft = WorkflowDraft.from_payload(supplied_document)
            else:
                raise WorkflowRunError(
                    "RUN_REQUEST_INVALID", "document 必须是工作流对象", 422
                )
            document = draft.to_payload()
            issues = self._runtime.preflight(document)
            if issues:
                raise WorkflowRunError(
                    "WORKFLOW_PREFLIGHT_FAILED",
                    "工作流包含尚未迁入或无法运行的节点",
                    422,
                    {
                        "issues": [
                            {
                                "nodeId": issue.node_id,
                                "path": issue.path,
                                "code": issue.code,
                                "message": issue.message,
                            }
                            for issue in issues
                        ]
                    },
                )
            custom_module_dependencies: dict[str, dict[str, object]] = {}
            try:
                workflow_dependencies = _workflow_dependency_snapshots(
                    self._documents,
                    document,
                    modules=self._modules,
                    custom_modules=custom_module_dependencies,
                )
            except WorkflowDocumentError as error:
                raise WorkflowRunError(
                    error.code, error.message, error.status, error.details
                ) from error
            for module_id, snapshot in custom_module_dependencies.items():
                workflow = snapshot.get("workflow")
                if not isinstance(workflow, Mapping):
                    raise WorkflowRunError(
                        "CUSTOM_MODULE_WORKFLOW_INVALID",
                        f"自定义模块工作流无效: {module_id}",
                        422,
                    )
                module_issues = self._runtime.preflight(workflow)
                if module_issues:
                    raise WorkflowRunError(
                        "WORKFLOW_PREFLIGHT_FAILED",
                        "自定义模块包含尚未迁入或无法运行的节点",
                        422,
                        {
                            "moduleId": module_id,
                            "issues": [
                                {
                                    "nodeId": issue.node_id,
                                    "path": issue.path,
                                    "code": issue.code,
                                    "message": issue.message,
                                }
                                for issue in module_issues
                            ],
                        },
                    )
            requires_browser = (
                self._runtime.requires_browser(document)
                or any(
                    self._runtime.requires_browser(snapshot)
                    for snapshot in workflow_dependencies.values()
                )
                or any(
                    self._runtime.requires_browser(workflow)
                    for snapshot in custom_module_dependencies.values()
                    if isinstance((workflow := snapshot.get("workflow")), Mapping)
                )
            )
            model_bindings = self._resolve_model_bindings(
                document,
                workflow_dependencies,
                custom_module_dependencies,
            )
            profile = self._profiles.get(profile_id)
            kernel = self._kernel(profile) if requires_browser else None
            start = WorkflowRunStart(
                run_id=run_id,
                workflow_id=workflow_id,
                document_id=document_id,
                workflow_name=draft.name,
                document_snapshot=copy.deepcopy(draft.document),
                layout_snapshot=copy.deepcopy(draft.layout),
                profile_id=profile_id,
                profile_snapshot={
                    **_profile_snapshot(profile),
                    "runOptions": {
                        "headless": headless,
                        "startNodeId": request.get("startNodeId"),
                        "mode": mode,
                    },
                },
                mode=cast(Any, mode),
                custom_module_snapshots=copy.deepcopy(custom_module_dependencies),
            )
            run = self._runs.start(start)
            if run.status != "starting" or self._resources.owner_id == run_id:
                return _summary(run)

            acquired = False
            try:
                proxy = None
                license_key = None
                if requires_browser:
                    assert kernel is not None
                    await self._resources.acquire(
                        run_id,
                        profile_id,
                        KernelRef(
                            cast(Any, profile.spec.browser_edition),
                            profile.spec.browser_version,
                        ),
                    )
                    acquired = True
                    proxy = await self._resolve_proxy(profile, run_id)
                    license_key = (
                        self._read_license()
                        if profile.spec.browser_edition == "licensed"
                        else None
                    )
                    if profile.spec.browser_edition == "licensed" and not license_key:
                        raise LicenseInvalid
                payload = _worker_payload(
                    start,
                    profile,
                    proxy,
                    license_key,
                    executable=kernel.executable_path if kernel is not None else None,
                    headless=headless,
                    artifact_root=self._artifact_root,
                    requires_browser=requires_browser,
                    workflow_dependencies=workflow_dependencies,
                    custom_module_dependencies=custom_module_dependencies,
                    model_bindings=model_bindings,
                )
                await self._workers.start(
                    run_id,
                    profile_id,
                    kernel.executable_path if kernel is not None else None,
                    payload,
                )
                self._runs.mark_running(run_id)
                running = self._runs.get(run_id)
                await self._events.publish(
                    "execution:started",
                    {
                        "workflowId": workflow_id,
                        "runId": run_id,
                        "documentId": document_id,
                    },
                )
                return _summary(running)
            except BaseException as error:
                if self._workers.busy():
                    await self._workers.stop(run_id)
                if acquired and self._resources.owner_id == run_id:
                    await self._resources.release(run_id)
                failure = (
                    {
                        "code": error.code,
                        "message": str(error),
                    }
                    if isinstance(error, LicenseInvalid)
                    else {
                        "code": "RUN_START_FAILED",
                        "message": "工作流浏览器启动失败",
                    }
                )
                failed = self._runs.finish(
                    run_id,
                    status="failed",
                    cleanup_completed=True,
                    error=failure,
                    terminal_log=_terminal_log("failed", 0, 0),
                )
                await self._events.publish(
                    "execution:completed",
                    {
                        **_event_identity(failed),
                        "result": {
                            "status": "failed",
                            "executedNodes": 0,
                            "failedNodes": 0,
                        },
                    },
                )
                if isinstance(error, WorkflowBrowserBusy):
                    raise WorkflowRunError(
                        "WORKFLOW_BROWSER_BUSY",
                        "当前工作区已有活跃浏览器会话",
                        409,
                    ) from error
                if isinstance(error, LicenseInvalid):
                    raise
                if isinstance(error, (RuntimeError, OSError)):
                    raise WorkflowRunError(
                        "RUN_START_FAILED", "工作流浏览器启动失败", 503
                    ) from error
                raise

    def _resolve_model_bindings(
        self,
        document: Mapping[str, Any],
        workflow_dependencies: Mapping[str, Mapping[str, Any]],
        custom_module_dependencies: Mapping[str, Mapping[str, object]],
    ) -> tuple[ModelExecutionBinding, ...]:
        references = _model_references(
            [
                document,
                *workflow_dependencies.values(),
                *(
                    workflow
                    for snapshot in custom_module_dependencies.values()
                    if isinstance((workflow := snapshot.get("workflow")), Mapping)
                ),
            ]
        )
        if not references:
            return ()
        if self._resolve_model is None:
            raise WorkflowRunError("MODEL_SERVICE_UNAVAILABLE", "模型服务不可用", 503)
        bindings: dict[str, ModelExecutionBinding] = {}
        for model_id, node_id, path in references:
            if model_id in bindings:
                continue
            try:
                bindings[model_id] = self._resolve_model(model_id)
            except ModelError as error:
                raise WorkflowRunError(
                    error.code,
                    error.message,
                    error.status,
                    {**error.details, "nodeId": node_id, "path": path},
                ) from error
        return tuple(bindings.values())

    async def stop(self, workflow_id: str, run_id: str) -> Mapping[str, Any]:
        async with self._command_lock:
            run = self._runs.get(run_id)
            if run.workflow_id != workflow_id:
                raise WorkflowRunError(
                    "RUN_OWNERSHIP_MISMATCH", "运行不属于指定工作流", 409
                )
            if run.status in {"completed", "failed", "stopped", "interrupted"}:
                return _summary(run)
            self._runs.request_stop(run_id)
            await self._workers.stop(run_id)
            return _summary(self._runs.get(run_id))

    async def on_worker_event(self, event: dict[str, object]) -> None:
        run_id = _required_string(event, "runId")
        run = self._runs.get(run_id)
        event_type = _required_string(event, "type")
        if event_type == "execution:command_applied":
            command_id = _required_string(event, "commandId")
            waiter = self._command_waiters.get(command_id)
            if waiter is not None and not waiter.done():
                waiter.set_result(None)
            return
        if event_type == "execution:input_prompt":
            request_id = _required_string(event, "requestId")
            prompt_node_id = _required_string(event, "nodeId")
            payload = {
                key: copy.deepcopy(value)
                for key, value in event.items()
                if key not in {"type", "runId"}
            }
            self._input_prompts[request_id] = {
                "requestId": request_id,
                "workflowId": run.workflow_id,
                "runId": run_id,
                "nodeId": prompt_node_id,
                "status": "pending",
            }
            persisted = self._repository.append_event(
                run_id,
                event_type,
                payload,
                now=datetime_now(),
                node_id=prompt_node_id,
                execution_id=_optional_string(event.get("executionId")),
                run_patch={"currentNodeId": prompt_node_id},
            )
            await self._events.publish(
                event_type,
                {
                    **payload,
                    "runId": run_id,
                    "workflowId": run.workflow_id,
                    "sequence": persisted.sequence,
                },
            )
            return
        if event_type == "execution:input_prompt_closed":
            request_id = _required_string(event, "requestId")
            state = self._input_prompts.get(request_id)
            status = _required_string(event, "status")
            if state is not None and status in {"answered", "cancelled", "expired"}:
                state["status"] = status
            return
        if event_type == "execution:js_script":
            request_id = _required_string(event, "requestId")
            js_node_id = _required_string(event, "nodeId")
            payload = {
                key: copy.deepcopy(value)
                for key, value in event.items()
                if key not in {"type", "runId"}
            }
            self._js_requests[request_id] = {
                "requestId": request_id,
                "workflowId": run.workflow_id,
                "runId": run_id,
                "nodeId": js_node_id,
                "status": "pending",
            }
            persisted = self._repository.append_event(
                run_id,
                event_type,
                payload,
                now=datetime_now(),
                node_id=js_node_id,
                execution_id=_optional_string(event.get("executionId")),
                run_patch={"currentNodeId": js_node_id},
            )
            await self._events.publish(
                event_type,
                {
                    **payload,
                    "runId": run_id,
                    "workflowId": run.workflow_id,
                    "sequence": persisted.sequence,
                },
            )
            return
        if event_type == "execution:js_script_closed":
            request_id = _required_string(event, "requestId")
            state = self._js_requests.get(request_id)
            status = _required_string(event, "status")
            if state is not None and status in {"completed", "failed", "expired"}:
                state["status"] = status
            return
        if event_type == "execution:tts_request":
            request_id = _required_string(event, "requestId")
            speech_node_id = _required_string(event, "nodeId")
            payload = {
                key: copy.deepcopy(value)
                for key, value in event.items()
                if key not in {"type", "runId"}
            }
            self._speech_requests[request_id] = {
                "requestId": request_id,
                "workflowId": run.workflow_id,
                "runId": run_id,
                "nodeId": speech_node_id,
                "status": "pending",
            }
            persisted = self._repository.append_event(
                run_id,
                event_type,
                payload,
                now=datetime_now(),
                node_id=speech_node_id,
                execution_id=_optional_string(event.get("executionId")),
                run_patch={"currentNodeId": speech_node_id},
            )
            await self._events.publish(
                event_type,
                {
                    **payload,
                    "runId": run_id,
                    "workflowId": run.workflow_id,
                    "sequence": persisted.sequence,
                },
            )
            return
        if event_type == "execution:tts_request_closed":
            request_id = _required_string(event, "requestId")
            state = self._speech_requests.get(request_id)
            status = _required_string(event, "status")
            if state is not None and status in {"completed", "failed", "expired"}:
                state["status"] = status
            return
        if event_type == "artifact:registered":
            self._repository.register_artifact(
                run_id=run_id,
                artifact_id=_required_string(event, "artifactId"),
                node_id=_required_string(event, "nodeId"),
                execution_id=_optional_string(event.get("executionId")),
                relative_path=_required_string(event, "relativePath"),
                size=_required_int(event, "size"),
                sha256=_required_string(event, "sha256"),
                mime_type=_required_string(event, "mimeType"),
                purpose=_required_string(event, "purpose"),
            )
            return
        if event_type in {"execution:completed", "execution:failed"}:
            self._terminal_intents[run_id] = copy.deepcopy(event)
            return
        node_id = _optional_string(event.get("nodeId"))
        execution_id = _optional_string(event.get("executionId"))
        if event_type == "execution:node_complete":
            if node_id is None or execution_id is None:
                raise WorkflowRunError("WORKER_EVENT_INVALID", "节点事件身份无效", 422)
            raw_execution_context = event.get("executionContext")
            if raw_execution_context is not None and not isinstance(
                raw_execution_context, Mapping
            ):
                raise WorkflowRunError(
                    "WORKER_EVENT_INVALID", "节点执行上下文无效", 422
                )
            execution_context = (
                copy.deepcopy(dict(raw_execution_context))
                if isinstance(raw_execution_context, Mapping)
                else None
            )
            success = event.get("success") is True
            artifact_ids = event.get("artifactIds", [])
            if not isinstance(artifact_ids, list) or not all(
                isinstance(item, str) for item in artifact_ids
            ):
                raise WorkflowRunError("WORKER_EVENT_INVALID", "节点产物身份无效", 422)
            result = {
                "success": success,
                "message": str(event.get("message") or ""),
                "error": event.get("error"),
                "data": copy.deepcopy(event.get("data")),
            }
            event_payload: dict[str, Any] = {"result": result}
            if execution_context is not None:
                event_payload["executionContext"] = execution_context
            persisted = self._repository.append_event(
                run_id,
                "execution:node-succeeded" if success else "execution:node-failed",
                event_payload,
                now=datetime_now(),
                node_id=node_id,
                execution_id=execution_id,
                run_patch={"currentNodeId": node_id},
                artifact_ids=tuple(artifact_ids),
            )
            completion_event: dict[str, Any] = {
                **_event_identity(run),
                "nodeId": node_id,
                "executionId": execution_id,
                "success": success,
                "sequence": persisted.sequence,
            }
            if execution_context is not None:
                completion_event["executionContext"] = execution_context
            await self._events.publish(
                "execution:node_complete",
                completion_event,
            )
            level = "success" if success else "error"
            message = str(event.get("message") or event.get("error") or "节点执行完成")
            log_payload: dict[str, Any] = {"level": level, "message": message}
            if execution_context is not None:
                log_payload["executionContext"] = execution_context
            log = self._repository.append_event(
                run_id,
                "execution:log",
                log_payload,
                now=datetime_now(),
                node_id=node_id,
                execution_id=execution_id,
            )
            await self._events.publish(
                "execution:log",
                {
                    **_event_identity(run),
                    "log": {
                        "sequence": log.sequence,
                        "id": f"{run_id}-{log.sequence}",
                        "timestamp": log.occurred_at.isoformat(),
                        "level": level,
                        "message": message,
                        "nodeId": node_id,
                        "executionId": execution_id,
                        "executionContext": execution_context,
                    },
                },
            )
            return
        payload = {
            key: copy.deepcopy(value)
            for key, value in event.items()
            if key not in {"type", "runId", "workflowId", "nodeId", "executionId"}
        }
        persisted = self._repository.append_event(
            run_id,
            event_type,
            payload,
            now=datetime_now(),
            node_id=node_id,
            execution_id=execution_id,
            run_patch={"currentNodeId": node_id} if node_id else None,
        )
        await self._events.publish(
            event_type,
            {
                **_event_identity(run),
                **({"nodeId": node_id} if node_id else {}),
                **({"executionId": execution_id} if execution_id else {}),
                **payload,
                "sequence": persisted.sequence,
            },
        )

    async def submit_event_command(
        self, command_id: str, event: str, data: Mapping[str, Any]
    ) -> tuple[dict[str, Any], int]:
        fingerprint = json.dumps(
            {"event": event, "data": data},
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        async with self._event_command_lock:
            previous = self._command_receipts.get(command_id)
            if previous is not None:
                old_fingerprint, receipt, status = previous
                if old_fingerprint != fingerprint:
                    return {
                        "commandId": command_id,
                        "success": False,
                        "error": "commandId 已用于不同请求",
                    }, 409
                return copy.deepcopy(receipt), status
            if event == "js_script_claim":
                return self._claim_js_script(command_id, fingerprint, data)
            if event == "js_script_result":
                return await self._complete_js_script(command_id, fingerprint, data)
            if event == "tts_claim":
                return self._claim_tts(command_id, fingerprint, data)
            if event == "tts_result":
                return await self._complete_tts(command_id, fingerprint, data)
            if event != "input_prompt_result":
                receipt = {
                    "commandId": command_id,
                    "success": False,
                    "error": "命令尚未实现",
                }
                self._command_receipts[command_id] = (fingerprint, receipt, 501)
                return copy.deepcopy(receipt), 501
            request_id = data.get("requestId")
            value = data.get("value")
            if (
                not isinstance(request_id, str)
                or not request_id
                or (value is not None and not isinstance(value, str))
                or set(data) != {"requestId", "value"}
            ):
                receipt = {
                    "commandId": command_id,
                    "success": False,
                    "error": "输入结果无效",
                }
                self._command_receipts[command_id] = (fingerprint, receipt, 422)
                return copy.deepcopy(receipt), 422
            state = self._input_prompts.get(request_id)
            if state is None or state["status"] != "pending":
                receipt = {
                    "commandId": command_id,
                    "success": False,
                    "error": "输入请求不存在或已结束",
                }
                self._command_receipts[command_id] = (fingerprint, receipt, 409)
                return copy.deepcopy(receipt), 409
            waiter = asyncio.get_running_loop().create_future()
            self._command_waiters[command_id] = waiter
            try:
                await self._workers.send_command(
                    state["runId"],
                    {
                        "type": event,
                        "commandId": command_id,
                        "requestId": request_id,
                        "value": value,
                    },
                )
                await asyncio.wait_for(waiter, timeout=10)
            except (RuntimeError, TimeoutError):
                receipt = {
                    "commandId": command_id,
                    "success": False,
                    "error": "输入结果未被运行进程确认",
                }
                self._command_receipts[command_id] = (fingerprint, receipt, 503)
                return copy.deepcopy(receipt), 503
            finally:
                self._command_waiters.pop(command_id, None)
            state["status"] = "cancelled" if value is None else "answered"
            receipt = {"commandId": command_id, "success": True}
            self._command_receipts[command_id] = (fingerprint, receipt, 200)
            return copy.deepcopy(receipt), 200

    def _claim_js_script(
        self, command_id: str, fingerprint: str, data: Mapping[str, Any]
    ) -> tuple[dict[str, Any], int]:
        request_id = data.get("requestId")
        claim_id = data.get("claimId")
        if (
            not isinstance(request_id, str)
            or not request_id
            or not isinstance(claim_id, str)
            or not claim_id
            or set(data) != {"requestId", "claimId"}
        ):
            return self._remember_command(
                command_id, fingerprint, "脚本请求及领取标识无效", 422
            )
        state = self._js_requests.get(request_id)
        if state is None or state["status"] not in {"pending", "claimed"}:
            return self._remember_command(
                command_id, fingerprint, "脚本请求不存在或已结束", 409
            )
        if state["status"] == "claimed" and state.get("claimId") != claim_id:
            return self._remember_command(
                command_id, fingerprint, "脚本已由其它客户端领取", 409
            )
        state["status"] = "claimed"
        state["claimId"] = claim_id
        receipt = {"commandId": command_id, "success": True, "requestId": request_id}
        self._command_receipts[command_id] = (fingerprint, receipt, 200)
        return copy.deepcopy(receipt), 200

    async def _complete_js_script(
        self, command_id: str, fingerprint: str, data: Mapping[str, Any]
    ) -> tuple[dict[str, Any], int]:
        request_id = data.get("requestId")
        claim_id = data.get("claimId")
        success = data.get("success")
        variables = data.get("variables")
        error = data.get("error")
        allowed = {"requestId", "claimId", "success", "result", "variables", "error"}
        if (
            not isinstance(request_id, str)
            or not request_id
            or not isinstance(claim_id, str)
            or not claim_id
            or not isinstance(success, bool)
            or not set(data).issubset(allowed)
            or (success and not isinstance(variables, Mapping))
            or (not success and (not isinstance(error, str) or not error.strip()))
        ):
            return self._remember_command(
                command_id, fingerprint, "脚本结果格式无效", 422
            )
        state = self._js_requests.get(request_id)
        if (
            state is None
            or state["status"] != "claimed"
            or state.get("claimId") != claim_id
        ):
            return self._remember_command(
                command_id, fingerprint, "脚本结果不属于当前领取者", 409
            )
        waiter = asyncio.get_running_loop().create_future()
        self._command_waiters[command_id] = waiter
        try:
            await self._workers.send_command(
                state["runId"],
                {"type": "js_script_result", "commandId": command_id, **dict(data)},
            )
            await asyncio.wait_for(waiter, timeout=10)
        except (RuntimeError, TimeoutError):
            return self._remember_command(
                command_id, fingerprint, "脚本结果未被运行进程确认", 503
            )
        finally:
            self._command_waiters.pop(command_id, None)
        state["status"] = "completed" if success else "failed"
        receipt = {"commandId": command_id, "success": True, "requestId": request_id}
        self._command_receipts[command_id] = (fingerprint, receipt, 200)
        return copy.deepcopy(receipt), 200

    def _remember_command(
        self,
        command_id: str,
        fingerprint: str,
        error: str,
        status: int,
    ) -> tuple[dict[str, Any], int]:
        receipt = {"commandId": command_id, "success": False, "error": error}
        self._command_receipts[command_id] = (fingerprint, receipt, status)
        return copy.deepcopy(receipt), status

    def _claim_tts(
        self, command_id: str, fingerprint: str, data: Mapping[str, Any]
    ) -> tuple[dict[str, Any], int]:
        request_id = data.get("requestId")
        claim_id = data.get("claimId")
        if (
            not isinstance(request_id, str)
            or not request_id
            or not isinstance(claim_id, str)
            or not claim_id
            or set(data) != {"requestId", "claimId"}
        ):
            return self._remember_command(
                command_id, fingerprint, "语音请求及领取标识无效", 422
            )
        state = self._speech_requests.get(request_id)
        if state is None or state["status"] not in {"pending", "claimed"}:
            return self._remember_command(
                command_id, fingerprint, "语音请求不存在或已结束", 409
            )
        if state["status"] == "claimed" and state.get("claimId") != claim_id:
            return self._remember_command(
                command_id, fingerprint, "语音已由其它客户端领取", 409
            )
        state["status"] = "claimed"
        state["claimId"] = claim_id
        receipt = {"commandId": command_id, "success": True, "requestId": request_id}
        self._command_receipts[command_id] = (fingerprint, receipt, 200)
        return copy.deepcopy(receipt), 200

    async def _complete_tts(
        self, command_id: str, fingerprint: str, data: Mapping[str, Any]
    ) -> tuple[dict[str, Any], int]:
        request_id = data.get("requestId")
        claim_id = data.get("claimId")
        success = data.get("success")
        error = data.get("error")
        allowed = {"requestId", "claimId", "success", "error"}
        if (
            not isinstance(request_id, str)
            or not request_id
            or not isinstance(claim_id, str)
            or not claim_id
            or not isinstance(success, bool)
            or not set(data).issubset(allowed)
            or (not success and (not isinstance(error, str) or not error.strip()))
        ):
            return self._remember_command(
                command_id, fingerprint, "语音结果格式无效", 422
            )
        state = self._speech_requests.get(request_id)
        if (
            state is None
            or state["status"] != "claimed"
            or state.get("claimId") != claim_id
        ):
            return self._remember_command(
                command_id, fingerprint, "语音结果不属于当前领取者", 409
            )
        waiter = asyncio.get_running_loop().create_future()
        self._command_waiters[command_id] = waiter
        try:
            await self._workers.send_command(
                state["runId"],
                {"type": "tts_result", "commandId": command_id, **dict(data)},
            )
            await asyncio.wait_for(waiter, timeout=10)
        except (RuntimeError, TimeoutError):
            return self._remember_command(
                command_id, fingerprint, "语音结果未被运行进程确认", 503
            )
        finally:
            self._command_waiters.pop(command_id, None)
        state["status"] = "completed" if success else "failed"
        receipt = {"commandId": command_id, "success": True, "requestId": request_id}
        self._command_receipts[command_id] = (fingerprint, receipt, 200)
        return copy.deepcopy(receipt), 200

    def event_command(self, command_id: str) -> tuple[dict[str, Any], int]:
        record = self._command_receipts.get(command_id)
        if record is None:
            raise WorkflowRunError("COMMAND_NOT_FOUND", "命令记录不存在", 404)
        _, receipt, status = record
        return {**copy.deepcopy(receipt), "httpStatus": status}, 200

    def input_prompt_state(self, request_id: str) -> dict[str, str]:
        state = self._input_prompts.get(request_id)
        if state is None:
            raise WorkflowRunError("INPUT_PROMPT_NOT_FOUND", "输入请求不存在", 404)
        return {
            key: state[key] for key in ("requestId", "workflowId", "nodeId", "status")
        }

    def js_script_state(self, request_id: str) -> dict[str, str]:
        state = self._js_requests.get(request_id)
        if state is None:
            raise WorkflowRunError("JS_SCRIPT_REQUEST_NOT_FOUND", "脚本请求不存在", 404)
        keys = ("requestId", "workflowId", "nodeId", "status", "claimId")
        return {key: state[key] for key in keys if key in state}

    def tts_request_state(self, request_id: str) -> dict[str, str]:
        state = self._speech_requests.get(request_id)
        if state is None:
            raise WorkflowRunError("TTS_REQUEST_NOT_FOUND", "语音请求不存在", 404)
        keys = ("requestId", "workflowId", "nodeId", "status", "claimId")
        return {key: state[key] for key in keys if key in state}

    async def on_worker_exit(self, run_id: str, return_code: int) -> None:
        # WorkflowWorkerManager invokes this only after the process tree and its
        # private directory are gone. Resource release is the final cleanup step.
        run = self._runs.get(run_id)
        for state in self._input_prompts.values():
            if state["runId"] == run_id and state["status"] == "pending":
                state["status"] = "expired"
        for state in self._js_requests.values():
            if state["runId"] == run_id and state["status"] in {"pending", "claimed"}:
                state["status"] = "expired"
        for state in self._speech_requests.values():
            if state["runId"] == run_id and state["status"] in {"pending", "claimed"}:
                state["status"] = "expired"
        if self._resources.owner_id == run_id:
            await self._resources.release(run_id)
        intent = self._terminal_intents.pop(run_id, None)
        if run.stop_requested:
            terminal: TerminalRunStatus = "stopped"
        elif (
            intent and intent.get("type") == "execution:completed" and return_code == 0
        ):
            terminal = "completed"
        else:
            terminal = "failed"
        error = None
        if terminal == "failed":
            error = {
                "code": "WORKFLOW_EXECUTION_FAILED",
                "message": str((intent or {}).get("error") or "工作流执行失败"),
            }
        finished = self._runs.finish(
            run_id,
            status=terminal,
            cleanup_completed=True,
            error=error,
            terminal_log=_terminal_log(
                terminal,
                int((intent or {}).get("executedNodes") or 0),
                1 if terminal == "failed" else 0,
            ),
        )
        if terminal == "stopped":
            await self._events.publish("execution:stopped", _event_identity(finished))
        else:
            await self._events.publish(
                "execution:completed",
                {
                    **_event_identity(finished),
                    "result": {
                        "status": terminal,
                        "executedNodes": int((intent or {}).get("executedNodes") or 0),
                        "failedNodes": 1 if terminal == "failed" else 0,
                    },
                },
            )

    def _kernel(self, profile: Profile) -> InstalledKernel:
        for kernel in self._installed_kernels():
            if (
                kernel.edition == profile.spec.browser_edition
                and kernel.version == profile.spec.browser_version
            ):
                return kernel
        raise KernelNotInstalled


def datetime_now() -> datetime:
    return datetime.now(UTC)


def _terminal_log(
    status: TerminalRunStatus, executed_nodes: int, failed_nodes: int
) -> dict[str, str]:
    label = {
        "completed": "执行完成",
        "stopped": "执行已停止",
        "failed": "执行失败",
        "interrupted": "执行已中断",
    }[status]
    level = (
        "success"
        if status == "completed"
        else "info"
        if status == "stopped"
        else "error"
    )
    return {
        "level": level,
        "message": f"{label}，共执行 {executed_nodes} 个节点，失败 {failed_nodes} 个",
    }


def _profile_snapshot(profile: Profile) -> dict[str, Any]:
    spec = asdict(profile.spec)
    spec.pop("start_url", None)
    return {
        "id": profile.id,
        "fingerprintSeed": profile.fingerprint_seed,
        **spec,
    }


def _worker_payload(
    start: WorkflowRunStart,
    profile: Profile,
    proxy: ProfileBrowserProxy | None,
    license_key: str | None,
    *,
    executable: Path | None,
    headless: bool,
    artifact_root: Path,
    requires_browser: bool,
    workflow_dependencies: dict[str, dict[str, Any]],
    custom_module_dependencies: dict[str, dict[str, object]],
    model_bindings: Sequence[ModelExecutionBinding],
) -> dict[str, Any]:
    spec = profile.spec
    executable_document = WorkflowDraft(
        start.document_id,
        start.workflow_name,
        copy.deepcopy(start.document_snapshot),
        copy.deepcopy(start.layout_snapshot),
    ).to_payload()
    return {
        "runId": start.run_id,
        "workflowId": start.workflow_id,
        "profileId": profile.id,
        "fingerprintSeed": profile.fingerprint_seed,
        "locale": spec.locale,
        "timezone": spec.timezone,
        "geoip": spec.geoip,
        "humanize": spec.humanize,
        "humanPreset": spec.human_preset,
        "userAgent": spec.user_agent,
        "viewport": spec.viewport,
        "colorScheme": spec.color_scheme,
        "extensionPaths": spec.extension_paths,
        "expertArgs": spec.expert_args,
        "browserVersion": spec.browser_version,
        "releaseChannel": spec.release_channel,
        "proxy": (
            {
                "server": proxy.server,
                "username": proxy.username,
                "password": proxy.password,
            }
            if proxy
            else None
        ),
        "licenseKey": license_key,
        "headless": headless,
        "artifactRoot": str(artifact_root),
        "requiresBrowser": requires_browser,
        "document": executable_document,
        "workflowDependencies": workflow_dependencies,
        "customModuleDependencies": custom_module_dependencies,
        "modelBindings": [
            {
                "modelId": binding.model_id,
                "modelKey": binding.model_key,
                "presetId": binding.connection.preset_id,
                "providerKind": binding.connection.provider_kind,
                "baseUrl": binding.connection.base_url,
                "secret": binding.secret,
            }
            for binding in model_bindings
        ],
        "executableIdentity": executable.name if executable is not None else None,
    }


def _model_references(
    documents: Sequence[Mapping[str, Any]],
) -> tuple[tuple[str, str, str], ...]:
    references: list[tuple[str, str, str]] = []
    for document in documents:
        nodes = document.get("nodes")
        if not isinstance(nodes, list):
            continue
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            node_id = node.get("id")
            data = node.get("data")
            if not isinstance(node_id, str) or not isinstance(data, Mapping):
                continue
            config = data.get("config")
            values = config if isinstance(config, Mapping) else data
            model_id = values.get("modelId")
            if isinstance(model_id, str) and model_id.strip():
                references.append((model_id.strip(), node_id, "config.modelId"))
            fallbacks = values.get("fallbackModels")
            if isinstance(fallbacks, list):
                for index, fallback in enumerate(fallbacks):
                    fallback_id = (
                        fallback.get("modelId")
                        if isinstance(fallback, Mapping)
                        else None
                    )
                    if isinstance(fallback_id, str) and fallback_id.strip():
                        references.append(
                            (
                                fallback_id.strip(),
                                node_id,
                                f"config.fallbackModels.{index}.modelId",
                            )
                        )
            fallback_ids = values.get("fallbackModelIds")
            if isinstance(fallback_ids, list):
                for index, fallback_id in enumerate(fallback_ids):
                    if isinstance(fallback_id, str) and fallback_id.strip():
                        references.append(
                            (
                                fallback_id.strip(),
                                node_id,
                                f"config.fallbackModelIds.{index}",
                            )
                        )
    return tuple(references)


def _workflow_dependency_snapshots(
    documents: WorkflowDocumentService,
    root_document: Mapping[str, Any],
    *,
    modules: CustomModuleService | None = None,
    custom_modules: dict[str, dict[str, object]] | None = None,
) -> dict[str, dict[str, Any]]:
    available: dict[str, dict[str, Any]] = {}
    cursor = 0
    while True:
        page = documents.list_summaries(cursor=cursor, limit=200)
        for summary in page.items:
            saved = documents.get(summary.id)
            payload = saved.to_payload()
            available[saved.id] = payload
            available.setdefault(saved.name, payload)
            available.setdefault(f"{saved.name}.json", payload)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    root = copy.deepcopy(dict(root_document))
    root_id = root.get("id")
    root_name = root.get("name")
    if isinstance(root_id, str):
        available[root_id] = root
    if isinstance(root_name, str):
        available[root_name] = root
        available[f"{root_name}.json"] = root

    snapshots: dict[str, dict[str, Any]] = {}
    frozen_modules = custom_modules if custom_modules is not None else {}
    queue = [("root", root)]
    visited: set[str] = set()
    while queue:
        identity, document = queue.pop(0)
        if identity in visited:
            continue
        visited.add(identity)
        references = _custom_module_references((document,))
        if references and modules is None:
            raise WorkflowRunError(
                "CUSTOM_MODULES_NOT_READY", "自定义模块服务尚未就绪", 503
            )
        if modules is not None:
            missing = tuple(ref for ref in references if ref not in frozen_modules)
            if missing:
                for module_id, snapshot in modules.freeze_closure(missing).items():
                    if module_id in frozen_modules:
                        continue
                    frozen_modules[module_id] = snapshot
                    workflow = snapshot.get("workflow")
                    if isinstance(workflow, Mapping):
                        queue.append((f"module:{module_id}", dict(workflow)))
        for reference in _workflow_references(document):
            candidates = [reference]
            if reference.lower().endswith(".json"):
                candidates.append(reference[:-5])
            else:
                candidates.append(f"{reference}.json")
            dependency = next(
                (
                    available[candidate]
                    for candidate in candidates
                    if candidate in available
                ),
                None,
            )
            if dependency is None:
                continue
            for key, value in available.items():
                if value is dependency:
                    snapshots[key] = copy.deepcopy(dependency)
            queue.append((f"workflow:{dependency.get('id')}", dependency))
    return snapshots


def _workflow_references(document: Mapping[str, Any]) -> tuple[str, ...]:
    variables = (
        {
            item["name"]: item.get("value")
            for item in document.get("variables", [])
            if isinstance(item, Mapping)
            and isinstance(item.get("name"), str)
            and item["name"]
        }
        if isinstance(document.get("variables"), list)
        else {}
    )
    references: list[str] = []
    nodes = document.get("nodes", [])
    if not isinstance(nodes, list):
        return ()
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        data = node.get("data")
        if (
            not isinstance(data, Mapping)
            or data.get("moduleType") != "run_workflow_file"
        ):
            continue
        config = data.get("config")
        values = config if isinstance(config, Mapping) else data
        raw = values.get("workflowFile", "") or values.get("workflow", "")
        resolved = resolve_value(raw, variables)
        if isinstance(resolved, str) and resolved.strip():
            references.append(resolved.strip().strip('"'))
    return tuple(references)


def _custom_module_references(
    documents: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    references: list[str] = []
    for document in documents:
        nodes = document.get("nodes", [])
        if not isinstance(nodes, list):
            continue
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            data = node.get("data")
            module_type = (
                data.get("moduleType")
                if isinstance(data, Mapping)
                else node.get("type")
            )
            if module_type != "custom_module":
                continue
            module_id = custom_module_reference(node)
            if module_id and module_id not in references:
                references.append(module_id)
    return tuple(references)


def _summary(run: WorkflowRun) -> dict[str, Any]:
    return {
        "runId": run.run_id,
        "workflowId": run.workflow_id,
        "documentId": run.document_id,
        "workflowName": run.workflow_name,
        "status": run.status,
        "startedAt": run.started_at.isoformat(),
        "finishedAt": run.finished_at.isoformat() if run.finished_at else None,
        "logCount": run.log_count,
    }


def _event_identity(run: WorkflowRun) -> dict[str, str]:
    return {"runId": run.run_id, "workflowId": run.workflow_id}


def _required_string(values: Mapping[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise WorkflowRunError("RUN_REQUEST_INVALID", f"{key} 不能为空", 422)
    return value


def _required_int(values: Mapping[str, Any], key: str) -> int:
    value = values.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise WorkflowRunError("WORKER_EVENT_INVALID", f"{key} 无效", 422)
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise WorkflowRunError("WORKER_EVENT_INVALID", "事件字符串字段无效", 422)
    return value
