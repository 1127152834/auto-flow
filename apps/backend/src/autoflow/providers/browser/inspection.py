from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any
from uuid import uuid4

from autoflow.providers.browser.inspection_script import (
    CANDIDATES_SCRIPT,
    HIGHLIGHT_SCRIPT,
    PICKER_SCRIPT,
)
from autoflow.providers.browser.workflow_locator import NodeFailure, locate_scope


class BrowserInspection:
    def __init__(self, context: Any) -> None:
        self.context = context
        self.pages: dict[str, Any] = {}
        self.revisions: dict[str, int] = {}
        self.target: str | None = None
        self.picks: dict[str, dict[str, Any]] = {}
        self.pending: str | None = None
        self.last_pick: str | None = None
        self._lock = asyncio.Lock()
        context.on('page', self._add_page)
        for page in context.pages:
            self._add_page(page)

    def _add_page(self, page: Any) -> None:
        if page in self.pages.values():
            return
        page_id = uuid4().hex
        self.pages[page_id], self.revisions[page_id] = page, 0
        page.on('framenavigated', lambda _: self._changed(page_id))
        page.on('framedetached', lambda _: self._changed(page_id))
        page.on('close', lambda: self._changed(page_id))

    def _changed(self, page_id: str) -> None:
        self.revisions[page_id] += 1
        for item in self.picks.values():
            if item['pageId'] == page_id and item['state'] in {'pending', 'selected'}:
                item.update(state='failed', result=None, error='页面或框架已变化，请重新拾取')
                if self.pending == item['requestId']:
                    self.pending = None
        if self.target == page_id and self.pages[page_id].is_closed():
            self.target = None

    def page(self, page_id: str) -> Any:
        page = self.pages.get(page_id)
        if page is None or page.is_closed():
            raise NodeFailure('INSPECTION_PAGE_CLOSED', '目标标签页已关闭，请重新选择')
        return page

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            if self.pending:
                await self._collect()
            if not self.pending:
                await self._disable()
            pages = []
            for identifier, page in self.pages.items():
                if not page.is_closed():
                    with suppress(Exception):
                        pages.append({'pageId': identifier, 'url': page.url[:2048], 'title': (await page.title())[:200], 'revision': self.revisions[identifier]})
            return {'pages': pages, 'targetPageId': self.target,
                    'pick': self.picks.get(self.last_pick) if self.last_pick else None}

    async def _disable(self) -> None:
        for page in self.pages.values():
            if page.is_closed():
                continue
            for frame in page.frames:
                with suppress(Exception):
                    await frame.evaluate("() => { const p=window.__autoflowPicker; if(p?.active) p.setActive(false); }")

    async def command(self, command: dict[str, Any]) -> dict[str, Any]:
        async with asyncio.timeout(10):
            async with self._lock:
                return await self._command(command)

    async def _command(self, command: dict[str, Any]) -> dict[str, Any]:
        action = command['action']
        if action == 'get-pick':
            item = self.picks.get(command['requestId'])
            if item is None:
                raise NodeFailure('INSPECTION_PICK_NOT_FOUND', '拾取请求不存在')
            if item['pageId'] != self.target and item['state'] in {'pending', 'selected'}:
                item.update(state='failed', result=None, error='目标标签页已变化，请重新拾取')
            return item
        if action == 'page':
            await self._cancel_pending()
            page_id = command['pageId']
            page = self.page(page_id)
            self.target = page_id
            if command.get('url'):
                await page.goto(command['url'], wait_until='domcontentloaded', timeout=10000)
            if command.get('focus'):
                await page.bring_to_front()
            return {}
        if action == 'pick':
            identifier, page_id = command['requestId'], command['pageId']
            if identifier in self.picks:
                if self.picks[identifier]['pageId'] != page_id:
                    raise NodeFailure('INSPECTION_REQUEST_CONFLICT', '拾取标识已用于另一页面')
                return self.picks[identifier]
            await self._cancel_pending()
            page = self.page(page_id)
            self.target = page_id
            revision = self.revisions[page_id]
            self.picks[identifier] = {'requestId': identifier, 'pageId': page_id, 'pageRevision': revision,
                                      'state': 'pending', 'result': None, 'error': None}
            self.last_pick = self.pending = identifier
            try:
                for frame in page.frames:
                    await frame.evaluate(PICKER_SCRIPT)
                    await frame.evaluate('() => window.__autoflowPicker.setActive(true)')
                await page.bring_to_front()
                if self.revisions[page_id] != revision:
                    raise NodeFailure('INSPECTION_PAGE_CHANGED', '页面已变化，请重新拾取')
            except BaseException:
                self.picks[identifier].update(state='failed', error='无法在此页面开启拾取')
                self.pending = None
                await self._disable()
                raise
            return self.picks[identifier]
        if action == 'cancel':
            item = self.picks.get(command['requestId'])
            if item and item['state'] == 'pending':
                item.update(state='cancelled')
                self.pending = None
                await self._disable()
            return item or {}
        if action == 'test':
            await self._cancel_pending()
            page_id = command['pageId']
            page, revision = self.page(page_id), self.revisions[page_id]
            deadline = asyncio.get_running_loop().time() + 10
            scope = await locate_scope(page, command.get('framePath', []), lambda: max(1, (deadline-asyncio.get_running_loop().time())*1000))
            try:
                matches = scope.locator(command['selector'])
                count = await matches.count()
                first = None
                if count:
                    first = await matches.first.evaluate("el => ({tag:el.tagName.toLowerCase(),text:(el.textContent||'').slice(0,200)})")
                    first['visible'] = await matches.first.is_visible()
                await matches.evaluate_all('(els) => (' + HIGHLIGHT_SCRIPT + ')(els.slice(0,100))')
            except Exception as error:
                raise NodeFailure('INSPECTION_SELECTOR_INVALID', '选择器无效或页面已变化', ['config', 'selector']) from error
            if revision != self.revisions[page_id] or page.is_closed():
                raise NodeFailure('INSPECTION_PAGE_CHANGED', '页面已变化，请重新测试')
            return {'pageId': page_id, 'pageRevision': revision, 'selector': command['selector'],
                    'framePath': command.get('framePath', []), 'count': count, 'first': first, 'truncated': count > 100}
        raise NodeFailure('INSPECTION_COMMAND_INVALID', '不支持的拾取命令')

    async def _cancel_pending(self) -> None:
        if self.pending:
            self.picks[self.pending]['state'] = 'cancelled'
            self.pending = None
        await self._disable()

    async def _candidate(self, scope: Any, handle: Any) -> dict[str, Any]:
        candidates = await handle.evaluate(CANDIDATES_SCRIPT)
        for candidate in candidates:
            try:
                locator = scope.locator(candidate['selector'])
                if await locator.count() == 1 and await locator.evaluate('(el, target) => el === target', handle):
                    return dict(candidate)
            except Exception:  # noqa: BLE001, S112 -- reject invalid attribute candidates and try the structural fallback.
                continue
        raise NodeFailure('INSPECTION_SELECTOR_UNAVAILABLE', '无法生成唯一且可执行的选择器')

    async def _collect(self) -> None:
        assert self.pending is not None
        item = self.picks[self.pending]
        page = self.page(item['pageId'])
        try:
            async with asyncio.timeout(10):
                for frame in page.frames:
                    if await frame.evaluate('() => Boolean(window.__autoflowPicker?.cancelled)'):
                        item['state'], self.pending = 'cancelled', None
                        return
                    handle = await frame.evaluate_handle('() => window.__autoflowPicker?.selected || null')
                    try:
                        element = handle.as_element()
                        if element is None:
                            continue
                        candidate = await self._candidate(frame, element)
                        chain: list[str] = []
                        current = frame
                        while current.parent_frame is not None:
                            owner = await current.frame_element()
                            try:
                                parent_candidate = await self._candidate(current.parent_frame, owner)
                                chain.insert(0, parent_candidate['selector'])
                                candidate['positional'] |= parent_candidate['positional']
                            finally:
                                await owner.dispose()
                            current = current.parent_frame
                        scope = await locate_scope(page, chain, lambda: 10000)
                        if not await scope.locator(candidate['selector']).evaluate('(el,t)=>el===t', element):
                            raise NodeFailure('INSPECTION_PAGE_CHANGED', '目标已变化')
                        metadata = await element.evaluate("el=>({tag:el.tagName.toLowerCase(),text:(el.textContent||'').slice(0,200)})")
                        if self.pending != item['requestId'] or self.revisions[item['pageId']] != item['pageRevision']:
                            return
                        item.update(state='selected', result={**candidate, **metadata, 'framePath': chain})
                        self.pending = None
                        return
                    finally:
                        await handle.dispose()
        except Exception:  # noqa: BLE001 -- normalize browser failures at the process boundary.
            item.update(state='failed', error='页面已变化或无法生成唯一定位，请重新拾取')
            self.pending = None
