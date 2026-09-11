import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import type { ApiClient } from '../../../shared/api/client'
import { DashboardPage } from '../pages/DashboardPage'

afterEach(cleanup)
function renderPage(handler: () => Promise<unknown>, onNavigate = vi.fn()) {
  const client: ApiClient = { request: <T,>() => handler() as Promise<T>, health: vi.fn(async () => ({ status: 'ok' as const, apiVersion: 'v1', instanceId: 'test' })) }
  const query = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={query}><DashboardPage client={client} onNavigate={onNavigate} /></QueryClientProvider>)
  return onNavigate
}

it('shows factual counts and labels enabled proxies precisely', async () => {
  renderPage(vi.fn(async () => ({ profiles: 4, enabledProxies: 7, proxyGroups: 2, installedKernels: 1, modelProviders: 2, models: 9, generatedAt: '2026-09-12T00:00:00Z' })))
  expect(await screen.findByText('已启用代理')).toBeInTheDocument()
  expect(screen.queryByText('可用代理')).not.toBeInTheDocument()
  expect(screen.getByText('9')).toBeInTheDocument()
})

it('shows unavailable model aggregation without inventing zero', async () => {
  renderPage(vi.fn(async () => ({ profiles: 0, enabledProxies: 0, proxyGroups: 0, installedKernels: 0, modelProviders: null, models: null, generatedAt: '2026-09-12T00:00:00Z' })))
  expect(await screen.findAllByText('未接入')).toHaveLength(2)
  expect(screen.getByText(/还没有已配置的资源/)).toBeInTheDocument()
})

it('does not show the empty message when only a model provider exists', async () => {
  renderPage(vi.fn(async () => ({ profiles: 0, enabledProxies: 0, proxyGroups: 0, installedKernels: 0, modelProviders: 1, models: 0, generatedAt: '2026-09-12T00:00:00Z' })))
  await screen.findByText('模型供应商')
  expect(screen.queryByText(/还没有已配置的资源/)).not.toBeInTheDocument()
})

it('keeps entrances usable on load failure and retries', async () => {
  const request = vi.fn().mockRejectedValueOnce(new Error('服务离线')).mockResolvedValueOnce({ profiles: 0, enabledProxies: 0, proxyGroups: 0, installedKernels: 0, modelProviders: null, models: null, generatedAt: '2026-09-12T00:00:00Z' })
  const navigate = renderPage(request)
  const user = userEvent.setup()
  expect(await screen.findByRole('alert')).toHaveTextContent('服务离线')
  await user.click(screen.getByRole('button', { name: /查看本地设置/ }))
  expect(navigate).toHaveBeenCalledWith('settings')
  await user.click(screen.getByRole('button', { name: '重试' }))
  expect(await screen.findAllByText('未接入')).toHaveLength(2)
})
