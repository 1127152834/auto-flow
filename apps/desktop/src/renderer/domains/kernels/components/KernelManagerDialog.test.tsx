import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useRef, useState } from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { ApiProvider } from '../../../app/ApiProvider'
import type { InstalledKernel, KernelCatalog, KernelOperation, License } from '../../../shared/api/types'
import { KernelManagerDialog } from './KernelManagerDialog'

const encoder = new TextEncoder()
const publicKernel: InstalledKernel = { edition: 'public', version: '146.0.1.1', executablePath: '/kernels/public/146', size: 104857600 }
const licensedKernel: InstalledKernel = { edition: 'licensed', version: '151.0.1.1', executablePath: '/kernels/licensed/151', size: 209715200 }
const invalidLicense: License = { configured: false, valid: false, plan: null, expires: null, seats: null }
const validLicense: License = { configured: true, valid: true, plan: 'pro', expires: null, seats: { active: 1, limit: 3 } }
const catalog: KernelCatalog = {
  wrapperVersion: '0.5.9', platform: 'darwin-arm64', catalogError: null, installed: [publicKernel],
  releases: [
    { edition: 'public', version: '146.0.1.1', chromiumVersion: '146.0.7680.80', releaseChannel: 'stable', publishedAt: '2026-09-01', archive: 'cloak-public.zip', size: 104857600, installed: true },
    { edition: 'licensed', version: '151.0.1.1', chromiumVersion: '151.0.7900.12', releaseChannel: 'preview', publishedAt: null, archive: null, size: null, installed: false },
  ],
}

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'content-type': 'application/json' } })
const eventFrame = (operations: KernelOperation[]) => encoder.encode(`event: snapshot\ndata: ${JSON.stringify({ type: 'snapshot', operations })}\n\n`)
const operation = (id: string, state: KernelOperation['state'], edition: 'public' | 'licensed' = 'public', releaseChannel: 'stable' | 'preview' = edition === 'public' ? 'stable' : 'preview'): KernelOperation => ({
  id, edition, requestedVersion: edition === 'public' ? '146.0.1.1' : '151.0.1.1', resolvedVersion: state === 'completed' ? (edition === 'public' ? '146.0.1.1' : '151.0.1.1') : null,
  releaseChannel, state, progress: null, message: null, error: state === 'failed' ? '网络中断' : null,
})

type ServerOptions = {
  catalog?: KernelCatalog | Error
  license?: License
  installed?: InstalledKernel[]
  route?(path: string, method: string, body: Record<string, unknown> | undefined): Response | Promise<Response> | undefined
}

function fakeServer(options: ServerOptions = {}) {
  let stream: ReadableStreamDefaultController<Uint8Array> | undefined
  let installedItems = options.installed ?? [publicKernel]
  let catalogReads = 0
  let installedReads = 0
  const calls: { path: string; method: string; body?: Record<string, unknown> }[] = []
  const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input)).pathname
    const method = init?.method ?? 'GET'
    const body = typeof init?.body === 'string' ? JSON.parse(init.body) as Record<string, unknown> : undefined
    calls.push({ path, method, body })
    const custom = options.route?.(path, method, body)
    if (custom) return await custom
    if (path === '/api/v1/kernels/events') return new Response(new ReadableStream({ start(controller) { stream = controller } }))
    if (path === '/api/v1/kernels/catalog') {
      catalogReads += 1
      return options.catalog instanceof Error ? json({ error: { code: 'CATALOG_UNAVAILABLE', message: options.catalog.message, details: {}, requestId: '' } }, 503) : json({ ...(options.catalog ?? catalog), installed: installedItems, releases: (options.catalog ?? catalog).releases.map((release) => ({ ...release, installed: installedItems.some((item) => item.edition === release.edition && item.version === release.version) })) })
    }
    if (path === '/api/v1/kernels/installed') { installedReads += 1; return json({ items: installedItems }) }
    if (path === '/api/v1/kernels/license' && method === 'GET') return json(options.license ?? invalidLicense)
    if (path === '/api/v1/kernels/default' && method === 'GET') return json({ revision: 0, kernel: null })
    if (path === '/api/v1/kernels/check-update' && method === 'POST') return json(options.catalog ?? catalog)
    throw new Error(`Unhandled request: ${method} ${path}`)
  })
  return {
    fetch,
    calls,
    get stream() { return stream },
    get catalogReads() { return catalogReads },
    get installedReads() { return installedReads },
    setInstalled(next: InstalledKernel[]) { installedItems = next },
  }
}

