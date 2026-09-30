import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider, focusManager } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { devices, environment, profile, fixtureSession, images, allocations, runs } from './prototype-fixtures'
import { ResourceBoard } from '../components/ResourceBoard'
import { CreateInstances } from '../components/CreateInstances'
import { DeviceConsole } from '../components/DeviceConsole'
import type { BatchRequest } from '../fleet-api'
import { ApiClientError } from '../../../shared/api/client'
const mocks = vi.hoisted(() => ({ instanceId: 'instance', client: { request: vi.fn(), stream: vi.fn() } }))
vi.mock('../../../app/ApiProvider', () => ({ useApi: () => ({ client: mocks.client, instanceId: mocks.instanceId }) }))
vi.mock('../components/AndroidVideo', () => ({ AndroidVideo: () => <canvas aria-label="安卓触控画面" /> }))
import { AndroidPage } from '../pages/AndroidPage'
const noop = vi.fn()
afterEach(cleanup)
beforeEach(() => {
  vi.clearAllMocks()
  mocks.instanceId = 'instance'
  mocks.client.request.mockImplementation(async (path: string, init?: { method?: string }) => {
    if (path.startsWith('/api/v1/android/management/operations?')) return { items: [], total: 0, nextCursor: null }
    if (path.endsWith('/cleanup/resources')) return { items: [] }
    if (path === '/api/v1/android/management/devices?limit=50') return { items: [{ deviceId: devices[0].deviceId, revision: devices[0].generation, name: devices[0].name, runtimeState: 'ready', owner: { kind: 'none', id: null }, observedAt: null, stale: false, specSnapshot: devices[0], latestOperation: null, allowedActions: ['open', 'stop'], blockedReasons: {} }], total: 1, nextCursor: null }
    return path.endsWith('/environment') ? environment : path.endsWith('/devices') ? [devices[0]] : path.endsWith('/profiles') ? [profile] : path.endsWith('/management/images') ? { items: [], total: 0, nextCursor: null } : path.endsWith('/sessions') && init?.method === 'POST' ? fixtureSession(true) : path.endsWith('/sessions/fixture') ? fixtureSession(true) : path.endsWith('/heartbeat') ? fixtureSession(true) : path.endsWith('/apps') ? { packages: [], currentPackage: null, shellRoot: 'unknown', applicationRoot: 'unknown' } : path.endsWith('/actions') ? { ...fixtureSession(true), state: 'closed' } : []
  })
})
it('opens embedded control only on explicit click; refresh does not create a native window', async () => {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await screen.findByRole('heading', { name: '手动控制中' })
  await waitFor(() => expect(mocks.client.request.mock.calls.filter(([path, init]) => path.endsWith('/sessions') && init?.method === 'POST')).toHaveLength(1))
  expect(mocks.client.request.mock.calls.some(([, init]) => init?.body?.action === 'native')).toBe(false)
  await userEvent.click(screen.getByRole('button', { name: '结束控制' }))
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/android/sessions/fixture/actions', expect.objectContaining({ body: expect.objectContaining({ action: 'end' }) })))
})

it('ends the control session before returning to the management list and stops heartbeats', async () => {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await screen.findByRole('heading', { name: '手动控制中' })
  await waitFor(() => expect(mocks.client.request.mock.calls.some(([path, init]) => path.endsWith('/heartbeat') && init?.method === 'POST')).toBe(true))
  await userEvent.click(screen.getByRole('button', { name: /返回资源看板/ }))
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/android/sessions/fixture/actions', expect.objectContaining({ body: expect.objectContaining({ action: 'end' }) })))
  await screen.findByText('实例管理')
  const heartbeatCount = mocks.client.request.mock.calls.filter(([path, init]) => path.endsWith('/heartbeat') && init?.method === 'POST').length
  await new Promise((resolve) => setTimeout(resolve, 30))
  expect(mocks.client.request.mock.calls.filter(([path, init]) => path.endsWith('/heartbeat') && init?.method === 'POST')).toHaveLength(heartbeatCount)
})

it('ends a session whose open response arrives after returning to the management list', async () => {
  let resolveOpen!: (value: ReturnType<typeof fixtureSession>) => void
  const opening = new Promise<ReturnType<typeof fixtureSession>>((resolve) => { resolveOpen = resolve })
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { method?: string }) =>
    path.endsWith('/sessions') && init?.method === 'POST' ? opening : fallback(path, init))
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await waitFor(() => expect(mocks.client.request.mock.calls.some(([path, init]) => path.endsWith('/sessions') && init?.method === 'POST')).toBe(true))
  await userEvent.click(screen.getByRole('button', { name: /返回资源看板/ }))
  expect(screen.queryByText('实例管理')).not.toBeInTheDocument()
  await act(async () => { resolveOpen(fixtureSession(true)); await opening })
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/android/sessions/fixture/actions', expect.objectContaining({ body: expect.objectContaining({ action: 'end' }) })))
  expect(screen.queryByRole('heading', { name: '手动控制中' })).not.toBeInTheDocument()
  await screen.findByText('实例管理')
})

it('keeps a late session visible for recovery when ending it is not confirmed', async () => {
  let resolveOpen!: (value: ReturnType<typeof fixtureSession>) => void
  const opening = new Promise<ReturnType<typeof fixtureSession>>((resolve) => { resolveOpen = resolve })
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { method?: string }) => {
    if (path.endsWith('/sessions') && init?.method === 'POST') return opening
    if (path.endsWith('/actions')) throw new Error('end lost')
    return fallback(path, init)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await waitFor(() => expect(mocks.client.request.mock.calls.some(([path]) => path.endsWith('/sessions'))).toBe(true))
  await userEvent.click(screen.getByRole('button', { name: /返回资源看板/ }))
  expect(screen.queryByText('实例管理')).not.toBeInTheDocument()
  await act(async () => { resolveOpen(fixtureSession(true)); await opening })
  await screen.findByText('控制会话状态未知', { selector: 'strong' })
  expect(screen.queryByText('实例管理')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: /返回资源看板/ })).toBeInTheDocument()
})

