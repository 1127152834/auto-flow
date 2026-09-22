import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
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
