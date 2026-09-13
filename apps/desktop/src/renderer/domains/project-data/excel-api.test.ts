import { describe, expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../../shared/api/client'
import { ApiClientError } from '../../shared/api/client'
import { createExcelApi } from './excel-api'

const operation = { projectId: 'p', idempotencyKey: 'key', kind: 'inspectExcel', operationId: 'op', status: 'accepted', resource: { type: 'project', projectId: 'p' } }
function setup() {
  const request = vi.fn()
  const fileRequest = vi.fn()
  const api = createExcelApi({ request } as unknown as StreamingApiClient, { request: fileRequest }, 'p')
  return { request, fileRequest, api }
}
describe('Excel operation transport', () => {
  it('uses the controlled file transport only for submission', async () => {
    const { api, fileRequest, request } = setup()
    fileRequest.mockResolvedValue({ operation })
    expect(await api.inspect('selection', 'key', () => true)).toEqual(operation)
    expect(fileRequest).toHaveBeenCalledWith('/api/v1/projects/p/table-imports/excel/inspect', expect.objectContaining({ body: { selectionToken: 'selection' }, headers: { 'Idempotency-Key': 'key' } }))
    expect(request).not.toHaveBeenCalled()
  })
  it('recovers accepted inspection without requiring a still valid file grant', async () => {
    const { api, fileRequest, request } = setup()
    fileRequest.mockRejectedValue(new TypeError('lost response'))
    request.mockResolvedValue(operation)
    expect(await api.inspect('selection', 'key', () => true)).toEqual(operation)
    expect(request).toHaveBeenCalledWith('/api/v1/projects/p/operations/by-idempotency-key/key', undefined)
    expect(fileRequest).toHaveBeenCalledTimes(1)
  })
  it('does not exchange the selected token again when the result is unknown', async () => {
    const { api, fileRequest, request } = setup()
    fileRequest.mockRejectedValue(new TypeError('lost'))
    request.mockRejectedValue(new ApiClientError('missing', 404, 'OPERATION_NOT_FOUND'))
    await expect(api.inspect('selection', 'key', () => true)).rejects.toThrow('原操作尚未接受')
    expect(fileRequest).toHaveBeenCalledTimes(1)
  })
  it('rejects an inspection whose resource belongs to a different project', async () => {
    const { api, request } = setup()
    request.mockResolvedValue({ ...operation, resource: { type: 'project', projectId: 'other' } })
    await expect(api.lookupInspection('key', () => true)).rejects.toThrow('当前项目不一致')
  })
})

it('keeps new imports in the project scope until their table is published', async () => {
  const { api, fileRequest, request } = setup()
  fileRequest.mockResolvedValue({ operation: { ...operation, kind: 'importExcel' } })
  const payload = { name: '资料', description: '', inspectionId: 'inspection', fingerprint: 'hash', sheetId: '1', identity: { mode: 'system' as const }, mapping: [] }
  expect((await api.startImport(payload, 'key', () => true)).status).toBe('accepted')
  expect(fileRequest).toHaveBeenCalledTimes(1)
  request.mockResolvedValue({ ...operation, kind: 'importExcel', status: 'succeeded', result: null })
  await expect(api.lookupImport('key', () => true)).rejects.toThrow('导入结果')
})

it('rejects a replacement result from another table and previews impact without a file proof', async () => {
  const { api, request, fileRequest } = setup()
  request.mockResolvedValueOnce({ ...operation, kind: 'importExcel', resource: { type: 'table', projectId: 'p', tableId: 'other' } })
  await expect(api.lookupImport('key', () => true, 'table')).rejects.toThrow('当前数据表不一致')
  request.mockResolvedValueOnce({ recordCount: 20 })
  expect(await api.replaceImpact('table')).toEqual({ recordCount: 20 })
  expect(fileRequest).not.toHaveBeenCalled()
})

it('submits exports with file proof and recovers them through the ordinary operation transport', async () => {
  const { api, request, fileRequest } = setup()
  const exported = { ...operation, kind: 'exportXlsx', resource: { type: 'table', projectId: 'p', tableId: 't' } }
  fileRequest.mockResolvedValue({ operation: exported })
  const body = { selectionToken: 'selection', datasetGeneration: 'g', scope: 'filter' as const, filter: 'x', orderBy: 'name', fieldIds: ['f'], includeStatus: true }
  expect(await api.startExport('t', body, 'key', () => true)).toEqual(exported)
  expect(fileRequest).toHaveBeenCalledWith('/api/v1/projects/p/tables/t/exports/xlsx', expect.objectContaining({ body, headers: { 'Idempotency-Key': 'key' } }))
  request.mockResolvedValue(exported)
  expect(await api.lookupExport('t', 'key', () => true)).toEqual(exported)
})

it('binds reconciliation results to the original export operation', async () => {
  const { api, request, fileRequest } = setup()
  request.mockResolvedValue({ ...operation, idempotencyKey: 'reconcile-key', kind: 'reconcileOperation', status: 'succeeded', resource: { type: 'table', projectId: 'p', tableId: 't' }, result: { targetOperationId: 'other', status: 'failed' } })
  await expect(api.lookupReconcile('t', 'export-op', 2, 'reconcile-key', () => true)).rejects.toThrow('原导出操作不一致')
  expect(fileRequest).not.toHaveBeenCalled()
})

it('rejects nonterminal reconciliation evidence for the wrong target or revision', async () => {
  const { api, request } = setup()
  const base = { ...operation, idempotencyKey: 'reconcile-key', kind: 'reconcileOperation', status: 'running', resource: { type: 'table', projectId: 'p', tableId: 't' } }
  request.mockResolvedValueOnce({ ...base, result: { targetOperationId: 'other', status: 'reconciling', expectedTargetRevision: 3 } })
  await expect(api.lookupReconcile('t', 'export-op', 2, 'reconcile-key', () => true)).rejects.toThrow('原导出操作不一致')
  request.mockResolvedValueOnce({ ...base, result: { targetOperationId: 'export-op', status: 'reconciling', expectedTargetRevision: 9 } })
  await expect(api.lookupReconcile('t', 'export-op', 2, 'reconcile-key', () => true)).rejects.toThrow('原导出版本不一致')
})
