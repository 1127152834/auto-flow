import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { chooseOption, choiceTestEnvironment } from '../../../shared/testing/choice-user'

choiceTestEnvironment()
import { ApiProvider } from '../../../app/ApiProvider'
import type { InstalledKernel, ProfileRead, ProfileTestBrowserList } from '../../../shared/api/types'
import { BrowserManagementPage } from './BrowserManagementPage'

const kernel: InstalledKernel = { edition: 'public', version: '145.0.1.1', executablePath: '/kernels/public/145', size: 1024 }
export const workProfile: ProfileRead = {
  id: 'profile-work', name: '工作环境', description: '长期登录环境', startUrl: 'about:blank', locale: 'zh-CN', timezone: 'Asia/Shanghai',
  geoip: false, headless: false, humanize: true, humanPreset: 'default', userAgent: null, viewportJson: null, colorScheme: null,
  extensionPathsJson: [], expertArgsJson: [], browserVersion: kernel.version, browserEdition: kernel.edition, releaseChannel: 'stable',
  proxyMode: 'none', proxyId: null, proxyPoolId: null, fingerprintSeed: 12345,
  createdAt: '2026-09-12T00:00:00Z', updatedAt: '2026-09-12T00:00:00Z',
}
export const testProfile: ProfileRead = { ...workProfile, id: 'profile-test', name: '测试环境', description: '固定代理', proxyMode: 'proxy', proxyId: 'proxy-1', fingerprintSeed: 23456 }

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'content-type': 'application/json' } })

function fakeServer(initialProfiles: ProfileRead[], initialProfileError = false) {
  let sessions: ProfileTestBrowserList['items'] = []
  let statusError = false
  let closeResponse: Promise<Response> | undefined
  let values = [...initialProfiles]
  let profileError = initialProfileError
  let regenerateResponse: Promise<Response> | undefined
  const launchResponses = new Map<string, Promise<Response>>()
  const calls: Array<{ path: string; method: string; body?: Record<string, unknown> }> = []
  const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input)).pathname
    const method = init?.method ?? 'GET'
    const body = typeof init?.body === 'string' ? JSON.parse(init.body) as Record<string, unknown> : undefined
    calls.push({ path, method, body })
    if (path === '/api/v1/kernels/events') return new Response(new ReadableStream({ start(controller) {
      init?.signal?.addEventListener('abort', () => controller.error(new DOMException('Aborted', 'AbortError')), { once: true })
    } }))
    if (path === '/api/v1/profiles' && method === 'GET') return profileError
      ? json({ error: { code: 'SERVICE_UNAVAILABLE', message: '配置服务暂不可用', details: {}, requestId: 'request-list' } }, 503)
      : json({ items: values, total: values.length })
    if (path === '/api/v1/profiles/test-browsers') return statusError ? json({ error: { message: '状态同步失败' } }, 503) : json({ items: sessions })
    if (path.endsWith('/test-browser') && method === 'DELETE') {
      const response = closeResponse ? await closeResponse : new Response(null, { status: 204 })
      if (response.ok) sessions = sessions.filter((item) => item.profileId !== decodeURIComponent(path.split('/').at(-2)!))
      return response
    }
    if (path.endsWith('/test-browser') && method === 'POST') {
      const id = decodeURIComponent(path.split('/').at(-2)!)
      const response = await (launchResponses.get(id) ?? json({ sessionId: crypto.randomUUID(), profileId: id, fingerprintSeed: values.find((profile) => profile.id === id)!.fingerprintSeed, warning: null }, 201))
      if (response.ok) {
        const result = await response.clone().json()
        sessions = [...sessions.filter((item) => item.profileId !== id), { sessionId: result.sessionId, profileId: id, state: 'running' }]
      }
      return response
    }
    if (path.endsWith('/regenerate-fingerprint') && method === 'POST') {
      if (regenerateResponse) return regenerateResponse.then(async (response) => {
        if (response.ok) {
          const updated = await response.clone().json() as ProfileRead
          values = values.map((profile) => profile.id === updated.id ? updated : profile)
        }
        return response
      })
      const id = decodeURIComponent(path.split('/').at(-2)!)
      const current = values.find((profile) => profile.id === id)!
      const updated = { ...current, fingerprintSeed: current.fingerprintSeed + 1 }
      values = values.map((profile) => profile.id === id ? updated : profile)
      return json(updated)
    }
    if (path.startsWith('/api/v1/profiles/') && path.endsWith('/duplicate') && method === 'POST') {
      const sourceId = decodeURIComponent(path.split('/').at(-2)!)
      const source = values.find((profile) => profile.id === sourceId)!
      const copy = { ...source, id: `${source.id}-copy`, name: String(body?.name), fingerprintSeed: source.fingerprintSeed + 100 }
      values = [...values, copy]
      return json(copy, 201)
    }
    if (path.startsWith('/api/v1/profiles/') && method === 'DELETE') {
      const id = decodeURIComponent(path.split('/').at(-1)!)
      values = values.filter((profile) => profile.id !== id)
      return new Response(null, { status: 204 })
    }
    if (path === '/api/v1/kernels/installed') return json({ items: [kernel] })
    if (path === '/api/v1/profiles/environment-options') return json({
      locales: [{ value: 'zh-CN', label: '中文' }],
      timezones: [{ value: 'Asia/Shanghai', label: '上海' }],
      userAgentTemplates: [{ value: 'Catalog UA Chrome/{major}.0.0.0', label: '服务端 UA' }],
    })
    if (path === '/api/v1/kernels/default') return json({ revision: 1, kernel })
    if (path === '/api/v1/proxy-options') return json({ proxies: [{ id: 'proxy-1', name: '测试代理', enabled: true }], pools: [] })
    if (path === '/api/v1/kernels/catalog') return json({ wrapperVersion: '0.5.9', platform: 'darwin-arm64', catalogError: null, installed: [kernel], releases: [{ ...kernel, chromiumVersion: '145.0.1.1', releaseChannel: 'stable', publishedAt: null, archive: null, installed: true }] })
    if (path === '/api/v1/kernels/license') return json({ configured: false, valid: false, plan: null, expires: null, seats: null })
    throw new Error(`Unexpected request: ${method} ${path}`)
  })
  return {
    fetch,
    calls,
    setSessions(value: ProfileTestBrowserList['items']) { sessions = value },
    setStatusError(value: boolean) { statusError = value },
    setCloseResponse(value: Promise<Response>) { closeResponse = value },
    setLaunchResponse(profileId: string, response: Promise<Response>) { launchResponses.set(profileId, response) },
    setProfileError(value: boolean) { profileError = value },
    setRegenerateResponse(response: Promise<Response>) { regenerateResponse = response },
  }
}

