import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../../../shared/api/client'
import { runQueryKeys } from '../hooks'
import { BatchDetailPage } from './BatchDetailPage'

const baseBatch = {
  batchId: '00000000-0000-4000-8000-000000000002', projectId: '00000000-0000-4000-8000-000000000001', automationId: '00000000-0000-4000-8000-000000000003', automationName: '资料整理', startOperationId: 'start', status: 'running', statusRevision: 1, managementRevision: 1, requestedCount: 2, createdTaskCount: 2, activeTaskCount: 1, createdAt: '2026-09-15T00:00:00Z', completedAt: null,
}

beforeEach(() => {
  let sequence = 0
  vi.stubGlobal('crypto', { randomUUID: () => `00000000-0000-4000-8000-${String(++sequence).padStart(12, '0')}` })
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key) })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('can send force stop after a verified normal stop was accepted', async () => {
  let stopping = false
  const commands: string[] = []
  const request = vi.fn(async (path: string, init?: { method?: string; headers?: Record<string, string> }) => {
    if (path.endsWith(`/batches/${baseBatch.batchId}`) && !init?.method) {
      const batch = { ...baseBatch, status: stopping ? 'stopping' : 'running', statusRevision: stopping ? 2 : 1 }
      return { batch, statusCounts: { running: 1, queued: 1 }, taskCount: 2, stopOperation: null, forceStopAllowed: stopping, forceStopAvailableAt: stopping ? '2026-09-15T00:00:30Z' : null, configurationSnapshot: {} }
    }
    if (path.includes('/tasks?')) return { items: [], page: 1, pageSize: 50, total: 0, sort: 'createdAt' }
    if (path.endsWith('/stop')) {
      stopping = true; commands.push(path)
      return { operation: { operationId: 'stop', projectId: baseBatch.projectId, idempotencyKey: init?.headers?.['Idempotency-Key'], kind: 'stopBatch', status: 'running', statusRevision: 1, resource: { type: 'batch', projectId: baseBatch.projectId, batchId: baseBatch.batchId }, result: null, error: null, createdAt: '', updatedAt: '', completedAt: null } }
    }
    if (path.endsWith('/force-stop')) {
      commands.push(path)
      return { operation: { operationId: 'force', projectId: baseBatch.projectId, idempotencyKey: init?.headers?.['Idempotency-Key'], kind: 'forceStopBatch', status: 'running', statusRevision: 1, resource: { type: 'batch', projectId: baseBatch.projectId, batchId: baseBatch.batchId }, result: null, error: null, createdAt: '', updatedAt: '', completedAt: null } }
    }
    throw new Error(`unexpected ${path}`)
  }) as StreamingApiClient['request']
  const client = { request, stream: vi.fn(), health: vi.fn() } as StreamingApiClient
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={queryClient}><BatchDetailPage workspaceKey="workspace" instanceId="instance" projectId={baseBatch.projectId} batchId={baseBatch.batchId} client={client} disabled={false} readOnly={false} onNavigate={vi.fn()}/></QueryClientProvider>)
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: '停止批次' }))
  await user.click(screen.getByRole('button', { name: '确认停止' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '强制停止' })).toBeEnabled())
  await user.click(screen.getByRole('button', { name: '强制停止' }))
  expect(screen.getByRole('button', { name: '确认强制停止' })).toBeDisabled()
  expect(screen.getByText('自动化', { selector: 'dt' })).toBeVisible()
  expect(screen.getByText('1', { selector: 'dd' })).toBeVisible()
  await user.type(screen.getByRole('textbox', { name: '确认强制停止' }), '强制停止')
  await user.click(screen.getByRole('button', { name: '确认强制停止' }))
  await waitFor(() => expect(commands).toHaveLength(2))
  expect(commands[0]).toMatch(/\/stop$/)
  expect(commands[1]).toMatch(/\/force-stop$/)
})

it('refetches tasks once when the batch first enters a terminal state', async () => {
  let terminal = false
  let taskReads = 0
  const request = vi.fn(async (path: string) => {
    if (path.endsWith(`/batches/${baseBatch.batchId}`)) return { batch: { ...baseBatch, status: terminal ? 'completed' : 'running', statusRevision: terminal ? 2 : 1 }, statusCounts: terminal ? { completed: 2 } : { running: 1, queued: 1 }, taskCount: 2, stopOperation: null, forceStopAllowed: false, forceStopAvailableAt: null, configurationSnapshot: {} }
    if (path.includes('/tasks?')) { taskReads += 1; return { items: [], page: 1, pageSize: 50, total: 0, sort: 'createdAt' } }
    throw new Error(`unexpected ${path}`)
  }) as StreamingApiClient['request']
  const client = { request, stream: vi.fn(), health: vi.fn() } as StreamingApiClient
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={queryClient}><BatchDetailPage workspaceKey="workspace" instanceId="instance" projectId={baseBatch.projectId} batchId={baseBatch.batchId} client={client} disabled={false} readOnly={false} onNavigate={vi.fn()}/></QueryClientProvider>)
  await waitFor(() => expect(taskReads).toBe(1))
  terminal = true
  await queryClient.invalidateQueries({ queryKey: runQueryKeys.batch('workspace', 'instance', baseBatch.projectId, baseBatch.batchId) })
  await waitFor(() => expect(screen.getByText('已完成')).toBeVisible())
  await waitFor(() => expect(taskReads).toBe(2))
  await new Promise(resolve => setTimeout(resolve, 20))
  expect(taskReads).toBe(2)
})

it('does not offer force stop while the backend grace gate is closed', async () => {
  const request = vi.fn(async (path: string) => {
    if (path.endsWith(`/batches/${baseBatch.batchId}`)) return { batch: { ...baseBatch, status: 'stopping', statusRevision: 2 }, statusCounts: { stopping: 1, cancelled: 1 }, taskCount: 2, stopOperation: null, forceStopAllowed: false, forceStopAvailableAt: '2026-09-15T00:00:30Z', configurationSnapshot: {} }
    if (path.includes('/tasks?')) return { items: [], page: 1, pageSize: 50, total: 0, sort: 'createdAt' }
    throw new Error(`unexpected ${path}`)
  }) as StreamingApiClient['request']
  const client = { request, stream: vi.fn(), health: vi.fn() } as StreamingApiClient
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={queryClient}><BatchDetailPage workspaceKey="workspace" instanceId="instance" projectId={baseBatch.projectId} batchId={baseBatch.batchId} client={client} disabled={false} readOnly={false} onNavigate={vi.fn()}/></QueryClientProvider>)
  expect(await screen.findByText(/普通停止宽限期结束后才允许强制停止/)).toBeVisible()
  expect(screen.queryByRole('button', { name: '强制停止' })).not.toBeInTheDocument()
})
