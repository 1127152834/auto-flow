import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../../../shared/api/client'
import { AutomationDirectoryPage } from './AutomationDirectoryPage'

const item = { automationId: 'a', projectId: 'p', name: '自动化', description: '', workflowId: 'wf', inputPlan: { inputs: [] }, parameterSchema: [], environmentPolicy: { source: 'newFromProfile' }, runPolicy: { maxTasks: 1, concurrency: 1, maxLiveInstances: 1, continueAfterFailure: false, automaticExecutionTimeoutSeconds: 900, manualDeadlineSeconds: 900 }, managementRevision: 1, createdAt: '2026-09-01T00:00:00Z', updatedAt: '2026-09-01T00:00:00Z' }
const page = { items: [item], total: 1, page: 1, pageSize: 50, sort: '-updatedAt' }
const storage = new Map<string, string>()
beforeEach(() => { storage.clear(); vi.stubGlobal('sessionStorage', { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value), clear: () => storage.clear() }) })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('isolates and restores controlled directory queries by workspace and project', async () => {
  const request = vi.fn().mockResolvedValue(page) as StreamingApiClient['request']
  const client = { request, stream: vi.fn(), health: vi.fn() }
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const props = { workspaceKey: 'one', instanceId: 'i', projectId: 'p', client, disabled: false, readOnly: false, onOpen: vi.fn(), onCreate: vi.fn() }
  const tree = (next = props) => <QueryClientProvider client={cache}><AutomationDirectoryPage {...next}/></QueryClientProvider>
  const view = render(tree())
  await userEvent.type(await screen.findByLabelText('搜索自动化'), '客户')
  expect(request).toHaveBeenCalledTimes(1)
  await userEvent.keyboard('{Enter}')
  await waitFor(() => expect(request).toHaveBeenLastCalledWith(expect.stringContaining('q=%E5%AE%A2%E6%88%B7'), expect.anything()))
  view.rerender(tree({ ...props, workspaceKey: 'two' }))
  expect(await screen.findByLabelText('搜索自动化')).toHaveValue('')
  view.rerender(tree(props))
  expect(await screen.findByLabelText('搜索自动化')).toHaveValue('客户')
})

it('does not render raw server diagnostics in the directory error state', async () => {
  const internal = '11111111-2222-4333-8444-555555555555'
  const request = vi.fn().mockRejectedValue(new Error(`failed ${internal}`)) as StreamingApiClient['request']
  const client = { request, stream: vi.fn(), health: vi.fn() }
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AutomationDirectoryPage workspaceKey="one" instanceId="i" projectId="p" client={client} disabled={false} readOnly={false} onOpen={vi.fn()} onCreate={vi.fn()}/></QueryClientProvider>)
  expect(await screen.findByText('自动化暂时无法加载')).toBeVisible()
  expect(document.body.textContent).not.toContain(internal)
})
