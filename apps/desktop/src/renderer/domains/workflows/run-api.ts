import type { StreamingApiClient } from '../../shared/api/client'
import { parseServerSentEvents } from '../../shared/api/events'
import type { DebugCommand, DebugCommandRead, DebugVariables, RunArtifacts, RunEvent, RunEvents, RunList, RunRead, RunStart } from './run-types'

const path = (id?: string) => `/api/v1/workflows/runs${id ? `/${encodeURIComponent(id)}` : ''}`

export function createWorkflowRunApi(client: StreamingApiClient) {
  return {
    debugCommand: (id: string, body: DebugCommand) => client.request<DebugCommandRead>(`${path(id)}/debug/commands`, { method: 'POST', body }),
    debugCommandStatus: (id: string, commandId: string) => client.request<DebugCommandRead>(`${path(id)}/debug/commands/${encodeURIComponent(commandId)}`),
    variables: (id: string, checkpointId = '', offset = 0, after = 0) => client.request<DebugVariables>(`${path(id)}/debug/variables?${new URLSearchParams({ ...(checkpointId ? { checkpointId } : {}), offset: String(offset), after: String(after), limit: '50' })}`),
    logs: (id: string, filters: Record<string, string>, afterSeq = 0, tail = false) => client.request<RunEvents>(`${path(id)}/logs?${new URLSearchParams({ ...filters, tail: String(tail), afterSeq: String(afterSeq), limit: '200' })}`),
    async export(id: string, kind: string, throughSeq: number, filters: Record<string, string> = {}) {
      const response = await client.stream(`${path(id)}/export?${new URLSearchParams({ ...filters, kind, throughSeq: String(throughSeq) })}`)
      return response.blob()
    },
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
    artifacts: (runId: string, after = 0, nodeId = '', executionId = '') => client.request<RunArtifacts>(`${path(runId)}/artifacts?${new URLSearchParams({ after: String(after), limit: '50', ...(nodeId ? { nodeId } : {}), ...(executionId ? { executionId } : {}) })}`),
    async artifact(runId: string, artifactId: string, signal?: AbortSignal) {
      const response = await client.stream(`${path(runId)}/artifacts/${encodeURIComponent(artifactId)}`, { signal })
      return response.blob()
    },
  }
}
export type WorkflowRunApi = ReturnType<typeof createWorkflowRunApi>
