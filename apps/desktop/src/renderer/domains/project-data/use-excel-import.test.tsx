import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { DataCommandNotAccepted, DataCommandUncertain } from './data-command'
import { useExcelImport } from './use-excel-import'

const request = { name: '客户', description: '', inspectionId: 'i', fingerprint: 'f', sheetId: 's', mapping: [], identity: { mode: 'system' as const } }
const operation = { operationId: 'o', operationKey: 'k', kind: 'importExcel', status: 'accepted', resource: { type: 'project', projectId: 'p' }, operationRevision: 1, result: null, error: null, createdAt: '', updatedAt: '' }
beforeEach(() => { const values = new Map<string, string>(); vi.stubGlobal('localStorage', { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key), clear: () => values.clear() }) }); afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

it('persists identity before POST and uncertain only looks up the original key', async () => {
  const api = { startImport: vi.fn().mockRejectedValue(new DataCommandUncertain('unknown')), replace: vi.fn(), lookupImport: vi.fn().mockResolvedValue(operation) }
  const hook = renderHook(() => useExcelImport({ api: api as never, scopeKey: 'w:p', contextKey: 'i1', active: true }))
  await act(() => hook.result.current.submit({ mode: 'create', request }))
  const saved = JSON.parse(localStorage.getItem('autoflow:excel-import:w:p')!)
  expect(saved.key).toBeTruthy(); expect(saved.body.request).toEqual(request)
  await act(() => hook.result.current.submit({ mode: 'create', request: { ...request, name: 'other' } }))
  expect(api.startImport).toHaveBeenCalledTimes(1)
  await act(() => hook.result.current.refresh())
  expect(api.lookupImport).toHaveBeenCalledWith(saved.key, expect.any(Function), undefined)
})

it('reopens on a new instance by lookup and retries confirmed 404 with the same key/body', async () => {
  localStorage.setItem('autoflow:excel-import:w:p', JSON.stringify({ key: 'original', body: { mode: 'create', request } }))
  const api = { startImport: vi.fn().mockResolvedValue(operation), replace: vi.fn(), lookupImport: vi.fn().mockRejectedValue(new DataCommandNotAccepted()) }
  const hook = renderHook(({ contextKey }) => useExcelImport({ api: api as never, scopeKey: 'w:p', contextKey, active: true }), { initialProps: { contextKey: 'i2' } })
  await waitFor(() => expect(hook.result.current.phase).toBe('notAccepted'))
  await act(() => hook.result.current.submit(hook.result.current.pending!.body))
  expect(api.startImport).toHaveBeenCalledWith(request, 'original', expect.any(Function))
})

it('ignores a late response after context revocation', async () => {
  let resolve!: (value: unknown) => void
  const api = { startImport: vi.fn(() => new Promise(value => { resolve = value })), replace: vi.fn(), lookupImport: vi.fn() }
  const completed = vi.fn(), hook = renderHook(({ contextKey }) => useExcelImport({ api: api as never, scopeKey: 'w:p', contextKey, active: true, onCompleted: completed }), { initialProps: { contextKey: 'i1' } })
  act(() => { void hook.result.current.submit({ mode: 'create', request }) })
  hook.rerender({ contextKey: 'i2' })
  await act(async () => resolve({ ...operation, status: 'succeeded' }))
  expect(completed).not.toHaveBeenCalled(); expect(hook.result.current.operation).toBeFalsy()
})

it('keeps unknown identity through reset but releases a definitively rejected request for editing', async () => {
  const uncertain = { startImport: vi.fn().mockRejectedValue(new DataCommandUncertain('offline')), replace: vi.fn(), lookupImport: vi.fn() }
  const first = renderHook(() => useExcelImport({ api: uncertain as never, scopeKey: 'w:p', contextKey: 'i1', active: true }))
  await act(() => first.result.current.submit({ mode: 'create', request })); act(() => first.result.current.reset())
  expect(first.result.current.pending?.key).toBeTruthy(); expect(localStorage.getItem('autoflow:excel-import:w:p')).not.toBeNull()
  first.unmount(); localStorage.clear()
  const rejected = { startImport: vi.fn().mockRejectedValue(new Error('字段验证失败')), replace: vi.fn(), lookupImport: vi.fn() }
  const second = renderHook(() => useExcelImport({ api: rejected as never, scopeKey: 'w:p', contextKey: 'i1', active: true }))
  await act(() => second.result.current.submit({ mode: 'create', request }))
  expect(second.result.current.pending).toBeNull(); expect(second.result.current.phase).toBe('ready'); expect(second.result.current.error).toBe('字段验证失败')
})

it('acknowledges delivered success so a later session can import a second file', async () => {
  const succeeded = { ...operation, status: 'succeeded', result: { importedRecordCount: 1, table: { projectId: 'p', tableId: 't1' } } }, api = { startImport: vi.fn().mockResolvedValue(succeeded), replace: vi.fn(), lookupImport: vi.fn() }, completed = vi.fn()
  const hook = renderHook(({ active }) => useExcelImport({ api: api as never, scopeKey: 'w:p', contextKey: 'i1', active, onCompleted: completed }), { initialProps: { active: true } })
  await act(() => hook.result.current.submit({ mode: 'create', request })); const firstKey = api.startImport.mock.calls[0][1]
  expect(completed).toHaveBeenCalledOnce(); expect(localStorage.getItem('autoflow:excel-import:w:p')).toBeNull()
  hook.rerender({ active: false }); hook.rerender({ active: true }); await act(() => hook.result.current.submit({ mode: 'create', request: { ...request, name: '第二张表' } }))
  expect(api.startImport).toHaveBeenCalledTimes(2); expect(api.startImport.mock.calls[1][1]).not.toBe(firstKey)
})

it('keeps terminal failure evidence until the user starts a new import', async () => {
  const failed = { ...operation, status: 'failed', error: { message: '写入失败' } }, api = { startImport: vi.fn().mockResolvedValueOnce(failed).mockResolvedValueOnce(operation), replace: vi.fn(), lookupImport: vi.fn() }
  const hook = renderHook(() => useExcelImport({ api: api as never, scopeKey: 'w:p', contextKey: 'i1', active: true }))
  await act(() => hook.result.current.submit({ mode: 'create', request })); expect(hook.result.current.operation?.status).toBe('failed'); expect(localStorage.getItem('autoflow:excel-import:w:p')).not.toBeNull()
  act(() => hook.result.current.reset()); expect(hook.result.current.operation).toBeNull(); await act(() => hook.result.current.submit({ mode: 'create', request: { ...request, name: '修正后' } })); expect(api.startImport).toHaveBeenCalledTimes(2)
})
// @vitest-environment jsdom
