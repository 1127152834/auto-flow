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
  let ended = false
  let repairCalls = 0
  const endResult = {
    operation: { operationId: 'end-1' },
    outcome: { phase: 'saved_unlinked', complete: false, conflicts: [{ record: { projectId: 'p', tableId: 't' }, expectedLinkRevision: 1, currentLinkRevision: 2 }] },
  }
  const request = vi.fn(async (path: string, init?: { method?: string; body?: Record<string, unknown> }) => {
    if (String(path).includes('/environment-instances')) return { items: [{ ...instance, state: instanceState }], page: 1, pageSize: 5, total: 1, sort: '-updatedAt' }
    if (String(path).includes('/tasks/task-1/end')) {
      if (init?.method !== 'POST') return ended ? { ...endResult, saveOperationId: 'save-1', associationPhase: repairCalls > 1 ? 'completed' : 'saved_unlinked', recordTargets: [{ recordRef: { projectId: 'p', tableId: 't' }, expectedLinkRevision: 1, replaceAllowed: false }] } : null
      ended = true
      return endResult
    }
    if (String(path).includes('/repair')) {
      repairCalls++
      return { operation: { operationId: `repair-${repairCalls}` }, outcome: repairCalls === 1 ? { phase: 'saved_unlinked', complete: false, conflicts: [{ record: { projectId: 'p', tableId: 't' }, currentLinkRevision: 3 }] } : { phase: 'completed', complete: true, conflicts: [] } }
    }
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
  await waitFor(() => expect(screen.getByRole('button', { name: '修复关联' })).toBeEnabled())
  expect(screen.queryByRole('button', { name: '结束并保留' })).not.toBeInTheDocument()
  instanceState = 'cleaned'
  await act(async () => { cache.setQueryData(['w', 'i', 'environments', 'p', 'task-instance', 'task-1', 0], { ...instance, state: 'cleaned' }) })
  await screen.findByText('本次浏览器工作副本已清理，不能再次保存本次会话。')
  expect(screen.queryByRole('button', { name: '结束并保留' })).not.toBeInTheDocument()
  await userEvent.click(await screen.findByRole('button', { name: '修复关联' }))
  expect(request).toHaveBeenCalledWith('/api/v1/projects/p/environment-operations/save-1/repair', expect.objectContaining({
    body: { recordTargets: [expect.objectContaining({ expectedLinkRevision: 2, replaceAllowed: false })] },
  }))
  await waitFor(() => expect(screen.getByRole('button', { name: '修复关联' })).toBeEnabled())
  await userEvent.click(screen.getByRole('button', { name: '修复关联' }))
  expect(request).toHaveBeenCalledWith('/api/v1/projects/p/environment-operations/save-1/repair', expect.objectContaining({
    body: { recordTargets: [expect.objectContaining({ expectedLinkRevision: 3, replaceAllowed: false })] },
  }))
  await waitFor(() => expect(screen.queryByRole('button', { name: '修复关联' })).not.toBeInTheDocument())
  expect(screen.queryByRole('button', { name: '结束并保留' })).not.toBeInTheDocument()
})

it('shows a cleaned work copy without offering to save it again', async () => {
  const request = vi.fn(async (path: string) => path.endsWith('/end') ? null : ({ items: [{ ...instance, state: 'cleaned' }], page: 1, pageSize: 5, total: 1, sort: '-updatedAt' }))
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <TaskEndPanel workspaceKey="w" instanceId="i" projectId="p" taskId="task-1" runId="run-1" executionGeneration={1} client={{ request } as unknown as StreamingApiClient} disabled={false} />
  </QueryClientProvider>)
  expect(await screen.findByText('本次浏览器工作副本已清理，不能再次保存本次会话。')).toBeVisible()
  expect(screen.queryByRole('button', { name: '结束并保留' })).not.toBeInTheDocument()
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  expect(request.mock.calls).toHaveLength(2)
})

