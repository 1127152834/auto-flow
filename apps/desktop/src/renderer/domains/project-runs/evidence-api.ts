import type { StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'
type Schema = components['schemas']; const encode = encodeURIComponent
export type LogFilter = { level?: 'debug' | 'info' | 'warning' | 'error'; nodeId?: string; query?: string }
export function createTaskEvidenceApi(client: StreamingApiClient, projectId: string, taskId: string) {
  const base = `/api/v1/projects/${encode(projectId)}/tasks/${encode(taskId)}`
  return {
    attempts: (page: number, signal?: AbortSignal) => client.request<Schema['NodeAttemptPage']>(`${base}/node-attempts?page=${page}&pageSize=100`, { signal }),
    logs: (afterSequence: number, filter: LogFilter, signal?: AbortSignal) => client.request<Schema['RunLogPage']>(`${base}/logs?afterSequence=${afterSequence}${filter.level ? `&level=${filter.level}` : ''}${filter.nodeId ? `&nodeId=${encode(filter.nodeId)}` : ''}${filter.query ? `&query=${encode(filter.query)}` : ''}&pageSize=200`, { signal }),
    outputs: (page: number, signal?: AbortSignal) => client.request<Schema['RunOutputPage']>(`${base}/outputs?page=${page}&pageSize=100`, { signal }),
  }
}
