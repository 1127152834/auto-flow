from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from builtins import list as ListType
from collections.abc import Awaitable, Callable, Iterator, Sequence
from contextlib import AbstractContextManager, ExitStack, contextmanager
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from autoflow.application.android.devices import AndroidDeviceService
from autoflow.application.profiles.service import ProfileService
from autoflow.application.workflows.browser_resources import acquire_browser
from autoflow.application.workflows.browser_resources import (
    resource_error as _resource_error,
)
from autoflow.domain.android.ports import AndroidError, AndroidWorkflowLauncher
from autoflow.domain.kernels.errors import LicenseInvalid
from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.profiles.models import Profile, ProfileBrowserProxy
from autoflow.domain.workflows.debug import prepare_debug
from autoflow.domain.workflows.models import WorkflowError, WorkflowIssue
from autoflow.domain.workflows.run_validation import (
    PreparedWorkflow,
    prepare_run,
    validate_runtime,
)
from autoflow.domain.workflows.runs import (
    ACTIVE_RUN_STATES,
    RunRecord,
    WorkflowRunLauncher,
    WorkflowRunRepository,
)

logger = logging.getLogger(__name__)


@dataclass
class _ActiveRun:
    task: asyncio.Task[None] | None = None
    executing: bool = False
    stopping: bool = False
    stop_task: asyncio.Task[None] | None = None
    cleanup_task: asyncio.Task[None] | None = None
    cleanup_failed: bool = False
    debug_failure: dict[str, Any] | None = None
    guards: ExitStack | None = None
    result: dict[str, Any] | None = None
    android: bool = False
    device_task: asyncio.Task[dict[str, Any]] | None = None


@dataclass(frozen=True)
class _PendingCompletion:
    event: dict[str, Any]
    changes: dict[str, Any]


