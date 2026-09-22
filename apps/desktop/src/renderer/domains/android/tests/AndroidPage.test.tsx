import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { devices, environment, profile, fixtureSession, images, allocations, runs } from './prototype-fixtures'
import { ResourceBoard } from '../components/ResourceBoard'
import { CreateInstances } from '../components/CreateInstances'
import { DeviceConsole } from '../components/DeviceConsole'
import type { BatchRequest } from '../fleet-api'
const mocks = vi.hoisted(() => ({ client: { request: vi.fn(), stream: vi.fn() } }))
vi.mock('../../../app/ApiProvider', () => ({ useApi: () => ({ client: mocks.client, instanceId: 'instance' }) }))
vi.mock('../components/AndroidVideo', () => ({ AndroidVideo: () => <canvas aria-label="安卓触控画面" /> }))
import { AndroidPage } from '../pages/AndroidPage'
const noop = vi.fn()
afterEach(cleanup)
beforeEach(() => {
  vi.clearAllMocks()
  mocks.client.request.mockImplementation(async (path: string, init?: { method?: string }) => {
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

it('marks a heartbeat failure as unknown and exposes no connected control state', async () => {
  mocks.client.request.mockImplementation(async (path: string, init?: { method?: string }) => {
    if (path.endsWith('/heartbeat')) throw new Error('heartbeat lost')
    if (path === '/api/v1/android/management/devices?limit=50') return { items: [{ deviceId: devices[0].deviceId, revision: devices[0].generation, name: devices[0].name, runtimeState: 'ready', owner: { kind: 'none', id: null }, observedAt: null, stale: false, specSnapshot: devices[0], latestOperation: null, allowedActions: ['open', 'stop'], blockedReasons: {} }], total: 1, nextCursor: null }
    if (path.endsWith('/sessions') && init?.method === 'POST') return fixtureSession(true)
    if (path.endsWith('/apps')) return { packages: ['org.example.notes'], applications: [{ packageName: 'org.example.notes', versionCode: 1, versionName: null, system: false, protected: false }], currentPackage: null, shellRoot: 'unknown', applicationRoot: 'unknown' }
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
    if (path === '/api/v1/android/management/operations/operation-1/verify') return { operationId: 'operation-1', requestId, targetId: devices[0].deviceId, action: 'start', state: 'succeeded', stageCode: 'verified', stageLabel: '已核实', attempt: 1, retryOf: null, createdAt: '', startedAt: '', finishedAt: '', resultCode: 'STATE_VERIFIED', message: null, allowedActions: [] }
    if (path.endsWith('/environment')) return environment
    if (path.endsWith('/profiles')) return [profile]
    if (path.endsWith('/images')) return { items: [], total: 0, nextCursor: null }
    if (path.endsWith('/backups')) return []
    if (path.endsWith('/capabilities')) return { management: true, control: true, images: true, bulk: true, backups: true, workflow: false, reasons: {} }
    if (path.endsWith('/cleanup/previews')) return { items: [], confirmationDigest: 'digest' }
    if (path.endsWith('/diagnostics')) return { id: 'diagnostic-1', state: 'ready', createdAt: '' }
    return []
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: '核实状态' }))
  await userEvent.click(screen.getByRole('button', { name: '确认操作' }))
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/android/management/operations/operation-1/verify', expect.objectContaining({ body: { requestId } })))
})
it('cleanup preview includes registered backups while diagnostics remain device scoped', async () => {
  const backup = { id: 'backup-1', deviceId: devices[0].deviceId, bytes: 12, imageId: profile.imageId, sha256: 'digest', formatVersion: 1, state: 'ready', createdAt: '' }
  mocks.client.request.mockImplementation(async (path: string, init?: { method?: string; body?: { resourceIds?: string[]; deviceIds?: string[] } }) => {
    if (path.endsWith('/backups') && !init?.method) return [backup]
    if (path.endsWith('/cleanup/previews')) {
      expect(init?.body?.resourceIds).toEqual(expect.arrayContaining([devices[0].deviceId, 'backup-1']))
      return { items: [], confirmationDigest: 'digest' }
    }
    if (path.endsWith('/diagnostics')) {
      expect(init?.body?.deviceIds).toEqual([devices[0].deviceId])
      return { id: 'diagnostic-1', state: 'ready', createdAt: '' }
    }
    if (path.endsWith('/images')) return { items: [], total: 0, nextCursor: null }
    if (path.endsWith('/environment')) return environment
    if (path.endsWith('/devices')) return [devices[0]]
    if (path.endsWith('/profiles')) return [profile]
    return []
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await screen.findByRole('heading', { name: '数据维护' })
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
  await userEvent.click(screen.getByRole('button', { name: '创建并启动' }))
  await userEvent.click(await screen.findByRole('button', { name: '按原编号核实创建' }))
  expect(submit.mock.calls[0][0]).toEqual(submit.mock.calls[1][0])
  expect(submit.mock.calls[0][0]).toMatchObject({ quantity: 1, instanceType: 'persistent' })
})

it('hides archived profiles while copying the source configuration snapshot', async () => {
  const archived = { ...profile, id: 'archived-profile', name: '已归档环境', archived: true }
  const submit = vi.fn(async (_value: BatchRequest): Promise<void> => {})
  render(<CreateInstances profiles={[archived, profile]} source={devices[0]} sourceSnapshot={{ profileId: archived.id, width: 1080, height: 1920, locale: 'en-US', timezone: 'UTC' }} environment={environment} onBack={noop} onProfiles={noop} onSubmit={submit} />)
  expect(screen.queryByRole('option', { name: '已归档环境' })).not.toBeInTheDocument()
  expect(screen.getByLabelText('分辨率')).toHaveValue('1080x1920')
  await userEvent.click(screen.getByRole('button', { name: '创建并启动' }))
  await waitFor(() => expect(submit).toHaveBeenCalled())
  expect(submit.mock.calls[0][0]).toMatchObject({ width: 1080, height: 1920, locale: 'en-US', timezone: 'UTC' })
})
it('readonly console never enables navigation or installation during workflow ownership', async () => {
  render(<DeviceConsole device={devices[2]} session={fixtureSession(false)} run={runs[devices[2].deviceId]} image={images[devices[2].deviceId]} onBack={noop} onSession={noop} onOpen={noop} onManage={noop} onAllocate={noop} onRefresh={noop} />)
  expect(screen.getByRole('button', { name: '返回' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '暂停并接管' })).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '应用' }))
  expect(screen.getByRole('button', { name: '上传 APK' })).toBeDisabled()
})
