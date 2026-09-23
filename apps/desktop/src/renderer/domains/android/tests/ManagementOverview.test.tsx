import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ManagementOverview } from '../components/ManagementOverview'
import type { AndroidManagementApi } from '../management-api'

vi.mock('../components/DevicePreview', () => ({ DevicePreview: ({ device }: { device: { name: string } }) => <div aria-label={`${device.name}预览`} /> }))

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

it('shows the owned manual session in the list with return and explicit end actions', async () => {
  const onOpen = vi.fn(), onEndControl = vi.fn()
  const api = { devices: vi.fn(async () => ({ total: 1, nextCursor: null, items: [{ deviceId: 'd', revision: 2, name: '原生窗口设备', runtimeState: 'ready', owner: { kind: 'manualSession', id: 'session-1' }, observedAt: null, stale: false, specSnapshot: {}, latestOperation: null, allowedActions: ['return_to_console', 'end_control'], blockedReasons: {} }] })) } as unknown as AndroidManagementApi
  render(<QueryClientProvider client={new QueryClient()}><ManagementOverview api={api} onOpen={onOpen} onEndControl={onEndControl} /></QueryClientProvider>)
  await userEvent.click(await screen.findByRole('button', { name: '查看原生窗口设备控制会话' }))
  expect(onOpen).toHaveBeenCalledWith('d')
  await userEvent.click(screen.getByRole('button', { name: '结束原生窗口设备控制会话' }))
  expect(onEndControl).toHaveBeenCalledWith('d', 'session-1')
})

it('renders a readonly preview card for ready management devices when preview API is provided', async () => {
  const api = {
    devices: vi.fn(async () => ({ total: 1, nextCursor: null, items: [{ deviceId: 'ready', revision: 4, name: '就绪预览', runtimeState: 'ready', owner: { kind: 'none', id: null }, observedAt: null, stale: false, specSnapshot: { width: 720, height: 1280 }, latestOperation: null, allowedActions: [], blockedReasons: {} }] })),
  } as unknown as AndroidManagementApi
  render(<QueryClientProvider client={new QueryClient()}><ManagementOverview api={api} previewApi={{} as never} /></QueryClientProvider>)
  expect(await screen.findByLabelText('就绪预览预览')).toBeVisible()
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


it('shows a quarantined restore and one reason without start or open actions', async () => {
  const reason = '数据恢复尚未完成或核实；目标只能核实后永久删除'
  const api = { devices: vi.fn(async () => ({ total: 1, nextCursor: null, items: [{ deviceId: 'partial', revision: 3, name: '中断恢复', runtimeState: 'stopped', restoreState: 'pending', owner: { kind: 'none', id: null }, observedAt: null, stale: false, specSnapshot: {}, latestOperation: null, allowedActions: ['verify', 'delete'], blockedReasons: { start: reason, restart: reason, open: reason, backup: reason } }] })) } as unknown as AndroidManagementApi
  render(<QueryClientProvider client={new QueryClient()}><ManagementOverview api={api} onOpen={vi.fn()} onManage={vi.fn()} /></QueryClientProvider>)
  expect(await screen.findByText('恢复数据待核实')).toBeVisible()
  expect(screen.getAllByText(`阻塞原因：${reason}`)).toHaveLength(1)
  expect(screen.queryByRole('button', { name: '启动设备' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '打开中断恢复' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '核实状态' })).toBeEnabled()
})
