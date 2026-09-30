import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../../../shared/api/client'
import { TaskEndPanel } from './TaskEndPanel'

beforeEach(() => { const values = new Map<string, string>(); vi.stubGlobal('localStorage', { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key) }) })
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

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
  const request = vi.fn(async (path: string, init?: { headers?: Record<string, string> }) => {
    if (path.includes('/environment-instances')) return { items: [] }
    if (path.endsWith('/tasks/task-1')) return { end: { ...durable, associationPhase: repaired ? 'completed' : 'saved_unlinked', repairTargets: [{ ...durable.repairTargets[0], currentLinkRevision: 7, currentEnvironmentId: 'other-env' }] }, run: { status: 'failed' } }
    if (path.endsWith('/environment-operations/save-1/repair')) { repaired = true; return { operation: { operationId: 'repair-1', projectId: 'p', idempotencyKey: init!.headers!['Idempotency-Key'], kind: 'repairEndAssociation', status: 'succeeded' }, outcome: { phase: 'completed' } } }
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

const repairRef = { projectId: 'p', tableId: 't', datasetGeneration: 'g', recordKey: { type: 'text', value: 'account' } }
const partialEnd = { operationId: 'end-1', saveOperationId: 'save-1', phase: 'saved_unlinked', associationPhase: 'saved_unlinked', repairTargets: [{ recordRef: repairRef, exists: true, currentLinkRevision: 7, currentEnvironmentId: null }] }
const approval = '确认按以上当前版本关联全部目标，并允许替换已有环境'
function repairUi(client: StreamingApiClient, instanceId = 'i') {
  return <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><TaskEndPanel workspaceKey="w" instanceId={instanceId} projectId="p" taskId="task-1" runId="run-1" executionGeneration={1} client={client} disabled={false} durableEnd={partialEnd} /></QueryClientProvider>
}
async function approveRepair() {
  await userEvent.click(screen.getByRole('button', { name: '读取当前关联并修复' }))
  await userEvent.click(await screen.findByRole('checkbox', { name: approval }))
  await userEvent.click(screen.getByRole('button', { name: '确认修复关联' }))
}

it.each([false, true])('recovers a committed repair with the original key, including reopen=%s', async reopen => {
  let key = '', committed = false, available = !reopen
  const request = vi.fn(async (path: string, init?: { headers?: Record<string, string> }) => {
    if (path.includes('/environment-instances')) return { items: [] }
    if (path.endsWith('/tasks/task-1')) return { end: { ...partialEnd, associationPhase: committed ? 'completed' : 'saved_unlinked' } }
    if (path.endsWith('/repair')) { key = init!.headers!['Idempotency-Key']; committed = true; throw new TypeError('response lost after commit') }
    if (path.includes('/operations/by-idempotency-key/')) {
      expect(path).toBe(`/api/v1/projects/p/operations/by-idempotency-key/${key}`)
      if (!available) throw new TypeError('offline')
      return { operationId: 'repair-1', projectId: 'p', idempotencyKey: key, kind: 'repairEndAssociation', status: 'succeeded' }
    }
    throw new Error(path)
  })
  const client = { request } as unknown as StreamingApiClient
  const mounted = render(repairUi(client))
  await approveRepair()
  if (reopen) {
    expect(await screen.findByRole('button', { name: '核对原修复操作' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '读取当前关联并修复' })).toBeDisabled()
    expect(screen.queryByRole('checkbox', { name: approval })).not.toBeInTheDocument()
    mounted.unmount()
    render(repairUi(client, 'reconnected'))
    expect(screen.getByRole('button', { name: '核对原修复操作' })).toBeEnabled()
    available = true
    await userEvent.click(screen.getByRole('button', { name: '核对原修复操作' }))
  }
  expect(await screen.findByText('关联已修复，历史运行失败事实保持不变。')).toBeVisible()
  expect(request.mock.calls.filter(([path]) => path.endsWith('/repair'))).toHaveLength(1)
})

it('revokes a late repair response on connection change and keeps its original pending key', async () => {
  let finish: (value: unknown) => void = () => undefined
  let key = ''
  const request = vi.fn(async (path: string, init?: { headers?: Record<string, string> }) => {
    if (path.includes('/environment-instances')) return { items: [] }
    if (path.endsWith('/tasks/task-1')) return { end: partialEnd }
    if (path.endsWith('/repair')) { key = init!.headers!['Idempotency-Key']; return new Promise(resolve => { finish = resolve }) }
    throw new Error(path)
  })
  const first = { request } as unknown as StreamingApiClient
  const nextRequest = vi.fn(async (path: string) => {
    if (path.includes('/environment-instances')) return { items: [] }
    throw new TypeError('new connection still offline')
  })
  const next = { request: nextRequest } as unknown as StreamingApiClient
  const mounted = render(repairUi(first))
  await approveRepair()
  mounted.rerender(repairUi(next))
  finish({ operation: { operationId: 'repair-1', projectId: 'p', idempotencyKey: key, kind: 'repairEndAssociation', status: 'succeeded' } })
  expect(await screen.findByRole('button', { name: '核对原修复操作' })).toBeEnabled()
  await userEvent.click(screen.getByRole('button', { name: '核对原修复操作' }))
  expect(nextRequest).toHaveBeenCalledWith(`/api/v1/projects/p/operations/by-idempotency-key/${key}`, undefined)
  expect(screen.getByRole('button', { name: '读取当前关联并修复' })).toBeDisabled()
  expect(nextRequest.mock.calls.some(([path]) => path.endsWith('/repair'))).toBe(false)
})

it('does not send a repair when its recovery key cannot be persisted', async () => {
  vi.spyOn(localStorage, 'setItem').mockImplementation(() => { throw new Error('storage unavailable') })
  const request = vi.fn(async (path: string) => path.includes('/environment-instances') ? { items: [] } : { end: partialEnd })
  render(repairUi({ request } as unknown as StreamingApiClient))
  await approveRepair()
  expect(await screen.findByRole('alert')).toBeVisible()
  expect(request.mock.calls.some(([path]) => path.endsWith('/repair'))).toBe(false)
})

it('does not carry pending repair authority into another workspace', async () => {
  const scope = `autoflow:end-repair:${JSON.stringify(['w', 'p', 'task-1', 'end-1'])}`
  localStorage.setItem(scope, JSON.stringify({ key: 'old-workspace-key' }))
  const request = vi.fn(async (_path: string) => ({ items: [] }))
  const client = { request } as unknown as StreamingApiClient
  const mounted = render(repairUi(client))
  expect(screen.getByRole('button', { name: '核对原修复操作' })).toBeEnabled()
  mounted.rerender(<QueryClientProvider client={new QueryClient()}><TaskEndPanel workspaceKey="other" instanceId="i" projectId="p" taskId="task-1" runId="run-1" executionGeneration={1} client={client} disabled={false} durableEnd={partialEnd} /></QueryClientProvider>)
  expect(screen.queryByRole('button', { name: '核对原修复操作' })).not.toBeInTheDocument()
  expect(request.mock.calls.some(call => String(call[0]).includes('old-workspace-key'))).toBe(false)
  expect(localStorage.getItem(scope)).toContain('old-workspace-key')
})