it('lets the user leave after a confirmed busy rejection creates no session', async () => {
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { method?: string }) => {
    if (path.endsWith('/sessions') && init?.method === 'POST')
      throw new ApiClientError('控制台已占用', 409, 'ANDROID_CONSOLE_BUSY')
    return fallback(path, init)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await waitFor(() => expect(screen.getByText('控制台已占用')).toBeInTheDocument())
  await userEvent.click(screen.getByRole('button', { name: /返回资源看板/ }))
  await screen.findByText('实例管理')
})

it('ends a late session after the Android page is unmounted', async () => {
  let resolveOpen!: (value: ReturnType<typeof fixtureSession>) => void
  const opening = new Promise<ReturnType<typeof fixtureSession>>((resolve) => { resolveOpen = resolve })
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { method?: string }) =>
    path.endsWith('/sessions') && init?.method === 'POST' ? opening : fallback(path, init))
  const view = render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await waitFor(() => expect(mocks.client.request.mock.calls.some(([path]) => path.endsWith('/sessions'))).toBe(true))
  view.unmount()
  await act(async () => { resolveOpen(fixtureSession(true)); await opening })
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/android/sessions/fixture/actions', expect.objectContaining({ body: expect.objectContaining({ action: 'end' }) })))
})

it('ends an already connected session when navigating away from Android', async () => {
  const view = render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await screen.findByRole('heading', { name: '手动控制中' })
  view.unmount()
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/android/sessions/fixture/actions', expect.objectContaining({ body: expect.objectContaining({ action: 'end' }) })))
})

it('blocks route navigation when ending embedded control is unconfirmed', async () => {
  const registerLeaveGuard = vi.fn()
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { body?: { action?: string } }) => {
    if (path.endsWith('/actions') && init?.body?.action === 'end') throw new Error('end lost')
    return fallback(path, init)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage registerLeaveGuard={registerLeaveGuard} /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await screen.findByRole('heading', { name: '手动控制中' })
  const guard = registerLeaveGuard.mock.lastCall?.[0]
  expect(typeof guard).toBe('function')
  expect(await guard()).toBe(false)
  expect(screen.queryByText('实例管理')).not.toBeInTheDocument()
  await waitFor(() => expect(document.querySelector('.ad-console-status')).toHaveTextContent('控制会话状态未知'))
})

it('leaves after server lease expiry only when the session and device owner both confirm release', async () => {
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { body?: { action?: string } }) => {
    if (path.endsWith('/actions') && init?.body?.action === 'end') throw new ApiClientError('会话已回收', 409, 'ANDROID_SESSION_STALE')
    if (path === '/api/v1/android/sessions/fixture' && !init?.body) return Promise.resolve({ ...fixtureSession(true), state: 'closed' })
    return fallback(path, init)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await screen.findByRole('heading', { name: '手动控制中' })
  await userEvent.click(screen.getByRole('button', { name: /返回资源看板/ }))
  await screen.findByText('实例管理')
  expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/android/sessions/fixture')
})

it('keeps control unknown when the session says closed but ownership is still held', async () => {
  let endAttempted = false
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { body?: { action?: string } }) => {
    if (path.endsWith('/actions') && init?.body?.action === 'end') { endAttempted = true; throw new ApiClientError('会话已回收', 409, 'ANDROID_SESSION_STALE') }
    if (path === '/api/v1/android/sessions/fixture' && !init?.body) return Promise.resolve({ ...fixtureSession(true), state: 'closed' })
    if (endAttempted && path === '/api/v1/android/management/devices?limit=50') return Promise.resolve({ items: [{ deviceId: devices[0].deviceId, revision: 1, name: devices[0].name, runtimeState: 'ready', owner: { kind: 'manualSession', id: 'fixture' }, observedAt: null, stale: false, specSnapshot: devices[0], latestOperation: null, allowedActions: ['return_to_console', 'end_control'], blockedReasons: {} }], total: 1, nextCursor: null })
    return fallback(path, init)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await screen.findByRole('heading', { name: '手动控制中' })
  await userEvent.click(screen.getByRole('button', { name: /返回资源看板/ }))
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/android/sessions/fixture'))
  expect(screen.queryByText('实例管理')).not.toBeInTheDocument()
  expect(document.querySelector('.ad-console-status')).toHaveTextContent('控制会话状态未知')
})

it('keeps an explicitly opened native window when navigating away', async () => {
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { body?: { action?: string } }) => {
    if (path.endsWith('/actions') && init?.body?.action === 'native')
      return Promise.resolve({ ...fixtureSession(true), endpoint: 'native', generation: 2 })
    return fallback(path, init)
  })
  const view = render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await screen.findByRole('heading', { name: '手动控制中' })
  await userEvent.click(screen.getByRole('button', { name: '更多设备操作' }))
  await userEvent.click(screen.getByRole('button', { name: '独立 Mac 窗口' }))
  await screen.findByText('正在独立 Mac 窗口操作')
  view.unmount()
  await act(async () => { await Promise.resolve() })
  expect(mocks.client.request.mock.calls.filter(([path, init]) => path.endsWith('/actions') && init?.body?.action === 'end')).toHaveLength(0)
})

it('recovers an owned native session from the management snapshot after route remount', async () => {
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { method?: string; body?: { action?: string } }) => {
    if (path === '/api/v1/android/management/devices?limit=50') return Promise.resolve({ items: [{ deviceId: devices[0].deviceId, revision: 2, name: devices[0].name, runtimeState: 'ready', owner: { kind: 'manualSession', id: 'fixture' }, observedAt: null, stale: false, specSnapshot: devices[0], latestOperation: null, allowedActions: ['return_to_console', 'end_control'], blockedReasons: {} }], total: 1, nextCursor: null })
    if (path === '/api/v1/android/sessions/fixture' && !init?.method) return Promise.resolve({ ...fixtureSession(true), endpoint: 'native', generation: 2 })
    return fallback(path, init)
  })
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const first = render(<QueryClientProvider client={queryClient}><AndroidPage /></QueryClientProvider>)
  await screen.findByText('实例管理')
  first.unmount()
  render(<QueryClientProvider client={queryClient}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: '查看测试设备 01控制会话' }))
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/android/sessions/fixture'))
  await screen.findByText('正在独立 Mac 窗口操作')
  expect(mocks.client.request.mock.calls.filter(([path, init]) => path.endsWith('/sessions') && init?.method === 'POST')).toHaveLength(0)
  await userEvent.click(screen.getByRole('button', { name: /返回资源看板/ }))
  await screen.findByText('实例管理')
  expect(mocks.client.request.mock.calls.filter(([path, init]) => path.endsWith('/actions') && init?.body?.action === 'end')).toHaveLength(0)
})

