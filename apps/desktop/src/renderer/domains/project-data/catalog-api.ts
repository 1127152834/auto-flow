import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'
import { DataCommandUncertain } from './api'

type Schema = components['schemas']
export type CatalogScope = Pick<Schema['DataFieldRef'], 'projectId' | 'tableId' | 'datasetGeneration'>
export type FieldDefinition = Schema['DataFieldView']
export type StatusDefinition = Schema['DataStatusView']
type Operation = Schema['ProjectOperationView']
type Action = 'create' | 'update'
const encode = encodeURIComponent
const definitive = (error: unknown) => error instanceof ApiClientError && error.status >= 400 && error.status < 500 && error.status !== 408
const mismatch = () => new Error('操作结果与当前字段或状态请求不一致')

export function createDataCatalogApi(client: StreamingApiClient, context: CatalogScope) {
  const scope = { ...context }
  const project = `/api/v1/projects/${encode(scope.projectId)}`
  const base = `${project}/tables/${encode(scope.tableId)}`
  const sameScope = (ref: Schema['DataFieldRef']) => ref.projectId === scope.projectId && ref.tableId === scope.tableId && ref.datasetGeneration === scope.datasetGeneration

  async function command<T>(path: string, method: 'POST' | 'PATCH', body: object, key: string, kind: Operation['kind'], resume: boolean, projectResult: (operation: Operation) => T): Promise<T> {
    const originalBody = structuredClone(body)
    const submit = () => client.request<T>(path, { method, headers: { 'Idempotency-Key': key }, body: originalBody })
    if (!resume) {
      try { return await submit() } catch (error) {
        if (definitive(error) || (error instanceof DOMException && error.name === 'AbortError')) throw error
      }
    }
    try {
      const operation = await client.request<Operation>(`${project}/operations/by-idempotency-key/${encode(key)}`)
      if (operation.projectId !== scope.projectId || operation.idempotencyKey !== key || operation.kind !== kind || operation.status !== 'succeeded') throw mismatch()
      return projectResult(operation)
    } catch (error) {
      if (!(error instanceof ApiClientError && error.status === 404 && error.code === 'OPERATION_NOT_FOUND')) throw new DataCommandUncertain(error)
      try { return await submit() } catch (retryError) {
        if (definitive(retryError)) throw retryError
        throw new DataCommandUncertain(retryError)
      }
    }
  }

  function fieldResult(action: Action, fieldId?: string) {
    return ({ resource, result }: Operation): Schema['DataFieldMutationView'] => {
      if (resource.type !== 'field' || !sameScope(resource.fieldRef) || (fieldId !== undefined && resource.fieldRef.fieldId !== fieldId)
        || !result || !('field' in result) || result.action !== action || !sameScope(result.field.ref) || result.field.ref.fieldId !== resource.fieldRef.fieldId) throw mismatch()
      return { field: result.field, tableRevision: result.tableRevision }
    }
  }

  function statusResult(action: Action, statusId?: string) {
    return ({ resource, result }: Operation): StatusDefinition => {
      if (resource.type !== 'status' || resource.projectId !== scope.projectId || resource.tableId !== scope.tableId || (statusId !== undefined && resource.statusId !== statusId)
        || !result || !('status' in result) || result.action !== action || result.status.statusId !== resource.statusId) throw mismatch()
      return result.status
    }
  }

  return {
    fields: (signal?: AbortSignal) => client.request<Schema['DataFieldDirectory']>(`${base}/fields`, { signal }),
    statuses: (signal?: AbortSignal) => client.request<Schema['DataStatusDirectory']>(`${base}/statuses`, { signal }),
    previewField: (fieldId: string, definition: Schema['DataFieldWrite'], signal?: AbortSignal) => client.request<Schema['FieldImpactReport']>(`${project}/mutation-impact`, {
      method: 'POST', signal, body: { action: 'updateField', target: { type: 'field', fieldRef: { ...scope, fieldId } }, change: definition },
    }),
    createField: (body: Schema['DataFieldCreate'], key: string, resume = false) => command(`${base}/fields`, 'POST', body, key, 'mutateField', resume, fieldResult('create')),
    updateField: (fieldId: string, body: Schema['DataFieldPatch'], key: string, resume = false) => command(`${base}/fields/${encode(fieldId)}`, 'PATCH', body, key, 'mutateField', resume, fieldResult('update', fieldId)),
    createStatus: (body: Schema['DataStatusCreate'], key: string, resume = false) => command(`${base}/statuses`, 'POST', body, key, 'mutateStatus', resume, statusResult('create')),
    updateStatus: (statusId: string, body: Schema['DataStatusPatch'], key: string, resume = false) => command(`${base}/statuses/${encode(statusId)}`, 'PATCH', body, key, 'mutateStatus', resume, statusResult('update', statusId)),
  }
}
