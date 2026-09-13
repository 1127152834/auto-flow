from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from contextlib import AbstractContextManager, ExitStack
from copy import deepcopy
from pathlib import Path
from typing import Any

from autoflow.application.profiles.service import ProfileService
from autoflow.application.workflows.browser_resources import (
    acquire_browser,
    resource_error,
)
from autoflow.application.workflows.runs import _wait_cleanup
from autoflow.domain.kernels.errors import LicenseInvalid
from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.profiles.models import Profile, ProfileBrowserProxy
from autoflow.domain.workflows.inspection import InspectionLauncher, inspection_target
from autoflow.domain.workflows.models import WorkflowError
from autoflow.domain.workflows.run_validation import PreparedWorkflow


class InspectionService:
    def __init__(self, profiles: ProfileService, installed: Callable[[], Sequence[InstalledKernel]],
                 kernel_guard: Callable[[Profile], AbstractContextManager[None]],
                 resolve_proxy: Callable[[Profile, str], Awaitable[ProfileBrowserProxy | None]],
                 read_license: Callable[[], str | None], launcher: InspectionLauncher,
                 run_busy: Callable[[], bool]) -> None:
        self._profiles, self._installed, self._kernel_guard = profiles, installed, kernel_guard
        self._resolve_proxy, self._read_license, self._launcher = resolve_proxy, read_license, launcher
        self._run_busy = run_busy
        self._records: dict[str, dict[str, Any]] = {}
        self._picks: dict[str, dict[str, dict[str, Any]]] = {}
        self._requests: dict[str, dict[str, str]] = {}
        self._guards: dict[str, ExitStack] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._closing_tasks: dict[str, asyncio.Task[None]] = {}
        self._stopping: set[str] = set()
        self._executing: set[str] = set()
        self._current: str | None = None
        self._shutdown = False

    def busy(self) -> bool:
        return bool(self._guards) or self._launcher.busy()

    def current(self) -> dict[str, Any] | None:
        return self.get(self._current) if self._current else None

    def get(self, session_id: str) -> dict[str, Any]:
        if session_id not in self._records:
            raise WorkflowError('INSPECTION_NOT_FOUND', '拾取会话不存在或服务已重启', 404)
        return deepcopy(self._records[session_id])

    def start(self, session_id: str, profile_id: str) -> dict[str, Any]:
        if session_id in self._records:
            if self._records[session_id]['profileId'] != profile_id:
                raise WorkflowError('INSPECTION_ID_CONFLICT', '会话标识已用于不同配置', 409)
            return self.get(session_id)
        if self._shutdown or self.busy() or self._run_busy():
            raise WorkflowError('INSPECTION_BUSY', '请先结束当前工作流运行或拾取会话', 409)
        guards = ExitStack()
        try:
            profile, executable = acquire_browser(guards, self._profiles, self._kernel_guard, self._installed, profile_id)
        except Exception as error:  # noqa: BLE001 -- normalize browser/resource failures without leaking page data.
            guards.close()
            raise resource_error(error) from None
        # No await between resource admission and registering ownership.
        self._records[session_id] = {'sessionId': session_id, 'profileId': profile_id,
                                    'profileName': profile.spec.name, 'state': 'starting', 'headless': False,
                                    'pages': [], 'targetPageId': None, 'pick': None, 'error': None}
        self._picks[session_id] = {}
        self._requests[session_id] = {}
        self._guards[session_id] = guards
        self._current = session_id
        self._tasks[session_id] = asyncio.create_task(self._execute(session_id, profile, executable))
        return self.get(session_id)

    async def _execute(self, session_id: str, profile: Profile, executable: Path) -> None:
        record = self._records[session_id]
        result: dict[str, Any] = {'state': 'succeeded', 'error': None}
        try:
            if session_id in self._stopping:
                return
            async with asyncio.timeout(110):
                proxy = await self._resolve_proxy(profile, session_id)
                license_key = self._read_license() if profile.spec.browser_edition == 'licensed' else None
                if profile.spec.browser_edition == 'licensed' and not license_key:
                    raise LicenseInvalid
            if session_id in self._stopping:
                return
            self._executing.add(session_id)
            result = await self._launcher.execute(session_id, PreparedWorkflow({}, [], {}, []), profile,
                                                  executable, proxy, license_key,
                                                  lambda event: self._event(session_id, event))
        except asyncio.CancelledError:
            pass
        except Exception as error:  # noqa: BLE001 -- normalize browser/resource failures without leaking page data.
            normalized = resource_error(error)
            result = {'state': 'failed', 'error': {'message': normalized.message}}
        finally:
            if self._launcher.busy():
                record.update(state='closing', error='浏览器清理尚未完成，请重试关闭')
            else:
                self._release(session_id, result)

    async def _event(self, session_id: str, event: dict[str, Any]) -> None:
        record = self._records[session_id]
        if session_id in self._stopping:
            return
        pick = event.get('pick')
        if pick:
            self._picks[session_id][pick['requestId']] = pick
        record.update(state='ready', pages=event['pages'], targetPageId=event['targetPageId'], pick=pick)

    def _release(self, session_id: str, result: dict[str, Any]) -> None:
        guards = self._guards.pop(session_id, None)
        if guards:
            guards.close()
        error = result.get('error')
        self._records[session_id].update(
            state='failed' if result['state'] == 'failed' and session_id not in self._stopping else 'closed',
            pages=[], targetPageId=None, error=error.get('message') if error else None,
        )
        for item in self._picks[session_id].values():
            if item['state'] == 'pending':
                item.update(state='cancelled')
        self._executing.discard(session_id)

    async def close(self, session_id: str) -> dict[str, Any]:
        self.get(session_id)
        if session_id not in self._guards:
            return self.get(session_id)
        task = self._closing_tasks.get(session_id)
        if task is None or task.done():
            self._stopping.add(session_id)
            self._records[session_id]['state'] = 'closing'
            task = asyncio.create_task(self._close(session_id))
            self._closing_tasks[session_id] = task
        await asyncio.shield(task)
        return self.get(session_id)

    async def _close(self, session_id: str) -> None:
        task = self._tasks[session_id]
        await asyncio.sleep(0)  # Allow newly admitted task to enter its finally block.
        if session_id in self._executing:
            try:
                await self._launcher.stop(session_id)
            except Exception:  # noqa: BLE001 -- normalize browser failures at the process boundary.
                self._records[session_id]['error'] = '浏览器清理尚未完成，请重试关闭'
                raise WorkflowError('WORKFLOW_CLEANUP_FAILED', '浏览器清理尚未完成，请重试关闭', 503) from None
        elif not task.done():
            task.cancel()
        await _wait_cleanup(task)
        if self._launcher.busy():
            raise WorkflowError('WORKFLOW_CLEANUP_FAILED', '浏览器清理尚未完成，请重试关闭', 503)
        self._release(session_id, {'state': 'succeeded', 'error': None})

    async def command(self, session_id: str, command: dict[str, Any]) -> dict[str, Any]:
        if self.get(session_id)['state'] != 'ready':
            raise WorkflowError('INSPECTION_NOT_READY', '拾取浏览器尚未就绪或已关闭', 409)
        return await self._launcher.command(session_id, command)

    async def pick(self, session_id: str, request_id: str, page_id: str) -> dict[str, Any]:
        self.get(session_id)
        accepted_page = self._requests[session_id].get(request_id)
        if accepted_page is not None and accepted_page != page_id:
            raise WorkflowError('INSPECTION_REQUEST_CONFLICT', '拾取标识已用于不同页面', 409)
        self._requests[session_id][request_id] = page_id
        previous = self._picks[session_id].get(request_id)
        if previous:
            if previous['pageId'] != page_id:
                raise WorkflowError('INSPECTION_REQUEST_CONFLICT', '拾取标识已用于不同页面', 409)
            return deepcopy(previous)
        result = await self.command(session_id, {'action': 'pick', 'requestId': request_id, 'pageId': page_id})
        # Heartbeat may already have delivered selected; never regress it to pending.
        if request_id not in self._picks[session_id]:
            self._picks[session_id][request_id] = result
        return deepcopy(self._picks[session_id][request_id])

    async def get_pick(self, session_id: str, request_id: str) -> dict[str, Any]:
        self.get(session_id)
        item = self._picks[session_id].get(request_id)
        if item is None:
            raise WorkflowError('INSPECTION_PICK_NOT_FOUND', '拾取请求尚未确认，请查询会话或重试原请求', 404)
        if item['state'] in {'pending', 'selected'} and self.get(session_id)['state'] == 'ready':
            item = await self.command(session_id, {'action': 'get-pick', 'requestId': request_id})
            self._picks[session_id][request_id] = item
        return deepcopy(item)

    async def cancel(self, session_id: str, request_id: str) -> dict[str, Any]:
        previous = await self.get_pick(session_id, request_id)
        if previous['state'] != 'pending':
            return previous
        result = await self.command(session_id, {'action': 'cancel', 'requestId': request_id})
        self._picks[session_id][request_id] = result
        return result

    async def test(self, session_id: str, page_id: str, selector: str,
                   frame_path: list[str], variables: list[dict[str, Any]], literal_paths: list[str] | None = None) -> dict[str, Any]:
        target = inspection_target(selector, frame_path, variables, literal_paths)
        return await self.command(session_id, {'action': 'test', 'pageId': page_id,
                                              'selector': target['selector'], 'framePath': target['framePath']})

    async def shutdown(self) -> None:
        self._shutdown = True
        for session_id in list(self._guards):
            task = asyncio.create_task(self.close(session_id))
            await _wait_cleanup(task)
        await self._launcher.shutdown()
