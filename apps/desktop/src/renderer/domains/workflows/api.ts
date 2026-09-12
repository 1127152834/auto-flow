import type { StreamingApiClient } from '../../shared/api/client'
import type { WorkflowCatalog, WorkflowContent, WorkflowList, WorkflowRead } from './types'

export function createWorkflowApi(client: Pick<StreamingApiClient, 'request'>) {
  return {
    catalog: () => client.request<WorkflowCatalog>('/api/v1/workflows/node-catalog'),
    list: () => client.request<WorkflowList>('/api/v1/workflows'),
    get: (id: string) => client.request<WorkflowRead>(`/api/v1/workflows/${encodeURIComponent(id)}`),
    create: (content: WorkflowContent) => client.request<WorkflowRead>('/api/v1/workflows', { method: 'POST', body: content }),
    save: (content: WorkflowContent, expectedRevision: number) => client.request<WorkflowRead>(`/api/v1/workflows/${encodeURIComponent(content.document.id)}`, { method: 'PUT', body: { ...content, expectedRevision } }),
  }
}
export type WorkflowApi = ReturnType<typeof createWorkflowApi>
