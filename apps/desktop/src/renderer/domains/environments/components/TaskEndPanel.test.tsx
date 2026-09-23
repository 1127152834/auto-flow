import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../../../shared/api/client'
import { TaskEndPanel } from './TaskEndPanel'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

const instance = {
  instanceId: 'inst-1',
  projectId: 'p',
  environmentId: null,
  state: 'active',
  source: 'fixedEnvironment',
  sourceContentGeneration: 1,
  instanceUseGeneration: 1,
  activeTaskId: 'task-1',
  activeRunId: 'run-1',
  maintenanceOperationId: null,
  profileId: 'profile',
  createdAt: '2026-09-17T00:00:00Z',
  updatedAt: '2026-09-17T00:00:00Z',
}

it('sends selected record targets and can repair a partial association', async () => {
  let instanceState = instance.state
  const request = vi.fn(async (path: string, _init?: { body?: Record<string, unknown> }) => {
    if (String(path).includes('/environment-instances')) return { items: [{ ...instance, state: instanceState }], page: 1, pageSize: 5, total: 1, sort: '-updatedAt' }
    if (String(path).includes('/tasks/task-1/end')) return {
      operation: { operationId: 'end-1' },
      outcome: { phase: 'saved_unlinked', complete: false, conflicts: [{ record: { projectId: 'p', tableId: 't' }, expectedLinkRevision: 1, currentLinkRevision: 2 }] },
    }
    if (String(path).includes('/repair')) return { operation: { operationId: 'repair-1' }, outcome: { phase: 'completed', complete: true, conflicts: [] } }
    throw new Error(`unexpected ${path}`)
  })
  const client = { request } as unknown as StreamingApiClient
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={cache}>
    <TaskEndPanel workspaceKey="w" instanceId="i" projectId="p" taskId="task-1" runId="run-1" executionGeneration={1} inputs={[{ alias: '主账号', recordRef: { projectId: 'p', tableId: 't', datasetGeneration: 'g', recordKey: { type: 'text', value: '主账号' } }, linkRevision: 1 }]} client={client} disabled={false} />
  </QueryClientProvider>)
  expect(await screen.findByText('主账号')).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '结束并保留' }))
  expect(request).toHaveBeenCalledWith('/api/v1/projects/p/tasks/task-1/end', expect.objectContaining({
    body: expect.objectContaining({
      retainEnvironment: expect.objectContaining({
        recordTargets: [expect.objectContaining({ expectedLinkRevision: 1, replaceAllowed: false })],
      }),
    }),
  }))
  await screen.findByRole('button', { name: '修复关联' })
  instanceState = 'cleaned'
  await act(async () => { cache.setQueryData(['w', 'i', 'environments', 'p', 'task-instance', 'task-1'], { ...instance, state: 'cleaned' }) })
  await screen.findByText('本次浏览器工作副本已清理，不能再次保存本次会话。')
  expect(screen.queryByRole('button', { name: '结束并保留' })).not.toBeInTheDocument()
  await userEvent.click(await screen.findByRole('button', { name: '修复关联' }))
  expect(request).toHaveBeenCalledWith('/api/v1/projects/p/environment-operations/end-1/repair', expect.objectContaining({
    body: { recordTargets: [expect.objectContaining({ expectedLinkRevision: 2, replaceAllowed: true })] },
  }))
  await waitFor(() => expect(screen.queryByRole('button', { name: '修复关联' })).not.toBeInTheDocument())
  expect(screen.queryByRole('button', { name: '结束并保留' })).not.toBeInTheDocument()
})

it('shows a cleaned work copy without offering to save it again', async () => {
  const request = vi.fn(async () => ({ items: [{ ...instance, state: 'cleaned' }], page: 1, pageSize: 5, total: 1, sort: '-updatedAt' }))
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <TaskEndPanel workspaceKey="w" instanceId="i" projectId="p" taskId="task-1" runId="run-1" executionGeneration={1} client={{ request } as unknown as StreamingApiClient} disabled={false} />
  </QueryClientProvider>)
  expect(await screen.findByText('本次浏览器工作副本已清理，不能再次保存本次会话。')).toBeVisible()
  expect(screen.queryByRole('button', { name: '结束并保留' })).not.toBeInTheDocument()
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  expect(request.mock.calls).toHaveLength(1)
})