function Provider({ children }: { children: React.ReactNode }) {
  return <ApiProvider baseUrl="http://127.0.0.1:43127" token="secret" instanceId="instance-1">{children}</ApiProvider>
}

function ControlledManager({ selected = null }: { selected?: InstalledKernel | null }) {
  const [open, setOpen] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  return <><button ref={trigger} onClick={() => setOpen(true)}>管理内核</button><KernelManagerDialog open={open} onOpenChange={setOpen} selectedKernel={selected} returnFocusTo={trigger.current} /></>
}

beforeEach(() => {
  Object.defineProperty(window, 'autoflow', { configurable: true, value: { revealKernel: vi.fn(async () => ({ revealed: true as const })) } })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('keeps its filter while closed and restores focus to the profile trigger', async () => {
  const server = fakeServer()
  vi.stubGlobal('fetch', server.fetch)
  const user = userEvent.setup()
  render(<Provider><ControlledManager /></Provider>)
  await user.click(screen.getByRole('button', { name: '管理内核' }))
  await screen.findByText('CloakBrowser 146.0.1.1')
  await user.click(screen.getByRole('button', { name: '正式版' }))
  expect(screen.queryByText('CloakBrowser 146.0.1.1')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '关闭内核管理' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '管理内核' })).toHaveFocus())
  await user.click(screen.getByRole('button', { name: '管理内核' }))
  expect(screen.getByRole('button', { name: '正式版' })).toHaveAttribute('aria-pressed', 'true')
  expect(server.calls.filter((call) => call.path === '/api/v1/kernels/events')).toHaveLength(1)
})

it('keeps local kernels manageable when the remote catalog is offline', async () => {
  const server = fakeServer({ catalog: new Error('无法连接发布服务'), installed: [publicKernel] })
  vi.stubGlobal('fetch', server.fetch)
  render(<Provider><KernelManagerDialog open onOpenChange={vi.fn()} selectedKernel={null} /></Provider>)
  expect(await screen.findByText('CloakBrowser 146.0.1.1')).toBeInTheDocument()
  expect(await screen.findByRole('alert', {}, { timeout: 5000 })).toHaveTextContent('无法连接发布服务')
  expect(screen.getByRole('button', { name: '打开目录' })).toBeEnabled()
})

it('calls the cancel API and blocks closing until a terminal event refreshes installed data', async () => {
  const queued = operation('operation-1', 'queued')
  const server = fakeServer({ route(path, method) {
    if (path === '/api/v1/kernels/download' && method === 'POST') return json(queued, 202)
    if (path === '/api/v1/kernels/operations/operation-1/cancel' && method === 'POST') return json(operation('operation-1', 'cancelling'), 202)
  } })
  vi.stubGlobal('fetch', server.fetch)
  const user = userEvent.setup()
  render(<Provider><ControlledManager /></Provider>)
  await user.click(screen.getByRole('button', { name: '管理内核' }))
  await screen.findByText('CloakBrowser 146.0.1.1')
  await user.click(screen.getByRole('button', { name: '全部版本' }))
  const licensedCard = screen.getByText('CloakBrowser 151.0.1.1').closest('li') as HTMLElement
  expect(within(licensedCard).getByRole('button', { name: '需要 License' })).toBeDisabled()
  const publicCard = screen.getByText('CloakBrowser 146.0.1.1').closest('li') as HTMLElement
  // Installed releases do not download; stream a separate active operation for the existing card.
  act(() => server.stream?.enqueue(eventFrame([queued])))
  await waitFor(() => expect(within(publicCard).getByRole('button', { name: '取消下载' })).toBeEnabled())
  expect(screen.getByRole('button', { name: '关闭内核管理' })).toBeDisabled()
  await user.click(within(publicCard).getByRole('button', { name: '取消下载' }))
  expect(server.calls).toContainEqual(expect.objectContaining({ path: '/api/v1/kernels/operations/operation-1/cancel', method: 'POST' }))
  expect(screen.getByRole('button', { name: '关闭内核管理' })).toBeDisabled()
  const reads = server.installedReads
  act(() => server.stream?.enqueue(eventFrame([operation('operation-1', 'cancelled')])))
  await waitFor(() => expect(screen.getByRole('button', { name: '关闭内核管理' })).toBeEnabled())
  await waitFor(() => expect(server.installedReads).toBeGreaterThan(reads))
})

