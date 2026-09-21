import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { devices, environment, profile, fixtureSession, images, allocations, runs } from './prototype-fixtures'
import { ResourceBoard } from '../components/ResourceBoard'
import { CreateInstances } from '../components/CreateInstances'
import { DeviceConsole } from '../components/DeviceConsole'
const mocks = vi.hoisted(() => ({ client: { request: vi.fn(), stream: vi.fn() } }))
vi.mock('../../../app/ApiProvider', () => ({ useApi: () => ({ client: mocks.client, instanceId: 'instance' }) }))
vi.mock('../components/AndroidVideo', () => ({ AndroidVideo: () => <canvas aria-label="安卓触控画面" /> }))
import { AndroidPage } from '../pages/AndroidPage'
const noop = vi.fn()
afterEach(cleanup)
beforeEach(() => {
  vi.clearAllMocks()
  mocks.client.request.mockImplementation(async (path: string, init?: { method?: string }) => path.endsWith('/environment') ? environment : path.endsWith('/devices') ? [devices[0]] : path.endsWith('/profiles') ? [profile] : path.endsWith('/sessions') && init?.method === 'POST' ? fixtureSession(true) : path.endsWith('/sessions/fixture') ? fixtureSession(true) : path.endsWith('/apps') ? { packages: [], currentPackage: null, shellRoot: 'unknown', applicationRoot: 'unknown' } : path.endsWith('/actions') ? { ...fixtureSession(true), state: 'closed' } : [])
})
it('opens embedded control only on explicit click; refresh does not create a native window', async () => {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: '打开设备' }))
  await screen.findByRole('heading', { name: '手动控制中' })
  await waitFor(() => expect(mocks.client.request.mock.calls.filter(([path, init]) => path.endsWith('/sessions') && init?.method === 'POST')).toHaveLength(1))
  expect(mocks.client.request.mock.calls.some(([, init]) => init?.body?.action === 'native')).toBe(false)
  await userEvent.click(screen.getByRole('button', { name: '结束控制' }))
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/android/sessions/fixture/actions', expect.objectContaining({ body: expect.objectContaining({ action: 'end' }) })))
})
it('management home does not request retired workflow, allocation, or run endpoints', async () => {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AndroidPage /></QueryClientProvider>)
  await screen.findByText('安卓设备')
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalled())
  expect(mocks.client.request.mock.calls.map(([path]) => path).filter((path) => /workflows|allocations|\/runs/.test(path))).toEqual([])
  expect(screen.queryByRole('button', { name: '分配给工作流' })).not.toBeInTheDocument()
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
it('readonly console never enables navigation or installation during workflow ownership', async () => {
  render(<DeviceConsole device={devices[2]} session={fixtureSession(false)} run={runs[devices[2].deviceId]} image={images[devices[2].deviceId]} onBack={noop} onSession={noop} onOpen={noop} onManage={noop} onAllocate={noop} onRefresh={noop} />)
  expect(screen.getByRole('button', { name: '返回' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '暂停并接管' })).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '应用' }))
  expect(screen.getByRole('button', { name: '上传 APK' })).toBeDisabled()
})