class WorkflowRunService:
    def __init__(
        self, repository: WorkflowRunRepository, profiles: ProfileService,
        installed_kernels: Callable[[], Sequence[InstalledKernel]],
        kernel_guard: Callable[[Profile], AbstractContextManager[None]],
        resolve_proxy: Callable[[Profile, str], Awaitable[ProfileBrowserProxy | None]],
        read_license: Callable[[], str | None], launcher: WorkflowRunLauncher,
        artifact_path: Callable[[str, str], Path],
        android: AndroidDeviceService | None = None,
        android_worker: AndroidWorkflowLauncher | None = None,
        save_android_image: Callable[[str, str, bytes], dict[str, Any]] | None = None,
        read_json: Callable[[Path], Any] | None = None,
        archive: Callable[[list[tuple[Path, dict[str, Any]]]], Iterator[bytes]] | None = None,
    ) -> None:
        self.android, self.android_worker = android, android_worker
        self.save_android_image = save_android_image
        self.repository = repository
        self._profiles = profiles
        self._installed_kernels = installed_kernels
        self._kernel_guard = kernel_guard
        self._resolve_proxy = resolve_proxy
        self._read_license = read_license
        self._launcher = launcher
        self._artifact_path = artifact_path
        self._read_json = read_json
        self._archive = archive
        self._command_locks: dict[str, asyncio.Lock] = {}
        self._active: dict[str, _ActiveRun] = {}
        self._pending_completions: dict[str, _PendingCompletion] = {}
        self._completion_lock = RLock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: dict[str, set[asyncio.Event]] = {}
        self.inspection_busy: Callable[[], bool] = lambda: False
        self._closing = False
        self._shutdown_task: asyncio.Task[None] | None = None

    def get(self, run_id: str) -> dict[str, Any]:
        self._retry_completions(run_id)
        with self._completion_lock:
            if run_id in self._pending_completions:
                raise WorkflowError(
                    "WORKFLOW_RUN_PERSISTENCE_PENDING",
                    "连接已关闭，但运行结果暂未保存；请重试查询或停止操作", 503,
                )
        record = self.repository.get(run_id)
        if record is None:
            raise WorkflowError("WORKFLOW_RUN_NOT_FOUND", "运行记录不存在", 404)
        page = self.artifacts(run_id, 0, 50)
        record.data.update(artifacts=page["items"], nextArtifactCursor=page["nextCursor"])
        operation = self._active.get(run_id)
        if operation is not None and operation.cleanup_failed:
            return {**record.data, "state": "stopping" if operation.stopping else "finishing", "error": _cleanup_error_data()}
        return record.data

    def list(self, workflow_id: str | None, offset: int, limit: int) -> dict[str, Any]:
        self._retry_completions()
        items = self.repository.list_runs(workflow_id, offset, limit + 1)
        return {
            "items": [item.data for item in items[:limit]],
            "activeRunId": self.repository.active_id(),
            "nextOffset": offset + limit if len(items) > limit else None,
        }

    async def start(
        self, run_id: str, document: dict[str, Any], layout: dict[str, Any], profile_id: str | None,
        target: dict[str, Any] | None = None,
        mode: str = "run", debug: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # No await between admission, resource guards, persistence and task ownership.
        self._loop = asyncio.get_running_loop()
        self._retry_completions()
        target = target or {"kind": "browser", "profileId": profile_id}
        is_android = target["kind"] == "android"
        if not is_android:
            profile_id = target["profileId"]
        request_hash = hashlib.sha256(json.dumps(
            [document, {key: value for key, value in layout.items() if key != "breakpoints" or value}, target if is_android else profile_id] + ([mode, debug] if mode == "debug" else []), sort_keys=True, ensure_ascii=False, allow_nan=False,
        ).encode()).hexdigest()
        existing = self.repository.get(run_id)
        if existing is not None:
            if existing.request_hash != request_hash:
                raise WorkflowError("WORKFLOW_RUN_ID_CONFLICT", "运行标识已用于不同请求", 409)
            return self.get(run_id)
        if self._closing:
            raise WorkflowError("WORKFLOW_RUN_SHUTTING_DOWN", "运行服务正在退出", 409)
        if self.inspection_busy():
            raise WorkflowError("INSPECTION_ACTIVE", "请先关闭拾取浏览器后运行", 409)
        if self.busy():
            raise WorkflowError("WORKFLOW_RUN_BUSY", "当前工作区已有运行，请先停止或等待完成", 409)
        prepared = prepare_debug(document, layout, debug or {"start": "entry"}) if mode == "debug" else prepare_run(document, layout)
        validate_runtime(prepared.document, is_android)
        guards = ExitStack()
        try:
            profile = None
            executable = None
            if is_android:
                if self.android is None or self.android_worker is None:
                    raise WorkflowError("ANDROID_UNAVAILABLE", "安卓运行环境未配置", 503)
                device = self.android.claim(target["deviceId"], run_id)
                guards.callback(self.android.rollback_claim)
                snapshot = {key: device.get(key) for key in ("deviceId", "name", "imageId", "width", "height")}
                target_name = device["name"]
            else:
                assert profile_id is not None
                profile, executable = acquire_browser(guards, self._profiles, self._kernel_guard, self._installed_kernels, profile_id)
                snapshot = {_camel(key): value for key, value in asdict(profile.spec).items()}
                snapshot.update(id=profile.id, fingerprintSeed=profile.fingerprint_seed)
                target_name = profile.spec.name
            now = datetime.now(UTC).isoformat()
            if mode == "debug" and not is_android:
                snapshot["headless"] = False
            record = RunRecord(request_hash, {
                "runId": run_id, "workflowId": document["id"], "name": document["name"],
                "profileId": profile_id if not is_android else None, "profileName": target_name if not is_android else None,
                "target": target, "targetName": target_name, "targetSnapshot": snapshot, "handoff": None,
                "mode": mode, "debug": {"state": "starting", "controlRevision": 0, "pauseId": None, "breakpoints": (debug or {}).get("breakpoints", []), "checkpointId": None} if mode == "debug" else None, "debugOptions": debug,
                "state": "starting", "document": deepcopy(document), "layout": deepcopy(layout),
                "profileSnapshot": snapshot if not is_android else None, "nodeOrder": list(prepared.node_ids),
                "currentNodeId": None, "startedAt": now, "finishedAt": None,
                "latestSeq": 1, "completedNodeIds": [], "artifactCount": 0, "executionCount": 0, "currentExecutionId": None, "currentLoopPath": [], "error": None, "artifacts": [],
                "warnings": [_issue(issue) for issue in prepared.warnings],
            })
            saved = self.repository.create(record)
            if saved is not record:
                guards.close()
                return saved.data
            operation = _ActiveRun(guards=guards, android=is_android)
            self._active[run_id] = operation
            operation.task = asyncio.create_task(
                self._execute(run_id, operation, prepared, profile, executable),
                name=f"workflow-run-{run_id}",
            )
            # Acceptance already committed this snapshot. Reading again after task
            # handoff could fail and release guards while the task owns execution.
            return deepcopy(saved.data)
        except Exception as error:  # noqa: BLE001 - normalize process/resource failures without exposing credentials
            guards.close()
            if isinstance(error, AndroidError):
                raise WorkflowError(error.code, error.message, error.status) from None
            raise _resource_error(error) from None

    def debug_command(self, run_id: str, identifier: str) -> dict[str, Any]:
        self.get(run_id)
        result = self.repository.command(run_id, identifier)
        if result is None:
            raise WorkflowError('DEBUG_COMMAND_NOT_FOUND', '调试命令不存在', 404)
        return result

    async def send_debug(self, run_id: str, command: dict[str, Any]) -> dict[str, Any]:
        async with self._command_locks.setdefault(run_id, asyncio.Lock()):
            record = self.get(run_id)
            digest = hashlib.sha256(json.dumps(command, sort_keys=True, allow_nan=False).encode()).hexdigest()
            existing = self.repository.command(run_id, command['commandId'])
            if existing is not None:
                self.repository.command(run_id, command['commandId'], digest)
                return existing
            if record.get('mode') != 'debug' or run_id not in self._active or self._active[run_id].stopping or record['state'] in {'starting', 'finishing', 'stopping'}:
                raise WorkflowError('DEBUG_UNAVAILABLE', '调试已结束或正在停止', 409)
            self.repository.command(run_id, command['commandId'], digest)
            try:
                await self._launcher.command(run_id, command)
            except WorkflowError as error:
                rejected = {'commandId': command['commandId'], 'state': 'rejected', 'debug': record.get('debug'), 'data': None, 'error': {'code': error.code, 'message': error.message}}
                self._append(run_id, {'type': 'debug_response', 'response': rejected}, {'_command': rejected})
            except Exception:  # noqa: BLE001 -- do not resend an uncertain command; its ID remains queryable.
                return self.debug_command(run_id, command['commandId'])
            return self.debug_command(run_id, command['commandId'])

    def variables(self, run_id: str, checkpoint_id: str | None, offset: int, limit: int, after: int) -> dict[str, Any]:
        run = self.get(run_id)
        checkpoint_id = checkpoint_id or (run.get('debug') or {}).get('checkpointId')
        items = []
        next_offset = None
        if checkpoint_id:
            path, artifact = self.artifact(run_id, checkpoint_id)
            if artifact.get('purpose') != 'diagnostic' or self._read_json is None:
                raise WorkflowError('DEBUG_CHECKPOINT_INVALID', '变量检查点不存在', 404)
            checkpoint = self._read_json(path)
            if checkpoint.get('kind') != 'checkpoint':
                raise WorkflowError('DEBUG_CHECKPOINT_INVALID', '此记录不是变量检查点', 422)
            values = checkpoint['variables']
            for value in values[offset:offset + limit]:
                text = json.dumps(value['value'], ensure_ascii=False, allow_nan=False)
                items.append({**{key: value[key] for key in ('name', 'scope', 'source')}, 'type': type(value['value']).__name__, 'preview': text[:240], 'artifactId': checkpoint_id})
            next_offset = offset + limit if len(values) > offset + limit else None
        diagnostics = self.repository.artifacts(run_id, after, limit + 1, purpose='diagnostic')
        return {'checkpointId': checkpoint_id, 'items': items, 'nextOffset': next_offset,
                'diagnosticArtifacts': diagnostics[:limit], 'nextCursor': diagnostics[limit - 1]['ordinal'] if len(diagnostics) > limit else None}

    def filtered_events(self, run_id: str, after: int, limit: int, through: int | None, filters: dict[str, str], tail: bool = False) -> dict[str, Any]:
        run = self.get(run_id)
        through = min(through if through is not None else run['latestSeq'], run['latestSeq'])
        items = self.repository.filtered_events(run_id, after, limit if tail else limit + 1, through, filters, tail)
        return {'items': items[:limit], 'hasMore': len(items) > limit, 'nextSeq': items[limit-1]['seq'] if len(items) > limit else through}

    def export(self, run_id: str, kind: str, through: int | None, filters: dict[str, str]) -> Iterator[bytes]:
        run = self.get(run_id)
        through = min(through if through is not None else run['latestSeq'], run['latestSeq'])
        if kind == 'logs':
            return self._export_logs(run_id, through, filters)
        entries: ListType[tuple[Path, dict[str, Any]]] = []
        cursor = 0
        while True:
            batch = self.repository.artifacts(run_id, cursor, 100, purpose='result' if kind == 'results' else 'diagnostic', through_seq=through)
            if not batch:
                break
            for item in batch:
                path, _ = self.artifact(run_id, item['id'])
                entries.append((path, item))
            cursor = batch[-1]['ordinal']
        if kind == 'results':
            assert self._archive is not None
            return self._archive(entries)
        return self._export_diagnostics(entries)

    def _export_logs(self, run_id: str, through: int, filters: dict[str, str]) -> Iterator[bytes]:
        cursor = 0
        while cursor < through:
            batch = self.repository.filtered_events(run_id, cursor, 200, through, filters)
            if not batch:
                break
            for item in batch:
                yield (json.dumps(item, ensure_ascii=False) + '\n').encode()
            cursor = batch[-1]['seq']

    def _export_diagnostics(self, entries: ListType[tuple[Path, dict[str, Any]]]) -> Iterator[bytes]:
        assert self._read_json is not None
        yield b'['
        for index, (path, item) in enumerate(entries):
            if index:
                yield b','
            # Stream JSON encoding; one registered diagnostic file is read at a time.
            for part in json.JSONEncoder(ensure_ascii=False).iterencode({'artifact': item, 'diagnostic': self._read_json(path)}):
                yield part.encode()
        yield b']'

    async def stop(self, run_id: str) -> dict[str, Any]:
        operation = self._active.get(run_id)
        if operation is None:
            record = self.get(run_id)
            if record["state"] in ACTIVE_RUN_STATES:
                raise WorkflowError("WORKFLOW_RUN_UNAVAILABLE", "运行进程状态不可用，请重新连接", 409)
            return record
        # Cleanup has its own task before touching persistence. A failed write or
        # disconnected HTTP request cannot leave stopping=True without a cancel owner.
        await asyncio.shield(self._request_stop(run_id, operation))
        return self.get(run_id)

    def _request_stop(self, run_id: str, operation: _ActiveRun) -> asyncio.Task[None]:
        if operation.stop_task is None or operation.stop_task.done():
            _reset_cleanup_retry(operation)
            operation.stopping = True
            operation.stop_task = asyncio.create_task(
                self._stop(run_id, operation), name=f"stop-workflow-{run_id}",
            )
        return operation.stop_task

    async def _stop(self, run_id: str, operation: _ActiveRun) -> None:
        try:
            if self._active.get(run_id) is operation:
                self._append(run_id, {"type": "stopping", "message": "正在停止运行并回收连接"}, {"state": "stopping"})
        except Exception:  # noqa: BLE001 - persistence failure must never prevent process cleanup
            logger.warning("workflow stopping event could not be saved: run_id=%s", run_id)
        if operation.executing:
            try:
                await self._cleanup(run_id, operation)
            except Exception:  # noqa: BLE001 - preserve cleanup ownership for an explicit retry
                self._record_cleanup_failure(run_id, operation)
                raise _cleanup_error() from None
        elif operation.task is not None:
            # Let an unstarted task enter its try/finally before cancellation.
            await asyncio.sleep(0)
            if not operation.executing and not operation.task.done():
                operation.task.cancel()
            elif operation.executing:
                try:
                    await self._cleanup(run_id, operation)
                except Exception:  # noqa: BLE001 - preserve cleanup ownership for an explicit retry
                    self._record_cleanup_failure(run_id, operation)
                    raise _cleanup_error() from None
        if operation.task is not None:
            await asyncio.shield(operation.task)
        if not await self._finish(run_id, operation):
            raise _cleanup_error()

    async def shutdown(self) -> None:
        self._closing = True
        if self._shutdown_task is None or (self._shutdown_task.done() and self._active):
            self._shutdown_task = asyncio.create_task(self._shutdown(), name="workflow-shutdown")
        await _wait_cleanup(self._shutdown_task)

    async def _shutdown(self) -> None:
        await asyncio.gather(*(
            self._request_stop(run_id, operation)
            for run_id, operation in list(self._active.items())
        ), return_exceptions=True)
        await self._launcher.shutdown()
        for run_id, operation in list(self._active.items()):
            _reset_cleanup_retry(operation)
            if operation.task is not None:
                await _wait_cleanup(operation.task)
            if not await self._finish(run_id, operation):
                raise _cleanup_error()
        self._retry_completions()

    def busy(self) -> bool:
        self._retry_completions()
        with self._completion_lock:
            pending = bool(self._pending_completions)
        return pending or bool(self._active) or self._launcher.busy() or self.repository.active_id() is not None

    def events(self, run_id: str, after_seq: int, limit: int) -> dict[str, Any]:
        self.get(run_id)
        items = self.repository.events(run_id, after_seq, limit + 1)
        visible = items[:limit]
        return {"items": visible, "hasMore": len(items) > limit, "nextSeq": visible[-1]["seq"] if visible else after_seq}

    @contextmanager
    def subscribe(self, run_id: str) -> Iterator[asyncio.Event]:
        self._loop = asyncio.get_running_loop()
        self.get(run_id)
        signal = asyncio.Event()
        subscribers = self._subscribers.setdefault(run_id, set())
        subscribers.add(signal)
        try:
            yield signal
        finally:
            subscribers.discard(signal)
            if not subscribers:
                self._subscribers.pop(run_id, None)

    def artifact(self, run_id: str, artifact_id: str) -> tuple[Path, dict[str, Any]]:
        artifact = self.repository.artifact(run_id, artifact_id)
        if artifact is not None:
            try:
                path = self._artifact_path(run_id, artifact["relativePath"])
                if not path.is_file():
                    raise OSError
            except (OSError, ValueError):
                raise WorkflowError("WORKFLOW_ARTIFACT_UNAVAILABLE", "产物文件不存在或路径不安全", 404) from None
            return path, artifact
        raise WorkflowError("WORKFLOW_ARTIFACT_NOT_FOUND", "运行产物不存在", 404)

    def artifacts(self, run_id: str, after: int, limit: int, node_id: str | None = None, execution_id: str | None = None) -> dict[str, Any]:
        if self.repository.get(run_id) is None:
            raise WorkflowError("WORKFLOW_RUN_NOT_FOUND", "运行记录不存在", 404)
        rows = self.repository.artifacts(run_id, after, limit + 1, node_id, execution_id)
        page = rows[:limit]
        return {"items": page, "nextCursor": page[-1]["ordinal"] if len(rows) > limit else None}

    async def _execute(
        self, run_id: str, operation: _ActiveRun, prepared: PreparedWorkflow,
        profile: Profile | None, executable: Path | None,
    ) -> None:
        result: dict[str, Any] = {"state": "cancelled", "error": None}
        cleanup_failed = False
        try:
            if operation.stopping:
                return
            for warning in prepared.warnings:
                self._append(run_id, {"type": "log", "level": "warning", "nodeId": warning.node_id, "message": warning.message})
            if operation.android:
                operation.executing = True
                operation.device_task = asyncio.create_task(self._run_android(run_id, operation, prepared))
                result = await asyncio.shield(operation.device_task)
                return
            assert profile is not None and executable is not None
            async with asyncio.timeout(110):
                proxy = await self._resolve_proxy(profile, run_id)
                license_key = self._read_license() if profile.spec.browser_edition == "licensed" else None
                if profile.spec.browser_edition == "licensed" and not license_key:
                    raise LicenseInvalid
            if operation.stopping:
                return
            operation.executing = True
            result = await self._launcher.execute(
                run_id, prepared, profile, executable, proxy, license_key,
                lambda event: self._worker_event(run_id, operation, event),
            )
        except asyncio.CancelledError:
            result = {"state": "cancelled", "error": None}
        except Exception as error:  # noqa: BLE001 - normalize process/resource failures without exposing credentials
            normalized = WorkflowError(error.code, error.message, error.status) if isinstance(error, AndroidError) else _resource_error(error)
            cleanup_failed = normalized.code == "WORKFLOW_CLEANUP_FAILED"
            issue = normalized.issues[0] if normalized.issues else None
            result = {"state": "failed", "error": {
                "code": normalized.code, "message": normalized.message,
                "nodeId": issue.node_id if issue else None, "path": issue.path if issue else [],
            }}
        finally:
            operation.result = result
            if cleanup_failed:
                self._record_cleanup_failure(run_id, operation)
            else:
                await self._finish(run_id, operation)

    async def _run_android(self, run_id: str, operation: _ActiveRun, prepared: PreparedWorkflow) -> dict[str, Any]:
        assert self.android is not None and self.android_worker is not None
        await self.android.connect()

        async def publish(event: dict[str, Any], changes: dict[str, Any]) -> None:
            if operation.stopping:
                raise asyncio.CancelledError
            handoff = changes.get("handoff")
            if handoff:
                receipts = dict(self.get(run_id).get("handoffReceipts", {}))
                receipts[handoff["handoffId"]] = dict(handoff["receipts"])
                changes = {**changes, "handoffReceipts": receipts}
            record = self.get(run_id)
            self._append(run_id, {**event, "executionId": record.get("currentExecutionId"), "loopPath": record.get("currentLoopPath", [])}, changes)

        async def command(event: dict[str, Any]) -> dict[str, Any]:
            assert self.android is not None
            node_id = event["nodeId"]
            record = self.get(run_id)
            if operation.stopping or node_id != record["currentNodeId"]:
                raise asyncio.CancelledError
            try:
                if event["operation"] == "android_manual":
                    await self.android.manual(node_id, event["args"], publish)
                    return {"result": None}
                data = await self.android.command(event["operation"], event["args"], float(event["args"]["timeoutSeconds"]))
                if event["operation"] == "android_screenshot":
                    assert self.save_android_image is not None
                    result = self.save_android_image(run_id, node_id, data)
                    return {"result": result["value"], "artifact": result["artifact"]}
                return {"result": None}
            except (AndroidError, TimeoutError) as error:
                return {"error": {"code": error.code if isinstance(error, AndroidError) else "ANDROID_TIMEOUT", "message": error.message if isinstance(error, AndroidError) else "安卓动作超时", "nodeId": node_id, "path": []}}

        return await self.android_worker.execute(run_id, prepared, lambda event: self._worker_event(run_id, operation, event), command)

    async def handoff_control(self, run_id: str, handoff_id: str, request_id: str, action: str) -> dict[str, Any]:
        record = self.get(run_id)
        prior = record.get("handoff")
        receipts = record.get("handoffReceipts", {}).get(handoff_id, {})
        if prior and prior["handoffId"] == handoff_id:
            receipts = prior.get("receipts", receipts)
        if request_id in receipts:
            if receipts[request_id] != action:
                raise WorkflowError("ANDROID_REQUEST_CONFLICT", "请求编号已用于不同操作", 409)
            return record
        operation = self._active.get(run_id)
        if not operation or not operation.android or operation.stopping or self.android is None:
            raise WorkflowError("ANDROID_HANDOFF_STALE", "当前运行不接受人工操作", 409)
        await self.android.control(handoff_id, request_id, action)
        return self.get(run_id)

    async def _cleanup_android(self, run_id: str, operation: _ActiveRun) -> None:
        assert self.android is not None and self.android_worker is not None
        self.android.request_stop()
        if operation.device_task is not None and not operation.device_task.done():
            operation.device_task.cancel()
        await self.android_worker.stop(run_id)
        if operation.device_task is not None:
            await asyncio.gather(operation.device_task, return_exceptions=True)
        await self.android.cleanup()

    async def _cleanup(self, run_id: str, operation: _ActiveRun) -> None:
        if operation.cleanup_task is None:
            operation.cleanup_task = asyncio.create_task(self._cleanup_android(run_id, operation) if operation.android else self._launcher.stop(run_id))
        await _wait_cleanup(operation.cleanup_task)

    def _record_cleanup_failure(self, run_id: str, operation: _ActiveRun) -> None:
        if operation.cleanup_failed:
            return
        operation.cleanup_failed = True
        try:
            self._append(run_id, {
                "type": "cleanup_failed", "level": "error", "message": _cleanup_error().message,
                "error": _cleanup_error_data(),
            }, {"state": "stopping" if operation.stopping else "finishing", "error": _cleanup_error_data()})
        except Exception:  # noqa: BLE001 - cleanup and retry ownership survives failed diagnostics
            logger.warning("workflow cleanup failure could not be saved: run_id=%s", run_id)

    async def _finish(self, run_id: str, operation: _ActiveRun) -> bool:
        if self._active.get(run_id) is not operation:
            return True
        record = None
        try:
            record = self.repository.get(run_id)
            if record is not None and record.data['state'] in {'starting', 'running'}:
                self._append(run_id, {'type': 'finishing', 'message': '调度结束，正在确认资源清理'}, {'state': 'stopping' if operation.stopping else 'finishing'})
        except Exception:  # noqa: BLE001 -- storage failure must not prevent browser cleanup.
            logger.warning('workflow finishing state could not be saved: run_id=%s', run_id)
        if operation.executing:
            try:
                await self._cleanup(run_id, operation)
            except Exception:  # noqa: BLE001 - keep guards and the slot until cleanup is confirmed
                self._record_cleanup_failure(run_id, operation)
                return False
        if self._active.get(run_id) is not operation:
            return True
        assert operation.result is not None
        state = "failed" if operation.debug_failure else "cancelled" if operation.stopping else operation.result["state"]
        outcome_error = operation.debug_failure or (None if state == "cancelled" else operation.result.get("error"))
        debug_state = None
        current_record = record
        if current_record is not None and current_record.data.get('debug'):
            debug_state = deepcopy(current_record.data['debug'])
            if debug_state.get('pausedAt'):
                debug_state['pauseDurationMs'] = debug_state.get('pauseDurationMs', 0) + max(0, round((datetime.now(UTC) - datetime.fromisoformat(debug_state['pausedAt'])).total_seconds() * 1000))
            debug_state.update(state=state, pauseId=None, pausedAt=None)
        completion = _PendingCompletion({"type": state, "level": "error" if state == "failed" else "info", "message": {
            "succeeded": "运行完成，浏览器已关闭", "failed": "运行失败，浏览器已关闭", "cancelled": "运行已停止，浏览器已关闭",
        }[state].replace("浏览器已关闭", "设备占用已释放，Android 与数据保留") if operation.android else {"succeeded": "运行完成，浏览器已关闭", "failed": "运行失败，浏览器已关闭", "cancelled": "运行已停止，浏览器已关闭"}[state], "error": outcome_error}, {"state": state, "finishedAt": datetime.now(UTC).isoformat(), "error": outcome_error, **({"debug": debug_state} if debug_state else {})})
        with self._completion_lock:
            self._pending_completions[run_id] = completion
        self._retry_completions(run_id)
        if operation.guards is not None:
            operation.guards.close()
        self._active.pop(run_id, None)
        self._command_locks.pop(run_id, None)
        return True

    async def _worker_event(self, run_id: str, operation: _ActiveRun, event: dict[str, Any]) -> None:
        stored_record = self.repository.get(run_id)
        assert stored_record is not None
        record = stored_record.data
        changes: dict[str, Any] = {}
        kind = event.get("type", "log")
        node_id = event.get("nodeId")
        if kind == "ready" and not operation.stopping:
            changes["state"] = "running"
        elif kind == "node_started":
            if not operation.stopping:
                changes["state"] = "running"
            changes["nodeExecutionCounts"] = {**record.get("nodeExecutionCounts", {}), node_id: record.get("nodeExecutionCounts", {}).get(node_id, 0) + 1}
            changes.update(currentNodeId=node_id, currentExecutionId=event.get("executionId"), currentLoopPath=event.get("loopPath", []), executionCount=record.get("executionCount", 0) + 1)
        elif kind == "node_succeeded":
            completed = record["completedNodeIds"]
            if node_id not in completed:
                changes["completedNodeIds"] = [*completed, node_id]
        elif kind == "node_failed" and not operation.stopping:
            if record.get('mode') == 'debug':
                operation.debug_failure = event.get('error')
            else:
                changes["state"] = "finishing"
        if kind in {'debug_state', 'debug_checkpoint'}:
            changes['debug'] = event['debug']
            if not operation.stopping:
                changes['state'] = event['debug']['state']
            if event.get('error'):
                operation.debug_failure = event['error']
                changes['error'] = event['error']
        if kind == 'debug_response':
            changes['_command'] = event['response']
        stored: dict[str, Any] = {key: event[key] for key in ("type", "nodeId", "level", "message", "durationMs", "error", "executionId", "loopPath", "branch", "debug", "reason", "response") if key in event}
        artifact = event.get("artifact")
        if artifact is not None:
            self._artifact_path(run_id, artifact["relativePath"])
            changes["_artifact"] = deepcopy(artifact)
            stored["artifactId"] = artifact["id"]
        self._append(run_id, stored, changes)

    def _append(self, run_id: str, event: dict[str, Any], changes: dict[str, Any] | None = None) -> None:
        self.repository.append(run_id, event, changes or {})
        # Notification follows the successful state/event transaction. Signals can coalesce:
        # every subscriber always re-reads durable events, so no log is ever dropped.
        if self._loop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._notify, run_id)

    def _notify(self, run_id: str) -> None:
        for signal in self._subscribers.get(run_id, ()):
            signal.set()

    def _retry_completions(self, run_id: str | None = None) -> None:
        # One bounded attempt per read/control operation. Keep retry ownership in
        # memory until commit succeeds; startup recovers the durable active record
        # as interrupted if the service must exit while storage remains unavailable.
        with self._completion_lock:
            for pending_id, completion in list(self._pending_completions.items()):
                if run_id is not None and pending_id != run_id:
                    continue
                try:
                    record = self.repository.get(pending_id)
                    if record is None or record.data["state"] in ACTIVE_RUN_STATES:
                        self._append(pending_id, completion.event, completion.changes)
                    # A commit whose acknowledgment failed may already be terminal.
                    # Checking first avoids duplicating its terminal event on retry.
                    self._pending_completions.pop(pending_id)
                except Exception:  # noqa: BLE001 - retain completion for a later bounded retry
                    logger.warning("workflow terminal event remains pending: run_id=%s", pending_id)



def _reset_cleanup_retry(operation: _ActiveRun) -> None:
    task = operation.cleanup_task
    if task is not None and task.done() and (task.cancelled() or task.exception() is not None):
        operation.cleanup_task = None


def _cleanup_error() -> WorkflowError:
    return WorkflowError("WORKFLOW_CLEANUP_FAILED", "运行连接清理尚未完成，请重试停止", 503)


def _cleanup_error_data() -> dict[str, Any]:
    error = _cleanup_error()
    return {"code": error.code, "message": error.message, "nodeId": None, "path": []}


def _camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


def _issue(issue: WorkflowIssue) -> dict[str, Any]:
    return {"nodeId": issue.node_id, "path": issue.path, "code": issue.code, "message": issue.message}




async def _wait_cleanup(task: asyncio.Task[Any]) -> None:
    # Request/host cancellation must not expose a terminal record or release guards
    # while the independent cleanup task still owns a browser process tree.
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
    task.result()