it('does not let a late cancelling response replace an SSE cancelled state', async () => {
  let resolveCancel!: (response: Response) => void
  const pendingCancel = new Promise<Response>((resolve) => { resolveCancel = resolve })
  const server = fakeServer({ route(path, method) {
    if (path === '/api/v1/kernels/operations/operation-1/cancel' && method === 'POST') return pendingCancel
  } })
  vi.stubGlobal('fetch', server.fetch)
  const user = userEvent.setup()
  render(<Provider><KernelManagerDialog open onOpenChange={vi.fn()} selectedKernel={null} /></Provider>)
  const card = (await screen.findByText('CloakBrowser 146.0.1.1')).closest('li') as HTMLElement
  act(() => server.stream?.enqueue(eventFrame([operation('operation-1', 'downloading')])))
  await user.click(await within(card).findByRole('button', { name: '取消下载' }))
  act(() => server.stream?.enqueue(eventFrame([operation('operation-1', 'cancelled')])))
  await within(card).findByText('下载已取消')
  resolveCancel(json(operation('operation-1', 'cancelling'), 202))
  await waitFor(() => expect(screen.getByRole('button', { name: '关闭内核管理' })).toBeEnabled())
  expect(within(card).getByText('下载已取消')).toBeInTheDocument()
})

it('retries a failed operation with a new operation id', async () => {
  const server = fakeServer({ license: validLicense, route(path, method, body) {
    if (path === '/api/v1/kernels/download' && method === 'POST') {
      expect(body).toEqual({ edition: 'licensed', version: '151.0.1.1', releaseChannel: 'preview' })
      return json(operation('operation-2', 'queued', 'licensed'), 202)
    }
  } })
  vi.stubGlobal('fetch', server.fetch)
  const user = userEvent.setup()
  render(<Provider><KernelManagerDialog open onOpenChange={vi.fn()} selectedKernel={null} /></Provider>)
  await screen.findByText('CloakBrowser 151.0.1.1')
  act(() => server.stream?.enqueue(eventFrame([operation('operation-1', 'failed', 'licensed')])))
  await user.click(await screen.findByRole('button', { name: '重试下载' }))
  await waitFor(() => expect(screen.getByText('准备下载')).toBeInTheDocument())
  expect(server.calls.filter((call) => call.path === '/api/v1/kernels/download')).toHaveLength(1)
})

it('shows same-version channels separately and downloads each channel payload', async () => {
  const dualCatalog: KernelCatalog = { ...catalog, releases: [
    { ...catalog.releases[1], releaseChannel: 'stable' },
    { ...catalog.releases[1], releaseChannel: 'preview' },
  ] }
  let nextId = 1
  const server = fakeServer({ catalog: dualCatalog, license: validLicense, route(path, method, body) {
    if (path === '/api/v1/kernels/download' && method === 'POST') return json(operation(`operation-${nextId++}`, 'failed', 'licensed', body?.releaseChannel as 'stable' | 'preview'), 202)
  } })
  vi.stubGlobal('fetch', server.fetch)
  const user = userEvent.setup()
  render(<Provider><KernelManagerDialog open onOpenChange={vi.fn()} selectedKernel={null} /></Provider>)
  await waitFor(() => expect(screen.getAllByText('CloakBrowser 151.0.1.1')).toHaveLength(2))
  const stableCard = screen.getByText('Stable').closest('li') as HTMLElement
  const previewCard = screen.getByText('Preview').closest('li') as HTMLElement
  await user.click(within(stableCard).getByRole('button', { name: '下载安装' }))
  await user.click(within(previewCard).getByRole('button', { name: '下载安装' }))
  expect(server.calls.filter((call) => call.path === '/api/v1/kernels/download').map((call) => call.body)).toEqual([
    { edition: 'licensed', version: '151.0.1.1', releaseChannel: 'stable' },
    { edition: 'licensed', version: '151.0.1.1', releaseChannel: 'preview' },
  ])
})

