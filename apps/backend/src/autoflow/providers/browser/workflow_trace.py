"""AutoFlow diagnostic enhancement; observes the existing CloakBrowser context.

Native Playwright tracing captures browser actions/DOM/network. The small index is
versioned independently; sources=True is NOT a claim to capture all website JS.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from time import monotonic
from typing import Any
from uuid import uuid4

from autoflow.infrastructure.filesystem.workflow_trace import TraceArchive

TRACE_MIME = "application/vnd.autoflow.trace+json"
SaveEvidence = Callable[[str, bytes, str], Awaitable[str]]


class WorkflowTrace:
    # ponytail: bounded per-run index; paginate native resources before raising these limits.
    MAX_EVENTS = 2000
    MAX_SNAPSHOTS = 100
    MAX_ARCHIVE = 64 * 1024 * 1024

    def __init__(self, context: Any, save: SaveEvidence, *, enabled: bool = True) -> None:
        self.context, self.save = context, save
        self.enabled = enabled
        self.identity = uuid4().hex
        self.started = monotonic()
        self.events: list[dict[str, Any]] = []
        self.gaps: set[str] = {"网页 JS 源码未单独采集；不保证 Worker 和动态脚本覆盖"}
        self.listeners: list[tuple[Any, str, Any]] = []
        self.pages: dict[int, str] = {}
        self.snapshots = 0
        self.native_started = False
        self.closed = False
        self.archive_id: str | None = None
        self.page_tasks: set[asyncio.Task[Any]] = set()
        self.cdp_sessions: list[Any] = []
        self.error_prefix = f"[autoflow-trace-error:{self.identity}]"

    def _listen(self, target: Any, name: str, callback: Any) -> None:
        target.on(name, callback)
        self.listeners.append((target, name, callback))

    def _record(self, kind: str, **payload: Any) -> dict[str, Any] | None:
        if self.closed:
            return None
        if len(self.events) >= self.MAX_EVENTS:
            self.gaps.add("结构化事件超过 2000 条；后续事件仅可能存在于原始归档")
            return None
        row = {"id": f"{self.identity}:{len(self.events)+1}", "kind": kind,
               "timeMs": round((monotonic()-self.started)*1000),
               "timestamp": datetime.now(UTC).isoformat(), **payload}
        self.events.append(row)
        return row

    def _page(self, page: Any) -> str:
        identity = id(page)
        if identity in self.pages:
            return self.pages[identity]
        page_id = f"page-{len(self.pages)+1}"
        self.pages[identity] = page_id
        if self.enabled:
            task = asyncio.create_task(self._observe_page(page, page_id))
            self.page_tasks.add(task)
            task.add_done_callback(self.page_tasks.discard)
            self._listen(page, "close", lambda *_: self._record("page-closed", pageId=page_id))
        return page_id

    async def _observe_page(self, page: Any, page_id: str) -> None:
        # CloakBrowser 145 suppresses Runtime.consoleAPICalled. Console domain
        # observes messages without replacing page console methods.
        try:
            async with asyncio.timeout(2):
                cdp = await self.context.new_cdp_session(page)
                self.cdp_sessions.append(cdp)
                def console(event: dict[str, Any]) -> None:
                    message = event.get('message', {})
                    text = str(message.get('text', ''))
                    kind = 'console'
                    if text.startswith(self.error_prefix):
                        kind, text = 'exception', text[len(self.error_prefix):]
                    self._record(kind, pageId=page_id, level=message.get('level'),
                                 message=text[:4096], truncated=len(text) > 4096)
                self._listen(cdp, 'Console.messageAdded', console)
                await cdp.send('Console.enable')
        except Exception:  # noqa: BLE001 -- closing pages and unsupported CDP domains.
            self.gaps.add('部分页面的控制台通道不可用')

    def _response(self, response: Any) -> None:
        from .workflow_session import redact_browser_url
        request = response.request
        try:
            frame = request.frame
            page_id = self._page(frame.page)
        except Exception:  # noqa: BLE001 -- service workers have no page frame.
            page_id = None
        self._record("network", pageId=page_id, url=redact_browser_url(response.url),
                     method=request.method, status=response.status, resourceType=request.resource_type,
                     attribution="page-background")

    async def start(self) -> None:
        if not self.enabled:
            self.gaps = {'本次未开启全程追踪，仅保留显式诊断节点证据'}
            return
        try:
            async with asyncio.timeout(3):
                await self.context.tracing.start(screenshots=True, snapshots=True, sources=False)
            self.native_started = True
            # CloakBrowser also suppresses Runtime binding/exception events. A tagged
            # console diagnostic forwards errors without swallowing the page exception.
            script = """(() => {
              const write = console.debug.bind(console);
              const send = value => { try { write(PREFIX + String(value).slice(0, 8192)); } catch {} };
              addEventListener('error', event => send(event.message + ' @ ' + event.filename + ':' + event.lineno), true);
              addEventListener('unhandledrejection', event => { try { send('Unhandled rejection: ' + String(event.reason)); } catch { send('Unhandled rejection (value unavailable)'); } });
            })()""".replace('PREFIX', json.dumps(self.error_prefix))
            await self.context.add_init_script(script)
            self._listen(self.context, "page", self._page)
            self._listen(self.context, "response", self._response)
            for page in self.context.pages:
                self._page(page)
                await page.evaluate(script)
            if self.page_tasks:
                await asyncio.gather(*self.page_tasks)
        except Exception:  # noqa: BLE001 -- diagnostics must not prevent workflow actions.
            self.gaps.add("浏览器追踪启动失败")

    async def execution(self, event: Mapping[str, Any], session: Any) -> None:
        if not self.enabled:
            return
        if event.get("type") not in {"execution:node_start", "execution:node_complete"}:
            return
        row = self._record("execution", nodeId=event.get("nodeId"),
                           executionId=event.get("executionId"), phase=event["type"],
                           success=event.get("success"), durationMs=event.get("duration"),
                           executionContext=event.get("executionContext"))
        if row is None or event["type"] != "execution:node_complete":
            return
        if self.snapshots >= self.MAX_SNAPSHOTS:
            self.gaps.add("独立页面快照超过 100 张；后续快照未单独保存")
            return
        try:
            page = session.current_page()
            row["pageId"] = self._page(page._raw)
            async with asyncio.timeout(2):
                content = await page.screenshot()
                if len(content) > 8 * 1024 * 1024:
                    raise ValueError("snapshot exceeds limit")
                row["snapshotId"] = await self.save(f"trace/{self.identity}/{self.snapshots}.png", content, "image/png")
            self.snapshots += 1
        except Exception:  # noqa: BLE001 -- no automatic retry of the browser action.
            row["snapshotMissing"] = True
            self.gaps.add("部分节点页面快照不可用或超过 2 秒采集预算")

    async def collect(self, kind: str, config: dict[str, Any], metadata: dict[str, Any], session: Any) -> dict[str, Any]:
        if self.closed:
            raise ValueError("TRACE_CLOSED: 追踪已经关闭")
        if kind == 'save_trace_segment':
            if not self.enabled:
                raise ValueError('TRACE_NOT_ENABLED: 本次未开启全程追踪')
            marker = config['startMarker']
            start = next((i for i, row in enumerate(self.events) if row['id'] == marker and row['kind'] == 'mark'), None) if marker else 0
            if start is None:
                raise ValueError('startMarker: 找不到当前会话中的标记实例，请引用标记输出的 id')
            segment_id = uuid4().hex
            payload = {'schemaVersion': 1, 'traceId': self.identity, 'name': config['diagnosticName'],
                       'events': self.events[start:], 'gaps': sorted(self.gaps),
                       'format': 'structured-evidence', 'localOnly': True, **metadata}
            artifact_id = await self.save(f'trace/{self.identity}/segment-{segment_id}.json',
                                         json.dumps(payload, ensure_ascii=False).encode(), 'application/json')
            return {'traceId': self.identity, 'artifactId': artifact_id, 'eventCount': len(payload['events']),
                    'format': 'structured-evidence', 'gaps': sorted(self.gaps)}
        if kind not in {'trace_mark', 'capture_diagnostics'}:
            raise ValueError('TRACE_ACTION_INVALID')
        row = self._record('mark' if kind == 'trace_mark' else 'diagnostic', message=config['diagnosticName'],
                           description=config['description'], correlation=config['correlation'], **metadata)
        if row is None:
            raise ValueError('TRACE_CAPACITY_REACHED: 无法继续登记诊断证据')
        if kind == 'trace_mark':
            return {'id': row['id'], 'traceId': self.identity}
        page = session.active_page() if config['target'] == 'frame' else session.current_page()
        row['pageId'] = self._page(session.current_page()._raw)
        result: dict[str, Any] = {'id': row['id'], 'traceId': self.identity, 'target': config['target'], 'gaps': []}
        for key, mime in [('includeScreenshot', 'image/png'), ('includeDom', 'text/html')]:
            if not config[key]:
                continue
            try:
                async with asyncio.timeout(3):
                    # Screenshots are the top-level viewport even when the DOM target is a frame.
                    content = await session.current_page().screenshot() if key == 'includeScreenshot' else (await page.content()).encode()
                    if len(content) > 8 * 1024 * 1024:
                        raise ValueError('超过 8 MiB')
                    suffix = 'png' if key == 'includeScreenshot' else 'html'
                    artifact = await self.save(f'trace/{self.identity}/diagnostic-{uuid4().hex}.{suffix}', content, mime)
                    row['snapshotId' if key == 'includeScreenshot' else 'domId'] = artifact
                    result['snapshotId' if key == 'includeScreenshot' else 'domId'] = artifact
            except Exception:  # noqa: BLE001 -- report each missing component, no silent substitution.
                result['gaps'].append(f'{key}: 采集失败、超时或超过 8 MiB')
        if config['includeConsole']:
            if not self.enabled:
                result['gaps'].append('includeConsole: 本次未开启全程追踪，没有历史控制台证据')
            result['consoleEvidenceIds'] = [item['id'] for item in self.events if item['kind'] in {'console', 'exception'} and item.get('pageId') == row['pageId']][-100:]
        row['gaps'] = result['gaps']
        return result

    async def finish(self) -> None:
        if self.closed:
            return
        self.closed = True
        for task in self.page_tasks:
            task.cancel()
        if self.page_tasks:
            await asyncio.gather(*self.page_tasks, return_exceptions=True)
        for target, name, callback in self.listeners:
            try:
                target.remove_listener(name, callback)
            except Exception:  # noqa: BLE001,S110 -- page can already be closed.
                pass
        archive = TraceArchive()
        try:
            if self.native_started:
                try:
                    async with asyncio.timeout(5):
                        await self.context.tracing.stop(path=str(archive.path))
                        content = await asyncio.to_thread(archive.read, self.MAX_ARCHIVE)
                        self.archive_id = await self.save(f"trace/{self.identity}/trace.zip", content, "application/zip")
                except Exception:  # noqa: BLE001 -- retain partial index and original run outcome.
                    self.gaps.add("原始追踪归档失败、超时或超过 64 MiB")
            manifest = {"schemaVersion": 1, "traceId": self.identity,
                        "status": "partial" if self.gaps else "saved",
                        "archiveId": self.archive_id, "gaps": sorted(self.gaps),
                        "events": self.events, "localOnly": True}
            await self.save(f"trace/{self.identity}/index.json",
                            json.dumps(manifest, ensure_ascii=False).encode(), TRACE_MIME)
        finally:
            archive.close()
