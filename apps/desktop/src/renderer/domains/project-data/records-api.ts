import type { StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'
import type { CatalogScope } from './catalog-api'
import { createDataCommand, type DataCommandPolicy } from './data-command'
import { encodeRecordKey, encodeUtf8Base64url } from './record-route'

type Schema = components['schemas']
export type DataRecord = Schema['DataRecordView']
export type RecordKey = Schema['DataRecordKey']
export type RecordListQuery = { filter?: unknown; orderBy?: unknown[]; page?: number; pageSize?: number }
const encode = encodeURIComponent
export function createRecordsApi(client: StreamingApiClient, context: CatalogScope) {
  const scope = { projectId: context.projectId, tableId: context.tableId, datasetGeneration: context.datasetGeneration }
  const base = `/api/v1/projects/${encode(scope.projectId)}/tables/${encode(scope.tableId)}/records`
  const command = createDataCommand(client, scope.projectId)
  const path = (key: RecordKey) => `${base}/${encodeRecordKey(key)}`
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
  function deletedRecordResult(key: RecordKey) {
    return ({ resource, result: snapshot }: Schema['ProjectOperationView']): Schema['RecordDeleteResult'] => {
      if (resource.type !== 'record' || !sameScope(resource.recordRef) || !sameKey(resource.recordRef.recordKey, key)
        || !snapshot || !('target' in snapshot) || snapshot.target.type !== 'record' || snapshot.deleted !== true
        || !sameScope(snapshot.target.recordRef) || !sameKey(snapshot.target.recordRef.recordKey, key)) throw new Error('删除结果与原记录请求不一致')
      return snapshot
    }
  }
  return {
    list: (query: RecordListQuery = {}, signal?: AbortSignal) => {
      const params = new URLSearchParams({ datasetGeneration: scope.datasetGeneration, page: String(query.page ?? 1), pageSize: String(query.pageSize ?? 50) })
      if (query.filter !== undefined) params.set('filter', encodeUtf8Base64url(JSON.stringify(query.filter)))
      if (query.orderBy !== undefined) params.set('orderBy', encodeUtf8Base64url(JSON.stringify(query.orderBy)))
      return client.request<Schema['DataRecordPage']>(`${base}?${params}`, { signal })
    },
    get: (key: RecordKey, signal?: AbortSignal) => {
      return client.request<DataRecord>(`${path(key)}?datasetGeneration=${encode(scope.datasetGeneration)}&recordKeyType=${encode(key.type)}`, { signal }).then(record => {
      if (!sameScope(record.ref) || !sameKey(record.ref.recordKey, key)) throw new Error('记录响应与当前地址不一致')
      return record
      })
    },
    previewDelete: (recordKey: RecordKey, signal?: AbortSignal) => client.request<Schema['DeletionImpactReport']>(`/api/v1/projects/${encode(scope.projectId)}/mutation-impact`, {
      method: 'POST', signal, body: { action: 'deleteRecord', target: { type: 'record', recordRef: { ...scope, recordKey: { ...recordKey } } } },
    }),
    createBatch: (body: Omit<Schema['DataRecordBatchCreate'], 'datasetGeneration'>, key: string, resume = false, policy?: DataCommandPolicy) => {
      const expectedIds = new Set(body.rows.map(row => row.clientRowId))
      return command(`${base}/batch`, 'POST', { ...body, datasetGeneration: scope.datasetGeneration }, key, 'createRecords', resume, operation => {
        const { resource, result: value } = operation
        if (resource.type !== 'table' || resource.projectId !== scope.projectId || resource.tableId !== scope.tableId
          || !value || !('records' in value) || value.records.length !== expectedIds.size || expectedIds.size !== body.rows.length
          || new Set(value.records.map(row => row.clientRowId)).size !== expectedIds.size
          || value.records.some(row => !expectedIds.has(row.clientRowId) || !sameScope(row.record.ref))) throw new Error('批量保存结果与原草稿不一致')
        return value
      }, { ...policy, acceptedResponse: true, retryIfNotAccepted: false })
    },
    create: (body: Omit<Schema['DataRecordCreate'], 'datasetGeneration'>, key: string, resume = false, policy?: DataCommandPolicy) => command(base, 'POST', { ...body, datasetGeneration: scope.datasetGeneration }, key, 'createRecord', resume, result(), policy),
    update: (recordKey: RecordKey, body: Omit<Schema['DataRecordPatch'], 'datasetGeneration' | 'recordKeyType'>, key: string, resume = false, policy?: DataCommandPolicy) => command(path(recordKey), 'PATCH', { ...body, datasetGeneration: scope.datasetGeneration, recordKeyType: recordKey.type }, key, 'updateRecord', resume, result({ ...recordKey }), policy),
    setStatus: (recordKey: RecordKey, body: Omit<Schema['DataRecordStatusWrite'], 'datasetGeneration' | 'recordKeyType'>, key: string, resume = false, policy?: DataCommandPolicy) => command(`${path(recordKey)}/status`, 'PUT', { ...body, datasetGeneration: scope.datasetGeneration, recordKeyType: recordKey.type }, key, 'setRecordStatus', resume, result({ ...recordKey }), policy),
    delete: (recordKey: RecordKey, body: Omit<Schema['RecordDelete'], 'datasetGeneration' | 'recordKeyType'>, key: string, resume = false, policy?: DataCommandPolicy) => command(path(recordKey), 'DELETE', { ...body, datasetGeneration: scope.datasetGeneration, recordKeyType: recordKey.type }, key, 'deleteRecord', resume, deletedRecordResult({ ...recordKey }), { ...policy, acceptedResponse: true }),
  }
}