it('keeps an SSE terminal state when an older download response arrives later', async () => {
  let resolveDownload!: (response: Response) => void
  const pendingDownload = new Promise<Response>((resolve) => { resolveDownload = resolve })
  const server = fakeServer({ license: validLicense, route(path, method) {
    if (path === '/api/v1/kernels/download' && method === 'POST') return pendingDownload
  } })
  vi.stubGlobal('fetch', server.fetch)
  const user = userEvent.setup()
  render(<Provider><KernelManagerDialog open onOpenChange={vi.fn()} selectedKernel={null} /></Provider>)
  const card = (await screen.findByText('CloakBrowser 151.0.1.1')).closest('li') as HTMLElement
  await user.click(within(card).getByRole('button', { name: '下载安装' }))
  await waitFor(() => expect(server.calls.some((call) => call.path === '/api/v1/kernels/download')).toBe(true))
  act(() => server.stream?.enqueue(eventFrame([operation('race-operation', 'queued', 'licensed')])))
  await within(card).findByText('准备下载')
  act(() => server.stream?.enqueue(eventFrame([operation('race-operation', 'completed', 'licensed')])))
  await within(card).findByText('安装完成')
  await waitFor(() => expect(server.installedReads).toBe(2))
  expect(server.catalogReads).toBe(2)
  resolveDownload(json(operation('race-operation', 'queued', 'licensed'), 202))
  await waitFor(() => expect(screen.getByRole('button', { name: '关闭内核管理' })).toBeEnabled())
  expect(within(card).getByText('安装完成')).toBeInTheDocument()
  expect(server.installedReads).toBe(2)
  expect(server.catalogReads).toBe(2)
})

it('disables a second download while another release is active but keeps cancel available', async () => {
  const extraRelease = { edition: 'public' as const, version: '147.0.1.1', chromiumVersion: '147.0.1.1', releaseChannel: 'stable' as const, publishedAt: null, archive: null, size: null, installed: false }
  const server = fakeServer({ license: validLicense, catalog: { ...catalog, releases: [...catalog.releases, extraRelease] } })
  vi.stubGlobal('fetch', server.fetch)
  const user = userEvent.setup()
  render(<Provider><KernelManagerDialog open onOpenChange={vi.fn()} selectedKernel={null} /></Provider>)
  const secondCard = (await screen.findByText('CloakBrowser 147.0.1.1')).closest('li') as HTMLElement
  act(() => server.stream?.enqueue(eventFrame([operation('operation-1', 'downloading', 'licensed')])))
  const activeCard = screen.getByText('CloakBrowser 151.0.1.1').closest('li') as HTMLElement
  await waitFor(() => expect(within(activeCard).getByRole('button', { name: '取消下载' })).toBeEnabled())
  expect(within(secondCard).getByRole('button', { name: '下载安装' })).toBeDisabled()
  await user.click(within(secondCard).getByRole('button', { name: '下载安装' }))
  expect(server.calls.filter((call) => call.path === '/api/v1/kernels/download')).toHaveLength(0)
})

