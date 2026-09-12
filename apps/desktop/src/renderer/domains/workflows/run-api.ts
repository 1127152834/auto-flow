import type { StreamingApiClient } from '../../shared/api/client'
import { parseServerSentEvents } from '../../shared/api/events'
import type { RunEvent, RunEvents, RunList, RunRead, RunStart } from './run-types'

const path = (id?: string) => `/api/v1/workflows/runs${id ? `/${encodeURIComponent(id)}` : ''}`

export function createWorkflowRunApi(client: StreamingApiClient) {
  return {
    list: (offset = 0) => client.request<RunList>(`${path()}?offset=${offset}&limit=20`),
    get: (id: string) => client.request<RunRead>(path(id)),
    start: (body: RunStart) => client.request<RunRead>(path(), { method: 'POST', body }),
    stop: (id: string) => client.request<RunRead>(`${path(id)}/stop`, { method: 'POST', timeoutMs: 120_000 }),
    events: (id: string, afterSeq: number) => client.request<RunEvents>(`${path(id)}/events?afterSeq=${afterSeq}&limit=200`),
    async watch(id: string, afterSeq: number, signal: AbortSignal, onEvent: (event: RunEvent) => void) {
      const response = await client.stream(`${path(id)}/stream?afterSeq=${afterSeq}`, { signal, headers: { accept: 'text/event-stream' } })
      if (!response.body) throw new Error('运行日志连接没有返回内容')
      for await (const event of parseServerSentEvents(response.body)) {
        if (signal.aborted) return
        if (event.event === 'run_event') onEvent(JSON.parse(event.data) as RunEvent)
      }
    },
    async artifact(runId: string, artifactId: string, signal?: AbortSignal) {
      const response = await client.stream(`${path(runId)}/artifacts/${encodeURIComponent(artifactId)}`, { signal })
      return response.blob()
    },
  }
}
export type WorkflowRunApi = ReturnType<typeof createWorkflowRunApi>
