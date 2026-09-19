import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../../../shared/api/client'
import { EnvironmentDetailPage } from './EnvironmentDetailPage'

const projectId = '00000000-0000-4000-8000-000000000001'
const environmentId = '00000000-0000-4000-8000-0000000000e1'
const operationId = '00000000-0000-4000-8000-0000000000op'

const environment = {
  environmentId, projectId, name: '登录态副本', state: 'ready', profileId: 'profile-1',
  notes: '', createdFromSource: 'manualSave', createdFromTaskId: null,
  ref: { contentGeneration: 3, metadataRevision: 5 },
  createdAt: '2026-09-18T00:00:00Z', updatedAt: '2026-09-19T00:00:00Z',
}

beforeEach(() => { vi.stubGlobal('crypto', { randomUUID: () => '00000000-0000-4000-8000-0000000000ff' }) })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const defaultOperation = {
  operationId, projectId, kind: 'deleteEnvironment', status: 'succeeded', idempotencyKey: '00000000-0000-4000-8000-0000000000ff',
  result: { target: { type: 'environment', projectId, environmentId }, deleted: true, detachedRecordCount: 2 },
  updatedAt: '2026-09-19T01:00:00Z', completedAt: '2026-09-19T01:02:00Z',
}

function harness(options: { blockers?: unknown[]; impacts?: unknown[]; operation?: unknown } = {}) {
  const blockers = options.blockers ?? []
  const impacts = options.impacts ?? []
  const operation = options.operation ?? defaultOperation
  const calls: { path: string; init?: { method?: string; headers?: Record<string, string>; body?: unknown } }[] = []
  const request = vi.fn(async (path: string, init?: { method?: string; headers?: Record<string, string>; body?: unknown }) => {
    calls.push({ path, init })
    if (path.endsWith('/impact?action=delete')) return { impactRevision: 4, impacts, blockers }
    if (path.endsWith(`/environments/${environmentId}`) && init?.method === 'DELETE') return { operation, outcome: 'deleted' }
    if (path.endsWith(`/environments/${environmentId}`)) return { environment, activeInstance: null, linkedRecordCount: 2 }
    if (path.includes('/profiles')) return { items: [{ id: 'profile-1', name: '公开版默认配置' }] }
    throw new Error(`unexpected ${path}`)
  }) as unknown as StreamingApiClient['request']
  const client = { request, stream: vi.fn(), health: vi.fn() } as unknown as StreamingApiClient
  const onNavigate = vi.fn()
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <EnvironmentDetailPage workspaceKey="w" instanceId="i" projectId={projectId} environmentId={environmentId} client={client} disabled={false} readOnly={false} onNavigate={onNavigate} />
  </QueryClientProvider>)
  return { calls, onNavigate }
}

it('lists the real delete impact and refuses to delete while an instance still occupies the environment', async () => {
  harness({
    impacts: [
      { code: 'ENVIRONMENT_CONTENT', resource: { type: 'environment', projectId, environmentId }, message: '持久环境 3 个已发布内容代次', blocking: false },
      { code: 'RECORDS_KEPT', resource: { type: 'environment', projectId, environmentId }, message: '关联记录保留，只解除引用', blocking: false },
    ],
    blockers: [{ code: 'INSTANCE_ACTIVE', resource: { type: 'environment', projectId, environmentId }, state: 'active', message: '现场实例仍在自动运行' }],
  })
  expect(await screen.findByText('• 持久环境 3 个已发布内容代次')).toBeVisible()
  expect(screen.getByText('• 删除被占用阻止：现场实例仍在自动运行（active）')).toBeVisible()
  expect(screen.getByRole('button', { name: '删除环境' })).toBeDisabled()
})

it('deletes with the frozen revisions and reports the published result with its audit trail', async () => {
  const user = userEvent.setup()
  const { calls, onNavigate } = harness({
    impacts: [{ code: 'ENVIRONMENT_CONTENT', resource: { type: 'environment', projectId, environmentId }, message: '持久环境 3 个已发布内容代次', blocking: false }],
  })
  await user.click(await screen.findByRole('button', { name: '删除环境' }))
  const confirm = (await screen.findAllByRole('button', { name: '删除环境' })).at(-1)!
  await user.click(confirm)
  expect(await screen.findByRole('heading', { name: '删除结果' })).toBeVisible()
  expect(screen.getByText('持久环境已删除')).toBeVisible()
  expect(screen.getByText('• 2 条记录的环境关联已解除')).toBeVisible()
  expect(screen.getByText(operationId)).toBeVisible()
  expect(screen.queryByText('• 关联记录保留，只解除引用')).toBeNull()
  await user.click(screen.getByRole('button', { name: '返回环境' }))
  expect(onNavigate).toHaveBeenCalledWith({ projectId, tab: 'environments' })
  const remove = calls.find(call => call.init?.method === 'DELETE')
  expect(remove?.path).toBe(`/api/v1/projects/${projectId}/environments/${environmentId}`)
  expect(remove?.init?.headers?.['Idempotency-Key']).toBe('00000000-0000-4000-8000-0000000000ff')
  expect(remove?.init?.body).toEqual({ impactRevision: 4, expectedMetadataRevision: 5, expectedContentGeneration: 3 })
})

it('separates an accepted command from a finished deletion instead of claiming the environment is gone', async () => {
  const user = userEvent.setup()
  harness({ operation: { operationId, projectId, kind: 'deleteEnvironment', status: 'running', idempotencyKey: '00000000-0000-4000-8000-0000000000ff', updatedAt: '2026-09-19T01:00:00Z' } })
  await user.click(await screen.findByRole('button', { name: '删除环境' }))
  await user.click((await screen.findAllByRole('button', { name: '删除环境' })).at(-1)!)
  expect(await screen.findByText('删除命令已被接受但尚未结束，请稍后重新打开环境页面核对结果。')).toBeVisible()
  expect(screen.queryByRole('heading', { name: '删除结果' })).toBeNull()
})
