// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { DataCommandNotAccepted, DataCommandUncertain } from './data-command'
import { useExcelExport } from './use-excel-export'

const body = { selectionToken: 'selection', datasetGeneration: 'g', scope: 'filter' as const, filter: 'q', orderBy: 'name', fieldIds: ['f1'], includeStatus: true }
const operation = { operationId: 'o', operationKey: 'k', kind: 'exportXlsx', status: 'accepted', statusRevision: 2, resource: { type: 'table', projectId: 'p', tableId: 't' }, operationRevision: 1, result: null, error: null, createdAt: '', updatedAt: '' }
beforeEach(() => { const values = new Map<string, string>(); vi.stubGlobal('localStorage', { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key), clear: () => values.clear() }) }); afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('persists the frozen request before POST and unknown only queries its original key', async () => {
  const api = { startExport: vi.fn().mockRejectedValue(new DataCommandUncertain('lost')), lookupExport: vi.fn().mockResolvedValue(operation), reconcileExport: vi.fn(), lookupReconcile: vi.fn() }
  const hook = renderHook(() => useExcelExport({ api: api as never, tableId: 't', scopeKey: 'w:p:t:s', contextKey: 'i1', active: true }))
  await act(() => hook.result.current.submit(body)); const saved = JSON.parse(localStorage.getItem('autoflow:excel-export:w:p:t:s')!)
  expect(saved.export.body).toEqual(body)
  await act(() => hook.result.current.submit({ ...body, fieldIds: ['other'] })); expect(api.startExport).toHaveBeenCalledTimes(1)
  await act(() => hook.result.current.refresh()); expect(api.lookupExport).toHaveBeenCalledWith('t', saved.export.key, expect.any(Function))
})

it('reopens across instances and confirmed absence retries the same frozen body and key', async () => {
  localStorage.setItem('autoflow:excel-export:w:p:t:s', JSON.stringify({ export: { key: 'original', tableId: 't', body } }))
  const api = { startExport: vi.fn().mockResolvedValue(operation), lookupExport: vi.fn().mockRejectedValue(new DataCommandNotAccepted()), reconcileExport: vi.fn(), lookupReconcile: vi.fn() }
  const hook = renderHook(() => useExcelExport({ api: api as never, tableId: 't', scopeKey: 'w:p:t:s', contextKey: 'i2', active: true }))
  await waitFor(() => expect(hook.result.current.phase).toBe('notAccepted')); await act(() => hook.result.current.retry())
  expect(api.startExport).toHaveBeenCalledWith('t', body, 'original', expect.any(Function))
})

it('isolates late responses and only completes successful exports', async () => {
  let resolve!: (value: unknown) => void
  const api = { startExport: vi.fn(() => new Promise(value => { resolve = value })), lookupExport: vi.fn(), reconcileExport: vi.fn(), lookupReconcile: vi.fn() }, complete = vi.fn()
  const hook = renderHook(({ contextKey }) => useExcelExport({ api: api as never, tableId: 't', scopeKey: 'w:p:t:s', contextKey, active: true, onCompleted: complete }), { initialProps: { contextKey: 'i1' } })
  act(() => { void hook.result.current.submit(body) }); hook.rerender({ contextKey: 'i2' }); await act(async () => resolve({ ...operation, status: 'succeeded' }))
  expect(complete).not.toHaveBeenCalled(); expect(hook.result.current.operation).toBeFalsy()
})

it('starts reconciliation with a durable key and then verifies the original export', async () => {
  const reconciling = { ...operation, status: 'reconciling' }, reconciled = { ...operation, operationId: 'r', kind: 'reconcileOperation', status: 'succeeded', resource: { type: 'table', projectId: 'p', tableId: 't' }, result: { targetOperationId: 'o', status: 'succeeded' } }
  const api = { startExport: vi.fn().mockResolvedValue(reconciling), lookupExport: vi.fn().mockResolvedValue({ ...operation, status: 'succeeded', result: { filename: 'x.xlsx', sha256: 'h', recordCount: 1 } }), reconcileExport: vi.fn().mockResolvedValue(reconciled), lookupReconcile: vi.fn() }
  const hook = renderHook(() => useExcelExport({ api: api as never, tableId: 't', scopeKey: 'w:p:t:s', contextKey: 'i1', active: true }))
  await act(() => hook.result.current.submit(body)); await act(() => hook.result.current.reconcile())
  expect(api.reconcileExport).toHaveBeenCalledWith('t', 'o', 2, expect.any(String), expect.any(Function)); expect(api.lookupExport).toHaveBeenCalledWith('t', expect.any(String), expect.any(Function))
})

it('consumes a delivered success and lets a later session export again', async () => {
  const succeeded = { ...operation, status: 'succeeded', result: { filename: 'x.xlsx', sha256: 'h', recordCount: 1 } }, api = { startExport: vi.fn().mockResolvedValue(succeeded), lookupExport: vi.fn(), reconcileExport: vi.fn(), lookupReconcile: vi.fn() }, complete = vi.fn()
  const hook = renderHook(({ active }) => useExcelExport({ api: api as never, tableId: 't', scopeKey: 'w:p:t:s', contextKey: 'i1', active, onCompleted: complete }), { initialProps: { active: true } })
  await act(() => hook.result.current.submit(body)); const firstKey = api.startExport.mock.calls[0][2]; expect(localStorage.getItem('autoflow:excel-export:w:p:t:s')).toBeNull()
  hook.rerender({ active: false }); hook.rerender({ active: true }); await act(() => hook.result.current.submit({ ...body, selectionToken: 'second' })); expect(api.startExport.mock.calls[1][2]).not.toBe(firstKey)
})
