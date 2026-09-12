import type { StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'

type Schema = components['schemas']
export type DataTable = Schema['DataTableView']
export type TableCreate = Omit<Schema['DataTableCreate'], 'sourceKind'>
export type TablePatch = Schema['DataTablePatch']
export type DirectoryQuery = { query: string; page: number; pageSize: number; sort: 'name' | '-name' | 'updatedAt' | '-updatedAt'; sourceKind?: DataTable['sourceKind'] }

import { createDataCommand } from './data-command'
export { DataCommandUncertain } from './data-command'
const encode = encodeURIComponent

export function createProjectDataApi(client: StreamingApiClient, projectId: string) {
  const base = `/api/v1/projects/${encode(projectId)}/tables`
  const execute = createDataCommand(client, projectId)
  function command(kind: 'createTable' | 'updateTable', body: TableCreate | TablePatch, key: string, tableId?: string, resume = false): Promise<DataTable> {
    return execute(tableId ? `${base}/${encode(tableId)}` : base, tableId ? 'PATCH' : 'POST', body, key, kind, resume, operation => {
      const { resource, result } = operation
      if (resource.type !== 'table' || resource.projectId !== projectId || (tableId !== undefined && resource.tableId !== tableId)
        || !result || !('tableId' in result) || result.tableId !== resource.tableId || result.projectId !== projectId) {
        throw new Error('操作结果与当前数据表保存请求不一致')
      }
      return result
    })
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