it('ends a persisted native session from the management list only after an explicit click', async () => {
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { method?: string; body?: { action?: string } }) => {
    if (path === '/api/v1/android/management/devices?limit=50') return Promise.resolve({ items: [{ deviceId: devices[0].deviceId, revision: 2, name: devices[0].name, runtimeState: 'ready', owner: { kind: 'manualSession', id: 'fixture' }, observedAt: null, stale: false, specSnapshot: devices[0], latestOperation: null, allowedActions: ['return_to_console', 'end_control'], blockedReasons: {} }], total: 1, nextCursor: null })
    if (path === '/api/v1/android/sessions/fixture' && !init?.method) return Promise.resolve({ ...fixtureSession(true), endpoint: 'native', generation: 2 })
    return fallback(path, init)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await screen.findByRole('button', { name: '结束测试设备 01控制会话' })
  expect(mocks.client.request.mock.calls.filter(([path, init]) => path.endsWith('/actions') && init?.body?.action === 'end')).toHaveLength(0)
  await userEvent.click(screen.getByRole('button', { name: '结束测试设备 01控制会话' }))
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/android/sessions/fixture/actions', expect.objectContaining({ body: expect.objectContaining({ action: 'end' }) })))
})

it('opening a second device does not close another device native window', async () => {
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { method?: string; body?: { action?: string; deviceId?: string } }) => {
    if (path === '/api/v1/android/management/devices?limit=50') return Promise.resolve({ items: devices.slice(0, 2).map(device => ({ deviceId: device.deviceId, revision: device.generation, name: device.name, runtimeState: 'ready', owner: { kind: 'none', id: null }, observedAt: null, stale: false, specSnapshot: device, latestOperation: null, allowedActions: ['open'], blockedReasons: {} })), total: 2, nextCursor: null })
    if (path.endsWith('/sessions') && init?.method === 'POST' && init.body?.deviceId === devices[1].deviceId) return Promise.resolve({ ...fixtureSession(true), id: 'fixture-b', deviceId: devices[1].deviceId })
    if (path.endsWith('/actions') && init?.body?.action === 'native') return Promise.resolve({ ...fixtureSession(true), endpoint: 'native', generation: 2 })
    return fallback(path, init)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await screen.findByRole('heading', { name: '手动控制中' })
  await userEvent.click(screen.getByRole('button', { name: '更多设备操作' }))
  await userEvent.click(screen.getByRole('button', { name: '独立 Mac 窗口' }))
  await screen.findByText('正在独立 Mac 窗口操作')
  await userEvent.click(screen.getByRole('button', { name: /返回资源看板/ }))
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 02/ }))
  await waitFor(() => expect(mocks.client.request.mock.calls.some(([path, init]) => path.endsWith('/sessions') && init?.body?.deviceId === devices[1].deviceId)).toBe(true))
  expect(mocks.client.request.mock.calls.filter(([path, init]) => path.endsWith('/actions') && init?.body?.action === 'end')).toHaveLength(0)
})

it('does not restore connected control from a late native response after end became unknown', async () => {
  let resolveNative!: (value: ReturnType<typeof fixtureSession>) => void
  const native = new Promise<ReturnType<typeof fixtureSession>>((resolve) => { resolveNative = resolve })
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { body?: { action?: string } }) => {
    if (path.endsWith('/actions') && init?.body?.action === 'native') return native
    if (path.endsWith('/actions') && init?.body?.action === 'end') throw new Error('end unknown')
    return fallback(path, init)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await screen.findByRole('heading', { name: '手动控制中' })
  await userEvent.click(screen.getByRole('button', { name: '更多设备操作' }))
  await userEvent.click(screen.getByRole('button', { name: '独立 Mac 窗口' }))
  await waitFor(() => expect(mocks.client.request.mock.calls.some(([path, init]) => path.endsWith('/actions') && init?.body?.action === 'native')).toBe(true))
  await userEvent.click(screen.getByRole('button', { name: /返回资源看板/ }))
  await waitFor(() => expect(document.querySelector('.ad-console-status')).toHaveTextContent('控制会话状态未知'))
  await act(async () => { resolveNative({ ...fixtureSession(true), endpoint: 'native', generation: 2 }); await native })
  expect(document.querySelector('.ad-console-status')).toHaveTextContent('控制会话状态未知')
  expect(document.querySelector('.ad-console-status')).not.toHaveTextContent('独立窗口')
})

it('does not adopt an old backend session after the instance changes', async () => {
  let resolveOpen!: (value: ReturnType<typeof fixtureSession>) => void
  const opening = new Promise<ReturnType<typeof fixtureSession>>((resolve) => { resolveOpen = resolve })
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { method?: string }) =>
    path.endsWith('/sessions') && init?.method === 'POST' ? opening : fallback(path, init))
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const view = render(<QueryClientProvider client={queryClient}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await waitFor(() => expect(mocks.client.request.mock.calls.some(([path]) => path.endsWith('/sessions'))).toBe(true))
  mocks.instanceId = 'replacement'
  view.rerender(<QueryClientProvider client={queryClient}><AndroidPage /></QueryClientProvider>)
  await act(async () => { resolveOpen(fixtureSession(true)); await opening })
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/android/sessions/fixture/actions', expect.objectContaining({ body: expect.objectContaining({ action: 'end' }) })))
  expect(screen.queryByRole('heading', { name: '手动控制中' })).not.toBeInTheDocument()
})

