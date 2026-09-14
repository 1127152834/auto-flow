// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ExcelApi } from './excel-api'
import { DataCommandNotAccepted, DataCommandUncertain } from './data-command'
import { useExcelInspection } from './use-excel-inspection'

beforeEach(() => {
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key), clear: () => values.clear() })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
const selection = { selectionToken: 'selected', displayName: '资料.xlsx', kind: 'excelInput' as const, expiresAt: '2099-01-01T00:00:00Z' }
const operation = { projectId: 'p', operationId: 'op', idempotencyKey: 'key', kind: 'inspectExcel', status: 'accepted', resource: { type: 'project', projectId: 'p' } }
function setup() {
  const inspect = vi.fn(), lookupInspection = vi.fn(), chooseInput = vi.fn(async () => selection)
  return { inspect, lookupInspection, chooseInput, api: { inspect, lookupInspection } as Pick<ExcelApi, 'inspect' | 'lookupInspection'> }
}
describe('inspection session recovery', () => {
  it('does not submit anything after cancelling file selection', async () => {
    const h = setup(); const chooseInput = vi.fn(async () => null)
    const hook = renderHook(() => useExcelInspection({ ...h, chooseInput, scopeKey: 'w:p', contextKey: 'instance1', active: true }))
    await act(async () => { await hook.result.current.choose() })
    expect(h.inspect).not.toHaveBeenCalled()
    expect(hook.result.current.selection).toBeNull()
  })
  it('keeps the original identity on unknown results and only resends after lookup proves not accepted', async () => {
    const h = setup(); h.inspect.mockRejectedValueOnce(new DataCommandUncertain(new Error('network')))
    const hook = renderHook(() => useExcelInspection({ ...h, scopeKey: 'w:p', contextKey: 'instance1', active: true }))
    await act(async () => { await hook.result.current.choose() })
    await act(async () => { await hook.result.current.submit() })
    const originalKey = h.inspect.mock.calls[0][1]
    expect(hook.result.current.phase).toBe('unknown')
    await act(async () => { await hook.result.current.submit() })
    expect(h.inspect).toHaveBeenCalledTimes(1)
    h.lookupInspection.mockRejectedValueOnce(new DataCommandNotAccepted())
    await act(async () => { await hook.result.current.refresh() })
    expect(hook.result.current.phase).toBe('notAccepted')
    h.inspect.mockResolvedValueOnce({ ...operation, idempotencyKey: originalKey })
    await act(async () => { await hook.result.current.submit() })
    expect(h.inspect.mock.calls[1].slice(0, 2)).toEqual(['selected', originalKey])
  })
  it('restores an accepted operation across instance changes without selecting or reading the file again', async () => {
    const h = setup(); h.inspect.mockImplementation(async (_token, key) => ({ ...operation, idempotencyKey: key }))
    h.lookupInspection.mockImplementation(async key => ({ ...operation, idempotencyKey: key }))
    const hook = renderHook(({ contextKey }) => useExcelInspection({ ...h, scopeKey: 'w:p', contextKey, active: true }), { initialProps: { contextKey: 'one' } })
    await act(async () => { await hook.result.current.choose() })
    await act(async () => { await hook.result.current.submit() })
    hook.rerender({ contextKey: 'two' })
    await waitFor(() => expect(h.lookupInspection).toHaveBeenCalled())
    expect(h.chooseInput).toHaveBeenCalledTimes(1)
    expect(h.inspect).toHaveBeenCalledTimes(1)
  })
  it('ignores a late file selection after the project changes', async () => {
    const h = setup(); let resolve!: (value: typeof selection) => void
    h.chooseInput.mockImplementation(() => new Promise(done => { resolve = done }))
    const hook = renderHook(({ scopeKey }) => useExcelInspection({ ...h, scopeKey, contextKey: 'one', active: true }), { initialProps: { scopeKey: 'w:p' } })
    let pending!: Promise<void>
    act(() => { pending = hook.result.current.choose() })
    hook.rerender({ scopeKey: 'w:other' })
    await act(async () => { resolve(selection); await pending })
    expect(hook.result.current.selection).toBeNull()
  })
})

it('persists identity before a command completes and ignores its late response after closing', async () => {
  const h = setup(); let finish!: (value: unknown) => void
  h.inspect.mockImplementation(() => new Promise(resolve => { finish = resolve }))
  const hook = renderHook(({ active }) => useExcelInspection({ ...h, scopeKey: 'w:p', contextKey: 'one', active }), { initialProps: { active: true } })
  await act(async () => { await hook.result.current.choose() })
  let submitting!: Promise<void>
  act(() => { submitting = hook.result.current.submit() })
  const originalKey = h.inspect.mock.calls[0][1]
  expect(JSON.parse(window.localStorage.getItem('autoflow:excel-inspection:w:p')!).key).toBe(originalKey)
  hook.rerender({ active: false })
  await act(async () => { finish({ ...operation, idempotencyKey: originalKey }); await submitting })
  expect(hook.result.current.operation).toBeNull()
  h.lookupInspection.mockResolvedValue({ ...operation, idempotencyKey: originalKey })
  hook.rerender({ active: true })
  await waitFor(() => expect(hook.result.current.operation?.operationId).toBe('op'))
  expect(h.inspect).toHaveBeenCalledTimes(1)
})

it('prevents a synchronous double submission while state has not rendered yet', async () => {
  const h = setup(); h.inspect.mockImplementation(async (_token, key) => ({ ...operation, idempotencyKey: key }))
  const hook = renderHook(() => useExcelInspection({ ...h, scopeKey: 'w:p', contextKey: 'one', active: true }))
  await act(async () => { await hook.result.current.choose() })
  await act(async () => { await Promise.all([hook.result.current.submit(), hook.result.current.submit()]) })
  expect(h.inspect).toHaveBeenCalledTimes(1)
})
