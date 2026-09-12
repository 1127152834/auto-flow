import type { StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'
import type { CatalogScope } from './catalog-api'
import { createDataCommand } from './data-command'

type Schema = components['schemas']
export type DataRecord = Schema['DataRecordView']
export type RecordKey = Schema['DataRecordKey']
export type RecordListQuery = { filter?: unknown; orderBy?: unknown[]; page?: number; pageSize?: number }
const encode = encodeURIComponent
function base64url(value: string): string {
  // TextEncoder otherwise replaces lone surrogates and silently changes identity.
  for (const character of value) {
    const point = character.codePointAt(0)!
    if (point >= 0xd800 && point <= 0xdfff) throw new Error('记录键或查询包含无效 Unicode 字符')
  }
  const bytes = new TextEncoder().encode(value)
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '')
}

export function createRecordsApi(client: StreamingApiClient, context: CatalogScope) {
  const scope = { ...context }
  const base = `/api/v1/projects/${encode(scope.projectId)}/tables/${encode(scope.tableId)}/records`
  const command = createDataCommand(client, scope.projectId)
  const path = (key: RecordKey) => `${base}/${base64url(key.value)}`
  const sameScope = (ref: Schema['DataRecordRef']) => ref.projectId === scope.projectId && ref.tableId === scope.tableId && ref.datasetGeneration === scope.datasetGeneration
  const sameKey = (a: RecordKey, b: RecordKey) => a.type === b.type && a.value === b.value
  function result(key?: RecordKey) {
    return (operation: Schema['ProjectOperationView']): DataRecord => {
      const { resource, result: snapshot } = operation
      if (resource.type !== 'record' || !sameScope(resource.recordRef) || (key && !sameKey(resource.recordRef.recordKey, key))
        || !snapshot || !('ref' in snapshot) || !sameScope(snapshot.ref) || !sameKey(snapshot.ref.recordKey, resource.recordRef.recordKey)) throw new Error('操作结果与当前记录请求不一致')
      return snapshot
    }
  }
  return {
    list: (query: RecordListQuery = {}, signal?: AbortSignal) => {
      const params = new URLSearchParams({ datasetGeneration: scope.datasetGeneration, page: String(query.page ?? 1), pageSize: String(query.pageSize ?? 50) })
      if (query.filter !== undefined) params.set('filter', base64url(JSON.stringify(query.filter)))
      if (query.orderBy !== undefined) params.set('orderBy', base64url(JSON.stringify(query.orderBy)))
      return client.request<Schema['DataRecordPage']>(`${base}?${params}`, { signal })
    },
    get: (key: RecordKey, signal?: AbortSignal) => client.request<DataRecord>(`${path(key)}?datasetGeneration=${encode(scope.datasetGeneration)}&recordKeyType=${encode(key.type)}`, { signal }),
    create: (body: Omit<Schema['DataRecordCreate'], 'datasetGeneration'>, key: string, resume = false) => command(base, 'POST', { ...body, datasetGeneration: scope.datasetGeneration }, key, 'createRecord', resume, result()),
    update: (recordKey: RecordKey, body: Omit<Schema['DataRecordPatch'], 'datasetGeneration' | 'recordKeyType'>, key: string, resume = false) => command(path(recordKey), 'PATCH', { ...body, datasetGeneration: scope.datasetGeneration, recordKeyType: recordKey.type }, key, 'updateRecord', resume, result({ ...recordKey })),
    setStatus: (recordKey: RecordKey, body: Omit<Schema['DataRecordStatusWrite'], 'datasetGeneration' | 'recordKeyType'>, key: string, resume = false) => command(`${path(recordKey)}/status`, 'PUT', { ...body, datasetGeneration: scope.datasetGeneration, recordKeyType: recordKey.type }, key, 'setRecordStatus', resume, result({ ...recordKey })),
  }
}
