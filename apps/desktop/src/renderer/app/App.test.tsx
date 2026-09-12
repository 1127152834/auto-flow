import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import type { DesktopSettingsSnapshot } from '../../shared/settings'
import { App } from './App'

const ready = (token = 'test', instanceId = 'test', port = 43127) => ({ state: 'ready' as const, apiVersion: 'v1' as const, port, baseUrl: `http://127.0.0.1:${port}`, token, instanceId })
const settings: DesktopSettingsSnapshot = {
  preferences: { zoom: 100, motion: 'system' }, workspace: { path: '/tmp/autoflow', previousPath: null, paths: { workspace: '/tmp/autoflow', database: '/tmp/autoflow/data/autoflow.sqlite3', profiles: '/tmp/autoflow/workspace/profiles', kernels: '/tmp/autoflow/data/kernels', logs: '/tmp/autoflow/logs' }, blocked: false, blockers: [], recovery: null, needsSelection: false },
  service: { state: 'stopped', apiVersion: null, baseUrl: null, message: '服务离线' }, runtime: { appVersion: '0.1.0', electronVersion: '41', chromeVersion: '140', nodeVersion: '24', platform: 'macos', arch: 'arm64', backendVersion: null, pythonVersion: null, sqliteVersion: null }, operation: 'idle',
}
const dashboard = { profiles: 4, enabledProxies: 3, proxyGroups: 2, installedKernels: 1, modelProviders: 2, models: 6, generatedAt: '2026-09-12T00:00:00Z' }

beforeEach(() => {
  window.location.hash = '#/dashboard'
  vi.stubGlobal('autoflow', { getSidecarStatus: vi.fn(async () => ready()), restartSidecar: vi.fn(async () => ready()), getSettings: vi.fn(async () => ({ ok: true, value: settings })), setPreferences: vi.fn(), chooseWorkspace: vi.fn(), confirmWorkspace: vi.fn(), openSettingsDirectory: vi.fn(), previewDiagnostics: vi.fn(), saveDiagnostics: vi.fn(), quitApplication: vi.fn() })
  window.autoflow.getRuntimeContext = vi.fn(async () => ({ workspaceKey: settings.workspace.path, sidecar: await window.autoflow.getSidecarStatus(), preferences: settings.preferences, operation: 'idle' as const }))
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.location.hash = '' })

function payload(path: string) {
  if (path.endsWith('/health')) return { status: 'ok', apiVersion: 'v1', instanceId: 'test' }
  if (path.endsWith('/api/v1/dashboard')) return dashboard
  if (path.endsWith('/api/v1/model-providers')) return { items: [], total: 0 }
  if (path.endsWith('/api/v1/proxy-panel/connections')) return { items: [] }
  if (path.includes('/api/v1/proxy-groups')) return { items: [], offset: 0, limit: 100, matched_count: 0 }
  if (path.endsWith('/api/v1/profiles/test-browsers')) return { items: [] }
  if (path.endsWith('/api/v1/profiles')) return { items: [], total: 0 }
  if (path.endsWith('/api/v1/proxy-options')) return { proxies: [], pools: [] }
  if (path.endsWith('/api/v1/kernels/installed')) return { items: [] }
  if (path.endsWith('/api/v1/kernels/default')) return { revision: 0, kernel: null }
  if (path.endsWith('/api/v1/kernels/license')) return { configured: false, valid: false, plan: null, expires: null, seats: null }
  if (path.endsWith('/api/v1/kernels/catalog')) return { wrapperVersion: '0.5.9', platform: 'darwin-arm64', catalogError: null, installed: [], releases: [] }
  if (path.endsWith('/api/v1/kernels/events')) return {}
  throw new Error(`Unexpected request: ${path}`)
}

it('shows the default dashboard with real aggregate data', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => Response.json(payload(url))))
  render(<App />)
  expect(await screen.findByRole('heading', { name: '总览' })).toBeInTheDocument()
  expect(await screen.findByText('已启用代理')).toBeInTheDocument()
  expect(screen.getByText('6')).toBeInTheDocument()
  expect(screen.getByText('本地服务正常')).toBeInTheDocument()
})

it('keeps settings reachable while the sidecar is offline', async () => {
  vi.mocked(window.autoflow.getSidecarStatus).mockRejectedValue(new Error('offline'))
  vi.stubGlobal('fetch', vi.fn())
  render(<App />)
  await screen.findByRole('button', { name: '重新连接' })
  await userEvent.setup().click(screen.getByRole('button', { name: '设置' }))
  expect(await screen.findByRole('heading', { name: '设置' })).toBeInTheDocument()
  expect(screen.getByText('已停止')).toBeInTheDocument()
  expect(fetch).not.toHaveBeenCalled()
})

it('navigates to browser, model, and proxy management with their own requests', async () => {
  const paths: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string) => { paths.push(url); return Response.json(payload(url)) }))
  const user = userEvent.setup(); render(<App />)
  await screen.findByRole('heading', { name: '总览' })
  await user.click(screen.getByRole('button', { name: '浏览器配置' }))
  expect(await screen.findByText('还没有浏览器配置')).toBeInTheDocument()
  expect(paths.some(path => path.endsWith('/api/v1/profiles'))).toBe(true)
  await user.click(screen.getByRole('button', { name: '模型管理' }))
  expect(await screen.findByRole('heading', { name: '模型管理' })).toBeInTheDocument()
  expect(paths.some(path => path.endsWith('/api/v1/model-providers'))).toBe(true)
  await user.click(screen.getByRole('button', { name: '代理管理' }))
  expect(await screen.findByRole('heading', { name: '代理管理' })).toBeInTheDocument()
  expect(paths.some(path => path.endsWith('/api/v1/proxy-panel/connections'))).toBe(true)
})

