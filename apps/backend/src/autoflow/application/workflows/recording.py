"""Recording admission, durable drafts, and bounded browser commands."""
from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from contextlib import AbstractContextManager, ExitStack
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Protocol

from autoflow.application.profiles.service import ProfileService
from autoflow.application.workflows.browser_resources import acquire_browser, resource_error
from autoflow.domain.profiles.models import Profile
from autoflow.domain.workflows.inspection import InspectionLauncher, inspection_target
from autoflow.domain.workflows.models import WorkflowError
from autoflow.domain.workflows.recording import MAX_VALUE_BYTES, generate
from autoflow.domain.workflows.run_validation import PreparedWorkflow


class RecordingStore(Protocol):
    def get(self, identifier: str) -> dict[str, Any]: ...
    def list_records(self, offset: int, limit: int) -> list[dict[str, Any]]: ...
    def create(self, record: dict[str, Any]) -> None: ...
    def update(self, identifier: str, patch: dict[str, Any], steps: list[dict[str, Any]] | None = None) -> dict[str, Any]: ...
    def steps(self, identifier: str, after: int = 0, limit: int = 50, *, ordered: bool = False) -> list[dict[str, Any]]: ...
    def step(self, identifier: str, step_id: str) -> dict[str, Any]: ...
    def edit(self, identifier: str, revision: int, changes: list[dict[str, Any]], order: list[str] | None) -> dict[str, Any]: ...
    def command(self, identifier: str, command_id: str, request_hash: str | None = None, value: dict[str, Any] | None = None) -> dict[str, Any] | None: ...
    def delete(self, identifier: str) -> None: ...


