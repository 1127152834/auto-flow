import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../../../shared/api/client'
import type { Environment } from '../api'
import { EnvironmentConfigurationEditor } from './EnvironmentConfigurationEditor'

const environment = { ref: { projectId: 'p', environmentId: 'e', metadataRevision: 2, contentGeneration: 3 }, browserConfiguration: { proxy: { mode: 'none' }, kernel: { edition: 'public', version: '1' } } } as Environment
beforeEach(() => { HTMLElement.prototype.hasPointerCapture = () => false; HTMLElement.prototype.setPointerCapture = () => {}; HTMLElement.prototype.releasePointerCapture = () => {}; HTMLElement.prototype.scrollIntoView = () => {}; const values = new Map<string, string>(); vi.stubGlobal('localStorage', { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key) }) })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
function mount(request: StreamingApiClient['request'], disabled = false) {
  const onSaved = vi.fn()
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><EnvironmentConfigurationEditor environment={environment} client={{ request } as StreamingApiClient} workspaceKey="w" instanceId="i" disabled={disabled} onSaved={onSaved} /></QueryClientProvider>)
  return onSaved
}
const catalog = (path: string) => path.endsWith('/proxy-options') ? { proxies: [{ id: 'proxy', name: '本地代理', enabled: true }], pools: [] } : { items: [{ edition: 'public', version: '1' }] }
it('keeps the original settings command across a lost response and remount', async () => {
  let uncertain = true
  const request = vi.fn(async (path, init) => {
    if (init?.method === 'PATCH') { if (uncertain) throw new Error('offline'); return environment }
    if (path.includes('/by-idempotency-key/')) { if (uncertain) throw new Error('offline'); return { projectId: 'p', kind: 'updateEnvironment', status: 'running', idempotencyKey: path.split('/').at(-1), resource: { environmentId: 'e' } } }
    return catalog(path)
  }) as unknown as StreamingApiClient['request']
  const user = userEvent.setup()
  mount(request)
  await user.click(await screen.findByRole('combobox', { name: '代理策略' }))
  await user.click(await screen.findByRole('option', { name: '固定代理' }))
  await user.click(screen.getByRole('combobox', { name: /^代理$/ }))
  await user.click(await screen.findByRole('option', { name: '本地代理' }))
  await user.click(screen.getByRole('button', { name: '保存实例设置' }))
  expect(await screen.findByRole('button', { name: '核对并恢复保存' })).toBeEnabled()
  const original = vi.mocked(request).mock.calls.find(([, init]) => init?.method === 'PATCH')![1]
  expect(original?.body).toEqual({ expectedMetadataRevision: 2, expectedContentGeneration: 3, browserConfiguration: { proxy: { mode: 'fixed', proxyId: 'proxy' }, kernel: { edition: 'public', version: '1' } } })
  cleanup(); uncertain = false
  const saved = mount(request)
  await user.click(await screen.findByRole('button', { name: '核对并恢复保存' }))
  expect(saved).toHaveBeenCalledOnce()
  const writes = vi.mocked(request).mock.calls.filter(([, init]) => init?.method === 'PATCH')
  expect(writes.at(-1)![1]).toEqual(original)
  expect(localStorage.getItem('autoflow:environment-configuration:w:p:e')).toBeNull()
})
it('does not allow editing or saving an occupied or read-only instance', async () => {
  mount(vi.fn(async path => catalog(path)) as unknown as StreamingApiClient['request'], true)
  expect(await screen.findByRole('combobox', { name: '代理策略' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '保存实例设置' })).toBeDisabled()
})