function renderBrowserPage({ profiles = [workProfile, testProfile], disabled = false, onReconnect = vi.fn(), profileError = false }: { profiles?: ProfileRead[]; disabled?: boolean; onReconnect?: () => void; profileError?: boolean } = {}) {
  const server = fakeServer(profiles, profileError)
  vi.stubGlobal('fetch', server.fetch)
  const page = (isDisabled: boolean) => <ApiProvider baseUrl="http://127.0.0.1:43127" token="fixture-token" instanceId="fixture-instance"><BrowserManagementPage disabled={isDisabled} onReconnect={onReconnect} /></ApiProvider>
  const view = render(page(disabled))
  return { ...view, server, onReconnect, rerenderDisabled(next: boolean) { view.rerender(page(next)) } }
}

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
beforeEach(() => {
  vi.stubGlobal('ResizeObserver', ResizeObserverStub)
  Object.defineProperty(window, 'autoflow', { configurable: true, value: { revealKernel: vi.fn(async () => ({ revealed: true as const })) } })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('filters profiles by name and proxy mode without another write request', async () => {
  const user = userEvent.setup()
  const { server } = renderBrowserPage()
  await screen.findByText(workProfile.name)
  await user.type(screen.getByRole('searchbox'), '工作')
  expect(screen.getByText(workProfile.name)).toBeVisible()
  expect(screen.queryByText(testProfile.name)).not.toBeInTheDocument()
  await user.clear(screen.getByRole('searchbox'))
  await chooseOption(user, screen.getByLabelText('代理模式筛选'), 'proxy')
  expect(screen.getByText(testProfile.name)).toBeVisible()
  expect(screen.queryByText(workProfile.name)).not.toBeInTheDocument()
  expect(server.calls.filter((call) => call.method !== 'GET')).toHaveLength(0)
})

it('resets filters to page one and returns to a valid page after deleting its last item', async () => {
  const profiles = Array.from({ length: 11 }, (_, index) => ({ ...workProfile, id: `profile-${index + 1}`, name: `配置 ${String(index + 1).padStart(2, '0')}`, fingerprintSeed: 10000 + index }))
  const user = userEvent.setup()
  renderBrowserPage({ profiles })
  await screen.findByText('配置 01')
  await user.click(screen.getByRole('button', { name: '下一页' }))
  expect(screen.getByText('第 2 / 2 页')).toBeInTheDocument()
  expect(screen.getByText('配置 11')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '删除 配置 11' }))
  await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '确认删除' }))
  await waitFor(() => expect(screen.getByText('第 1 / 1 页')).toBeInTheDocument())
  expect(screen.getByText('配置 01')).toBeInTheDocument()

  await user.type(screen.getByRole('searchbox'), '配置 10')
  expect(screen.getByText('第 1 / 1 页')).toBeInTheDocument()
  expect(screen.getByText('配置 10')).toBeInTheDocument()
})