class RecordingService:
    def __init__(self, repository: RecordingStore, profiles: ProfileService, installed: Callable,
                 kernel_guard: Callable[[Profile], AbstractContextManager[None]], resolve_proxy: Callable[..., Awaitable],
                 read_license: Callable, launcher: InspectionLauncher, busy: Callable[[], bool],
                 write_value: Callable, read_value: Callable, remove_values: Callable) -> None:
        self.repository, self.profiles, self.installed = repository, profiles, installed
        self.kernel_guard, self.resolve_proxy, self.read_license = kernel_guard, resolve_proxy, read_license
        self.launcher, self.other_busy = launcher, busy
        self.write_value, self.read_value, self.remove_values = write_value, read_value, remove_values
        self.guards: dict[str, ExitStack] = {}
        self.tasks: dict[str, asyncio.Task] = {}
        self.controls: dict[str, asyncio.Task] = {}
        self.locks: dict[str, asyncio.Lock] = {}
        self.stopping: set[str] = set()
        self.shutdown_requested = False

    def busy(self) -> bool:
        return bool(self.guards) or self.launcher.busy()

    def start(self, identifier: str, profile_id: str, document_id: str | None) -> dict[str, Any]:
        try:
            old = self.repository.get(identifier)
        except WorkflowError as error:
            if error.status != 404:
                raise
        else:
            if old['profileId'] != profile_id or old['sourceDocumentId'] != document_id:
                raise WorkflowError('RECORDING_ID_CONFLICT', '录制标识已用于不同请求', 409)
            return old
        if self.shutdown_requested or self.busy() or self.other_busy():
            raise WorkflowError('RECORDING_BUSY', '请先结束运行、调试或拾取浏览器', 409)
        guards = ExitStack()
        try:
            profile, executable = acquire_browser(guards, self.profiles, self.kernel_guard, self.installed, profile_id)
            now = datetime.now(UTC).isoformat()
            record: dict[str, Any] = {'recordingId': identifier, 'profileId': profile_id, 'profileName': profile.spec.name,
                      'sourceDocumentId': document_id, 'browserState': 'starting', 'captureState': 'idle',
                      'revision': 1, 'lastSeq': 0, 'cutoffSeq': None, 'pages': [], 'targetPageId': None,
                      'issues': [], 'error': None, 'segment': 0, 'createdAt': now, 'updatedAt': now}
            self.repository.create(record)
        except Exception:
            guards.close()
            raise
        self.guards[identifier] = guards
        self.locks[identifier] = asyncio.Lock()
        self.tasks[identifier] = asyncio.create_task(self._run(identifier, profile, executable))
        return record

    async def _run(self, identifier: str, profile: Profile, executable: Any) -> None:
        result: dict[str, Any] = {'state': 'succeeded'}
        try:
            async with asyncio.timeout(110):
                proxy = await self.resolve_proxy(profile, identifier)
                license_key = self.read_license() if profile.spec.browser_edition == 'licensed' else None
                if profile.spec.browser_edition == 'licensed' and not license_key:
                    raise WorkflowError('LICENSE_UNAVAILABLE', '所选内核需要可用 License', 422)
            if identifier not in self.stopping:
                result = await self.launcher.execute(identifier, PreparedWorkflow({}, [], {}, []), profile, executable, proxy, license_key,
                                                     lambda event: self._event(identifier, event))
        except asyncio.CancelledError:
            pass
        except Exception as error:  # noqa: BLE001 -- do not leak launch credentials or browser exception text.
            result = {'state': 'failed', 'error': resource_error(error).message}
        finally:
            if self.launcher.busy():
                self.repository.update(identifier, {'browserState': 'closing', 'error': '浏览器清理未完成，请重试关闭'})
            else:
                self.guards.pop(identifier).close()
                old = self.repository.get(identifier)
                self.repository.update(identifier, {'browserState': 'failed' if result['state'] == 'failed' else 'closed',
                    'captureState': old['captureState'] if old['captureState'] == 'stopped' else 'interrupted',
                    'pages': [], 'targetPageId': None, 'error': '录制进程异常结束，仅保留已确认步骤' if result['state'] == 'failed' else old['error']})

    async def _event(self, identifier: str, event: dict[str, Any]) -> None:
        steps = []
        last = self.repository.get(identifier)['lastSeq']
        for step in event.get('steps', []):
            if step['seq'] <= last:
                continue
            item = deepcopy(step)
            if len(json.dumps(item['config'], ensure_ascii=False).encode()) > 16384:
                item['valueRef'] = self.write_value(identifier, item['config'])
                item['config'] = {k: v for k, v in item['config'].items() if k not in {'text', 'values'}}
            steps.append(item)
        self.repository.update(identifier, {'browserState': 'closing' if identifier in self.stopping else 'ready',
            'captureState': event['captureState'], 'pages': event['pages'], 'targetPageId': event['targetPageId'],
            'segment': event['segment'], 'issues': event['issues']}, steps)

    def submit(self, identifier: str, request: dict[str, Any]) -> dict[str, Any]:
        record = self.repository.get(identifier)
        command_id, digest = request['commandId'], _digest(request)
        old = self.repository.command(identifier, command_id, digest)
        if old:
            return old
        if request['action'] != 'close' and request['expectedRevision'] != record['revision']:
            raise WorkflowError('RECORDING_REVISION_CONFLICT', '录制状态已变化，请刷新', 409)
        if identifier not in self.guards and request['action'] != 'close':
            raise WorkflowError('RECORDING_CLOSED', '录制浏览器已关闭，不能恢复临时会话', 409)
        value = {'commandId': command_id, 'state': 'accepted', 'result': None, 'error': None}
        self.repository.command(identifier, command_id, digest, value)
        task = asyncio.create_task(self._apply(identifier, request, digest))
        self.controls[command_id] = task
        task.add_done_callback(lambda _: self.controls.pop(command_id, None))
        return value

    async def _apply(self, identifier: str, request: dict[str, Any], digest: str) -> None:
        result = {'commandId': request['commandId'], 'state': 'applied', 'result': None, 'error': None}
        try:
            if request['action'] == 'close':
                await self.close(identifier)
            else:
                async with self.locks[identifier]:
                    record = self.repository.get(identifier)
                    if request['expectedRevision'] != record['revision']:
                        raise WorkflowError('RECORDING_REVISION_CONFLICT', '命令所属录制状态已过期', 409)
                    response = await self.launcher.command(identifier, request)
                    cutoff = response.get('cutoffSeq')
                    if cutoff is not None:
                        async with asyncio.timeout(10):
                            while self.repository.get(identifier)['lastSeq'] < cutoff:
                                await asyncio.sleep(.05)
                    patch: dict[str, Any] = {'revision': record['revision'] + 1}
                    if request['action'] == 'stop':
                        patch['cutoffSeq'] = cutoff
                    self.repository.update(identifier, patch)
                    result['result'] = response
        except asyncio.CancelledError:
            result.update(state='unknown', error='操作被关闭或服务退出中断')
        except Exception as error:  # noqa: BLE001 -- keep command ambiguity distinct from success.
            result.update(state='unknown' if isinstance(error, TimeoutError) else 'rejected', error=error.message if isinstance(error, WorkflowError) else '录制命令未能确认，请重新查询')
        self.repository.command(identifier, request['commandId'], digest, result)

    async def close(self, identifier: str) -> dict[str, Any]:
        if identifier not in self.guards:
            return self.repository.get(identifier)
        old = self.repository.get(identifier)
        if identifier not in self.stopping and old['browserState'] == 'ready':
            try:
                response = await self.launcher.command(identifier, {'action': 'stop'})
                async with asyncio.timeout(10):
                    while self.repository.get(identifier)['lastSeq'] < response['cutoffSeq']:
                        await asyncio.sleep(.05)
                self.repository.update(identifier, {'captureState': 'stopped', 'cutoffSeq': response['cutoffSeq']})
            except Exception:  # noqa: BLE001 -- closing may still clean up an incomplete capture.
                self.repository.update(identifier, {'captureState': 'interrupted', 'error': '关闭前刷新未确认，仅保留已确认步骤'})
        self.stopping.add(identifier)
        self.repository.update(identifier, {'browserState': 'closing'})
        task = self.tasks.get(identifier)
        if self.launcher.busy():
            await self.launcher.stop(identifier)
        elif task and not task.done():
            task.cancel()
        if task:
            await asyncio.gather(task, return_exceptions=True)
        if self.launcher.busy():
            raise WorkflowError('RECORDING_CLEANUP_PENDING', '录制浏览器清理尚未完成，请重试关闭', 409)
        if identifier in self.guards:
            self.guards.pop(identifier).close()
            self.repository.update(identifier, {'browserState': 'closed', 'pages': [], 'targetPageId': None})
        return self.repository.get(identifier)

    def hydrate(self, identifier: str, step: dict[str, Any]) -> dict[str, Any]:
        return {**step, 'config': self.read_value(identifier, step['valueRef'])} if step.get('valueRef') else step

    def edit(self, identifier: str, revision: int, changes: list[dict[str, Any]], order: list[str] | None) -> dict[str, Any]:
        record = self.repository.get(identifier)
        if record['captureState'] not in {'stopped', 'interrupted'}:
            raise WorkflowError('RECORDING_STILL_ACTIVE', '停止录制后才能审查修改', 409)
        prepared = deepcopy(changes)
        for change in prepared:
            if 'config' in change:
                encoded = json.dumps(change['config'], allow_nan=False, ensure_ascii=False).encode()
                if len(encoded) > MAX_VALUE_BYTES:
                    raise WorkflowError('RECORDING_VALUE_LIMIT', '单步骤输入超过1 MiB', 422)
                change['valueRef'] = None
                if len(encoded) > 16384:
                    change['valueRef'] = self.write_value(identifier, change['config'])
                    change['config'] = {k: v for k, v in change['config'].items() if k not in {'text', 'values'}}
        return self.repository.edit(identifier, revision, prepared, order)

    def generate(self, identifier: str, request: dict[str, Any]) -> dict[str, Any]:
        record = self.repository.get(identifier)
        digest = _digest(request)
        old = self.repository.command(identifier, request['generationId'], digest)
        if old:
            return old['result']
        if record['captureState'] not in {'stopped', 'interrupted'} or record['revision'] != request['expectedRevision']:
            raise WorkflowError('RECORDING_REVISION_CONFLICT', '请停止录制并刷新审查结果', 409)
        steps = [self.hydrate(identifier, s) for s in self.repository.steps(identifier, limit=10000, ordered=True)]
        result = generate(identifier, request['generationId'], steps, request['target'])
        result['recordingRevision'] = record['revision']
        result['coverageIssues'] = record['issues']
        self.repository.command(identifier, request['generationId'], digest, {'commandId': request['generationId'], 'state': 'applied', 'result': result, 'error': None})
        return result

    async def test(self, identifier: str, request: dict[str, Any]) -> dict[str, Any]:
        target = inspection_target(request['selector'], request.get('framePath', []), request.get('variables', []), request.get('literalPaths', []))
        return await self.launcher.command(identifier, {'action': 'test', 'pageId': request['pageId'], **target})

    def delete(self, identifier: str) -> None:
        if identifier in self.guards:
            raise WorkflowError('RECORDING_STILL_ACTIVE', '请先关闭录制浏览器', 409)
        self.repository.get(identifier)
        self.remove_values(identifier)
        self.repository.delete(identifier)

    async def shutdown(self) -> None:
        self.shutdown_requested = True
        for identifier in list(self.guards):
            await self.close(identifier)
        await asyncio.gather(*list(self.controls.values()), return_exceptions=True)
        await self.launcher.shutdown()


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