it('ends a connected session before opening the copy form', async () => {
  let resolveEnd!: () => void
  const ending = new Promise<void>((resolve) => { resolveEnd = resolve })
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation(async (path: string, init?: { method?: string }) => {
    if (path.endsWith('/actions')) { await ending; return { ...fixtureSession(true), state: 'closed' } }
    return fallback(path, init)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await screen.findByRole('heading', { name: '手动控制中' })
  await userEvent.click(screen.getByRole('button', { name: '复制配置' }))
  expect(screen.queryByRole('button', { name: '创建并启动' })).not.toBeInTheDocument()
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/android/sessions/fixture/actions', expect.objectContaining({ body: expect.objectContaining({ action: 'end' }) })))
  resolveEnd()
  await screen.findByRole('button', { name: '创建并启动' })
})

it('waits for a confirmed session end before returning to the management list', async () => {
  let resolveEnd!: (value: unknown) => void
  const end = new Promise((resolve) => { resolveEnd = resolve })
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation(async (path: string, init?: { method?: string }) => {
    if (path.endsWith('/actions')) {
      await end
      return { ...fixtureSession(true), state: 'closed' }
    }
    return fallback(path, init)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await screen.findByRole('heading', { name: '手动控制中' })
  await userEvent.click(screen.getByRole('button', { name: /返回资源看板/ }))
  expect(screen.queryByText('实例管理')).not.toBeInTheDocument()
  expect(screen.getByText('控制会话状态未知', { selector: 'strong' })).toBeInTheDocument()
  const heartbeatCount = mocks.client.request.mock.calls.filter(([path, init]) => path.endsWith('/heartbeat') && init?.method === 'POST').length
  await new Promise((resolve) => setTimeout(resolve, 30))
  expect(mocks.client.request.mock.calls.filter(([path, init]) => path.endsWith('/heartbeat') && init?.method === 'POST')).toHaveLength(heartbeatCount)
  resolveEnd(undefined)
  await screen.findByText('实例管理')
})

it('marks a heartbeat failure as unknown and exposes no connected control state', async () => {
  mocks.client.request.mockImplementation(async (path: string, init?: { method?: string }) => {
    if (path.endsWith('/heartbeat')) throw new Error('heartbeat lost')
    if (path === '/api/v1/android/management/devices?limit=50') return { items: [{ deviceId: devices[0].deviceId, revision: devices[0].generation, name: devices[0].name, runtimeState: 'ready', owner: { kind: 'none', id: null }, observedAt: null, stale: false, specSnapshot: devices[0], latestOperation: null, allowedActions: ['open', 'stop'], blockedReasons: {} }], total: 1, nextCursor: null }
    if (path.endsWith('/sessions') && init?.method === 'POST') return fixtureSession(true)
    if (path.endsWith('/apps')) return { packages: ['org.example.notes'], applications: [{ packageName: 'org.example.notes', versionCode: 1, versionName: null, system: false, protected: false }], currentPackage: null, shellRoot: 'unknown', applicationRoot: 'unknown' }
    if (path.startsWith('/api/v1/android/management/operations?action=pull')) return { items: [], total: 0, nextCursor: null }
    if (path.endsWith('/images')) return { items: [], total: 0, nextCursor: null }
    return path.endsWith('/environment') ? environment : path.endsWith('/profiles') ? [profile] : path.endsWith('/sessions/fixture') ? fixtureSession(true) : []
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await screen.findByRole('heading', { name: '手动控制中' })
  await waitFor(() => expect(screen.getAllByText(/控制会话状态未知/).length).toBeGreaterThan(0))
  await userEvent.click(screen.getByRole('button', { name: '应用' }))
  const app = screen.getByText('org.example.notes').closest('article')!
  expect(within(app).getByRole('button', { name: '启动' })).toBeDisabled()
})
it('management home does not request retired workflow, allocation, or run endpoints', async () => {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await screen.findByText('实例管理')
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalled())
  expect(mocks.client.request.mock.calls.map(([path]) => path).filter((path) => /workflows|allocations|\/runs/.test(path))).toEqual([])
  expect(screen.queryByRole('button', { name: '分配给工作流' })).not.toBeInTheDocument()
})

it('manual device details do not offer retired workflow allocation', async () => {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await screen.findByRole('heading', { name: '手动控制中' })
  expect(screen.queryByRole('button', { name: '分配给工作流' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '运行记录' })).not.toBeInTheDocument()
  expect(mocks.client.request.mock.calls.map(([path]) => path).filter((path) => /\/runs(?:\?|$)/.test(path))).toEqual([])
})

it('management home does not poll the retired device list endpoint', async () => {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await screen.findByText('实例管理')
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalled())
  expect(mocks.client.request.mock.calls.filter(([path]) => path === '/api/v1/android/devices')).toHaveLength(0)
})

it('verifies a management operation with its original request id', async () => {
  const requestId = 'request-original'
  mocks.client.request.mockImplementation(async (path: string) => {
    if (path === '/api/v1/android/management/devices?limit=50') return {
      items: [{ deviceId: devices[0].deviceId, revision: devices[0].generation, name: devices[0].name, runtimeState: 'unknown', owner: { kind: 'none', id: null }, observedAt: null, stale: true, specSnapshot: devices[0], latestOperation: { operationId: 'operation-1' }, allowedActions: ['verify'], blockedReasons: { state: '请核实设备状态' } }], total: 1, nextCursor: null,
    }
    if (path === '/api/v1/android/management/operations/operation-1') return { operationId: 'operation-1', requestId, targetId: devices[0].deviceId, action: 'start', state: 'needs_verification', stageCode: 'verify', stageLabel: '等待核实', attempt: 1, retryOf: null, createdAt: '', startedAt: '', finishedAt: null, resultCode: null, message: null, allowedActions: ['verify'] }
    if (path === `/api/v1/android/management/operations?deviceId=${devices[0].deviceId}&limit=50`) return { items: [{ operationId: 'operation-1', requestId, targetId: devices[0].deviceId, action: 'start', state: 'needs_verification', stageCode: 'verify', stageLabel: '等待核实', attempt: 1, createdAt: '2026-09-23T00:00:00Z', allowedActions: ['verify'] }], total: 1, nextCursor: null }
    if (path === '/api/v1/android/management/operations/operation-1/verify') return { operationId: 'operation-1', requestId, targetId: devices[0].deviceId, action: 'start', state: 'succeeded', stageCode: 'verified', stageLabel: '已核实', attempt: 1, retryOf: null, createdAt: '', startedAt: '', finishedAt: '', resultCode: 'STATE_VERIFIED', message: null, allowedActions: [] }
    if (path.endsWith('/environment')) return environment
    if (path.endsWith('/profiles')) return [profile]
    if (path.startsWith('/api/v1/android/management/operations?action=pull')) return { items: [], total: 0, nextCursor: null }
    if (path.endsWith('/images')) return { items: [], total: 0, nextCursor: null }
    if (path.endsWith('/backups')) return []
    if (path.endsWith('/capabilities')) return { management: true, control: true, images: true, bulk: true, backups: true, workflow: false, reasons: {} }
    if (path.endsWith('/cleanup/previews')) return { items: [], confirmationDigest: 'digest' }
    if (path.endsWith('/diagnostics')) return { id: 'diagnostic-1', state: 'ready', createdAt: '' }
    return []
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: `查看${devices[0].name}操作历史` }))
  await userEvent.click(await screen.findByRole('button', { name: '核实操作 operation-1' }))
  expect(screen.getByRole('heading', { name: '核实状态' })).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '确认操作' }))
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/android/management/operations/operation-1/verify', expect.objectContaining({ body: { requestId } })))
})

