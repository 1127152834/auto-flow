import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { DesktopRuntimeContext } from '../../shared/runtime'
import { useDesktopSession } from './useDesktopSession'

const context = (workspaceKey = '/workspace-a', instanceId = 'a'): DesktopRuntimeContext => ({ workspaceKey, sidecar: { state: 'ready', apiVersion: 'v1', port: 43127, baseUrl: 'http://127.0.0.1:43127', token: instanceId, instanceId }, preferences: { zoom: 100, motion: 'system' }, operation: 'idle' })
let changed: (context: DesktopRuntimeContext) => void
const health = (instanceId: string) => Response.json({ status: 'ok', apiVersion: 'v1', instanceId })

beforeEach(() => {
  vi.stubGlobal('autoflow', {
    getRuntimeContext: vi.fn(async () => context()),
    onRuntimeContextChanged: vi.fn((listener: typeof changed) => { changed = listener; return vi.fn() }),
    restartSidecar: vi.fn(async () => context().sidecar),
  })
  vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => health(new Headers(init?.headers).get('x-autoflow-token') ?? 'a')))
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('uses the one runtime snapshot and refreshes its client without resetting a same-workspace session', async () => {
  const view = renderHook(() => useDesktopSession())
  await waitFor(() => expect(view.result.current.status).toBe('connected'))
  const previousClient = view.result.current.session!.client
  act(() => changed(context('/workspace-a', 'replacement')))
  await waitFor(() => expect(view.result.current.session!.instanceId).toBe('replacement'))
  expect(view.result.current.session!.workspaceKey).toBe('/workspace-a')
  expect(view.result.current.session!.client).not.toBe(previousClient)
  expect(view.result.current.workspaceChanging).toBe(false)
})

it('keeps the previous document session locked until the new workspace health check finishes', async () => {
  const view = renderHook(() => useDesktopSession())
  await waitFor(() => expect(view.result.current.status).toBe('connected'))
  let finish!: (response: Response) => void
  vi.mocked(fetch).mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
  act(() => changed(context('/workspace-b', 'b')))
  expect(view.result.current.status).toBe('loading')
  expect(view.result.current.workspaceChanging).toBe(true)
  expect(view.result.current.session!.workspaceKey).toBe('/workspace-a')
  await act(async () => finish(health('b')))
  expect(view.result.current.session!.workspaceKey).toBe('/workspace-b')
  expect(view.result.current.workspaceChanging).toBe(false)
  expect(view.result.current.status).toBe('connected')
})

it('does not restore a stale workspace when an older connection completes after a switch', async () => {
  let finishOld!: (response: Response) => void
  vi.mocked(fetch).mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve }))
  const view = renderHook(() => useDesktopSession())
  await waitFor(() => expect(fetch).toHaveBeenCalledOnce())
  act(() => changed(context('/workspace-b', 'b')))
  await waitFor(() => expect(view.result.current.session?.workspaceKey).toBe('/workspace-b'))
  await act(async () => finishOld(health('a')))
  expect(view.result.current.session!.workspaceKey).toBe('/workspace-b')
  expect(view.result.current.session!.token).toBe('b')
})

it('fails visibly without fabricating a workspace identity when runtime context is unavailable', async () => {
  vi.mocked(window.autoflow.getRuntimeContext).mockRejectedValue(new Error('runtime unavailable'))
  const view = renderHook(() => useDesktopSession())
  await waitFor(() => expect(view.result.current.status).toBe('offline'))
  expect(view.result.current.session).toBeNull()
  expect(view.result.current.message).toBe('runtime unavailable')
  expect(fetch).not.toHaveBeenCalled()
})

it('ordinary recovery reconnects without restarting the sidecar or an active browser run', async () => {
  const view = renderHook(() => useDesktopSession())
  await waitFor(() => expect(view.result.current.status).toBe('connected'))
  await act(async () => view.result.current.reconnect())
  expect(window.autoflow.restartSidecar).not.toHaveBeenCalled()
  expect(view.result.current.status).toBe('connected')
})

it('ignores a delayed polling snapshot after a newer runtime notification connected', async () => {
  let finishOldPoll!: (value: DesktopRuntimeContext) => void
  vi.mocked(window.autoflow.getRuntimeContext)
    .mockResolvedValueOnce(context())
    .mockImplementationOnce(() => new Promise(resolve => { finishOldPoll = resolve }))
  const view = renderHook(() => useDesktopSession())
  await waitFor(() => expect(view.result.current.status).toBe('connected'))
  await waitFor(() => expect(window.autoflow.getRuntimeContext).toHaveBeenCalledTimes(2), { timeout: 2000 })
  act(() => changed(context('/workspace-b', 'b')))
  await waitFor(() => expect(view.result.current.session?.workspaceKey).toBe('/workspace-b'))
  const requests = vi.mocked(fetch).mock.calls.length
  await act(async () => finishOldPoll(context()))
  expect(view.result.current.status).toBe('connected')
  expect(view.result.current.session!.workspaceKey).toBe('/workspace-b')
  expect(view.result.current.workspaceChanging).toBe(false)
  expect(fetch).toHaveBeenCalledTimes(requests)
})