it('waits for a starting sidecar before checking health', async () => {
  vi.mocked(window.autoflow.getSidecarStatus).mockResolvedValueOnce({ state: 'starting' }).mockResolvedValueOnce(ready())
  vi.stubGlobal('fetch', vi.fn(async (url: string) => Response.json(payload(url))))
  render(<App />)
  expect(await screen.findByText('本地服务正常')).toBeInTheDocument()
  expect(window.autoflow.getSidecarStatus).toHaveBeenCalledTimes(2)
})

it('restarts the sidecar and reconnects after the recovery action', async () => {
  const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError('network error')).mockImplementation(async (url: string) => Response.json(payload(url)))
  vi.stubGlobal('fetch', fetchMock); render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '重新连接' }))
  expect(await screen.findByText('本地服务正常')).toBeInTheDocument()
  expect(window.autoflow.restartSidecar).toHaveBeenCalledOnce()
})

it('reacquires the sidecar once after a model auth error and stops repeated recovery', async () => {
  window.location.hash = '#/models'; const requests: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string) => { requests.push(url); if (url.endsWith('/health')) return Response.json({ status: 'ok', apiVersion: 'v1', instanceId: 'test' }); return Response.json({ error: { code: 'SIDECAR_UNAUTHORIZED', message: '本地服务认证失效', details: {} } }, { status: 401 }) }))
  render(<App />)
  expect(await screen.findByRole('button', { name: '重新连接' })).toBeInTheDocument()
  await waitFor(() => expect(window.autoflow.getSidecarStatus).toHaveBeenCalledTimes(2))
  expect(requests.filter(url => url.endsWith('/model-providers'))).toHaveLength(2)
})

it('never replays a model-test POST after reacquiring sidecar credentials', async () => {
  window.location.hash = '#/models'
  const provider = { id: 'p1', name: 'Local fixture', providerKind: 'custom', baseUrl: 'http://127.0.0.1:1234/v1', presetId: 'custom', apiKeyConfigured: false, enabled: true, description: '', connectionStatus: 'untested', lastCheckedAt: null, lastCheckMessage: null, models: [{ id: 'm1', providerId: 'p1', modelKey: 'test-model', displayName: 'Test Model', tagsJson: [], enabled: true, contextWindow: null, description: '' }] }; let modelPosts = 0
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => { if (url.endsWith('/health')) return Response.json({ status: 'ok', apiVersion: 'v1', instanceId: 'test' }); if (init?.method === 'POST') { modelPosts++; return Response.json({ error: { code: 'SIDECAR_UNAUTHORIZED', message: '本地服务认证失效', details: {} } }, { status: 401 }) }; return Response.json({ items: [provider], total: 1 }) }))
  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: 'Test Model 测试模型' }))
  await waitFor(() => expect(window.autoflow.getSidecarStatus).toHaveBeenCalledTimes(2))
  expect(await screen.findByRole('button', { name: 'Test Model 测试模型' })).toBeEnabled()
  expect(modelPosts).toBe(1)
})

it('rebuilds the dashboard client after the sidecar instance changes without reusing the old token', async () => {
  vi.mocked(window.autoflow.getSidecarStatus).mockResolvedValueOnce(ready('old-token', 'old', 43127)).mockResolvedValue(ready('new-token', 'new', 43128))
  const dashboardTokens: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => { const token = new Headers(init?.headers).get('x-autoflow-token') ?? ''; if (url.endsWith('/health')) return Response.json({ status: 'ok', apiVersion: 'v1', instanceId: token === 'old-token' ? 'old' : 'new' }); if (url.endsWith('/api/v1/dashboard')) { dashboardTokens.push(token); return Response.json(dashboard) }; throw new Error(`Unexpected request: ${url}`) }))
  render(<App />)
  await screen.findByRole('heading', { name: '总览' })
  await waitFor(() => expect(dashboardTokens).toContain('new-token'), { timeout: 2500 })
  expect(dashboardTokens.slice(dashboardTokens.indexOf('new-token'))).toEqual(['new-token'])
})

it('keeps an open browser draft when a new sidecar instance replaces the token', async () => {
  window.location.hash = '#/profiles'
  vi.mocked(window.autoflow.getSidecarStatus).mockResolvedValueOnce(ready('old-token', 'old', 43127)).mockResolvedValue(ready('new-token', 'new', 43128))
  const requests: Array<{ token: string; path: string; method: string }> = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const path = new URL(url).pathname
    const token = new Headers(init?.headers).get('x-autoflow-token') ?? ''
    const method = init?.method ?? 'GET'
    requests.push({ token, path, method })
    if (path === '/api/v1/kernels/events') return new Response(new ReadableStream({ start(controller) {
      init?.signal?.addEventListener('abort', () => controller.error(new DOMException('Aborted', 'AbortError')), { once: true })
    } }))
    if (path === '/health') return Response.json({ status: 'ok', apiVersion: 'v1', instanceId: token === 'old-token' ? 'old' : 'new' })
    return Response.json(payload(url))
  }))
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: '新建配置' }))
  await user.type(screen.getByLabelText('名称'), '跨实例草稿')
  await waitFor(() => expect(requests.some((request) => request.token === 'new-token' && request.path === '/api/v1/profiles')).toBe(true), { timeout: 2500 })
  expect(screen.getByLabelText('名称')).toHaveValue('跨实例草稿')
  expect(requests.filter((request) => request.method !== 'GET')).toHaveLength(0)
})