it('keeps a POST-created task after an older snapshot omits its id', async () => {
  const extraRelease = { edition: 'public' as const, version: '147.0.1.1', chromiumVersion: '147.0.1.1', releaseChannel: 'stable' as const, publishedAt: null, archive: null, size: null, installed: false }
  const server = fakeServer({ license: validLicense, catalog: { ...catalog, releases: [...catalog.releases, extraRelease] }, route(path, method) {
    if (path === '/api/v1/kernels/download' && method === 'POST') return json(operation('operation-new', 'queued', 'licensed'), 202)
  } })
  vi.stubGlobal('fetch', server.fetch)
  const user = userEvent.setup()
  render(<Provider><KernelManagerDialog open onOpenChange={vi.fn()} selectedKernel={null} /></Provider>)
  const activeCard = (await screen.findByText('CloakBrowser 151.0.1.1')).closest('li') as HTMLElement
  const secondCard = screen.getByText('CloakBrowser 147.0.1.1').closest('li') as HTMLElement
  await user.click(within(activeCard).getByRole('button', { name: '下载安装' }))
  await within(activeCard).findByText('准备下载')
  act(() => server.stream?.enqueue(eventFrame([operation('operation-old', 'failed', 'licensed')])))
  await waitFor(() => expect(within(activeCard).getByRole('button', { name: '取消下载' })).toBeEnabled())
  expect(within(activeCard).queryByText('网络中断')).not.toBeInTheDocument()
  expect(within(secondCard).getByRole('button', { name: '下载安装' })).toBeDisabled()
  await user.click(within(secondCard).getByRole('button', { name: '下载安装' }))
  expect(server.calls.filter((call) => call.path === '/api/v1/kernels/download')).toHaveLength(1)
})

it('refreshes installed kernels after a completed operation', async () => {
  const server = fakeServer({ license: validLicense })
  vi.stubGlobal('fetch', server.fetch)
  render(<Provider><KernelManagerDialog open onOpenChange={vi.fn()} selectedKernel={null} /></Provider>)
  const title = await screen.findByText('CloakBrowser 151.0.1.1')
  const card = title.closest('li') as HTMLElement
  act(() => server.stream?.enqueue(eventFrame([operation('operation-1', 'queued', 'licensed')])))
  await within(card).findByText('准备下载')
  server.setInstalled([publicKernel, licensedKernel])
  act(() => server.stream?.enqueue(eventFrame([operation('operation-1', 'completed', 'licensed')])))
  await waitFor(() => expect(within(card).getByRole('button', { name: '打开目录' })).toBeEnabled())
})

