import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import type { ProjectSummary } from './types'
import { ProjectsWorkspace } from './pages/ProjectsWorkspace'

const internal = '11111111-2222-4333-8444-555555555555'
const project = {
  projectId: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee', name: '资料项目', description: '', managementRevision: 1,
  lifecycleState: 'active', defaultResources: { profileId: null, proxy: { mode: 'none' }, modelProviderId: null },
  createdAt: '2026-09-15T00:00:00Z', updatedAt: '2026-09-15T00:00:00Z', lastOpenedAt: null,
  availability: { automations: 'available', data: 'available', runs: 'available', environments: 'available', statistics: 'notImplemented', sync: 'available' },
} satisfies ProjectSummary

class ResizeObserverStub { observe() {} unobserve() {} disconnect() {} }
beforeEach(() => {
  vi.stubGlobal('ResizeObserver', ResizeObserverStub)
  sessionStorage.clear()
  sessionStorage.setItem('autoflow:projects-ui:w1', JSON.stringify({ mode: 'all' }))
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

function mount(request: StreamingApiClient['request'], route: { projectId?: string; tab: 'overview' } = { tab: 'overview' }) {
  const client = { request, health: vi.fn(), stream: vi.fn() } as StreamingApiClient
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ProjectsWorkspace route={route} workspaceKey="w1" instanceId="i1" client={client} disabled={false} onNavigate={vi.fn()} registerLeaveGuard={vi.fn()} /></QueryClientProvider>)
}

function expectNoInternalIdentity() {
  for (const identity of [internal, project.projectId]) {
    expect(document.body.textContent).not.toContain(identity)
    for (const element of document.querySelectorAll('[title],[placeholder],[aria-label],[aria-description]')) {
      for (const attribute of ['title', 'placeholder', 'aria-label', 'aria-description']) expect(element.getAttribute(attribute) ?? '').not.toContain(identity)
    }
  }
}

it('maps a coded overview failure without exposing its internal diagnostic identity', async () => {
  const request = vi.fn((path: string) => path.endsWith('/overview')
    ? Promise.reject(new ApiClientError(`overview ${internal}`, 503, 'RESOURCE_UNAVAILABLE'))
    : Promise.resolve(project))
  mount(request as StreamingApiClient['request'], { projectId: project.projectId, tab: 'overview' })
  expect(await screen.findByRole('alert')).toHaveTextContent('所需资源暂不可用，请检查配置')
  expect(screen.getByRole('button', { name: '重试概览' })).toBeVisible()
  expectNoInternalIdentity()
})

it('maps an unknown open-project failure while preserving the real directory and retry operation', async () => {
  const request = vi.fn((path: string) => path.endsWith('/open')
    ? Promise.reject(new ApiClientError(`open ${internal}`, 500, 'UNKNOWN_OPEN_FAILURE'))
    : Promise.resolve({ items: [project], page: 1, pageSize: 50, total: 1, sort: '-lastOpenedAt' }))
  mount(request as StreamingApiClient['request'])
  await userEvent.setup().click(await screen.findByRole('button', { name: '资料项目' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('操作失败，请重试')
  expect(screen.getByRole('button', { name: '重试' })).toBeVisible()
  expect(screen.getByRole('button', { name: '资料项目' })).toBeVisible()
  await userEvent.setup().click(screen.getByRole('button', { name: '重试' }))
  await waitFor(() => expect(request.mock.calls.filter(([path]) => path.endsWith('/open'))).toHaveLength(2))
  expectNoInternalIdentity()
})
