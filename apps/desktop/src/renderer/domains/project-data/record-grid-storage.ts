import { z } from 'zod'
import type { components } from '../../shared/api/generated'
import type { GridDraftRow } from './record-grid-draft'
import { MAX_GRID_BYTES } from './record-grid-draft'

export type GridScope = { workspaceId: string; projectId: string; tableId: string; datasetGeneration: string }
export type GridPending = { key: string; payload: components['schemas']['DataRecordBatchCreate'] }
export type GridSession = {
  schemaVersion: 1; scope: GridScope; tableRevision: number; rows: GridDraftRow[]
  pending: GridPending | null; receipt: { key: string; clientRowIds: string[] } | null
}
const uuid = z.string().uuid(), revision = z.number().int().min(1).max(Number.MAX_SAFE_INTEGER)
const scalar = z.union([z.string(), z.number().finite().refine(n => !Number.isInteger(n) || Number.isSafeInteger(n)), z.boolean(), z.null(), z.object({ kind: z.literal('date'), precision: z.enum(['date', 'datetime']), value: z.string(), offset: z.string().nullable() }).strict()])
const cell = z.object({ presence: z.enum(['missing', 'null', 'value']), text: z.string(), boolean: z.boolean(), precision: z.enum(['date', 'datetime']), offset: z.string(), inputError: z.string().optional() }).strict()
const row = z.object({ clientRowId: uuid, cells: z.record(uuid, cell) }).strict()
const payload = z.object({ datasetGeneration: uuid, expectedTableRevision: revision, rows: z.array(z.object({ clientRowId: uuid, values: z.array(z.object({ fieldId: uuid, value: scalar }).strict()) }).strict()).min(1).max(100) }).strict()
const sessionSchema = z.object({
  schemaVersion: z.literal(1), scope: z.object({ workspaceId: z.string().min(1), projectId: uuid, tableId: uuid, datasetGeneration: uuid }).strict(),
  tableRevision: revision, rows: z.array(row).max(100), pending: z.object({ key: uuid, payload }).strict().nullable(),
  receipt: z.object({ key: uuid, clientRowIds: z.array(uuid).min(1).max(100) }).strict().nullable(),
}).strict()
const key = (scope: GridScope) => `autoflow:record-grid:v1:${[scope.workspaceId, scope.projectId, scope.tableId].map(encodeURIComponent).join(':')}`
function checked(value: unknown): GridSession {
  const parsed = sessionSchema.safeParse(value)
  if (!parsed.success) throw new Error('草稿格式无效，未执行保存请求')
  const data = parsed.data
  const ids = new Set(data.rows.map(r => r.clientRowId))
  if (ids.size !== data.rows.length) throw new Error('草稿行身份重复')
  if (data.pending) {
    const pending = data.pending.payload
    if (pending.datasetGeneration !== data.scope.datasetGeneration || pending.expectedTableRevision !== data.tableRevision
      || new Set(pending.rows.map(r => r.clientRowId)).size !== pending.rows.length
      || pending.rows.some(r => !ids.has(r.clientRowId) || new Set(r.values.map(c => c.fieldId)).size !== r.values.length)
      || new TextEncoder().encode(JSON.stringify(pending)).length > MAX_GRID_BYTES) throw new Error('草稿待核验请求与上下文不一致')
  }
  if (data.receipt && (!data.pending || data.receipt.key !== data.pending.key
    || data.receipt.clientRowIds.length !== data.pending.payload.rows.length
    || new Set(data.receipt.clientRowIds).size !== data.receipt.clientRowIds.length
    || data.receipt.clientRowIds.some(id => !data.pending!.payload.rows.some(r => r.clientRowId === id)))) throw new Error('草稿保存收据无效')
  return data
}
export function writeGridSession(storage: Pick<Storage, 'setItem'>, value: GridSession): void {
  const data = checked(value), text = JSON.stringify(data)
  if (new TextEncoder().encode(text).length > 3 * MAX_GRID_BYTES) throw new Error('草稿过大，未能持久保存')
  storage.setItem(key(data.scope), text)
}
export function readGridSession(storage: Pick<Storage, 'getItem'>, scope: GridScope, allowPreviousGeneration = false): GridSession | null {
  const text = storage.getItem(key(scope))
  if (text === null) return null
  let value: unknown
  try {
    if (new TextEncoder().encode(text).length > 3 * MAX_GRID_BYTES) throw new Error('size')
    value = JSON.parse(text)
  } catch { throw new Error('草稿无法读取，未执行保存请求') }
  const data = checked(value)
  if (data.scope.workspaceId !== scope.workspaceId || data.scope.projectId !== scope.projectId || data.scope.tableId !== scope.tableId) throw new Error('草稿不属于当前数据表')
  if (!allowPreviousGeneration && data.scope.datasetGeneration !== scope.datasetGeneration) throw new Error('数据已更新，旧草稿已隔离；请在原上下文核验待完成操作')
  return data
}
