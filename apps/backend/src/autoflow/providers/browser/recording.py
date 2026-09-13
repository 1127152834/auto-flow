"""Browser-side passive recording with owned pages and confirmed-step buffering."""
from __future__ import annotations

import asyncio
import json
from collections import deque
from contextlib import suppress
from typing import Any
from uuid import uuid4

from autoflow.domain.workflows.recording import ACTIONS, MAX_RECORDING_BYTES, MAX_STEPS, MAX_VALUE_BYTES, problem
from autoflow.providers.browser.inspection import BrowserInspection
from autoflow.providers.browser.recording_script import RECORDING_SCRIPT
from autoflow.providers.browser.workflow_locator import NodeFailure


class BrowserRecording:
    def __init__(self, context: Any) -> None:
        self.context = context
        self.inspection = BrowserInspection(context)
        self.state = 'idle'
        self.segment = 0
        self.sequence = 0
        self.total_bytes = 0
        self.pending: deque[dict[str, Any]] = deque()
        self.issues: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._seen: dict[tuple[str, str], int] = {}
        self._tasks: set[asyncio.Task[Any]] = set()
        context.on('page', self._page)
        for page in context.pages:
            self._page(page)

    @property
    def target(self) -> str | None:
        return self.inspection.target

    @target.setter
    def target(self, value: str | None) -> None:
        self.inspection.target = value

    @property
    def pages(self) -> dict[str, Any]:
        return self.inspection.pages

    async def initialize(self) -> None:
        await self.context.expose_binding('__autoflowRecord', self._receive)
        await self.context.add_init_script(RECORDING_SCRIPT)
        for page in self.context.pages:
            for frame in page.frames:
                await frame.evaluate(RECORDING_SCRIPT)

    def _spawn(self, coroutine: Any) -> None:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _page(self, page: Any) -> None:
        page.on('framenavigated', lambda frame: self._spawn(self._navigated(page, frame)))
        page.on('close', lambda: self._closed(page))

    def _id(self, page: Any) -> str:
        return next(identifier for identifier, item in self.pages.items() if item is page)

    def _append(self, action: str, page_id: str, config: dict[str, Any], *, source: str = '', issues: list[dict[str, Any]] | None = None) -> None:
        size = len(json.dumps(config, ensure_ascii=False).encode())
        if size > MAX_VALUE_BYTES or self.sequence >= MAX_STEPS or self.total_bytes + size > MAX_RECORDING_BYTES:
            self.state = 'paused'
            if not any(i['code'] == 'RECORDING_LIMIT' for i in self.issues):
                self.issues.append(problem('RECORDING_LIMIT', '达到录制容量上限，未保存超限操作，请分段录制'))
            return
        self.sequence += 1
        self.total_bytes += size
        self.pending.append({'stepId': str(uuid4()), 'seq': self.sequence, 'action': action, 'pageId': page_id,
                             'segment': self.segment, 'sourceEventIds': [source] if source else [], 'config': config,
                             'issues': issues or [], 'label': '', 'excluded': False, 'useVariables': False})

    async def _receive(self, source: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
        element = None
        async with self._lock:
            try:
                page, frame = source['page'], source['frame']
                page_id = self._id(page)
                if self.state not in {'recording', 'pausing', 'stopping'} or raw.get('segment') != self.segment:
                    return {'received': False}
                if raw.get('action') not in ACTIONS or not isinstance(raw.get('config'), dict) or not isinstance(raw.get('epoch'), str) or type(raw.get('sourceSeq')) is not int:
                    raise ValueError('invalid event')
                key = (page_id, raw['epoch'])
                if raw['sourceSeq'] <= self._seen.get(key, 0):
                    return {'received': True}
                if raw['sourceSeq'] != self._seen.get(key, 0) + 1:
                    self.issues.append(problem('RECORDING_SOURCE_GAP', '页面事件序号不连续，请检查缺失步骤'))
                self._seen[key] = raw['sourceSeq']
                config = raw['config']
                element = await frame.evaluate_handle('p=>window.__autoflowRecording?.epoch===p.epoch ? window.__autoflowRecording.elements.get(p.targetId) : null', raw)
                problems: list[dict[str, Any]] = []
                try:
                    async with asyncio.timeout(2):
                        candidate = await self.inspection._candidate(frame, element)
                        chain: list[str] = []
                        current = frame
                        while current.parent_frame is not None:
                            owner = await current.frame_element()
                            try:
                                parent = await self.inspection._candidate(current.parent_frame, owner)
                                chain.insert(0, parent['selector'])
                            finally:
                                await owner.dispose()
                            current = current.parent_frame
                        config.update(selector=candidate['selector'], framePath=chain)
                except Exception:  # noqa: BLE001 -- a navigating page may destroy the selected element.
                    config.update(selector='', framePath=[])
                    problems.append(problem('RECORDING_SELECTOR_UNVERIFIED', '目标已变化，需补充并测试定位', 'config.selector'))
                self._append(raw['action'], page_id, config, source=f"{page_id}/{raw['epoch']}/{raw['sourceSeq']}", issues=problems)
                return {'received': True}
            except Exception:  # noqa: BLE001 -- never silently claim a malformed/destroyed source was captured.
                self.issues.append(problem('RECORDING_CAPTURE_GAP', '页面事件未能完整接收，请检查导航前后步骤'))
                return {'received': False}
            finally:
                if element is not None:
                    await element.dispose()

    async def _navigated(self, page: Any, frame: Any) -> None:
        try:
            await frame.evaluate(RECORDING_SCRIPT)
            if self.state == 'recording':
                await frame.evaluate('segment=>window.__autoflowRecording.set(true,segment)', self.segment)
                if frame is page.main_frame and page.url.startswith(('http://', 'https://')):
                    self._append('navigate', self._id(page), {'url': page.url, 'navigation': 'unconfirmed'})
        except Exception:  # noqa: BLE001 -- retain explicit coverage limitations.
            if self.state == 'recording':
                self.issues.append(problem('RECORDING_FRAME_GAP', '导航中的页面或框架未完成录制注入'))

    def _closed(self, page: Any) -> None:
        if self.state == 'recording':
            self._append('close', self._id(page), {})
            self.issues.append(problem('RECORDING_PAGE_CLOSED', '页面手动关闭，末尾缓冲可能未确认，请审查', severity='warning'))

    async def _set(self, active: bool) -> None:
        for page in self.pages.values():
            if page.is_closed():
                continue
            for frame in page.frames:
                try:
                    async with asyncio.timeout(5):
                        await frame.evaluate(RECORDING_SCRIPT)
                        result = await frame.evaluate('p=>window.__autoflowRecording.set(p.active,p.segment)', {'active': active, 'segment': self.segment})
                        if result.get('failed'):
                            raise ValueError('unconfirmed source')
                except Exception:  # noqa: BLE001 -- failed flush is an explicit incomplete prefix.
                    self.issues.append(problem('RECORDING_FLUSH_GAP', '部分框架未完成刷新，已保存步骤可能不完整'))

    async def command(self, command: dict[str, Any]) -> dict[str, Any]:
        action = command['action']
        if action == 'ack':
            while self.pending and self.pending[0]['seq'] <= command['seq']:
                self.pending.popleft()
            return {}
        if action in {'start', 'resume'}:
            if self.state != ('idle' if action == 'start' else 'paused'):
                raise NodeFailure('RECORDING_STATE_INVALID', '当前状态不允许开始或继续')
            self.segment += 1
            self.state = 'recording'
            if action == 'start':
                page = self.inspection.page(command.get('pageId') or self.target or '')
                self.target = self._id(page)
                if page.url.startswith(('http://', 'https://')):
                    self._append('navigate', self.target, {'url': page.url, 'navigation': 'direct'})
            else:
                self.issues.append(problem('RECORDING_PAUSE_GAP', '暂停期间的页面操作没有录入', severity='warning'))
            await self._set(True)
        elif action in {'pause', 'stop'}:
            if self.state == 'stopped' and action == 'stop':
                return {'cutoffSeq': self.sequence}
            if self.state not in {'recording', 'paused', 'idle'}:
                raise NodeFailure('RECORDING_STATE_INVALID', '当前状态不允许暂停或停止')
            self.state = 'pausing' if action == 'pause' else 'stopping'
            await self._set(False)
            self.state = 'paused' if action == 'pause' else 'stopped'
        elif action in {'page', 'test'}:
            if action == 'test' and self.state not in {'stopped', 'interrupted'}:
                raise NodeFailure('RECORDING_TEST_UNAVAILABLE', '停止录制后才能测试定位')
            data = await self.inspection.command(command)
            if action == 'page' and self.state == 'recording':
                if command.get('url'):
                    self._append('navigate', command['pageId'], {'url': command['url'], 'navigation': 'direct'})
                else:
                    self._append('page', command['pageId'], {})
            return data
        else:
            raise NodeFailure('RECORDING_COMMAND_INVALID', '不支持的录制命令')
        return {'captureState': self.state, 'cutoffSeq': self.sequence, 'segment': self.segment, 'issues': self.issues}

    async def snapshot(self) -> dict[str, Any]:
        snapshot = await self.inspection.snapshot()
        steps: list[dict[str, Any]] = []
        size = 0
        for step in self.pending:
            size += len(json.dumps(step, ensure_ascii=False).encode())
            if steps and (size > 1500000 or len(steps) >= 50):
                break
            steps.append(step)
        return {**snapshot, 'captureState': self.state, 'steps': steps, 'lastSeq': self.sequence,
                'segment': self.segment, 'issues': self.issues[-100:]}

    async def dispose(self) -> None:
        for task in self._tasks:
            task.cancel()
        with suppress(Exception):
            await asyncio.gather(*self._tasks, return_exceptions=True)
