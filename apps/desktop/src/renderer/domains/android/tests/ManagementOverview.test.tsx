import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ManagementOverview } from '../components/ManagementOverview'
import type { AndroidManagementApi } from '../management-api'

afterEach(cleanup)

it('renders snapshot devices and available actions without workflow data', async () => {
  const api = { devices: vi.fn(async () => ({ total: 1, nextCursor: null, items: [{ deviceId: 'd', revision: 2, name: '测试设备', runtimeState: 'ready', owner: { kind: 'none', id: null }, observedAt: null, stale: false, specSnapshot: {}, latestOperation: null, allowedActions: ['open', 'stop'], blockedReasons: {} }] })), operations: vi.fn(), environment: vi.fn(), capabilities: vi.fn(), images: vi.fn(), bulk: vi.fn(), bulkAction: vi.fn(), cleanupPreview: vi.fn(), cleanup: vi.fn(), diagnostics: vi.fn() } as unknown as AndroidManagementApi
  render(<QueryClientProvider client={new QueryClient()}><ManagementOverview api={api} onCreate={vi.fn()} onOpen={vi.fn()} onManage={vi.fn()} /></QueryClientProvider>)
  expect(await screen.findByText('测试设备')).toBeVisible()
  expect(screen.getByText('可操作：open、stop')).toBeVisible()
  expect(screen.getByRole('button', { name: '创建实例' })).toBeVisible()
  expect(screen.getByRole('button', { name: '打开测试设备' })).toBeVisible()
})

it('renders blocked reasons and translated stale status', async () => {
  const api = {
    devices: vi.fn(async () => ({
      total: 1,
      nextCursor: null,
      items: [{
        deviceId: 'blocked',
        revision: 3,
        name: '容量受限设备',
        runtimeState: 'unknown',
        owner: { kind: 'none', id: null },
        observedAt: null,
        stale: true,
        specSnapshot: {},
        latestOperation: null,
        allowedActions: [],
        blockedReasons: { capacity: '可用内存不足，等待容量释放' },
      }],
    })),
  } as unknown as AndroidManagementApi

  render(<QueryClientProvider client={new QueryClient()}><ManagementOverview api={api} /></QueryClientProvider>)

  expect(await screen.findByText('待核实', { selector: 'span' })).toBeVisible()
  expect(screen.getByText(/状态陈旧/)).toHaveTextContent('状态陈旧 · 待核实')
  expect(screen.getByText('阻塞原因：可用内存不足，等待容量释放')).toBeVisible()
})

it('does not offer to open a stopped instance', async () => {
  const api = {
    devices: vi.fn(async () => ({
      total: 1,
      nextCursor: null,
      items: [{ deviceId: 'stopped', revision: 1, name: '已停止设备', runtimeState: 'stopped', owner: { kind: 'none', id: null }, observedAt: null, stale: false, specSnapshot: {}, latestOperation: null, allowedActions: ['start'], blockedReasons: {} }],
    })),
  } as unknown as AndroidManagementApi

  render(<QueryClientProvider client={new QueryClient()}><ManagementOverview api={api} onOpen={vi.fn()} /></QueryClientProvider>)

  expect(await screen.findByRole('button', { name: '打开已停止设备' })).toBeDisabled()
})

it('shows status totals and filters by template and retained data', async () => {
  const api = {
    devices: vi.fn(async () => ({
      total: 3,
      nextCursor: null,
      items: [
        { deviceId: 'ready', revision: 1, name: '标准就绪', runtimeState: 'ready', owner: { kind: 'none', id: null }, observedAt: null, stale: false, specSnapshot: { profileId: 'p1', profileName: '标准模板', dataRetained: false }, latestOperation: null, allowedActions: [], blockedReasons: {} },
        { deviceId: 'stopped', revision: 1, name: '保留停止', runtimeState: 'retained', owner: { kind: 'none', id: null }, observedAt: null, stale: false, specSnapshot: { profileId: 'p2', profileName: '调试模板', dataRetained: true }, latestOperation: null, allowedActions: [], blockedReasons: {} },
        { deviceId: 'unknown', revision: 1, name: '待核实', runtimeState: 'unknown', owner: { kind: 'none', id: null }, observedAt: null, stale: false, specSnapshot: { profileId: 'p1', profileName: '标准模板', dataRetained: false }, latestOperation: null, allowedActions: ['verify'], blockedReasons: {} },
      ],
    })),
  } as unknown as AndroidManagementApi

  render(<QueryClientProvider client={new QueryClient()}><ManagementOverview api={api} /></QueryClientProvider>)
  expect(await screen.findByLabelText('实例统计')).toHaveTextContent('总数 3')
  expect(screen.getByLabelText('实例统计')).toHaveTextContent('运行中 1')
  expect(screen.getByLabelText('实例统计')).toHaveTextContent('已停止 1')
  expect(screen.getByLabelText('实例统计')).toHaveTextContent('需处理 1')
  await userEvent.selectOptions(screen.getByLabelText('筛选模板'), 'p2')
  expect(screen.getByText('保留停止')).toBeVisible()
  expect(screen.queryByText('标准就绪')).not.toBeInTheDocument()
  await userEvent.selectOptions(screen.getByLabelText('筛选数据'), 'retained')
  expect(screen.getByText('保留停止')).toBeVisible()
})

it('keeps the last snapshot and marks it stale when refresh disconnects', async () => {
  let disconnected = false
  const api = { devices: vi.fn(async () => disconnected ? Promise.reject(new Error('offline')) : { total: 1, nextCursor: null, items: [{ deviceId: 'd', revision: 1, name: '缓存设备', runtimeState: 'ready', owner: { kind: 'none', id: null }, observedAt: null, stale: false, specSnapshot: {}, latestOperation: null, allowedActions: ['start'], blockedReasons: {} }] }) } as unknown as AndroidManagementApi
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><ManagementOverview api={api} onManage={vi.fn()} /></QueryClientProvider>)
  expect(await screen.findByText('缓存设备')).toBeVisible()
  disconnected = true
  await client.invalidateQueries({ queryKey: ['android-management', 'default', 'devices'] })
  expect(await screen.findByRole('alert')).toHaveTextContent('连接已断开')
  expect(screen.getByText('缓存设备')).toBeVisible()
  expect(screen.getByText('修订 1 · 快照陈旧 · 已就绪')).toBeVisible()
  expect(screen.getByRole('button', { name: '启动设备' })).toBeDisabled()
})

it('does not execute operational actions for unknown or stale devices', async () => {
  const onManage = vi.fn()
  const api = { devices: vi.fn(async () => ({ total: 1, nextCursor: null, items: [{ deviceId: 'd', revision: 1, name: '待核实', runtimeState: 'unknown', owner: { kind: 'none', id: null }, observedAt: null, stale: true, specSnapshot: {}, latestOperation: null, allowedActions: ['start', 'verify'], blockedReasons: {} }] })) } as unknown as AndroidManagementApi
  render(<QueryClientProvider client={new QueryClient()}><ManagementOverview api={api} onManage={onManage} /></QueryClientProvider>)
  expect(await screen.findByRole('button', { name: '启动设备' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '核实状态' })).toBeEnabled()
  await userEvent.click(screen.getByRole('button', { name: '核实状态' }))
  expect(onManage).toHaveBeenCalledWith('d', 'verify', undefined, undefined)
})