it('recovers a worker End after remount and repairs the saved operation rather than its parent End', async () => {
  let repaired = false
  const request = vi.fn(async (path: string) => {
    if (path.includes('/environment-instances')) return { items: [{ ...instance, state: 'cleaned' }], page: 1, pageSize: 5, total: 1 }
    if (path.endsWith('/tasks/task-1/end')) return {
      operation: { operationId: 'parent-end', status: 'failed' }, saveOperationId: 'child-save',
      associationPhase: repaired ? 'completed' : 'saved_unlinked',
      recordTargets: [{ recordRef: { projectId: 'p', tableId: 't' }, expectedLinkRevision: 1, replaceAllowed: false }, { recordRef: { projectId: 'p', tableId: 'created' }, expectedLinkRevision: 1, replaceAllowed: false }],
      outcome: { phase: 'saved_unlinked', complete: false, conflicts: [{ record: { projectId: 'p', tableId: 't' }, currentLinkRevision: 2 }] },
    }
    if (path.endsWith('/environment-operations/child-save/repair')) {
      repaired = true
      return { operation: { operationId: 'repair-1' }, outcome: { phase: 'completed', complete: true, conflicts: [] } }
    }
    throw new Error(`unexpected ${path}`)
  })
  function mount() {
    return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <TaskEndPanel workspaceKey="w" instanceId="i" projectId="p" taskId="task-1" runId="run-1" executionGeneration={1} client={{ request } as unknown as StreamingApiClient} disabled={false} />
    </QueryClientProvider>)
  }
  const first = mount()
  const authorize = await screen.findByRole('checkbox', { name: '允许本次修复替换所选记录的现有关联' })
  expect(authorize).not.toBeChecked()
  await userEvent.click(authorize)
  await userEvent.click(await screen.findByRole('button', { name: '修复关联' }))
  await waitFor(() => expect(screen.queryByRole('button', { name: '修复关联' })).not.toBeInTheDocument())
  expect(request).toHaveBeenCalledWith('/api/v1/projects/p/environment-operations/child-save/repair', expect.objectContaining({ body: { recordTargets: [expect.objectContaining({ recordRef: { projectId: 'p', tableId: 't' }, expectedLinkRevision: 2, replaceAllowed: true }), expect.objectContaining({ recordRef: { projectId: 'p', tableId: 'created' }, expectedLinkRevision: 1, replaceAllowed: true })] } }))
  first.unmount()
  mount()
  await screen.findByText('已修复记录关联，原任务的失败结果保持不变。')
  expect(screen.queryByRole('button', { name: '修复关联' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '结束并保留' })).not.toBeInTheDocument()
})

it('reloads retention facts when the live Run status revision advances', async () => {
  let finished = false
  const request = vi.fn(async (path: string) => {
    if (path.includes('/environment-instances')) return { items: [{ ...instance, state: finished ? 'cleaned' : 'active' }], page: 1, pageSize: 5, total: 1 }
    if (path.endsWith('/end')) return finished ? { operation: { operationId: 'parent' }, saveOperationId: 'saved', associationPhase: 'saved_unlinked', recordTargets: [{ recordRef: { projectId: 'p', tableId: 't' }, expectedLinkRevision: 1, replaceAllowed: false }], outcome: { phase: 'saved_unlinked', conflicts: [] } } : null
    throw new Error(`unexpected ${path}`)
  })
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const view = (revision: number) => <QueryClientProvider client={cache}>
    <TaskEndPanel workspaceKey="w" instanceId="i" projectId="p" taskId="task-1" runId="run-1" executionGeneration={1} statusRevision={revision} client={{ request } as unknown as StreamingApiClient} disabled={false} />
  </QueryClientProvider>
  const panel = render(view(1))
  await screen.findByRole('button', { name: '结束并保留' })
  finished = true
  panel.rerender(view(2))
  expect(await screen.findByRole('button', { name: '修复关联' })).toBeEnabled()
  expect(screen.queryByRole('button', { name: '结束并保留' })).not.toBeInTheDocument()
})

