import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import { emptyAutomationForm } from './form-schema'
import { useAutomationCommand } from './use-automation-command'

beforeEach(() => { const values = new Map<string,string>(); vi.stubGlobal('localStorage', { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => { values.set(key, value) }, removeItem: (key: string) => { values.delete(key) } }) })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
const body = { ...emptyAutomationForm('workflow'), name: '资料整理' }
const saved = { ...body, automationId: 'automation', projectId: 'project', managementRevision: 1 }
const client = (request: StreamingApiClient['request']): StreamingApiClient => ({ request, health: vi.fn(), stream: vi.fn() })

it('keeps the original command across reconnect and recovers without resubmitting', async () => {
  let resolve!: (value: unknown) => void
  const request = vi.fn().mockImplementationOnce(() => new Promise(done => { resolve = done }))
  const oldClient = client(request), onSaved = vi.fn()
  const { result, rerender } = renderHook(props => useAutomationCommand(props), { initialProps: { client: oldClient, instanceId: 'old', projectId: 'project', workspaceKey: 'workspace', disabled: false, readOnly: false, onSaved } })
  let execution!: Promise<void>
  act(() => { execution = result.current.submit(body) })
  const key = request.mock.calls[0][1].headers['Idempotency-Key']
  const lookup = vi.fn().mockResolvedValue({ projectId: 'project', kind: 'createAutomation', idempotencyKey: key, status: 'succeeded', resource: { type: 'automation', projectId: 'project', automationId: 'automation' }, result: saved })
  rerender({ client: client(lookup), instanceId: 'new', projectId: 'project', workspaceKey: 'workspace', disabled: false, readOnly: false, onSaved })
  await act(async () => { resolve(saved); await execution })
  expect(onSaved).not.toHaveBeenCalled()
  expect(result.current.recovering).toBe(true)
  await act(async () => result.current.lookup())
  expect(lookup).toHaveBeenCalledWith(`/api/v1/projects/project/operations/by-idempotency-key/${key}`)
  expect(onSaved).toHaveBeenCalledWith(saved, key)
  expect(result.current.locked()).toBe(false)
})

it('requires explicit retry after authoritative absence and reuses frozen body and key', async () => {
  const request = vi.fn().mockRejectedValueOnce(new TypeError('断线')).mockRejectedValueOnce(new ApiClientError('未接受', 404, 'OPERATION_NOT_FOUND')).mockResolvedValueOnce(saved)
  const clientValue = client(request)
  const { result } = renderHook(() => useAutomationCommand({ client: clientValue, instanceId: 'i', projectId: 'project', workspaceKey: 'workspace', disabled: false, readOnly: false, onSaved: vi.fn() }))
  const candidate = structuredClone(body)
  await act(async () => result.current.submit(candidate))
  candidate.name = '提交后修改'
  expect(request).toHaveBeenCalledTimes(2)
  expect(result.current.notAccepted).toBe(true)
  await act(async () => result.current.retry())
  expect(request.mock.calls[2]).toEqual(request.mock.calls[0])
})

it('retains conflicts for user correction and never sends when the workspace is switching', async () => {
  const request = vi.fn().mockRejectedValue(new ApiClientError('资料已修改', 409, 'REVISION_CONFLICT', { fields: { name: '名称冲突' } }))
  const clientValue = client(request)
  const { result, rerender } = renderHook(props => useAutomationCommand(props), { initialProps: { client: clientValue, instanceId: 'i', projectId: 'project', workspaceKey: 'workspace', disabled: false, readOnly: false, onSaved: vi.fn() } })
  await act(async () => result.current.submit({ ...body, expectedManagementRevision: 1 }, 'automation'))
  expect(result.current.conflict).toBe(true)
  expect(result.current.fields.name).toBe('名称冲突')
  expect(result.current.locked()).toBe(false)
  rerender({ client: clientValue, instanceId: 'i', projectId: 'project', workspaceKey: 'workspace', disabled: true, readOnly: false, onSaved: vi.fn() })
  await act(async () => result.current.submit(body))
  expect(request).toHaveBeenCalledTimes(1)
})

it('restores an unknown command after remount and queries its exact identity in read-only mode', async () => {
  const request = vi.fn().mockRejectedValue(new TypeError('断线'))
  const firstClient = client(request)
  const first = renderHook(() => useAutomationCommand({ client: firstClient, workspaceKey: 'workspace', instanceId: 'one', projectId: 'project', disabled: false, readOnly: false, onSaved: vi.fn() }))
  await act(async () => first.result.current.submit(body))
  const key = request.mock.calls[0][1].headers['Idempotency-Key']
  first.unmount()
  const onSaved = vi.fn(), lookup = vi.fn().mockResolvedValue({ projectId: 'project', kind: 'createAutomation', idempotencyKey: key, status: 'succeeded', resource: { type: 'automation', projectId: 'project', automationId: 'automation' }, result: saved })
  const secondClient = client(lookup)
  const second = renderHook(() => useAutomationCommand({ client: secondClient, workspaceKey: 'workspace', instanceId: 'two', projectId: 'project', disabled: false, readOnly: true, onSaved }))
  expect(second.result.current.restoredCommand?.body).toEqual(body)
  expect(second.result.current.recovering).toBe(true)
  await act(async () => second.result.current.lookup())
  expect(onSaved).toHaveBeenCalledWith(saved, key)
  expect(lookup).toHaveBeenCalledExactlyOnceWith(`/api/v1/projects/project/operations/by-idempotency-key/${key}`)
})

it('does not submit if the recovery envelope cannot be saved', async () => {
  const request = vi.fn(), clientValue = client(request)
  const { result } = renderHook(() => useAutomationCommand({ client: clientValue, workspaceKey: 'workspace', instanceId: 'one', projectId: 'project', disabled: false, readOnly: false, onSaved: vi.fn() }))
  vi.spyOn(localStorage, 'setItem').mockImplementation(() => { throw new Error('storage full') })
  await act(async () => result.current.submit(body))
  expect(request).not.toHaveBeenCalled()
  expect(result.current.error).toContain('本次未提交')
})