it('submits retained-volume restoration through the public device operation', async () => {
  const retained = { ...devices[0], androidStatus: 'retained', dataRetained: true }
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { method?: string }) => {
    if (path === '/api/v1/android/management/devices?limit=50') return Promise.resolve({ items: [{ deviceId: retained.deviceId, revision: retained.generation, name: retained.name, runtimeState: 'retained', owner: { kind: 'none', id: null }, observedAt: null, stale: false, specSnapshot: retained, latestOperation: null, allowedActions: ['restore', 'delete'], blockedReasons: {} }], total: 1, nextCursor: null })
    if (path === '/api/v1/android/devices') return Promise.resolve([retained])
    if (path.endsWith('/operations') && init?.method === 'POST') return Promise.resolve(retained)
    return fallback(path, init)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: '恢复实例' }))
  expect(screen.getByRole('heading', { name: '恢复保留数据' })).toBeVisible()
  const consent = screen.getByRole('checkbox', { name: /最终磁盘占用无法可靠估计/ })
  expect(consent).not.toBeChecked()
  await userEvent.click(consent)
  await userEvent.click(screen.getByRole('button', { name: '确认操作' }))
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalledWith(`/api/v1/android/devices/${retained.deviceId}/operations`, expect.objectContaining({ body: expect.objectContaining({ action: 'restore', deleteData: false, allowUnknownDiskEstimate: true }) })))
})