it('locks fingerprint regeneration until completion and reports success', async () => {
  let resolve!: (response: Response) => void
  const pending = new Promise<Response>((done) => { resolve = done })
  const user = userEvent.setup()
  const { server } = renderBrowserPage({ profiles: [workProfile] })
  server.setRegenerateResponse(pending)
  const button = await screen.findByRole('button', { name: `重新生成 ${workProfile.name} 的指纹` })
  await user.dblClick(button)
  await waitFor(() => expect(server.calls.filter((call) => call.path.endsWith('/regenerate-fingerprint'))).toHaveLength(1))
  expect(screen.getByText('生成中…')).toBeInTheDocument()
  expect(button).toBeDisabled()
  resolve(json({ ...workProfile, fingerprintSeed: 54321 }))
  expect(await screen.findByText(/指纹已重新生成：12345 → 54321/)).toBeInTheDocument()
  expect(screen.getByLabelText(`${workProfile.name} 的指纹种子`)).toHaveTextContent('54321')
})

it('renders a structured initial error and retries into the empty state', async () => {
  const user = userEvent.setup()
  const { server } = renderBrowserPage({ profiles: [], profileError: true })
  const error = await screen.findByRole('alert', {}, { timeout: 5000 })
  expect(error).toHaveTextContent('配置服务暂不可用')
  server.setProfileError(false)
  await user.click(within(error).getByRole('button', { name: '重试' }))
  expect(await screen.findByText('还没有浏览器配置')).toBeInTheDocument()
})

it('keeps stale profiles visible when a background refresh fails', async () => {
  const user = userEvent.setup()
  const { server } = renderBrowserPage({ profiles: [workProfile] })
  await screen.findByText(workProfile.name)
  server.setProfileError(true)
  await user.click(screen.getByRole('button', { name: `重新生成 ${workProfile.name} 的指纹` }))
  const stale = await screen.findByRole('alert', {}, { timeout: 5000 })
  expect(stale).toHaveTextContent('已加载的数据会继续保留')
  expect(screen.getByText(workProfile.name)).toBeInTheDocument()
  expect(screen.getByLabelText(`${workProfile.name} 的指纹种子`)).toHaveTextContent('12346')
})

it('keeps the form draft mounted while the nested kernel manager opens and restores focus', async () => {
  const user = userEvent.setup()
  renderBrowserPage({ profiles: [] })
  await user.click(await screen.findByRole('button', { name: '新建配置' }))
  await user.type(screen.getByLabelText('名称'), '未保存草稿')
  await user.click(screen.getByRole('tab', { name: '内核与代理' }))
  const trigger = screen.getByRole('button', { name: '管理内核' })
  await user.click(trigger)
  expect(await screen.findByRole('heading', { name: 'CloakBrowser 内核管理' })).toBeInTheDocument()
  const overlays = document.querySelectorAll('[data-slot="modal-overlay"]')
  expect(overlays).toHaveLength(2)
  expect([...overlays].every((overlay) => (overlay as HTMLElement).style.zIndex.includes('var(--layer-modal)'))).toBe(true)
  await user.click(screen.getByRole('button', { name: '关闭内核管理' }))
  await waitFor(() => expect(trigger).toHaveFocus())
  await user.click(screen.getByRole('tab', { name: '基础信息' }))
  expect(screen.getByLabelText('名称')).toHaveValue('未保存草稿')
})

it('preserves portal drafts, blocks offline writes, and reconnects from the active dialog', async () => {
  const onReconnect = vi.fn()
  const user = userEvent.setup()
  const view = renderBrowserPage({ onReconnect })
  await user.click(await screen.findByRole('button', { name: `复制 ${workProfile.name}` }))
  await user.type(screen.getByLabelText('新配置名称'), '离线副本')
  view.rerenderDisabled(true)
  const dialog = screen.getByRole('dialog')
  expect(within(dialog).getByLabelText('新配置名称')).toHaveValue('离线副本')
  expect(within(dialog).getByRole('button', { name: '创建副本' })).toBeDisabled()
  await user.click(within(dialog).getByRole('button', { name: '重新连接' }))
  expect(onReconnect).toHaveBeenCalledOnce()
  expect(view.server.calls.filter((call) => call.method === 'POST')).toHaveLength(0)
})

