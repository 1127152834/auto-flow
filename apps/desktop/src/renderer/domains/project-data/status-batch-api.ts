import type { StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'
import { DataCommandUncertain } from './data-command'
import { createOperationCommand } from './operation-command'

type Schema = components['schemas']
export type StatusBatchRequest = Schema['RecordStatusBatchRequest']
export type StatusBatchPreview = Schema['RecordStatusBatchPreview']
export type ProjectOperation = Schema['ProjectOperationView']

export function createStatusBatchApi(client: StreamingApiClient, projectId: string, tableId: string) {
  const base = `/api/v1/projects/${encodeURIComponent(projectId)}/tables/${encodeURIComponent(tableId)}/record-status-batches`
  const command = createOperationCommand(client, projectId)
  const inTable = (operation: ProjectOperation) => {
    const resource = operation.resource
    if (resource.type !== 'table' || resource.projectId !== projectId || resource.tableId !== tableId) throw new Error('批量状态操作与当前数据表不一致')
    return operation
  }
  const guardedLookup = async (key: string, current: () => boolean) => {
    if (!current()) throw new DataCommandUncertain(new Error('当前上下文已失效'))
    const result = await command.lookup(key, 'setRecordStatuses', current)
    if (!current()) throw new DataCommandUncertain(new Error('当前上下文已失效'))
    return inTable(result)
  }
  const lookupCancel = async (key: string, current: () => boolean) => {
    if (!current()) throw new DataCommandUncertain(new Error('当前上下文已失效'))
    const result = await command.lookup(key, 'cancelRecordStatuses', current)
    if (!current()) throw new DataCommandUncertain(new Error('当前上下文已失效'))
    return inTable(result)
  }
  return {
    preview: (body: StatusBatchRequest, signal?: AbortSignal) => client.request<StatusBatchPreview>(`${base}/preview`, { method: 'POST', body: structuredClone(body), signal }),
    start: async (body: StatusBatchRequest, key: string, current: () => boolean) => inTable(await command.submit(base, body, key, 'setRecordStatuses', current)),
    lookup: guardedLookup,
    lookupCancel,
    cancel: async (operationId: string, expectedOperationRevision: number, key: string, current: () => boolean) => inTable(await command.submit(
      `${base}/${encodeURIComponent(operationId)}/cancel`, { expectedOperationRevision }, key, 'cancelRecordStatuses', current,
    )),
  }
}

export type StatusBatchApi = ReturnType<typeof createStatusBatchApi>
