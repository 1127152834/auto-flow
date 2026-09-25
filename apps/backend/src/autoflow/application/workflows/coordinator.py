from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Thread
from typing import Any, Protocol, cast
from uuid import uuid4

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
from autoflow.domain.workflows.scope import APPROVED_NODE_TYPES
from autoflow.domain.workflows.variables import resolve_value

from .documents import WorkflowDocumentService
from .modules import CustomModuleService
from .runs import WorkflowRunRepository, WorkflowRunService
from .runtime import WorkflowRuntime
from .webhooks import webhook_payload

_MAX_INLINE_DIAGNOSTIC_BYTES = 64 * 1024


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
        release_proxy: Callable[[str], None] | None = None,
        read_license: Callable[[], str | None],
        workers: WorkflowWorkers,
        resources: WorkflowResources,
        events: StudioEventJournal,
        artifact_root: Path,
        modules: CustomModuleService | None = None,
        resolve_model: Callable[[str], ModelExecutionBinding] | None = None,
        resolve_default_model: Callable[[str], str] | None = None,
        resolve_credential: Callable[[str], Mapping[str, str]] | None = None,
    ) -> None:
        self._documents = documents
        self._runs = runs
        self._repository = run_repository
        self._runtime = runtime
        self._profiles = profiles
        self._installed_kernels = installed_kernels
        self._resolve_proxy = resolve_proxy
        self._release_proxy = release_proxy
        self._read_license = read_license
        self._workers = workers
        self._resources = resources
        self._events = events
        self._artifact_root = artifact_root.resolve()
        self._modules = modules
        self._resolve_model = resolve_model
        self._resolve_default_model = resolve_default_model
        self._resolve_credential = resolve_credential
        self._credential_reads: dict[str, Event] = {}
        self._terminal_intents: dict[str, dict[str, Any]] = {}
        self._command_lock = asyncio.Lock()
        self._event_command_lock = asyncio.Lock()
        self._input_prompts: dict[str, dict[str, str]] = {}
        self._js_requests: dict[str, dict[str, str]] = {}
        self._speech_requests: dict[str, dict[str, str]] = {}
        self._desktop_action_requests: dict[str, dict[str, str]] = {}
        self._webhook_requests: dict[str, dict[str, Any]] = {}
        self._debug_pauses: dict[str, dict[str, Any]] = {}
        self._active_runs_by_workflow: dict[str, set[str]] = {}
        self._command_receipts: dict[str, tuple[str, dict[str, Any], int]] = {}
        self._event_command_runs: dict[str, str] = {}
        self._command_waiters: dict[str, asyncio.Future[str | None]] = {}

    async def start(
        self, workflow_id: str, request: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        run_id = _required_string(request, "runId")
        document_id = _required_string(request, "documentId")
        profile_id = _required_string(request, "profileId")
        step_mode = request.get("stepMode", False)
        if not isinstance(step_mode, bool):
            raise WorkflowRunError("RUN_REQUEST_INVALID", "stepMode 必须是布尔值", 422)
        raw_breakpoints = request.get("breakpoints", [])
        if not isinstance(raw_breakpoints, list) or not all(
            isinstance(item, str) and item for item in raw_breakpoints
        ):
            raise WorkflowRunError("RUN_REQUEST_INVALID", "breakpoints 必须是节点标识数组", 422)
        breakpoints = list(dict.fromkeys(raw_breakpoints))
        raw_start_node_id = request.get("startNodeId")
        if raw_start_node_id is not None and (
            not isinstance(raw_start_node_id, str) or not raw_start_node_id
        ):
            raise WorkflowRunError("RUN_REQUEST_INVALID", "startNodeId 必须是节点标识", 422)
        start_node_id = cast(str | None, raw_start_node_id)
        raw_run_to_node_id = request.get("runToNodeId")
        if raw_run_to_node_id is not None and (
            not isinstance(raw_run_to_node_id, str) or not raw_run_to_node_id
        ):
            raise WorkflowRunError("RUN_REQUEST_INVALID", "runToNodeId 必须是节点标识", 422)
        run_to_node_id = cast(str | None, raw_run_to_node_id)
        if start_node_id is not None and run_to_node_id is not None:
            raise WorkflowRunError(
                "RUN_REQUEST_INVALID", "不能同时指定调试起点和运行至此目标", 422
            )
        mode = (
            "debug"
            if bool(
                request.get("debug")
                or step_mode
                or breakpoints
                or start_node_id
                or run_to_node_id
            )
            else "run"
        )
        headless = request.get("headless", False)
        if not isinstance(headless, bool):
            raise WorkflowRunError("RUN_REQUEST_INVALID", "headless 必须是布尔值", 422)

        run_options = {
            "headless": headless,
            "startNodeId": start_node_id,
            "runToNodeId": run_to_node_id,
            "mode": mode,
            "stepMode": step_mode,
            "breakpoints": breakpoints,
        }
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
            # Retries compare caller-owned inputs against the original resource
            # snapshot before consulting resources that may since have changed.
            previous = self._repository.get(run_id)
            if previous is not None:
                replay = WorkflowRunStart(
                    run_id=run_id,
                    workflow_id=workflow_id,
                    document_id=document_id,
                    workflow_name=draft.name,
                    document_snapshot=copy.deepcopy(draft.document),
                    layout_snapshot=copy.deepcopy(draft.layout),
                    profile_id=profile_id,
                    profile_snapshot={
                        **previous.profile_snapshot,
                        "runOptions": run_options,
                    },
                    mode=cast(Any, mode),
                    custom_module_snapshots=previous.custom_module_snapshots,
                    project_id=request.get("projectId"),
                )
                return _summary(self._runs.start(replay))
            document = draft.to_payload()
            document_node_ids = {
                str(node["id"])
                for node in document.get("nodes", [])
                if isinstance(node, Mapping)
                and isinstance(node.get("id"), str)
                and node["id"]
            }
            if not set(breakpoints).issubset(document_node_ids):
                raise WorkflowRunError(
                    "BREAKPOINT_NODE_NOT_FOUND",
                    "断点必须属于运行快照中的节点",
                    422,
                )
            if run_to_node_id is not None and run_to_node_id not in document_node_ids:
                raise WorkflowRunError(
                    "RUN_TO_NODE_NOT_FOUND", "运行至此目标不存在于运行快照", 422
                )
            if start_node_id is not None:
                start_node = next(
                    (
                        node
                        for node in document.get("nodes", [])
                        if isinstance(node, Mapping) and node.get("id") == start_node_id
                    ),
                    None,
                )
                if start_node is None:
                    raise WorkflowRunError(
                        "START_NODE_NOT_FOUND", "调试起点不存在于运行快照", 422
                    )
                start_data = start_node.get("data")
                start_type = (
                    start_data.get("moduleType")
                    if isinstance(start_data, Mapping)
                    else start_node.get("type")
                )
                if start_node.get("parentId") or start_type in {
                    "condition_end",
                    "loop_end",
                    "break_loop",
                    "continue_loop",
                }:
                    raise WorkflowRunError(
                        "START_NODE_INVALID",
                        "只能从顶层普通节点、条件起点或循环起点开始调试",
                        422,
                    )
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
            raw_custom_module_dependencies = copy.deepcopy(custom_module_dependencies)
            resolved_default_model = self._apply_project_model_default(
                [document, *workflow_dependencies.values(), *(
                    workflow for snapshot in custom_module_dependencies.values()
                    if isinstance((workflow := snapshot.get("workflow")), dict)
                )],
                request.get("projectId") or draft.document.get("projectId"),
            )
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
                    "runOptions": run_options,
                    **({"resolvedDefaultModelId": resolved_default_model} if resolved_default_model else {}),
                },
                mode=cast(Any, mode),
                custom_module_snapshots=raw_custom_module_dependencies,
                project_id=request.get("projectId"),
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
                    executable_document=document,
                )
                await self._workers.start(
                    run_id,
                    profile_id,
                    kernel.executable_path if kernel is not None else None,
                    payload,
                )
                self._runs.mark_running(run_id)
                self._active_runs_by_workflow.setdefault(workflow_id, set()).add(run_id)
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
                    if self._release_proxy is not None:
                        self._release_proxy(run_id)
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

    def _apply_project_model_default(
        self, documents: Sequence[dict[str, Any]], project_id: str | None,
    ) -> str | None:
        resolved: str | None = None
        for document in documents:
            for node in document.get("nodes", []):
                if not isinstance(node, Mapping):
                    continue
                data = node.get("data")
                if not isinstance(data, dict):
                    continue
                node_type = data.get("moduleType", node.get("type"))
                if not isinstance(node_type, str) or node_type not in APPROVED_NODE_TYPES or not node_type.startswith("ai_"):
                    continue
                config = data.get("config")
                values = config if isinstance(config, dict) else data
                model_id = values.get("modelId")
                details = {"nodeId": node.get("id"), "path": "config.modelId"}
                if model_id is not None and not isinstance(model_id, str):
                    raise WorkflowRunError("MODEL_ID_INVALID", "模型标识必须是字符串", 422, details)
                if isinstance(model_id, str) and model_id.strip():
                    continue
                if project_id is None:
                    continue
                if self._resolve_default_model is None:
                    raise WorkflowRunError("MODEL_SERVICE_UNAVAILABLE", "项目默认模型服务不可用", 503, details)
                if resolved is None:
                    try:
                        resolved = self._resolve_default_model(project_id)
                    except (ModelError, WorkflowRunError) as error:
                        raise WorkflowRunError(error.code, error.message, error.status, {**error.details, **details}) from error
                values["modelId"] = resolved
        return resolved

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
            if run.status != "failed_paused":
                self._runs.request_stop(run_id)
            await self._workers.stop(run_id)
            return _summary(self._runs.get(run_id))

    async def debug_control(
        self,
        workflow_id: str,
        action: str,
        request: Mapping[str, Any],
    ) -> tuple[dict[str, Any], int]:
        command_id = _required_string(request, "commandId")
        fingerprint = self._debug_fingerprint(
            {"workflowId": workflow_id, "action": action, **dict(request)}
        )
        async with self._event_command_lock:
            previous = self._debug_command(command_id)
            if previous is not None:
                old_fingerprint, receipt, status = previous
                if old_fingerprint != fingerprint:
                    return {
                        "commandId": command_id,
                        "runId": str(request.get("runId") or ""),
                        "pauseId": str(request.get("pauseId") or ""),
                        "controlRevision": int(request.get("controlRevision") or 0),
                        "workflowId": workflow_id,
                        "action": action,
                        "success": False,
                        "error": "commandId 已用于不同请求",
                    }, 409
                return copy.deepcopy(receipt), status

            run_id = _required_string(request, "runId")
            pause_id = _required_string(request, "pauseId")
            revision = request.get("controlRevision")
            run = self._runs.get(run_id)
            pause = self._debug_pauses.get(run_id)
            error = None
            if run.workflow_id != workflow_id:
                error = "运行不属于指定工作流"
            elif action not in {"resume", "step"}:
                error = "调试命令无效"
            elif (
                run.status != "paused"
                or pause is None
                or pause.get("pauseId") != pause_id
                or pause.get("controlRevision") != revision
            ):
                error = "暂停标识或控制修订已失效"
            receipt = {
                "commandId": command_id,
                "runId": run_id,
                "pauseId": pause_id,
                "controlRevision": revision,
                "workflowId": workflow_id,
                "action": action,
                "success": error is None,
                "error": error,
            }
            if error is not None:
                self._remember_debug_command(
                    run_id, command_id, fingerprint, receipt, 409
                )
                return copy.deepcopy(receipt), 409

            waiter = asyncio.get_running_loop().create_future()
            self._command_waiters[command_id] = waiter
            try:
                await self._workers.send_command(
                    run_id,
                    {
                        "type": f"debug_{action}",
                        "commandId": command_id,
                        "pauseId": pause_id,
                        "controlRevision": revision,
                    },
                )
                worker_error = await asyncio.wait_for(waiter, timeout=10)
                if worker_error is not None:
                    receipt["success"] = False
                    receipt["error"] = worker_error
                    self._remember_debug_command(
                        run_id, command_id, fingerprint, receipt, 409
                    )
                    return copy.deepcopy(receipt), 409
            except (RuntimeError, TimeoutError):
                receipt["success"] = False
                receipt["error"] = "调试命令未被运行进程确认"
                self._remember_debug_command(
                    run_id, command_id, fingerprint, receipt, 503
                )
                return copy.deepcopy(receipt), 503
            finally:
                self._command_waiters.pop(command_id, None)
            self._remember_debug_command(
                run_id, command_id, fingerprint, receipt, 200
            )
            return copy.deepcopy(receipt), 200

    async def debug_breakpoints(
        self, workflow_id: str, breakpoints: list[str], *, project_id: str | None = None,
    ) -> Mapping[str, Any]:
        active = {
            run_id
            for run_id in self._active_runs_by_workflow.get(workflow_id, set())
            if self._runs.get(run_id).status in {"starting", "running", "paused"}
        }
        if len(active) != 1:
            raise WorkflowRunError(
                "DEBUG_RUN_NOT_FOUND", "指定工作流没有唯一的活跃运行", 409
            )
        run_id = next(iter(active))
        run = self._runs.get(run_id)
        if project_id is not None and run.project_id != project_id:
            raise WorkflowRunError("RUN_NOT_FOUND", "运行记录不存在", 404)
        node_ids = {
            str(node["id"])
            for node in run.document_snapshot.get("nodes", [])
            if isinstance(node, Mapping)
            and isinstance(node.get("id"), str)
            and node["id"]
        }
        if not set(breakpoints).issubset(node_ids):
            raise WorkflowRunError(
                "BREAKPOINT_NODE_NOT_FOUND",
                "断点必须属于运行快照中的节点",
                422,
            )
        command_id = str(uuid4())
        waiter = asyncio.get_running_loop().create_future()
        self._command_waiters[command_id] = waiter
        try:
            await self._workers.send_command(
                run_id,
                {
                    "type": "debug_breakpoints",
                    "commandId": command_id,
                    "breakpoints": list(dict.fromkeys(breakpoints)),
                },
            )
            worker_error = await asyncio.wait_for(waiter, timeout=10)
            if worker_error is not None:
                raise WorkflowRunError("BREAKPOINT_UPDATE_REJECTED", worker_error, 409)
        except (RuntimeError, TimeoutError) as error:
            raise WorkflowRunError(
                "BREAKPOINT_UPDATE_UNCONFIRMED",
                "断点更新未被运行进程确认",
                503,
            ) from error
        finally:
            self._command_waiters.pop(command_id, None)
        return {"success": True, "runId": run_id, "breakpoints": breakpoints}

    async def debug_variables(
        self,
        workflow_id: str,
        request: Mapping[str, Any],
    ) -> tuple[dict[str, Any], int]:
        command_id = _required_string(request, "commandId")
        fingerprint = self._debug_fingerprint(
            {"workflowId": workflow_id, "action": "variables", **dict(request)}
        )
        async with self._event_command_lock:
            previous = self._debug_command(command_id)
            if previous is not None:
                old_fingerprint, receipt, status = previous
                if old_fingerprint != fingerprint:
                    return {
                        **dict(request),
                        "workflowId": workflow_id,
                        "success": False,
                        "error": "commandId 已用于不同请求",
                    }, 409
                return copy.deepcopy(receipt), status
            run_id = _required_string(request, "runId")
            pause_id = _required_string(request, "pauseId")
            revision = request.get("controlRevision")
            run = self._runs.get(run_id)
            pause = self._debug_pauses.get(run_id)
            error = None
            if run.workflow_id != workflow_id:
                error = "运行不属于指定工作流"
            elif (
                run.status != "paused"
                or pause is None
                or pause.get("pauseId") != pause_id
                or pause.get("controlRevision") != revision
            ):
                error = "暂停标识或控制修订已失效"
            receipt = {
                **_debug_receipt_request(request),
                "workflowId": workflow_id,
                "success": error is None,
                "error": error,
            }
            if error is not None:
                self._remember_debug_command(
                    run_id, command_id, fingerprint, receipt, 409
                )
                return copy.deepcopy(receipt), 409
            waiter = asyncio.get_running_loop().create_future()
            self._command_waiters[command_id] = waiter
            try:
                await self._workers.send_command(
                    run_id,
                    {
                        "type": "debug_variables",
                        "commandId": command_id,
                        "pauseId": pause_id,
                        "controlRevision": revision,
                        "changes": copy.deepcopy(request.get("changes")),
                    },
                )
                worker_error = await asyncio.wait_for(waiter, timeout=10)
                if worker_error is not None:
                    receipt["success"] = False
                    receipt["error"] = worker_error
                    self._remember_debug_command(
                        run_id, command_id, fingerprint, receipt, 409
                    )
                    return copy.deepcopy(receipt), 409
            except (RuntimeError, TimeoutError):
                receipt["success"] = False
                receipt["error"] = "变量修改未被运行进程确认"
                self._remember_debug_command(
                    run_id, command_id, fingerprint, receipt, 503
                )
                return copy.deepcopy(receipt), 503
            finally:
                self._command_waiters.pop(command_id, None)
            self._remember_debug_command(
                run_id, command_id, fingerprint, receipt, 200
            )
            return copy.deepcopy(receipt), 200

    async def _read_worker_credential(self, run_id: str, name: str, field: str) -> str | None:
        resolver = self._resolve_credential
        previous = self._credential_reads.get(run_id)
        run = self._runs.get(run_id)
        if resolver is None or (previous is not None and not previous.is_set()):
            return None
        if run.stop_requested or run.status not in {"starting", "running", "paused"}:
            return None
        done, discard = Event(), Event()
        result: list[str | None] = []
        self._credential_reads[run_id] = done

        def read() -> None:
            try:
                value = resolver(name).get(field)
                if not discard.is_set():
                    result.append(value)
            except Exception:  # noqa: BLE001 -- source preserves unavailable placeholders.
                result.clear()
            finally:
                done.set()

        # Native keychain UI can block indefinitely. One outstanding read per run;
        # daemon ownership avoids blocking stop/sidecar exit on that system prompt.
        Thread(target=read, daemon=True, name="workflow-credential-read").start()
        try:
            async with asyncio.timeout(3):
                while not done.is_set():
                    current = self._runs.get(run_id)
                    if current.stop_requested or current.status not in {"starting", "running", "paused"}:
                        return None
                    await asyncio.sleep(0.02)
            return result[0] if result else None
        except TimeoutError:
            return None
        finally:
            discard.set()
            if done.is_set():
                self._credential_reads.pop(run_id, None)

    async def on_worker_event(self, event: dict[str, object]) -> None:
        run_id = _required_string(event, "runId")
        run = self._runs.get(run_id)
        event_type = _required_string(event, "type")
        if event_type == "credential:read":
            # Secrets only cross this owned worker pipe, never the journal/HTTP/SSE.
            request_id = _required_string(event, "requestId")
            name, field = event.get("name"), event.get("field")
            if not isinstance(name, str) or not isinstance(field, str):
                raise TypeError("凭据请求名称和字段必须是字符串")
            # Empty parts are legal unmatched source references, not pipe failure.
            value = await self._read_worker_credential(run_id, name, field) if name and field else None
            current = self._runs.get(run_id)
            if current.stop_requested or current.status not in {"starting", "running", "paused"}:
                return
            await self._workers.send_command(run_id, {
                "type": "credential:result", "requestId": request_id, "value": value,
            })
            return
        if event_type == "execution:failed_paused":
            pause_id = _required_string(event, "pauseId")
            paused_node_id = _required_string(event, "node_id")
            revision = _required_int(event, "controlRevision")
            payload = {
                key: copy.deepcopy(value)
                for key, value in event.items()
                if key not in {"type", "runId", "workflowId"}
            }
            error = {
                "code": "WORKFLOW_EXECUTION_FAILED",
                "message": str(event.get("error") or "工作流执行失败"),
                "nodeId": paused_node_id,
            }
            self._debug_pauses[run_id] = {
                "pauseId": pause_id,
                "controlRevision": revision,
                "nodeId": paused_node_id,
            }
            self._terminal_intents[run_id] = copy.deepcopy(event)
            persisted = self._repository.append_event(
                run_id,
                event_type,
                payload,
                now=datetime_now(),
                node_id=paused_node_id,
                run_patch={
                    "status": "failed_paused",
                    "currentNodeId": paused_node_id,
                    "error": error,
                },
            )
            await self._events.publish(
                event_type,
                {**_event_identity(run), **payload, "sequence": persisted.sequence},
            )
            return
        if event_type == "execution:paused":
            pause_id = _required_string(event, "pauseId")
            paused_node_id = _required_string(event, "node_id")
            revision = _required_int(event, "controlRevision")
            payload = {
                key: copy.deepcopy(value)
                for key, value in event.items()
                if key not in {"type", "runId", "workflowId"}
            }
            self._debug_pauses[run_id] = {
                "pauseId": pause_id,
                "controlRevision": revision,
                "nodeId": paused_node_id,
            }
            persisted = self._repository.append_event(
                run_id,
                event_type,
                payload,
                now=datetime_now(),
                node_id=paused_node_id,
                run_patch={"status": "paused", "currentNodeId": paused_node_id},
            )
            await self._events.publish(
                event_type,
                {**_event_identity(run), **payload, "sequence": persisted.sequence},
            )
            return
        if event_type == "execution:resumed":
            pause_id = _required_string(event, "pauseId")
            pause = self._debug_pauses.get(run_id)
            if pause is not None and pause.get("pauseId") == pause_id:
                self._debug_pauses.pop(run_id, None)
            payload = {
                key: copy.deepcopy(value)
                for key, value in event.items()
                if key not in {"type", "runId", "workflowId"}
            }
            persisted = self._repository.append_event(
                run_id,
                event_type,
                payload,
                now=datetime_now(),
                run_patch={"status": "running"},
            )
            await self._events.publish(
                event_type,
                {**_event_identity(run), **payload, "sequence": persisted.sequence},
            )
            return
        if event_type == "execution:webhook_waiting":
            request_id = _required_string(event, "requestId")
            webhook_id = _required_string(event, "webhookId")
            webhook_node_id = _required_string(event, "nodeId")
            raw_headers = event.get("validateHeaders")
            raw_params = event.get("validateParams")
            validate_headers = dict(raw_headers) if isinstance(raw_headers, Mapping) else {}
            validate_params = dict(raw_params) if isinstance(raw_params, Mapping) else {}
            raw_status = event.get("responseStatus")
            response_status = raw_status if isinstance(raw_status, int) else 200
            self._webhook_requests[webhook_id] = {
                "requestId": request_id,
                "workflowId": run.workflow_id,
                "runId": run_id,
                "nodeId": webhook_node_id,
                "status": "pending",
                "method": _required_string(event, "method"),
                "validateHeaders": copy.deepcopy(validate_headers),
                "validateParams": copy.deepcopy(validate_params),
                "responseBody": copy.deepcopy(event.get("responseBody") or {}),
                "responseStatus": response_status,
            }
            payload = {
                "requestId": request_id,
                "webhookId": webhook_id,
                "method": event["method"],
                "validationHeaderNames": list(validate_headers),
                "validationParamNames": list(validate_params),
            }
            persisted = self._repository.append_event(
                run_id,
                event_type,
                payload,
                now=datetime_now(),
                node_id=webhook_node_id,
                execution_id=_optional_string(event.get("executionId")),
                run_patch={"currentNodeId": webhook_node_id},
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
        if event_type == "execution:webhook_closed":
            webhook_id = _required_string(event, "webhookId")
            request_id = _required_string(event, "requestId")
            state = self._webhook_requests.get(webhook_id)
            if state is not None and state["requestId"] == request_id:
                self._webhook_requests.pop(webhook_id, None)
            return
        if event_type == "execution:command_applied":
            command_id = _required_string(event, "commandId")
            waiter = self._command_waiters.get(command_id)
            if waiter is not None and not waiter.done():
                waiter.set_result(None)
            return
        if event_type == "execution:command_rejected":
            command_id = _required_string(event, "commandId")
            waiter = self._command_waiters.get(command_id)
            if waiter is not None and not waiter.done():
                waiter.set_result(_required_string(event, "error"))
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
        if event_type == "execution:desktop_action":
            request_id = _required_string(event, "requestId")
            action_node_id = _required_string(event, "nodeId")
            payload = {
                key: copy.deepcopy(value)
                for key, value in event.items()
                if key not in {"type", "runId"}
            }
            self._desktop_action_requests[request_id] = {
                "requestId": request_id,
                "workflowId": run.workflow_id,
                "runId": run_id,
                "nodeId": action_node_id,
                "status": "pending",
            }
            persisted = self._repository.append_event(
                run_id,
                event_type,
                payload,
                now=datetime_now(),
                node_id=action_node_id,
                execution_id=_optional_string(event.get("executionId")),
                run_patch={"currentNodeId": action_node_id},
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
        if event_type == "execution:desktop_action_closed":
            request_id = _required_string(event, "requestId")
            state = self._desktop_action_requests.get(request_id)
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
            level = (event.get("logLevel") or "success") if success else "error"
            if not isinstance(level, str) or level not in {"debug", "info", "success", "warning", "error"}:
                level = "success" if success else "error"
            message = str(event.get("message") or event.get("error") or "节点执行完成")
            log_payload: dict[str, Any] = {
                "level": level, "message": message,
                "isUserLog": event.get("isUserLog") is True,
                "isSystemLog": event.get("isSystemLog") is True,
                "duration": event.get("duration"),
            }
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
                        **log_payload,
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
        if event_type == "execution:log":
            # Standalone worker warnings use the same UI log envelope as node logs.
            await self._events.publish(event_type, {
                **_event_identity(run),
                "log": {
                    **payload, "sequence": persisted.sequence,
                    "id": f"{run_id}-{persisted.sequence}",
                    "timestamp": persisted.occurred_at.isoformat(),
                    "nodeId": node_id, "executionId": execution_id,
                },
            })
            return
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
            request_id = data.get("requestId")
            if isinstance(request_id, str):
                owner = self.request_run(request_id)
                if owner is not None:
                    self._event_command_runs[command_id] = owner
            if event == "js_script_claim":
                return self._claim_js_script(command_id, fingerprint, data)
            if event == "js_script_result":
                return await self._complete_js_script(command_id, fingerprint, data)
            if event == "tts_claim":
                return self._claim_tts(command_id, fingerprint, data)
            if event == "tts_result":
                return await self._complete_tts(command_id, fingerprint, data)
            if event == "desktop_action_claim":
                return self._claim_desktop_action(command_id, fingerprint, data)
            if event == "desktop_action_result":
                return await self._complete_desktop_action(command_id, fingerprint, data)
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

    def has_webhook(self, webhook_id: str) -> bool:
        return webhook_id in self._webhook_requests

    async def trigger_webhook(
        self,
        webhook_id: str,
        *,
        method: str,
        headers: Mapping[str, str],
        query: Mapping[str, str],
        body: Any,
    ) -> tuple[Any, int]:
        async with self._event_command_lock:
            state = self._webhook_requests.get(webhook_id)
            if state is None or state["status"] != "pending":
                raise WorkflowRunError(
                    "WEBHOOK_NOT_FOUND",
                    "Webhook不存在、HTTP方法不匹配或已经触发",
                    404,
                )
            data = webhook_payload(state, method=method, headers=headers, query=query, body=body)

            request_id = str(state["requestId"])
            command_id = str(uuid4())
            waiter = asyncio.get_running_loop().create_future()
            self._command_waiters[command_id] = waiter
            state["status"] = "delivering"
            try:
                await self._workers.send_command(
                    str(state["runId"]),
                    {
                        "type": "webhook_result",
                        "commandId": command_id,
                        "requestId": request_id,
                        "data": data,
                    },
                )
                await asyncio.wait_for(waiter, timeout=10)
            except (RuntimeError, TimeoutError) as error:
                raise WorkflowRunError(
                    "WEBHOOK_DELIVERY_UNCONFIRMED",
                    "Webhook已接收，但运行进程未确认",
                    503,
                ) from error
            finally:
                self._command_waiters.pop(command_id, None)
            return copy.deepcopy(state["responseBody"] or {"success": True}), int(
                state["responseStatus"]
            )

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

    def _claim_desktop_action(
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
                command_id, fingerprint, "平台操作请求及领取标识无效", 422
            )
        state = self._desktop_action_requests.get(request_id)
        if state is None or state["status"] not in {"pending", "claimed"}:
            return self._remember_command(
                command_id, fingerprint, "平台操作请求不存在或已结束", 409
            )
        if state["status"] == "claimed" and state.get("claimId") != claim_id:
            return self._remember_command(
                command_id, fingerprint, "平台操作已由其它客户端领取", 409
            )
        state["status"] = "claimed"
        state["claimId"] = claim_id
        receipt = {"commandId": command_id, "success": True, "requestId": request_id}
        self._command_receipts[command_id] = (fingerprint, receipt, 200)
        return copy.deepcopy(receipt), 200

    async def _complete_desktop_action(
        self, command_id: str, fingerprint: str, data: Mapping[str, Any]
    ) -> tuple[dict[str, Any], int]:
        request_id = data.get("requestId")
        claim_id = data.get("claimId")
        success = data.get("success")
        error = data.get("error")
        allowed = {"requestId", "claimId", "success", "value", "error"}
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
                command_id, fingerprint, "平台操作结果格式无效", 422
            )
        state = self._desktop_action_requests.get(request_id)
        if (
            state is None
            or state["status"] != "claimed"
            or state.get("claimId") != claim_id
        ):
            return self._remember_command(
                command_id, fingerprint, "平台操作结果不属于当前领取者", 409
            )
        waiter = asyncio.get_running_loop().create_future()
        self._command_waiters[command_id] = waiter
        try:
            await self._workers.send_command(
                state["runId"],
                {"type": "desktop_action_result", "commandId": command_id, **dict(data)},
            )
            await asyncio.wait_for(waiter, timeout=10)
        except (RuntimeError, TimeoutError):
            return self._remember_command(
                command_id, fingerprint, "平台操作结果未被运行进程确认", 503
            )
        finally:
            self._command_waiters.pop(command_id, None)
        state["status"] = "completed" if success else "failed"
        receipt = {"commandId": command_id, "success": True, "requestId": request_id}
        self._command_receipts[command_id] = (fingerprint, receipt, 200)
        return copy.deepcopy(receipt), 200

    def event_command(self, command_id: str) -> tuple[dict[str, Any], int]:
        record = self._debug_command(command_id)
        if record is None:
            raise WorkflowRunError("COMMAND_NOT_FOUND", "命令记录不存在", 404)
        _, receipt, status = record
        return {**copy.deepcopy(receipt), "httpStatus": status}, 200

    def _debug_command(
        self, command_id: str
    ) -> tuple[str, dict[str, Any], int] | None:
        record = self._command_receipts.get(command_id)
        if record is None:
            record = self._repository.get_debug_command(command_id)
            if record is not None:
                self._command_receipts[command_id] = record
        return record

    def _remember_debug_command(
        self,
        run_id: str,
        command_id: str,
        fingerprint: str,
        receipt: dict[str, Any],
        status: int,
    ) -> None:
        record = self._repository.save_debug_command(
            run_id,
            command_id,
            request_hash=fingerprint,
            receipt=receipt,
            http_status=status,
        )
        self._command_receipts[command_id] = record

    @staticmethod
    def _debug_fingerprint(payload: Mapping[str, Any]) -> str:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    def request_run(self, request_id: str) -> str | None:
        for requests in (self._input_prompts, self._js_requests, self._speech_requests, self._desktop_action_requests):
            state = requests.get(request_id)
            if state is not None:
                return state["runId"]
        return None

    def command_run(self, command_id: str) -> str | None:
        owner = self._event_command_runs.get(command_id)
        if owner is not None:
            return owner
        record = self._debug_command(command_id)
        if record is not None:
            run_id = record[1].get("runId")
            return run_id if isinstance(run_id, str) else None
        return None

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

    def desktop_action_state(self, request_id: str) -> dict[str, str]:
        state = self._desktop_action_requests.get(request_id)
        if state is None:
            raise WorkflowRunError(
                "DESKTOP_ACTION_NOT_FOUND", "平台操作请求不存在", 404
            )
        keys = ("requestId", "workflowId", "nodeId", "status", "claimId")
        return {key: state[key] for key in keys if key in state}

    async def on_worker_exit(self, run_id: str, return_code: int) -> None:
        # WorkflowWorkerManager invokes this only after the process tree and its
        # private directory are gone. Resource release is the final cleanup step.
        run = self._runs.get(run_id)
        self._credential_reads.pop(run_id, None)
        self._debug_pauses.pop(run_id, None)
        active = self._active_runs_by_workflow.get(run.workflow_id)
        if active is not None:
            active.discard(run_id)
            if not active:
                self._active_runs_by_workflow.pop(run.workflow_id, None)
        for state in self._input_prompts.values():
            if state["runId"] == run_id and state["status"] == "pending":
                state["status"] = "expired"
        for state in self._js_requests.values():
            if state["runId"] == run_id and state["status"] in {"pending", "claimed"}:
                state["status"] = "expired"
        for state in self._speech_requests.values():
            if state["runId"] == run_id and state["status"] in {"pending", "claimed"}:
                state["status"] = "expired"
        for state in self._desktop_action_requests.values():
            if state["runId"] == run_id and state["status"] in {"pending", "claimed"}:
                state["status"] = "expired"
        for webhook_id, state in tuple(self._webhook_requests.items()):
            if state["runId"] == run_id:
                self._webhook_requests.pop(webhook_id, None)
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
            failed_node_id = (intent or {}).get("failedNodeId") or (intent or {}).get("node_id")
            if isinstance(failed_node_id, str) and failed_node_id:
                error["nodeId"] = failed_node_id
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
    executable_document: dict[str, Any],
) -> dict[str, Any]:
    spec = profile.spec
    run_options = start.profile_snapshot.get("runOptions", {})
    if not isinstance(run_options, Mapping):
        run_options = {}
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
        "proxyId": proxy.proxy_id if proxy else None,
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
        "debug": start.mode == "debug",
        "stepMode": bool(run_options.get("stepMode") or run_options.get("startNodeId")),
        "breakpoints": copy.deepcopy(run_options.get("breakpoints", [])),
        "startNodeId": run_options.get("startNodeId"),
        "runToNodeId": run_options.get("runToNodeId"),
        "document": {**executable_document, "id": start.document_id},
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
    project_id: str | None = None,
    require_resolved: bool = False,
) -> dict[str, dict[str, Any]]:
    available: dict[str, dict[str, Any]] = {}
    cursor = 0
    while True:
        page = documents.list_summaries(cursor=cursor, limit=200, project_id=project_id)
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
    queue = [("root", root), *(
        (f"module:{module_id}", dict(workflow))
        for module_id, snapshot in frozen_modules.items()
        if isinstance((workflow := snapshot.get("workflow")), Mapping)
    )]
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
                if require_resolved:
                    raise WorkflowRunError(
                        "WORKFLOW_DEPENDENCY_MISSING",
                        f"找不到工作流依赖：{reference}",
                        422,
                        {"reference": reference},
                    )
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
        "projectId": run.project_id,
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


def _debug_receipt_request(request: Mapping[str, Any]) -> dict[str, Any]:
    receipt = copy.deepcopy(dict(request))
    changes = receipt.get("changes")
    if not isinstance(changes, list):
        return receipt
    for change in changes:
        if not isinstance(change, dict) or "value" not in change:
            continue
        encoded = json.dumps(
            change["value"],
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode()
        if len(encoded) <= _MAX_INLINE_DIAGNOSTIC_BYTES:
            continue
        preview = encoded[:90].decode(errors="replace")
        if len(encoded) > 180:
            preview += "…" + encoded[-90:].decode(errors="replace")
        change["value"] = {
            "externalized": True,
            "size": len(encoded),
            "preview": preview,
        }
    return receipt


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