it('keeps the retained restore confirmation and request ID after a lost response', async () => {
  const retained = { ...devices[0], androidStatus: 'retained', dataRetained: true }
  const fallback = mocks.client.request.getMockImplementation()!
  let sent = 0
  mocks.client.request.mockImplementation((path: string, init?: { method?: string }) => {
    if (path === '/api/v1/android/management/devices?limit=50') return Promise.resolve({ items: [{ deviceId: retained.deviceId, revision: retained.generation, name: retained.name, runtimeState: 'retained', owner: { kind: 'none', id: null }, observedAt: null, stale: false, specSnapshot: retained, latestOperation: null, allowedActions: ['restore'], blockedReasons: {} }], total: 1, nextCursor: null })
    if (path === '/api/v1/android/devices') return Promise.resolve([retained])
    if (path.endsWith('/operations') && init?.method === 'POST') return ++sent === 1 ? Promise.reject(new Error('响应丢失')) : Promise.resolve(retained)
    return fallback(path, init)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: '恢复实例' }))
  const consent = screen.getByRole('checkbox', { name: /最终磁盘占用无法可靠估计/ })
  await userEvent.click(consent)
  await userEvent.click(screen.getByRole('button', { name: '确认操作' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('响应丢失')
  expect(consent).toBeDisabled()
  expect(screen.getByRole('button', { name: '取消' })).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: '确认操作' }))
  await waitFor(() => expect(sent).toBe(2))
  const bodies = mocks.client.request.mock.calls.filter(([path, init]) => path.endsWith('/operations') && init?.method === 'POST').map(([, init]) => init.body)
  expect(bodies[1]).toEqual(bodies[0])
})
it('cleanup preview includes registered backups while diagnostics remain device scoped', async () => {
  const backup = { id: 'backup-1', deviceId: devices[0].deviceId, bytes: 12, imageId: profile.imageId, sha256: 'digest', formatVersion: 1, state: 'ready', createdAt: '' }
  mocks.client.request.mockImplementation(async (path: string, init?: { method?: string; body?: { resourceIds?: string[]; deviceIds?: string[] } }) => {
    if (path.endsWith('/cleanup/resources')) return { items: [{ id: devices[0].deviceId, kind: 'device', size: 1 }, { id: 'backup-1', kind: 'backup', size: 12 }] }
    if (path.endsWith('/backups') && !init?.method) return [backup]
    if (path.endsWith('/cleanup/previews')) {
      expect(init?.body?.resourceIds).toEqual(expect.arrayContaining([devices[0].deviceId, 'backup-1']))
      return { items: [], confirmationDigest: 'digest' }
    }
    if (path.endsWith('/diagnostics')) {
      expect(init?.body?.deviceIds).toEqual([devices[0].deviceId])
      return { id: 'diagnostic-1', state: 'ready', createdAt: '' }
    }
    if (path.startsWith('/api/v1/android/management/operations?action=pull')) return { items: [], total: 0, nextCursor: null }
    if (path.endsWith('/images')) return { items: [], total: 0, nextCursor: null }
    if (path.endsWith('/environment')) return environment
    if (path.endsWith('/devices')) return [devices[0]]
    if (path.endsWith('/profiles')) return [profile]
    return []
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await screen.findByRole('heading', { name: '数据维护' })
  await userEvent.click(await screen.findByRole('checkbox', { name: /保留的数据：/ }))
  await userEvent.click(screen.getByRole('checkbox', { name: /备份：backup-1/ }))
  await userEvent.click(screen.getByRole('button', { name: '预览清理' }))
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/android/management/cleanup/previews', expect.anything()))
  await userEvent.click(screen.getByRole('button', { name: '生成脱敏诊断' }))
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/android/management/diagnostics', expect.anything()))
})
it('preserves the six-card three-column board and both waiting tasks', () => {
  render(<ResourceBoard devices={devices} profiles={[profile]} allocations={allocations} runs={runs} batches={[]} images={images} onCreate={noop} onProfiles={noop} onOpen={noop} onAllocate={noop} onManage={noop} onRuns={noop} onBatch={noop} />)
  expect(screen.getAllByRole('article')).toHaveLength(6)
  expect(screen.getByRole('heading', { name: /工作流占用\s*2/ })).toBeVisible()
  expect(screen.getByText('登录回归')).toBeVisible()
  expect(screen.getByText('指定测试设备 06')).toBeVisible()
})
it('defaults to one persistent instance and preserves the batch id after an unknown response', async () => {
  const submit = vi.fn().mockRejectedValue(new Error('连接中断'))
  render(<CreateInstances profiles={[profile]} environment={environment} onBack={noop} onProfiles={noop} onSubmit={submit} />)
  expect(screen.getByRole('spinbutton', { name: '数量' })).toHaveValue(1)
  const consent = screen.getByRole('checkbox', { name: /最终磁盘占用无法可靠估计/ })
  expect(consent).not.toBeChecked()
  await userEvent.click(consent)
  await userEvent.click(screen.getByRole('button', { name: '创建并启动' }))
  expect(consent).toBeDisabled()
  await userEvent.click(await screen.findByRole('button', { name: '按原编号核实创建' }))
  expect(submit.mock.calls[0][0]).toEqual(submit.mock.calls[1][0])
  expect(submit.mock.calls[0][0]).toMatchObject({ quantity: 1, instanceType: 'persistent', allowUnknownDiskEstimate: true })
})

it('resets batch disk confirmation after changing the target configuration', async () => {
  const submit = vi.fn(async (_value: BatchRequest): Promise<void> => {})
  render(<CreateInstances profiles={[profile]} environment={environment} onBack={noop} onProfiles={noop} onSubmit={submit} />)
  const consent = screen.getByRole('checkbox', { name: /最终磁盘占用无法可靠估计/ })
  await userEvent.click(consent)
  await userEvent.clear(screen.getByRole('textbox', { name: '实例名称' }))
  await userEvent.type(screen.getByRole('textbox', { name: '实例名称' }), '新设备')
  expect(consent).not.toBeChecked()
  await userEvent.click(screen.getByRole('button', { name: '创建并启动' }))
  await waitFor(() => expect(submit).toHaveBeenCalled())
  expect(submit.mock.calls[0][0]).toMatchObject({ allowUnknownDiskEstimate: false })
})

it('hides archived profiles while copying the source configuration snapshot', async () => {
  const archived = { ...profile, id: 'archived-profile', name: '已归档环境', archived: true }
  const submit = vi.fn(async (_value: BatchRequest): Promise<void> => {})
  render(<CreateInstances profiles={[archived, profile]} source={devices[0]} sourceSnapshot={{ profileId: profile.id, profileRevision: 7, width: 1080, height: 1920, locale: 'en-US', timezone: 'UTC', allowUnknownDiskEstimate: true }} environment={environment} onBack={noop} onProfiles={noop} onSubmit={submit} />)
  expect(screen.queryByRole('option', { name: '已归档环境' })).not.toBeInTheDocument()
  expect(screen.getByLabelText('分辨率')).toHaveValue('1080x1920')
  await userEvent.click(screen.getByRole('button', { name: '创建并启动' }))
  await waitFor(() => expect(submit).toHaveBeenCalled())
  expect(submit.mock.calls[0][0]).toMatchObject({ sourceDeviceId: devices[0].deviceId, profileRevision: 7, width: 1080, height: 1920, locale: 'en-US', timezone: 'UTC', allowUnknownDiskEstimate: false })
})

it('keeps an archived source snapshot selectable and blocks creation after editing without an active template', async () => {
  const archived = { ...profile, id: 'archived-profile', name: '已归档环境', archived: true }
  const submit = vi.fn(async (_value: BatchRequest): Promise<void> => {})
  render(<CreateInstances profiles={[archived]} source={devices[0]} sourceSnapshot={{ profileId: archived.id, profileName: archived.name, imageId: archived.imageId, profileRevision: 7, width: 1080, height: 1920, locale: 'en-US', timezone: 'UTC' }} environment={environment} onBack={noop} onProfiles={noop} onSubmit={submit} />)
  expect(screen.getByRole('option', { name: /已归档环境/ })).toBeVisible()
  expect(screen.getByText(/复制源快照/)).toBeVisible()
  await userEvent.selectOptions(screen.getByLabelText('分辨率'), '720x1280')
  expect(screen.getByRole('button', { name: '创建并启动' })).toBeDisabled()
  expect(submit).not.toHaveBeenCalled()
})

it('clears source copy mode when selecting another template', async () => {
  const archived = { ...profile, id: 'archived-profile', name: '已归档环境', archived: true }
  const submit = vi.fn(async (_value: BatchRequest): Promise<void> => {})
  render(<CreateInstances profiles={[archived, profile]} source={devices[0]} sourceSnapshot={{ profileId: archived.id, profileName: archived.name, profileRevision: 7, width: 1080, height: 1920, locale: 'en-US', timezone: 'UTC' }} environment={environment} onBack={noop} onProfiles={noop} onSubmit={submit} />)
  await userEvent.selectOptions(screen.getByLabelText('选择环境配置'), profile.id)
  expect(screen.queryByText(/复制源快照/)).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '创建并启动' }))
  await waitFor(() => expect(submit).toHaveBeenCalled())
  expect(submit.mock.calls[0][0]).toMatchObject({ profileId: profile.id, sourceDeviceId: undefined, profileRevision: profile.revision })
})
it('readonly console never enables navigation or installation during workflow ownership', async () => {
  render(<DeviceConsole device={devices[2]} session={fixtureSession(false)} run={runs[devices[2].deviceId]} image={images[devices[2].deviceId]} onBack={noop} onSession={noop} onOpen={noop} onManage={noop} onRefresh={noop} />)
  expect(screen.getByRole('button', { name: '返回' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '暂停并接管' })).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '应用' }))
  expect(screen.getByRole('button', { name: '上传 APK' })).toBeDisabled()
})

