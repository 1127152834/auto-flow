import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../../../shared/api/client'
import { RunDirectoryPage } from './RunDirectoryPage'

const projectId = '00000000-0000-4000-8000-000000000001'
const manualItemId = '00000000-0000-4000-8000-00000000000d'
const taskId = '00000000-0000-4000-8000-00000000000e'
const runId = '00000000-0000-4000-8000-00000000000c'

const manualItem = {
  manualItemId, projectId, taskId, runId, instanceId: '00000000-0000-4000-8000-00000000000a',
  checkpointRevision: 3, status: 'waiting', statusRevision: 2, expiresAt: new Date(Date.now() + 13 * 60_000).toISOString(),
  allowedTargets: [], resumeStarted: false, reason: '需要人工完成验证码',
  createdAt: '2026-09-18T05:00:00Z', updatedAt: '2026-09-18T05:00:00Z',
}

afterEach(() => { cleanup(); sessionStorage.clear() })

function renderPage(view: 'batches' | 'tasks' | 'manual') {
  const request = vi.fn(async (path: string) => {
    if (path.includes('/manual-items?')) return { items: [manualItem], page: 1, pageSize: 50, total: 1 }
    if (path.includes('/batches')) return { items: [], page: 1, pageSize: 50, total: 0 }
    if (path.includes('/tasks')) return { items: [], page: 1, pageSize: 50, total: 0 }
    if (path.includes('/automations')) return { items: [], page: 1, pageSize: 200, total: 0 }
    throw new Error(`unexpected ${path}`)
  }) as unknown as StreamingApiClient['request']
  const client = { request, stream: vi.fn(), health: vi.fn() } as unknown as StreamingApiClient
  const onNavigate = vi.fn()
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={queryClient}><RunDirectoryPage workspaceKey="workspace" instanceId="instance" projectId={projectId} client={client} disabled={false} readOnly={false} view={view} onNavigate={onNavigate}/></QueryClientProvider>)
  const paths = () => (request as unknown as { mock: { calls: [string][] } }).mock.calls.map(([path]) => path)
  return { paths, onNavigate }
}

it('exposes the waiting-manual tab beside batches and tasks with the approved query', async () => {
  const { paths } = renderPage('manual')
  for (const tab of ['批次记录', '任务记录', '等待人工']) expect(screen.getByRole('tab', { name: tab })).toBeVisible()
  expect(screen.getByRole('tab', { name: '等待人工' })).toHaveAttribute('aria-selected', 'true')
  expect(await screen.findByText('需要人工完成验证码')).toBeVisible()
  // 默认只看等待处理，并按剩余保留时间排序
  await waitFor(() => expect(paths().some(path => path.includes('/manual-items?') && path.includes('status=waiting') && path.includes('sort=expiresAt'))).toBe(true))
  // 等待人工没有「运行记录排序」这种批次/任务专用控件
  expect(screen.queryByLabelText('运行记录排序')).not.toBeInTheDocument()
})

it('enters the single manual detail route from the directory row', async () => {
  const { onNavigate } = renderPage('manual')
  fireEvent.click(await screen.findByRole('button', { name: /查看事项/ }))
  expect(onNavigate).toHaveBeenCalledWith({ projectId, tab: 'runs', runView: 'manual', manualItemId })
})

it('keeps the batch and task views wired to their own routes', async () => {
  const { onNavigate } = renderPage('batches')
  expect(screen.getByRole('tab', { name: '批次记录' })).toHaveAttribute('aria-selected', 'true')
  await userEvent.click(screen.getByRole('tab', { name: '等待人工' }))
  expect(onNavigate).toHaveBeenCalledWith({ projectId, tab: 'runs', runView: 'manual' })
})

it('opens the manual item from a waiting task row and keeps the task link for the rest', async () => {
  const waiting = { taskId, projectId, batchId: runId, runId, runRequestId: runId, status: 'waiting_manual', statusRevision: 1, inputSnapshotId: 'snapshot', taskOrdinal: 14, automationName: '资料整理', batchStartedAt: null, inputIdentifier: 'R014', endNodeName: '人工核对', manualItemId, createdAt: '2026-09-18T05:00:00Z', completedAt: null }
  const succeeded = { ...waiting, taskId: '00000000-0000-4000-8000-0000000000f1', status: 'succeeded', taskOrdinal: 15, manualItemId: null, completedAt: '2026-09-18T05:10:00Z' }
  const request = vi.fn(async (path: string) => {
    if (path.includes('/tasks')) return { items: [waiting, succeeded], page: 1, pageSize: 50, total: 2 }
    if (path.includes('/batches')) return { items: [], page: 1, pageSize: 200, total: 0 }
    if (path.includes('/automations')) return { items: [], page: 1, pageSize: 200, total: 0 }
    throw new Error(`unexpected ${path}`)
  }) as unknown as StreamingApiClient['request']
  const client = { request, stream: vi.fn(), health: vi.fn() } as unknown as StreamingApiClient
  const onNavigate = vi.fn()
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><RunDirectoryPage workspaceKey="workspace" instanceId="instance" projectId={projectId} client={client} disabled={false} readOnly={false} view="tasks" onNavigate={onNavigate}/></QueryClientProvider>)
  // 只有真实挂在等待人工的事项才有入口，其它任务仍然进入任务详情
  expect(await screen.findByText('任务 14')).toBeVisible()
  expect(screen.getByRole('button', { name: /查看事项/ })).toBeVisible()
  expect(screen.getByRole('button', { name: /查看任务/ })).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: /查看事项/ }))
  expect(onNavigate).toHaveBeenCalledWith({ projectId, tab: 'runs', runView: 'manual', manualItemId })
  fireEvent.click(screen.getByRole('button', { name: /查看任务/ }))
  expect(onNavigate).toHaveBeenCalledWith({ projectId, tab: 'runs', taskId: succeeded.taskId, taskTab: 'logs' })
})
