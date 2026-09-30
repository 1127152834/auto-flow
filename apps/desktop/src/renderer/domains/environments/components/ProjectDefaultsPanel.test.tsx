import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApiClientError, type StreamingApiClient } from '../../../shared/api/client'
import type { ProjectView } from '../../projects/types'
import { ProjectDefaultsPanel } from './ProjectDefaultsPanel'

const project = { projectId: 'p', managementRevision: 4, defaultResources: { profileId: 'a', proxy: { mode: 'sourceDefault' }, modelProviderId: 'keep-model' } } as ProjectView
beforeEach(() => {
  HTMLElement.prototype.hasPointerCapture = () => false; HTMLElement.prototype.setPointerCapture = () => {}; HTMLElement.prototype.releasePointerCapture = () => {}; HTMLElement.prototype.scrollIntoView = () => {}
  const values = new Map<string, string>(); vi.stubGlobal('localStorage', { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key) })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
function mount(request: StreamingApiClient['request'], readOnly = false, initial = project) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ProjectDefaultsPanel project={initial} client={{ request } as StreamingApiClient} workspaceKey="w" instanceId="i" readOnly={readOnly} /></QueryClientProvider>)
}
const catalog = (path: string) => path.endsWith('/profiles') ? { items: [{ id: 'a', name: '模板 A' }, { id: 'b', name: '模板 B' }] } : { proxies: [], pools: [] }
it('saves browser defaults with the revision and preserves the model provider', async () => {
  const request = vi.fn(async (path, init) => init?.method === 'PATCH' ? { ...project, managementRevision: 5, defaultResources: (init.body as { defaultResources: unknown }).defaultResources } : catalog(path)) as unknown as StreamingApiClient['request']
  mount(request)
  const user = userEvent.setup()
  await user.click(await screen.findByRole('combobox', { name: '默认浏览器模板' }))
  await user.click(await screen.findByRole('option', { name: '模板 B' }))
  await user.click(screen.getByRole('button', { name: '保存默认设置' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '保存默认设置' })).toBeDisabled())
  expect(vi.mocked(request).mock.calls.find(([, init]) => init?.method === 'PATCH')?.[1]?.body).toEqual({ expectedManagementRevision: 4, defaultResources: { profileId: 'b', proxy: { mode: 'sourceDefault' }, modelProviderId: 'keep-model' } })
})
it('recovers a lost response after remount by looking up the original command', async () => {
  let key = '', offline = true
  const saved = { ...project, managementRevision: 5, defaultResources: { ...project.defaultResources, profileId: 'b' } }
  const request = vi.fn(async (path, init) => {
    if (init?.method === 'PATCH') { key = (init.headers as Record<string, string>)['Idempotency-Key']; throw new Error('lost response') }
    if (path.includes('/by-idempotency-key/')) { if (offline) throw new Error('offline'); expect(path).toContain(key); return { status: 'succeeded', kind: 'updateProject', resource: { type: 'project' }, result: saved } }
    return catalog(path)
  }) as unknown as StreamingApiClient['request']
  const user = userEvent.setup(); mount(request)
  await user.click(await screen.findByRole('combobox', { name: '默认浏览器模板' })); await user.click(await screen.findByRole('option', { name: '模板 B' }))
  await user.click(screen.getByRole('button', { name: '保存默认设置' }))
  expect(await screen.findByRole('button', { name: '核对保存结果' })).toBeEnabled()
  cleanup(); offline = false; mount(request)
  await user.click(await screen.findByRole('button', { name: '核对保存结果' }))
  await waitFor(() => expect(screen.getByRole('combobox', { name: '默认浏览器模板' })).toHaveTextContent('模板 B'))
  expect(vi.mocked(request).mock.calls.filter(([, init]) => init?.method === 'PATCH')).toHaveLength(1)
})
it('keeps the draft after a conflict and refuses unavailable defaults and read-only edits', async () => {
  const request = vi.fn(async (path, init) => { if (init?.method === 'PATCH') throw new ApiClientError('conflict', 409, 'REVISION_CONFLICT'); return catalog(path) }) as unknown as StreamingApiClient['request']
  const user = userEvent.setup(); mount(request)
  await user.click(await screen.findByRole('combobox', { name: '默认浏览器模板' })); await user.click(await screen.findByRole('option', { name: '模板 B' })); await user.click(screen.getByRole('button', { name: '保存默认设置' }))
  expect(await screen.findByRole('alert')).toBeVisible()
  expect(screen.getByRole('combobox', { name: '默认浏览器模板' })).toHaveTextContent('模板 B')
  cleanup(); mount(request, true, { ...project, defaultResources: { ...project.defaultResources, profileId: 'deleted' } })
  expect(await screen.findByText('默认模板不可用，请重新选择。')).toBeVisible()
  expect(screen.getByRole('combobox', { name: '默认浏览器模板' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '保存默认设置' })).toBeDisabled()
})