it('refreshes the default revision after a compare-and-swap conflict', async () => {
  let defaultReads = 0
  const server = fakeServer({ route(path, method) {
    if (path === '/api/v1/kernels/default' && method === 'GET') return json(defaultReads++ === 0 ? { revision: 2, kernel: null } : { revision: 3, kernel: licensedKernel })
    if (path === '/api/v1/kernels/default' && method === 'PUT') return json({ error: { code: 'KERNEL_DEFAULT_CONFLICT', message: 'revision stale', details: {}, requestId: '' } }, 409)
  } })
  vi.stubGlobal('fetch', server.fetch)
  const user = userEvent.setup()
  render(<Provider><KernelManagerDialog open onOpenChange={vi.fn()} selectedKernel={null} /></Provider>)
  await user.click(await screen.findByRole('button', { name: '设为默认' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('已刷新当前状态')
  expect(server.calls.find((call) => call.path === '/api/v1/kernels/default' && call.method === 'PUT')?.body).toEqual({ expectedRevision: 2, kernel: { edition: 'public', version: '146.0.1.1' } })
  expect(defaultReads).toBe(2)
})

it('keeps delete confirmation on top, restores nested focus, reveals via IPC, and marks a removed selection unavailable', async () => {
  const server = fakeServer({ route(path, method) {
    if (path === '/api/v1/kernels/146.0.1.1' && method === 'DELETE') { server.setInstalled([]); return new Response(null, { status: 204 }) }
  } })
  vi.stubGlobal('fetch', server.fetch)
  const user = userEvent.setup()
  render(<Provider><KernelManagerDialog open onOpenChange={vi.fn()} selectedKernel={publicKernel} /></Provider>)
  await user.click(await screen.findByRole('button', { name: '打开目录' }))
  expect(window.autoflow.revealKernel).toHaveBeenCalledWith({ edition: 'public', version: '146.0.1.1' })
  const deleteButton = screen.getByRole('button', { name: '删除' })
  await user.click(deleteButton)
  const confirmation = screen.getByRole('alertdialog', { name: '删除浏览器内核' })
  await user.click(within(confirmation).getByRole('button', { name: '取消' }))
  await waitFor(() => expect(deleteButton).toHaveFocus())
  await user.click(deleteButton)
  await user.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: '确认删除' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('当前表单选择的内核已不可用')
})

it('shows real login and logout failures without offering both actions', async () => {
  const loginServer = fakeServer({ route(path, method) {
    if (path === '/api/v1/kernels/license' && method === 'POST') return json({ error: { code: 'LICENSE_INVALID', message: 'License 无效', details: {}, requestId: '' } }, 422)
  } })
  vi.stubGlobal('fetch', loginServer.fetch)
  const user = userEvent.setup()
  const view = render(<Provider><KernelManagerDialog open onOpenChange={vi.fn()} selectedKernel={null} /></Provider>)
  await user.type(await screen.findByLabelText('License Key'), 'bad-key')
  await user.click(screen.getByRole('button', { name: '验证并登录' }))
  expect(await screen.findByText('License 无效')).toBeInTheDocument()
  view.unmount()

  const logoutServer = fakeServer({ license: validLicense, route(path, method) {
    if (path === '/api/v1/kernels/license' && method === 'DELETE') return json({ error: { code: 'LICENSE_BUSY', message: '授权任务仍在运行', details: {}, requestId: '' } }, 409)
  } })
  vi.stubGlobal('fetch', logoutServer.fetch)
  render(<Provider><KernelManagerDialog open onOpenChange={vi.fn()} selectedKernel={null} /></Provider>)
  await user.click(await screen.findByRole('button', { name: '退出登录' }))
  expect(await screen.findByText('授权任务仍在运行')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '验证并登录' })).not.toBeInTheDocument()
})

it.each([{ installedItems: [] }, { installedItems: [publicKernel] }])('keeps cancellation reachable after catalog loss and filtering ($installedItems)', async ({ installedItems }) => {
  const active = operation('orphan-download', 'downloading', 'licensed')
  const server = fakeServer({ license: validLicense, installed: installedItems, route(path, method) {
    if (path === '/api/v1/kernels/download' && method === 'POST') return json(active, 202)
    if (path === '/api/v1/kernels/check-update' && method === 'POST') return json({ ...catalog, releases: [], installed: installedItems, catalogError: 'provider offline' })
    if (path === '/api/v1/kernels/operations/orphan-download/cancel' && method === 'POST') return json({ ...active, state: 'cancelling' }, 202)
  } })
  vi.stubGlobal('fetch', server.fetch)
  const user = userEvent.setup()
  render(<Provider><ControlledManager /></Provider>)
  await user.click(screen.getByRole('button', { name: '管理内核' }))
  const card = (await screen.findByText('CloakBrowser 151.0.1.1')).closest('li') as HTMLElement
  await user.click(within(card).getByRole('button', { name: '下载安装' }))
  expect(await screen.findByRole('button', { name: '取消下载' })).toBeEnabled()
  await user.click(screen.getByRole('button', { name: '已安装' }))
  expect(within(screen.getByRole('region', { name: '活动内核下载' })).getByRole('button', { name: '取消下载' })).toBeEnabled()
  await user.click(screen.getByRole('button', { name: '刷新版本列表' }))
  await screen.findByText(/provider offline/)
  for (const filter of ['全部版本', '公开版', '正式版', '已安装']) {
    await user.click(screen.getByRole('button', { name: filter }))
    expect(screen.getByRole('button', { name: '取消下载' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '关闭内核管理' })).toBeDisabled()
  }
  await user.click(screen.getByRole('button', { name: '取消下载' }))
  await screen.findByText('正在取消')
  expect(server.calls.filter(call => call.path.endsWith('/orphan-download/cancel'))).toHaveLength(1)
  act(() => server.stream?.enqueue(eventFrame([{ ...active, state: 'cancelled' }])))
  await waitFor(() => expect(screen.getByRole('button', { name: '关闭内核管理' })).toBeEnabled())
  await user.click(screen.getByRole('button', { name: '关闭内核管理' }))
  expect(screen.queryByRole('dialog', { name: 'CloakBrowser 内核管理' })).not.toBeInTheDocument()
})