it('retains corrected versions while repairing successive conflicts in a target group', async () => {
  const refs = ['a', 'b'].map(tableId => ({ projectId: 'p', tableId }))
  const submitted: number[][] = []
  const request = vi.fn(async (path: string, init?: { body?: { recordTargets: { expectedLinkRevision: number }[] } }) => {
    if (path.includes('/environment-instances')) return { items: [{ ...instance, state: 'cleaned' }] }
    if (path.endsWith('/end')) return {
      operation: { operationId: 'end' }, saveOperationId: 'save', associationPhase: 'saved_unlinked',
      recordTargets: refs.map(recordRef => ({ recordRef, expectedLinkRevision: 1, replaceAllowed: false })),
      outcome: { phase: 'saved_unlinked', conflicts: [{ record: refs[0], currentLinkRevision: 2 }] },
    }
    if (path.endsWith('/repair')) {
      submitted.push(init!.body!.recordTargets.map(target => target.expectedLinkRevision))
      return { operation: { operationId: `repair-${submitted.length}` }, outcome: { phase: 'saved_unlinked', conflicts: [{ record: refs[submitted.length === 1 ? 1 : 0], currentLinkRevision: 3 }] } }
    }
    throw new Error(`unexpected ${path}`)
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <TaskEndPanel workspaceKey="w" instanceId="i" projectId="p" taskId="task-1" runId="run-1" executionGeneration={1} client={{ request } as unknown as StreamingApiClient} disabled={false} />
  </QueryClientProvider>)
  for (let attempt = 0; attempt < 3; attempt++) {
    await waitFor(() => expect(screen.getByRole('button', { name: '修复关联' })).toBeEnabled())
    await userEvent.click(screen.getByRole('button', { name: '修复关联' }))
    await waitFor(() => expect(submitted).toHaveLength(attempt + 1))
  }
  expect(submitted).toEqual([[2, 1], [2, 3], [3, 3]])
})

it.each(['saved_unlinked', 'completed'])('does not save again when the child is %s before the parent End settles', async associationPhase => {
  const request = vi.fn(async (path: string) => path.endsWith('/end') ? {
    operation: { operationId: 'end', status: 'accepted' }, saveOperationId: 'save', associationPhase, outcome: null,
    recordTargets: [{ recordRef: { projectId: 'p', tableId: 't' }, expectedLinkRevision: 1, replaceAllowed: false }],
  } : { items: [{ ...instance, state: 'closed' }] })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <TaskEndPanel workspaceKey="w" instanceId="i" projectId="p" taskId="task-1" runId="run-1" executionGeneration={1} client={{ request } as unknown as StreamingApiClient} disabled={false} />
  </QueryClientProvider>)
  await waitFor(() => expect(request).toHaveBeenCalledTimes(2))
  await screen.findByRole('region', { name: /环境|结束/ })
  expect(screen.queryByRole('button', { name: '结束并保留' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '结束并关闭' })).not.toBeInTheDocument()
  if (associationPhase === 'saved_unlinked') expect(screen.getByRole('button', { name: '修复关联' })).toBeEnabled()
})

it('does not treat pending or failed End lookup as an absent saved result', async () => {
  let rejectLookup!: (error: Error) => void
  const pending = new Promise((_resolve, reject) => { rejectLookup = reject })
  const request = vi.fn(async (path: string) => path.endsWith('/end') ? pending : { items: [instance] })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <TaskEndPanel workspaceKey="w" instanceId="i" projectId="p" taskId="task-1" runId="run-1" executionGeneration={1} client={{ request } as unknown as StreamingApiClient} disabled={false} />
  </QueryClientProvider>)
  await waitFor(() => expect(request).toHaveBeenCalledTimes(2))
  expect(screen.getByRole('status')).toHaveTextContent('正在读取任务环境')
  expect(screen.queryByRole('button', { name: '结束并保留' })).not.toBeInTheDocument()
  await act(async () => rejectLookup(new Error('offline')))
  expect(await screen.findByRole('alert')).toHaveTextContent('保留结果读取失败')
  expect(screen.queryByRole('button', { name: '结束并保留' })).not.toBeInTheDocument()
})

it.each([['cleaned', false], ['active', true]] as const)('does not offer to retain a cleaned copy (%s, %s)', async (state, environmentCleaned) => {
  const client = { request: vi.fn(async (path: string) => path.endsWith('/end') ? null : { items: [{ ...instance, state }], page: 1, pageSize: 5, total: 1 }) } as unknown as StreamingApiClient
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <TaskEndPanel workspaceKey="w" instanceId="i" projectId="p" taskId="task-1" runId="run-1" executionGeneration={1} client={client} disabled={false} environmentCleaned={environmentCleaned}/>
  </QueryClientProvider>)
  expect(await screen.findByText('本次浏览器工作副本已清理，不能再次保存本次会话。')).toBeVisible()
  expect(screen.queryByRole('button', { name: '结束并保留' })).not.toBeInTheDocument()
})
