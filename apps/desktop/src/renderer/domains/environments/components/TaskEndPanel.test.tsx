import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
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
  const request = vi.fn(async (path: string, _init?: { body?: Record<string, unknown> }) => {
    if (String(path).includes('/environment-instances')) return { items: [instance], page: 1, pageSize: 5, total: 1, sort: '-updatedAt' }
    if (String(path).includes('/tasks/task-1/end')) return {
      operation: { operationId: 'end-1' },
      outcome: { phase: 'saved_unlinked', complete: false, conflicts: [{ record: { projectId: 'p', tableId: 't' }, expectedLinkRevision: 1, currentLinkRevision: 2 }] },
    }
    if (String(path).includes('/repair')) return { operation: { operationId: 'repair-1' }, outcome: { phase: 'completed', complete: true, conflicts: [] } }
    throw new Error(`unexpected ${path}`)
  })
  const client = { request } as unknown as StreamingApiClient
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
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
  expect(await screen.findByRole('button', { name: '修复关联' })).toBeEnabled()
  expect(screen.getByRole('button', { name: '结束并保留' })).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: '修复关联' }))
  expect(request).toHaveBeenCalledWith('/api/v1/projects/p/environment-operations/end-1/repair', expect.objectContaining({
    body: { recordTargets: [expect.objectContaining({ expectedLinkRevision: 2, replaceAllowed: true })] },
  }))
})

it.each([['cleaned', false], ['active', true]] as const)('does not offer to retain a cleaned copy (%s, %s)', async (state, environmentCleaned) => {
  const client = { request: vi.fn().mockResolvedValue({ items: [{ ...instance, state }], page: 1, pageSize: 5, total: 1 }) } as unknown as StreamingApiClient
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <TaskEndPanel workspaceKey="w" instanceId="i" projectId="p" taskId="task-1" runId="run-1" executionGeneration={1} client={client} disabled={false} environmentCleaned={environmentCleaned}/>
  </QueryClientProvider>)
  expect(await screen.findByText('临时环境已清理，无法再保留此工作副本；已保存的环境不受影响。')).toBeVisible()
  expect(screen.queryByRole('button', { name: '结束并保留' })).not.toBeInTheDocument()
})

it('reads a durable partial End and preserves its full error after reopening', () => {
  const client = { request: vi.fn() } as unknown as StreamingApiClient
  render(<QueryClientProvider client={new QueryClient()}>
    <TaskEndPanel workspaceKey="w" instanceId="i" projectId="p" taskId="task-1" runId="run-1" executionGeneration={2} client={client} disabled durableEnd={{ operationId: 'end-1', phase: 'saved_unlinked', businessResult: 'succeeded', outcome: { saved: { environmentId: 'saved-env', contentGeneration: 1 }, complete: false }, error: { code: 'LINK_REVISION_CONFLICT', message: '原目标关联已变化', details: { expectedRevision: 1, currentRevision: 2 } } }} />
  </QueryClientProvider>)
  expect(screen.getByText('上下文已保存，关联未完成')).toBeVisible()
  expect(screen.getByRole('alert')).toHaveTextContent('LINK_REVISION_CONFLICT')
  expect(screen.getByRole('alert')).toHaveTextContent('currentRevision')
  expect(screen.getByText(/saved-env/)).toBeVisible()
  expect(client.request).not.toHaveBeenCalled()
})

it('reopens durable partial End, confirms fresh versions, and repairs by save identity', async () => {
  const ref = { projectId: 'p', tableId: 't', datasetGeneration: 'g', recordKey: { type: 'text', value: 'account' } }
  const durable = { operationId: 'end-1', saveOperationId: 'save-1', phase: 'saved_unlinked', associationPhase: 'saved_unlinked', businessResult: 'succeeded', outcome: { saved: { environmentId: 'env' }, targets: [ref] }, repairTargets: [{ recordRef: ref, exists: true, currentLinkRevision: 2, currentEnvironmentId: null }] }
  let repaired = false
  const request = vi.fn(async (path: string) => {
    if (path.includes('/environment-instances')) return { items: [] }
    if (path.endsWith('/tasks/task-1')) return { end: { ...durable, associationPhase: repaired ? 'completed' : 'saved_unlinked', repairTargets: [{ ...durable.repairTargets[0], currentLinkRevision: 7, currentEnvironmentId: 'other-env' }] }, run: { status: 'failed' } }
    if (path.endsWith('/environment-operations/save-1/repair')) { repaired = true; return { outcome: { phase: 'completed' } } }
    throw new Error(`unexpected ${path}`)
  })
  const client = { request } as unknown as StreamingApiClient
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const ui = () => <QueryClientProvider client={cache}><TaskEndPanel workspaceKey="w" instanceId="i" projectId="p" taskId="task-1" runId="run-1" executionGeneration={1} client={client} disabled={false} durableEnd={durable} /></QueryClientProvider>
  const first = render(ui())
  first.unmount()
  render(ui())
  await userEvent.click(screen.getByRole('button', { name: '读取当前关联并修复' }))
  expect(await screen.findByText(/当前版本 7/)).toBeVisible()
  expect(screen.getByRole('button', { name: '确认修复关联' })).toBeDisabled()
  expect(request.mock.calls.filter(([path]) => path.endsWith('/repair'))).toHaveLength(0)
  await userEvent.click(screen.getByRole('checkbox', { name: '确认按以上当前版本关联全部目标，并允许替换已有环境' }))
  await userEvent.click(screen.getByRole('button', { name: '确认修复关联' }))
  expect(request).toHaveBeenCalledWith('/api/v1/projects/p/environment-operations/save-1/repair', expect.objectContaining({ body: { recordTargets: [{ recordRef: ref, expectedLinkRevision: 7, replaceAllowed: true }] } }))
  expect(await screen.findByRole('status')).toHaveTextContent('关联已修复，历史运行失败事实保持不变')
  expect(screen.queryByRole('button', { name: '确认修复关联' })).not.toBeInTheDocument()
})