it('keeps an offline form draft without saving it automatically', async () => {
  const onReconnect = vi.fn()
  const user = userEvent.setup()
  const view = renderBrowserPage({ profiles: [], onReconnect })
  await user.click(await screen.findByRole('button', { name: '新建配置' }))
  await user.type(screen.getByLabelText('名称'), '断线草稿')
  view.rerenderDisabled(true)
  expect(screen.getByLabelText('名称')).toHaveValue('断线草稿')
  expect(screen.getByRole('button', { name: '创建配置' })).toBeDisabled()
  await user.click(screen.getByRole('button', { name: '重新连接' }))
  expect(onReconnect).toHaveBeenCalledOnce()
  expect(view.server.calls.filter((call) => call.method === 'POST')).toHaveLength(0)
})

it('blocks an already-open kernel or delete action while offline but still allows reconnect and close', async () => {
  const onReconnect = vi.fn()
  const user = userEvent.setup()
  const view = renderBrowserPage({ profiles: [workProfile], onReconnect })
  await user.click(await screen.findByRole('button', { name: `编辑 ${workProfile.name}` }))
  await user.click(screen.getByRole('tab', { name: '内核与代理' }))
  await user.click(screen.getByRole('button', { name: '管理内核' }))
  const manager = await screen.findByRole('dialog', { name: 'CloakBrowser 内核管理' })
  view.rerenderDisabled(true)
  expect(within(manager).getByRole('button', { name: '取消默认' })).toBeDisabled()
  expect(within(manager).getByRole('button', { name: '关闭内核管理' })).toBeEnabled()
  await user.click(within(manager).getByRole('button', { name: '重新连接' }))
  expect(onReconnect).toHaveBeenCalledOnce()
  expect(view.server.calls.filter((call) => call.method !== 'GET')).toHaveLength(0)
  await user.click(within(manager).getByRole('button', { name: '关闭内核管理' }))

  view.rerenderDisabled(false)
  await user.keyboard('{Escape}')
  await user.click(screen.getByRole('button', { name: `删除 ${workProfile.name}` }))
  view.rerenderDisabled(true)
  const confirmation = screen.getByRole('dialog', { name: '删除浏览器配置' })
  expect(within(confirmation).getByRole('button', { name: '确认删除' })).toBeDisabled()
  await user.click(within(confirmation).getByRole('button', { name: '重新连接' }))
  expect(onReconnect).toHaveBeenCalledTimes(2)
  expect(view.server.calls.filter((call) => call.method === 'DELETE')).toHaveLength(0)
})


it('retains running state, closes the browser, and keeps different cards independent', async () => {
  let resolve!: (response: Response) => void
  const pending = new Promise<Response>((done) => { resolve = done })
  const user = userEvent.setup()
  const { server } = renderBrowserPage()
  server.setLaunchResponse(workProfile.id, pending)
  const first = await screen.findByRole('button', { name: `打开 ${workProfile.name} 的测试浏览器` })
  const second = screen.getByRole('button', { name: `打开 ${testProfile.name} 的测试浏览器` })
  await user.dblClick(first)
  expect(server.calls.filter((call) => call.path.endsWith('/test-browser'))).toHaveLength(1)
  expect(first).toBeDisabled()
  expect(second).toBeEnabled()
  await user.click(second)
  expect(await screen.findByText(/测试环境 的测试浏览器已打开/)).toBeInTheDocument()
  expect(first).toBeDisabled()
  resolve(json({ sessionId: 'session-1', profileId: workProfile.id, fingerprintSeed: workProfile.fingerprintSeed, warning: null }, 201))
  await waitFor(() => expect(first).toBeEnabled())
  expect(first).toHaveAccessibleName(`关闭 ${workProfile.name} 的测试浏览器`)
  await user.click(first)
  expect(await screen.findByRole('button', { name: `打开 ${workProfile.name} 的测试浏览器` })).toBeEnabled()
  expect(server.calls.filter((call) => call.path.endsWith('/test-browser') && call.method === 'POST')).toHaveLength(2)
  expect(server.calls.filter((call) => call.path.endsWith('/test-browser') && call.method === 'DELETE')).toHaveLength(1)
  expect(server.calls.filter((call) => call.path.endsWith('/test-browser')).every((call) => call.body === undefined)).toBe(true)
})

