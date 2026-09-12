import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'

type Schema = components['schemas']
export type DataTable = Schema['DataTableView']
export type TableCreate = Omit<Schema['DataTableCreate'], 'sourceKind'>
export type TablePatch = Schema['DataTablePatch']
export type DirectoryQuery = { query: string; page: number; pageSize: number; sort: 'name' | '-name' | 'updatedAt' | '-updatedAt'; sourceKind?: DataTable['sourceKind'] }

export class DataCommandUncertain extends Error {
  constructor(readonly cause: unknown) {
    super('上次保存结果尚未确认，请先核对结果。')
    this.name = 'DataCommandUncertain'
  }
}
const encode = encodeURIComponent
const definitive = (error: unknown) => error instanceof ApiClientError && error.status >= 400 && error.status < 500 && error.status !== 408

export function createProjectDataApi(client: StreamingApiClient, projectId: string) {
  const base = `/api/v1/projects/${encode(projectId)}/tables`
  async function command(kind: 'createTable' | 'updateTable', body: TableCreate | TablePatch, key: string, tableId?: string, resume = false): Promise<DataTable> {
    const submit = () => client.request<DataTable>(tableId ? `${base}/${encode(tableId)}` : base, {
      method: tableId ? 'PATCH' : 'POST', headers: { 'Idempotency-Key': key }, body,
    })
    if (!resume) {
      try { return await submit() } catch (error) {
        if (definitive(error) || (error instanceof DOMException && error.name === 'AbortError')) throw error
      }
    }
    try {
      const operation = await client.request<Schema['ProjectOperationView']>(`/api/v1/projects/${encode(projectId)}/operations/by-idempotency-key/${encode(key)}`)
      const { resource, result } = operation
      if (operation.idempotencyKey !== key || operation.kind !== kind || operation.status !== 'succeeded'
        || resource.type !== 'table' || resource.projectId !== projectId || (tableId !== undefined && resource.tableId !== tableId)
        || !result || !('tableId' in result) || result.tableId !== resource.tableId || result.projectId !== projectId) {
        throw new Error('操作结果与当前数据表保存请求不一致')
      }
      return result
    } catch (error) {
      if (!(error instanceof ApiClientError && error.status === 404 && error.code === 'OPERATION_NOT_FOUND')) throw new DataCommandUncertain(error)
      try { return await submit() } catch (retryError) {
        if (definitive(retryError)) throw retryError
        throw new DataCommandUncertain(retryError)
      }
    }
  }
  return {
    list: (query: DirectoryQuery, signal?: AbortSignal) => {
      const source = query.sourceKind ? `&sourceKind=${encode(query.sourceKind)}` : ''
      return client.request<Schema['DataTablePage']>(`${base}?q=${encode(query.query)}&page=${query.page}&pageSize=${query.pageSize}&sort=${encode(query.sort)}${source}`, { signal })
    },
    get: (tableId: string, signal?: AbortSignal) => client.request<DataTable>(`${base}/${encode(tableId)}`, { signal }),
    create: (body: TableCreate, key: string) => command('createTable', body, key),
    patch: (tableId: string, body: TablePatch, key: string) => command('updateTable', body, key, tableId),
    resumeCreate: (body: TableCreate, key: string) => command('createTable', body, key, undefined, true),
    resumePatch: (tableId: string, body: TablePatch, key: string) => command('updateTable', body, key, tableId, true),
  }
}