it('discards an in-flight heartbeat failure while switching control endpoints', async () => {
  let rejectHeartbeat!: (error: Error) => void
  const heartbeat = new Promise<ReturnType<typeof fixtureSession>>((_, reject) => { rejectHeartbeat = reject })
  let finishSwitch!: (session: ReturnType<typeof fixtureSession>) => void
  const switching = new Promise<ReturnType<typeof fixtureSession>>((resolve) => { finishSwitch = resolve })
  const next = { ...fixtureSession(true), endpoint: 'native' as const, generation: 2 }
  let switched = false
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { body?: { action?: string } }) => {
    if (path.endsWith('/heartbeat')) return switched ? Promise.resolve(next) : heartbeat
    if (path.endsWith('/actions') && init?.body?.action === 'native') return switching
    return fallback(path, init)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await screen.findByRole('heading', { name: '手动控制中' })
  await waitFor(() => expect(mocks.client.request.mock.calls.some(([path]) => path.endsWith('/heartbeat'))).toBe(true))
  await userEvent.click(screen.getByRole('button', { name: '更多设备操作' }))
  await userEvent.click(screen.getByRole('button', { name: '独立 Mac 窗口' }))
  await act(async () => { rejectHeartbeat(new ApiClientError('切换中的旧租约', 410, 'ANDROID_SESSION_EXPIRED')); await heartbeat.catch(() => {}) })
  await act(async () => { switched = true; finishSwitch(next); await switching })
  await screen.findByText('正在独立 Mac 窗口操作')
  expect(screen.queryByText('控制会话状态未知，请重新连接并核实设备')).not.toBeInTheDocument()
})

it.each(['native', 'embedded'] as const)('does not restore a cached readonly endpoint after switching to %s at the same generation', async (endpoint) => {
  const initial = { ...fixtureSession(false), deviceId: devices[0].deviceId, endpoint: endpoint === 'native' ? 'embedded' as const : 'native' as const }
  const next = { ...initial, endpoint }
  let switched = false
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { method?: string; body?: { action?: string } }) => {
    if (path.endsWith('/sessions') && init?.method === 'POST') return Promise.resolve(initial)
    if (path.endsWith('/heartbeat')) return switched ? new Promise(() => {}) : Promise.resolve(initial)
    if (path.endsWith('/actions') && init?.body?.action === endpoint) { switched = true; return Promise.resolve(next) }
    return fallback(path, init)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await waitFor(() => expect(mocks.client.request.mock.calls.some(([path]) => path.endsWith('/heartbeat'))).toBe(true))
  await userEvent.click(screen.getByRole('button', { name: '更多设备操作' }))
  await userEvent.click(screen.getByRole('button', { name: endpoint === 'native' ? '独立 Mac 窗口' : '返回页面操作' }))
  await waitFor(() => expect(mocks.client.request.mock.calls.filter(([path]) => path.endsWith('/heartbeat')).length).toBeGreaterThan(1))
  if (endpoint === 'native') await screen.findByText('正在独立 Mac 窗口操作')
  else await waitFor(() => expect(screen.queryByText('正在独立 Mac 窗口操作')).not.toBeInTheDocument())
})

it('keeps endpoint transitions scoped to the backend and session that started them', async () => {
  let finishOld!: (session: ReturnType<typeof fixtureSession>) => void
  const oldSwitch = new Promise<ReturnType<typeof fixtureSession>>((resolve) => { finishOld = resolve })
  let finishNew!: (session: ReturnType<typeof fixtureSession>) => void
  const newSwitch = new Promise<ReturnType<typeof fixtureSession>>((resolve) => { finishNew = resolve })
  const replacement = { ...fixtureSession(true), id: 'replacement-session' }
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { method?: string; body?: { action?: string } }) => {
    if (path.endsWith('/sessions') && init?.method === 'POST') return Promise.resolve(mocks.instanceId === 'instance' ? fixtureSession(true) : replacement)
    if (path.endsWith('/heartbeat')) return Promise.resolve(path.includes(replacement.id) ? replacement : fixtureSession(true))
    if (path.endsWith('/actions') && init?.body?.action === 'native') return path.includes(replacement.id) ? newSwitch : oldSwitch
    return fallback(path, init)
  })
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const view = render(<QueryClientProvider client={queryClient}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await screen.findByRole('heading', { name: '手动控制中' })
  await userEvent.click(screen.getByRole('button', { name: '更多设备操作' }))
  await userEvent.click(screen.getByRole('button', { name: '独立 Mac 窗口' }))
  mocks.instanceId = 'replacement'
  view.rerender(<QueryClientProvider client={queryClient}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: /打开测试设备 01/ }))
  await screen.findByRole('heading', { name: '手动控制中' })
  await waitFor(() => expect(mocks.client.request.mock.calls.some(([path]) => path === '/api/v1/android/sessions/replacement-session/heartbeat')).toBe(true))
  await userEvent.click(screen.getByRole('button', { name: '更多设备操作' }))
  await userEvent.click(screen.getByRole('button', { name: '独立 Mac 窗口' }))
  const heartbeats = () => mocks.client.request.mock.calls.filter(([path]) => path === '/api/v1/android/sessions/replacement-session/heartbeat').length
  const count = heartbeats()
  await act(async () => { finishOld({ ...fixtureSession(true), endpoint: 'native', generation: 2 }); await oldSwitch })
  await act(async () => { await queryClient.invalidateQueries({ queryKey: ['android', 'replacement', 'session'] }) })
  expect(heartbeats()).toBe(count)
  await act(async () => { finishNew({ ...replacement, endpoint: 'native', generation: 2 }); await newSwitch })
})