it('shows launch failure on its own card, does not retry automatically, and blocks offline launches', async () => {
  const user = userEvent.setup()
  const view = renderBrowserPage()
  view.server.setLaunchResponse(workProfile.id, Promise.resolve(json({ error: { code: 'PROFILE_TEST_BROWSER_FAILED', message: '所选内核无法启动', details: {}, requestId: '' } }, 500)))
  await user.click(await screen.findByRole('button', { name: `打开 ${workProfile.name} 的测试浏览器` }))
  const card = screen.getByText(workProfile.name).closest('li')!
  expect(await within(card).findByRole('alert')).toHaveTextContent('所选内核无法启动')
  await user.click(screen.getByRole('button', { name: `打开 ${testProfile.name} 的测试浏览器` }))
  expect(within(card).getByRole('alert')).toHaveTextContent('所选内核无法启动')
  expect(view.server.calls.filter((call) => call.path.endsWith('/test-browser'))).toHaveLength(2)
  view.rerenderDisabled(true)
  expect(screen.getByRole('button', { name: `打开 ${workProfile.name} 的测试浏览器` })).toBeDisabled()
})

it('reports a navigation warning without claiming that the browser failed to open', async () => {
  const user = userEvent.setup()
  const { server } = renderBrowserPage({ profiles: [workProfile] })
  server.setLaunchResponse(workProfile.id, Promise.resolve(json({ sessionId: 'session-1', profileId: workProfile.id, fingerprintSeed: 12345, warning: '起始页面加载失败，请在窗口中重试。' }, 201)))
  await user.click(await screen.findByRole('button', { name: `打开 ${workProfile.name} 的测试浏览器` }))
  expect(await screen.findByRole('alert')).toHaveTextContent('测试浏览器已打开，但起始页面加载失败')
  expect(screen.getByRole('button', { name: `关闭 ${workProfile.name} 的测试浏览器` })).toBeEnabled()
})


it('reconciles native close and an existing session from backend polling', async () => {
  const { server } = renderBrowserPage({ profiles: [workProfile] })
  server.setSessions([{ profileId: workProfile.id, sessionId: 'existing', state: 'running' }])
  expect(await screen.findByRole('button', { name: `关闭 ${workProfile.name} 的测试浏览器` }, { timeout: 3000 })).toBeEnabled()
  expect(server.calls.filter((call) => call.method !== 'GET')).toHaveLength(0)
  server.setSessions([])
  expect(await screen.findByRole('button', { name: `打开 ${workProfile.name} 的测试浏览器` }, { timeout: 3000 })).toBeEnabled()
})

it('disables repeated close until completion and retains running state on close failure', async () => {
  const user = userEvent.setup()
  const { server } = renderBrowserPage({ profiles: [workProfile] })
  await user.click(await screen.findByRole('button', { name: `打开 ${workProfile.name} 的测试浏览器` }))
  let resolve!: (response: Response) => void
  server.setCloseResponse(new Promise((done) => { resolve = done }))
  const button = await screen.findByRole('button', { name: `关闭 ${workProfile.name} 的测试浏览器` })
  await user.dblClick(button)
  expect(button).toBeDisabled()
  expect(button).toHaveTextContent('正在关闭…')
  expect(server.calls.filter((call) => call.method === 'DELETE')).toHaveLength(1)
  resolve(json({ error: { code: 'PROFILE_TEST_BROWSER_UNAVAILABLE', message: '关闭失败，请重试', details: {}, requestId: 'close-test' } }, 503))
  expect(await screen.findByRole('alert')).toHaveTextContent('关闭失败')
  expect(button).toBeEnabled()
  expect(button).toHaveTextContent('关闭浏览器')
})

it('keeps last known running state and blocks actions when status synchronization fails', async () => {
  const user = userEvent.setup()
  const view = renderBrowserPage({ profiles: [workProfile] })
  await user.click(await screen.findByRole('button', { name: `打开 ${workProfile.name} 的测试浏览器` }))
  const close = await screen.findByRole('button', { name: `关闭 ${workProfile.name} 的测试浏览器` })
  view.server.setStatusError(true)
  expect(await screen.findByText(/浏览器运行状态同步失败/, {}, { timeout: 3000 })).toBeVisible()
  expect(close).toBeDisabled()
  view.server.setStatusError(false)
  await user.click(screen.getByRole('button', { name: '重试同步' }))
  await waitFor(() => expect(close).toBeEnabled())
  view.rerenderDisabled(true)
  expect(close).toBeDisabled()
})
