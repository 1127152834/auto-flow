import { useEffect, useRef } from 'react'
import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import { parseServerSentEvents } from '../../shared/api/events'
import type { components } from '../../shared/api/generated'
type Event = components['schemas']['ProjectRunEventView']
type EventPage = components['schemas']['ProjectRunEventPage']
export type RunEventCursor = { runId: string; sequence: number; terminal: boolean }
const terminalStates = new Set(['succeeded', 'failed', 'cancelled', 'timed_out', 'interrupted'])
const safeStreamFailures = new Set([
  '运行事件补读结果不连续',
  '运行事件存在缺口，正在补读',
  '运行事件身份无效',
  '运行终态不能被旧状态覆盖',
  '运行事件封装不一致',
])
export function advanceRunEvent(current: RunEventCursor, event: Event): RunEventCursor {
  if (event.runId !== current.runId || !Number.isSafeInteger(event.sequence) || event.sequence < 1) throw new Error('运行事件身份无效')
  if (event.sequence <= current.sequence) return current
  if (event.sequence !== current.sequence + 1) throw new Error('运行事件存在缺口，正在补读')
  const terminal = event.kind === 'runStatus' && terminalStates.has(String(event.payload.status))
  if (current.terminal && event.kind === 'runStatus' && !terminal) throw new Error('运行终态不能被旧状态覆盖')
  return { runId: current.runId, sequence: event.sequence, terminal: current.terminal || terminal }
}
function pause(signal: AbortSignal, ms: number) { return new Promise<void>(resolve => { if (signal.aborted) { resolve(); return }; const done = () => { clearTimeout(timer); signal.removeEventListener('abort', done); resolve() }; const timer = setTimeout(done, ms); signal.addEventListener('abort', done, { once: true }) }) }
export async function watchRunEvents(client: StreamingApiClient, options: { projectId: string; taskId: string; runId: string; signal: AbortSignal; onChange(): void; onError?(message?: string): void }) {
  const { signal } = options, path = `/api/v1/projects/${encodeURIComponent(options.projectId)}/tasks/${encodeURIComponent(options.taskId)}/events`
  let cursor: RunEventCursor = { runId: options.runId, sequence: 0, terminal: false }, retry = 0
  const apply = (event: Event) => { const next = advanceRunEvent(cursor, event); if (next !== cursor && !signal.aborted) { cursor = next; options.onChange() } }
  while (!signal.aborted) {
    try {
      // Every connection first repairs the persisted prefix. A snapshot is never used to skip a gap.
      let page: EventPage
      do {
        page = await client.request<EventPage>(`${path}?afterSequence=${cursor.sequence}`, { signal })
        if (signal.aborted) return
        for (const event of page.items) apply(event)
        if (page.afterSequence !== cursor.sequence || page.lastSequence < cursor.sequence || page.hasMore && page.items.length === 0) throw new Error('运行事件补读结果不连续')
      } while (page.hasMore && !signal.aborted)
      options.onError?.(undefined); retry = 0
      if (page.terminal) return
      const response = await client.stream(`${path}/stream?afterSequence=${cursor.sequence}`, { signal, headers: { accept: 'text/event-stream' } })
      if (!response.body) throw new Error('无法读取运行事件连接')
      for await (const frame of parseServerSentEvents(response.body)) {
        if (signal.aborted) return
        const event = JSON.parse(frame.data) as Event
        if (String(event.sequence) !== frame.id || event.kind !== frame.event) throw new Error('运行事件封装不一致')
        apply(event)
      }
      if (cursor.terminal) return
    } catch (error) {
      if (signal.aborted) return
      options.onError?.(error instanceof Error && safeStreamFailures.has(error.message) ? error.message : '运行事件连接中断，正在补读')
      if (error instanceof ApiClientError && [401, 403, 404].includes(error.status)) return
    }
    await pause(signal, Math.min(5000, 1000 * 2 ** retry++))
  }
}
export function useRunEvents(options: { client: StreamingApiClient; workspaceKey: string; instanceId: string; projectId: string; taskId: string; runId?: string; disabled: boolean; onChange(): void; onError?(message?: string): void }) {
  const latest = useRef(options); latest.current = options
  const { client, workspaceKey, instanceId, projectId, taskId, runId, disabled } = options
  useEffect(() => {
    if (disabled || !runId) return
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout> | undefined
    void watchRunEvents(client, { projectId, taskId, runId, signal: controller.signal,
      onChange() { if (timer === undefined) timer = setTimeout(() => { timer = undefined; if (!controller.signal.aborted) latest.current.onChange() }, 100) },
      onError(message) { if (!controller.signal.aborted) latest.current.onError?.(message) },
    })
    return () => { controller.abort(); clearTimeout(timer) }
  }, [client, workspaceKey, instanceId, projectId, taskId, runId, disabled])
}
