import { renderHook, waitFor } from '@testing-library/react'
import { createElement, StrictMode, type ReactNode } from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import { runQueryKeys, useBatchCommand } from './hooks'
const values = new Map<string, string>()
beforeEach(() => { vi.stubGlobal('localStorage', { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key) }); vi.stubGlobal('crypto', { randomUUID: () => 'same-key' }) })
afterEach(() => { values.clear(); vi.unstubAllGlobals() })
const client = (request: StreamingApiClient['request']): StreamingApiClient => ({ request, stream: vi.fn(), health: vi.fn() })
const batch = { batchId: 'b', projectId: 'p', automationId: 'a', startOperationId: 'op', status: 'accepted', statusRevision: 1, managementRevision: 1, requestedCount: 1, createdTaskCount: 0, activeTaskCount: 0, createdAt: '' }
const startScope = { type: 'start' as const, automationId: 'a' }
const stopScope = { type: 'stop' as const, batchId: 'b' }
it('scopes every query key by workspace instance project and filters', () => { expect(runQueryKeys.batches('w', 'i', 'p', { page: 1, pageSize: 50, sort: '-createdAt' })).toEqual(['w', 'i', 'project-runs', 'p', 'batches', { page: 1, pageSize: 50, sort: '-createdAt' }]) })
it('persists one user-generated key and fences a late response after instance change', async () => {
  let resolve!: (value: unknown) => void; const response = new Promise(resolveValue => { resolve = resolveValue }), request = vi.fn(() => response) as StreamingApiClient['request'], completed = vi.fn()
  const props = { client: client(request), workspaceKey: 'w', instanceId: 'i1', projectId: 'p', scope: startScope, disabled: false, readOnly: false, onCompleted: completed }
  const hook = renderHook(({ instanceId }) => useBatchCommand({ ...props, instanceId }), { initialProps: { instanceId: 'i1' } })
  void hook.result.current.start('a', { expectedAutomationRevision: 1, parameters: {} }); await waitFor(() => expect(request).toHaveBeenCalledTimes(1)); hook.rerender({ instanceId: 'i2' })
  resolve({ operation: { projectId: 'p', idempotencyKey: 'same-key', kind: 'startBatch', status: 'succeeded', resource: { type: 'batch', projectId: 'p', batchId: 'b' }, result: { batch } } }); await response; await Promise.resolve()
  expect(completed).not.toHaveBeenCalled(); expect([...values.values()][0]).toContain('same-key')
})
it('remains active in StrictMode and reloads pending state when workspace changes', async () => {
  const request = vi.fn().mockResolvedValue({ operation: { projectId: 'p', idempotencyKey: 'same-key', kind: 'startBatch', status: 'succeeded', resource: { type: 'batch', projectId: 'p', batchId: 'b' }, result: { batch } } }) as StreamingApiClient['request']
  const completed = vi.fn()
  const base = { client: client(request), instanceId: 'i', projectId: 'p', scope: startScope, disabled: false, readOnly: false, onCompleted: completed }
  const wrapper = ({ children }: { children: ReactNode }) => createElement(StrictMode, null, children)
  const hook = renderHook(({ workspaceKey }) => useBatchCommand({ ...base, workspaceKey }), { initialProps: { workspaceKey: 'one' }, wrapper })
  void hook.result.current.start('a', { expectedAutomationRevision: 1, parameters: {} }); await waitFor(() => expect(completed).toHaveBeenCalledTimes(1))
  values.set('autoflow:project-run-command:["two","p","start","a"]', '{broken')
  hook.rerender({ workspaceKey: 'two' }); await waitFor(() => expect(hook.result.current.error).toContain('无法读取'))
  void hook.result.current.start('a', { expectedAutomationRevision: 1, parameters: {} }); expect(request).toHaveBeenCalledTimes(1)
  hook.result.current.discardInvalidRecovery(); await waitFor(() => expect(hook.result.current.error).toBeUndefined()); expect(values.has('autoflow:project-run-command:["two","p","start","a"]')).toBe(false)
})
it('allows a stop cleanup in read-only mode while blocking a new start', async () => {
  const operation = { operationId: 'op', projectId: 'p', idempotencyKey: 'same-key', kind: 'stopBatch', status: 'running', statusRevision: 1, resource: { type: 'batch', projectId: 'p', batchId: 'b' }, result: null }
  const request = vi.fn().mockResolvedValue({ operation }) as StreamingApiClient['request']
  const hook = renderHook(() => useBatchCommand({ client: client(request), workspaceKey: 'w', instanceId: 'i', projectId: 'p', scope: stopScope, disabled: false, readOnly: true, onCompleted: vi.fn() }))
  void hook.result.current.start('a', { expectedAutomationRevision: 1, parameters: {} }); expect(request).not.toHaveBeenCalled()
  void hook.result.current.stop('b', { expectedStatusRevision: 1, reason: '清理' }); await waitFor(() => expect(request).toHaveBeenCalledTimes(1)); expect(hook.result.current.recovering).toBe(true)
})
it('contains unavailable recovery storage and allows explicit cleanup', async () => {
  const removeItem = vi.fn()
  vi.stubGlobal('localStorage', { getItem: () => { throw new DOMException('denied', 'SecurityError') }, setItem: vi.fn(), removeItem })
  const hook = renderHook(() => useBatchCommand({ client: client(vi.fn()), workspaceKey: 'w', instanceId: 'i', projectId: 'p', scope: startScope, disabled: false, readOnly: false, onCompleted: vi.fn() }))
  expect(hook.result.current.error).toContain('无法读取')
  hook.result.current.discardInvalidRecovery(); await waitFor(() => expect(hook.result.current.error).toBeUndefined()); expect(removeItem).toHaveBeenCalledTimes(1)
})
it('keeps the original recovery envelope locked when lookup returns 401', async () => {
  const key = 'autoflow:project-run-command:["w","p","stop","b"]'
  values.set(key, JSON.stringify({ type: 'stop', batchId: 'b', body: { expectedStatusRevision: 1, reason: '停止' }, key: 'original' }))
  const request = vi.fn().mockRejectedValue(new ApiClientError('unauthorized', 401, 'UNAUTHORIZED')) as StreamingApiClient['request']
  const stableClient = client(request)
  const hook = renderHook(() => useBatchCommand({ client: stableClient, workspaceKey: 'w', instanceId: 'i', projectId: 'p', scope: stopScope, disabled: false, readOnly: false, onCompleted: vi.fn() }))
  await waitFor(() => expect(hook.result.current.recovering).toBe(true)); void hook.result.current.lookup(); await waitFor(() => expect(hook.result.current.error).toContain('尚未确认'))
  expect(values.get(key)).toContain('original'); hook.result.current.acknowledgeAccepted(); expect(values.get(key)).toContain('original'); expect(hook.result.current.locked()).toBe(true)
})
it('only unlocks an accepted stop after explicit acknowledgement, then permits force stop', async () => {
  const operation = (kind: 'stopBatch' | 'forceStopBatch') => ({ operationId: `op-${kind}`, projectId: 'p', idempotencyKey: 'same-key', kind, status: 'running', statusRevision: 1, resource: { type: 'batch', projectId: 'p', batchId: 'b' }, result: null })
  const request = vi.fn().mockResolvedValueOnce({ operation: operation('stopBatch') }).mockResolvedValueOnce({ operation: operation('forceStopBatch') }) as StreamingApiClient['request']
  const accepted = vi.fn(), hook = renderHook(() => useBatchCommand({ client: client(request), workspaceKey: 'w', instanceId: 'i', projectId: 'p', scope: stopScope, disabled: false, readOnly: false, onAccepted: accepted, onCompleted: vi.fn() }))
  void hook.result.current.stop('b', { expectedStatusRevision: 1, reason: '停止' }); await waitFor(() => expect(accepted).toHaveBeenCalledTimes(1))
  void hook.result.current.forceStop('b', { expectedStatusRevision: 2, reason: '强停' }); expect(request).toHaveBeenCalledTimes(1)
  hook.result.current.acknowledgeAccepted(); await waitFor(() => expect(hook.result.current.locked()).toBe(false))
  void hook.result.current.forceStop('b', { expectedStatusRevision: 2, reason: '强停' }); await waitFor(() => expect(request).toHaveBeenCalledTimes(2))
})
it('allows synchronous acknowledgement inside the verified accepted callback', async () => {
  const operation = { operationId: 'op', projectId: 'p', idempotencyKey: 'same-key', kind: 'stopBatch', status: 'running', statusRevision: 1, resource: { type: 'batch', projectId: 'p', batchId: 'b' }, result: null }
  const request = vi.fn().mockResolvedValue({ operation }) as StreamingApiClient['request']
  let acknowledge = () => {}
  const hook = renderHook(() => useBatchCommand({ client: client(request), workspaceKey: 'w', instanceId: 'i', projectId: 'p', scope: stopScope, disabled: false, readOnly: false, onAccepted: () => acknowledge(), onCompleted: vi.fn() }))
  acknowledge = () => hook.result.current.acknowledgeAccepted()
  void hook.result.current.stop('b', { expectedStatusRevision: 1, reason: '停止' })
  await waitFor(() => expect(hook.result.current.busy).toBe(false))
  expect(hook.result.current.locked()).toBe(false)
  expect(values.size).toBe(0)
})
it('persists commands under target-scoped recovery keys', async () => {
  const request = vi.fn().mockRejectedValue(new Error('network')) as StreamingApiClient['request']
  const start = renderHook(() => useBatchCommand({ client: client(request), workspaceKey: 'w', instanceId: 'i', projectId: 'p', scope: startScope, disabled: false, readOnly: false, onCompleted: vi.fn() }))
  void start.result.current.start('a', { expectedAutomationRevision: 1, parameters: {} })
  await waitFor(() => expect(values.has('autoflow:project-run-command:["w","p","start","a"]')).toBe(true))
  start.unmount()
  const stop = renderHook(() => useBatchCommand({ client: client(request), workspaceKey: 'w', instanceId: 'i', projectId: 'p', scope: stopScope, disabled: false, readOnly: false, onCompleted: vi.fn() }))
  void stop.result.current.stop('b', { expectedStatusRevision: 1, reason: '停止' })
  await waitFor(() => expect(values.has('autoflow:project-run-command:["w","p","stop","b"]')).toBe(true))
  const forceStop = renderHook(() => useBatchCommand({ client: client(request), workspaceKey: 'w', instanceId: 'i', projectId: 'p', scope: { type: 'stop', batchId: 'b2' }, disabled: false, readOnly: false, onCompleted: vi.fn() }))
  void forceStop.result.current.forceStop('b2', { expectedStatusRevision: 1, reason: '强停' })
  await waitFor(() => expect(values.has('autoflow:project-run-command:["w","p","stop","b2"]')).toBe(true))
  expect(values).toHaveLength(3)
})