it('keeps embedded heartbeats alive beyond the hidden lease window while display polling pauses', async () => {
  vi.useFakeTimers()
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { method?: string }) =>
    path.endsWith('/input') ? Promise.resolve(fixtureSession(true)) : fallback(path, init))
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  try {
    render(<QueryClientProvider client={queryClient}><AndroidPage /></QueryClientProvider>)
    await act(async () => { await vi.advanceTimersByTimeAsync(10) })
    fireEvent.click(screen.getByRole('button', { name: /打开测试设备 01/ }))
    await act(async () => { await vi.advanceTimersByTimeAsync(10) })
    expect(screen.getByRole('heading', { name: '手动控制中' })).toBeVisible()
    const count = (suffix: string) => mocks.client.request.mock.calls.filter(([path]) => path.endsWith(suffix)).length
    const beats = count('/heartbeat'), apps = count('/apps'), snapshots = count('/management/devices?limit=50')
    focusManager.setFocused(false)
    await act(async () => { await vi.advanceTimersByTimeAsync(35_000) })
    expect(count('/heartbeat') - beats).toBeGreaterThanOrEqual(6)
    expect(count('/apps')).toBe(apps)
    expect(count('/management/devices?limit=50')).toBe(snapshots)
    focusManager.setFocused(true)
    await act(async () => { await vi.advanceTimersByTimeAsync(10) })
    fireEvent.click(screen.getByRole('button', { name: '主页' }))
    await act(async () => { await vi.advanceTimersByTimeAsync(10) })
    expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/android/sessions/fixture/input', expect.objectContaining({ body: expect.objectContaining({ kind: 'key', keycode: 3 }) }))
    expect(mocks.client.request.mock.calls.filter(([path, init]) => path.endsWith('/sessions') && init?.method === 'POST')).toHaveLength(1)
  } finally {
    cleanup()
    queryClient.clear()
    focusManager.setFocused(undefined)
    vi.useRealTimers()
  }
})

it('creates a stopped backup through device maintenance without starting or claiming control', async () => {
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { method?: string }) => {
    if (path === '/api/v1/android/management/devices?limit=50') return Promise.resolve({ items: [{ deviceId: devices[0].deviceId, revision: 7, name: devices[0].name, runtimeState: 'stopped', owner: { kind: 'none', id: null }, observedAt: null, stale: false, specSnapshot: devices[0], latestOperation: null, allowedActions: ['start', 'delete'], blockedReasons: {} }], total: 1, nextCursor: null })
    if (path.endsWith('/backups') && init?.method === 'POST') return Promise.resolve({ id: 'backup-stopped' })
    return fallback(path, init)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: `维护${devices[0].name}` }))
  await userEvent.click(screen.getByRole('button', { name: '创建停机备份' }))
  await screen.findByText('备份已创建')
  expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/android/management/backups', expect.objectContaining({ body: expect.objectContaining({ deviceId: devices[0].deviceId, expectedRevision: 7 }) }))
  expect(mocks.client.request.mock.calls.filter(([path, init]) => init?.method === 'POST' && (path.endsWith('/sessions') || path.endsWith('/operations')))).toEqual([])
})

it('restores a workspace backup after its source device has been deleted', async () => {
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { method?: string }) => {
    if (path === '/api/v1/android/management/devices?limit=50') return Promise.resolve({ items: [], total: 0, nextCursor: null })
    if (path.endsWith('/backups') && !init?.method) return Promise.resolve([{ id: 'orphan-backup', deviceId: 'deleted-source', bytes: 123, state: 'ready', imageId: profile.imageId, sha256: 'digest', formatVersion: 1, createdAt: '' }])
    if (path.endsWith('/backups/orphan-backup/restore')) return Promise.resolve({ operationId: 'restore-new' })
    return fallback(path, init)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: '恢复为新实例' }))
  await screen.findByText(/恢复已提交，操作 restore-new/)
  expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/android/management/backups/orphan-backup/restore', expect.objectContaining({ body: expect.objectContaining({ newName: '恢复实例', allowUnknownDiskEstimate: false }) }))
  expect(mocks.client.request.mock.calls.filter(([path, init]) => init?.method === 'POST' && (path.endsWith('/sessions') || path.endsWith('/operations')))).toEqual([])
})

it.each(['failed lifecycle', 'unknown without operation', 'pending restore'])('recovers current device state for %s without rewriting a historical receipt', async (scenario) => {
  const pendingRestore = scenario === 'pending restore'
  let recovered = false
  const fallback = mocks.client.request.getMockImplementation()!
  mocks.client.request.mockImplementation((path: string, init?: { method?: string; body?: { action?: string } }) => {
    if (path === '/api/v1/android/management/devices?limit=50') return Promise.resolve({ items: [{ deviceId: devices[0].deviceId, revision: recovered ? 8 : 7, name: devices[0].name, runtimeState: recovered || pendingRestore ? 'stopped' : 'unknown', owner: { kind: 'none', id: null }, observedAt: null, stale: !recovered && !pendingRestore, restoreState: pendingRestore ? 'pending' : undefined, specSnapshot: devices[0], latestOperation: recovered ? { operationId: 'recover-current', action: 'recover', state: 'succeeded' } : scenario === 'unknown without operation' ? null : { operationId: 'historical-failed', requestId: 'old-request', action: pendingRestore ? 'restore' : 'start', state: 'failed' }, allowedActions: recovered ? pendingRestore ? ['verify', 'delete'] : ['start', 'delete'] : ['verify'], blockedReasons: pendingRestore ? { start: '数据恢复尚未完成或核实', backup: '数据恢复尚未完成或核实' } : {} }], total: 1, nextCursor: null })
    if (path === `/api/v1/android/devices/${devices[0].deviceId}/operations` && init?.body?.action === 'recover') { recovered = true; return Promise.resolve(devices[0]) }
    if (path === '/api/v1/android/management/operations/historical-failed') return Promise.resolve({ requestId: 'old-request', state: 'failed' })
    return fallback(path, init)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: '核实状态' }))
  await userEvent.click(screen.getByRole('button', { name: '确认操作' }))
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalledWith(`/api/v1/android/devices/${devices[0].deviceId}/operations`, expect.objectContaining({ body: expect.objectContaining({ action: 'recover' }) })))
  expect(mocks.client.request.mock.calls.some(([path]) => path.includes('/management/operations/historical-failed/verify'))).toBe(false)
  await screen.findByRole('button', { name: '删除实例' })
  if (pendingRestore) {
    expect(screen.queryByRole('button', { name: '启动设备' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: `维护${devices[0].name}` }))
    expect(screen.getByRole('button', { name: '创建停机备份' })).toBeDisabled()
  } else {
    expect(screen.getByRole('button', { name: '启动设备' })).toBeEnabled()
  }
})
