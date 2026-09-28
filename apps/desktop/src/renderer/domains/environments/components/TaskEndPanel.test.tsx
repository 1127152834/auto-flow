import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
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
