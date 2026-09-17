import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import { choiceTestEnvironment } from '../../shared/testing/choice-user'
import type { Automation } from '../project-automations/types'
import { AutomationDetailPage } from '../project-automations/pages/AutomationDetailPage'

choiceTestEnvironment()

const INTERNAL_ID = '123e4567-e89b-42d3-a456-426614174000'
const AUTOMATION_ID = '223e4567-e89b-42d3-a456-426614174001'
const stored = new Map<string, string>()

beforeEach(() => {
  stored.clear()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => stored.get(key) ?? null,
    setItem: (key: string, value: string) => stored.set(key, value),
    removeItem: (key: string) => stored.delete(key),
  })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const automation: Automation = {
  automationId: AUTOMATION_ID,
  projectId: 'project',
  workflowId: 'workflow',
  name: '资料整理',
  description: '',
  managementRevision: 3,
  inputPlan: { inputs: [] },
  parameterSchema: [],
  environmentPolicy: { source: 'newFromProfile' },
  runPolicy: { maxTasks: 2, concurrency: 1, maxLiveInstances: 1, continueAfterFailure: false, automaticExecutionTimeoutSeconds: 900, manualDeadlineSeconds: 900 },
  createdAt: '2026-09-15T04:41:00Z',
  updatedAt: '2026-09-15T04:41:00Z',
}

const resourceResponse = (path: string) => {
  if (path === '/api/v1/workflows') return { items: [{ workflowId: 'workflow', name: '资料工作流', revision: 1, updatedAt: '', validation: { status: 'ready', runnable: true, issues: [] } }] }
  if (path === '/api/v1/model-providers') return { items: [], total: 0 }
  if (path === '/api/v1/profiles') return { items: [], total: 0 }
  if (path === '/api/v1/proxy-options') return { proxies: [], pools: [] }
  if (path.includes('/tables?')) return { items: [], total: 0, page: 1, pageSize: 200, sort: 'name' }
}

function mount(request: StreamingApiClient['request']) {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(<QueryClientProvider client={cache}><AutomationDetailPage workspaceKey="workspace" instanceId="instance" projectId="project" automationId={AUTOMATION_ID} client={{ request, stream: vi.fn(), health: vi.fn() }} disabled={false} readOnly={false} onCreated={vi.fn()} onBatchCreated={vi.fn()} registerLeaveGuard={vi.fn()} /></QueryClientProvider>)
  return cache
}

function expectNoPerceptibleIdentity(...ids: string[]) {
  for (const id of ids.length ? ids : [INTERNAL_ID, AUTOMATION_ID]) {
    expect(document.body.textContent).not.toContain(id)
    for (const element of document.body.querySelectorAll<HTMLElement>('[title], [placeholder], [aria-label], [aria-description]')) {
      for (const attribute of ['title', 'placeholder', 'aria-label', 'aria-description']) expect(element.getAttribute(attribute) ?? '').not.toContain(id)
    }
  }
}

it('maps an initial automation read failure without exposing the internal identity and keeps retry available', async () => {
  const requestMock = vi.fn(async (path: string) => {
    const resource = resourceResponse(path); if (resource) return resource
    if (path.endsWith(`/automations/${AUTOMATION_ID}/validation`)) return { status: 'ready', valid: true, runnable: true, issues: [], capabilityRequirements: [], checkedAt: '' }
    if (path.endsWith(`/automations/${AUTOMATION_ID}`)) throw new ApiClientError(`resource ${INTERNAL_ID} unavailable`, 503, 'RESOURCE_UNAVAILABLE')
    throw new Error(`unexpected ${path}`)
  })
  mount(requestMock as StreamingApiClient['request'])

  expect(await screen.findByText(/所需资源暂不可用，请检查配置/)).toBeVisible()
  expect(screen.getByRole('button', { name: '重试读取' })).toBeVisible()
  expectNoPerceptibleIdentity()
  await userEvent.setup().click(screen.getByRole('button', { name: '重试读取' }))
  await waitFor(() => expect(requestMock.mock.calls.filter(([path]) => String(path).endsWith(`/automations/${AUTOMATION_ID}`))).toHaveLength(2))
})

it('maps a resource read failure while preserving the dirty automation draft and retry action', async () => {
  const request = vi.fn(async (path: string) => {
    if (path === '/api/v1/workflows') throw new ApiClientError(`workflow ${INTERNAL_ID} unavailable`, 503, 'RESOURCE_UNAVAILABLE')
    const resource = resourceResponse(path); if (resource) return resource
    if (path.endsWith('/validation')) return { status: 'ready', valid: true, runnable: true, issues: [], capabilityRequirements: [], checkedAt: '' }
    if (path.endsWith(`/automations/${AUTOMATION_ID}`)) return automation
    throw new Error(`unexpected ${path}`)
  }) as StreamingApiClient['request']
  mount(request)
  const user = userEvent.setup()
  const name = await screen.findByLabelText('自动化名称')
  await user.clear(name); await user.type(name, '保留的草稿')

  expect(await screen.findByText(/所需资源暂不可用，请检查配置/)).toBeVisible()
  expect(name).toHaveValue('保留的草稿')
  expect(screen.getByRole('button', { name: '重新读取资料' })).toBeVisible()
  expectNoPerceptibleIdentity()
})

function validationRequest() {
  return vi.fn(async (path: string) => {
    const resource = resourceResponse(path); if (resource) return resource
    if (path.endsWith('/validation')) return { status: 'blocked', valid: true, runnable: false, issues: [{ code: 'UNKNOWN_VALIDATION_CODE', message: `node ${INTERNAL_ID} is unavailable`, path: ['workflowId'] }], capabilityRequirements: [], checkedAt: '' }
    if (path.endsWith(`/automations/${AUTOMATION_ID}`)) return automation
    throw new Error(`unexpected ${path}`)
  }) as StreamingApiClient['request']
}

it('maps an unknown validation issue on the editor while preserving the draft', async () => {
  mount(validationRequest())
  const user = userEvent.setup()
  const name = await screen.findByLabelText('自动化名称')
  await user.clear(name); await user.type(name, '验证中的草稿')
  await user.click(await screen.findByText('查看运行条件 · 尚未满足'))

  expect(screen.getByText('操作失败，请重试')).toBeVisible()
  expect(name).toHaveValue('验证中的草稿')
  expectNoPerceptibleIdentity()
})

it('maps an unknown validation issue in the real launch dialog without exposing its internal identity', async () => {
  mount(validationRequest())
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: '启动运行' }))

  const dialog = await screen.findByRole('dialog')
  expect(dialog).toBeVisible()
  expect(within(dialog).getByText('操作失败，请重试')).toBeVisible()
  expect(screen.getByRole('button', { name: '取消' })).toBeVisible()
  expectNoPerceptibleIdentity()
})
