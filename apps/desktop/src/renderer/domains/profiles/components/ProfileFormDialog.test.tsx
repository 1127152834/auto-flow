import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApiProvider } from '../../../app/ApiProvider'
import type { InstalledKernel, KernelRef, ProfileRead } from '../../../shared/api/types'
import { Toaster } from '../../../shared/components/Toaster'
import { ProfileFormDialog, type ProfileFormDialogProps } from './ProfileFormDialog'

const installedKernel: InstalledKernel = {
  edition: 'public', version: '146.0.1.1', executablePath: '/fixture/chrome', size: 1,
}
const otherKernel: InstalledKernel = {
  edition: 'licensed', version: '145.0.0.1', executablePath: '/fixture/chrome-pro', size: 2,
}
const profile: ProfileRead = {
  id: '00000000-0000-4000-8000-000000000001', name: '既有配置', description: '', startUrl: 'about:blank',
  locale: null, timezone: null, geoip: false, headless: false, humanize: false, humanPreset: 'default',
  userAgent: null, viewportJson: null, colorScheme: null, extensionPathsJson: [], expertArgsJson: [],
  browserVersion: installedKernel.version, browserEdition: installedKernel.edition, releaseChannel: 'stable',
  proxyMode: 'none', proxyId: null, proxyPoolId: null, fingerprintSeed: 12345,
  createdAt: '2026-09-12T00:00:00Z', updatedAt: '2026-09-12T00:00:00Z',
}

type FakeOptions = {
  initialProfile?: ProfileRead | null
  defaultKernel?: KernelRef | null
  onOpenChange?: (open: boolean) => void
  onManageKernel?: ProfileFormDialogProps['onManageKernel']
  write?: (body: Record<string, unknown>, method: string) => Promise<Response> | Response
}

function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: { 'content-type': 'application/json' } })
}

function renderEditor(options: FakeOptions = {}) {
  const writes: Array<{ method: string; body: Record<string, unknown> }> = []
  const onOpenChange = vi.fn(options.onOpenChange)
  const onManageKernel = vi.fn(options.onManageKernel ?? (() => undefined))
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input)).pathname
    const method = init?.method ?? 'GET'
    if (path === '/api/v1/kernels/installed') return json({ items: [installedKernel, otherKernel] })
    if (path === '/api/v1/kernels/default') return json({ revision: 1, kernel: options.defaultKernel === undefined ? installedKernel : options.defaultKernel })
    if (path === '/api/v1/proxy-options') return json({ proxies: [], pools: [] })
    if (path === '/api/v1/profiles' || path.startsWith('/api/v1/profiles/')) {
      const body = JSON.parse(String(init?.body)) as Record<string, unknown>
      writes.push({ method, body })
      if (options.write) return options.write(body, method)
      return json({ ...profile, ...body, name: body.name ?? profile.name }, method === 'POST' ? 201 : 200)
    }
    throw new Error(`Unexpected request: ${method} ${path}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  const view = render(<ApiProvider baseUrl="http://127.0.0.1:1" token="fixture-token" instanceId="fixture-instance">
    <ProfileFormDialog open initialProfile={options.initialProfile ?? null} onOpenChange={onOpenChange} onManageKernel={onManageKernel} />
    <Toaster />
  </ApiProvider>)
  return { ...view, fetchMock, onOpenChange, onManageKernel, writes }
}

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
beforeEach(() => vi.stubGlobal('ResizeObserver', ResizeObserverStub))
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('does not lose the draft when dismissing discard confirmation', async () => {
  const user = userEvent.setup()
  renderEditor({ defaultKernel: null })
  await user.type(screen.getByLabelText('名称'), '工作环境')
  await user.keyboard('{Escape}')
  await user.click(await screen.findByRole('button', { name: '继续编辑' }))
  expect(screen.getByLabelText('名称')).toHaveValue('工作环境')
})

it('switches tabs and focuses the first local validation error', async () => {
  const user = userEvent.setup()
  renderEditor()
  await user.type(screen.getByLabelText('名称'), '工作环境')
  await user.click(screen.getByRole('tab', { name: '高级选项' }))
  await user.type(screen.getByLabelText('高级参数（每行一个）'), '--proxy-server=http://fixture')
  await user.click(screen.getByRole('tab', { name: '基础信息' }))
  await user.click(screen.getByRole('button', { name: '创建配置' }))
  await waitFor(() => expect(screen.getByRole('tab', { name: '高级选项' })).toHaveAttribute('data-state', 'active'))
  expect(screen.getByLabelText('高级参数（每行一个）')).toHaveFocus()
})

it('maps a 422 field error to its tab and keeps the draft', async () => {
  const user = userEvent.setup()
  renderEditor({ write: () => json({ error: {
    code: 'VALIDATION_ERROR', message: '字段无效', details: { fields: { timezone: '时区不可用' } }, requestId: 'request-1',
  } }, 422) })
  await user.type(screen.getByLabelText('名称'), '工作环境')
  await user.click(screen.getByRole('button', { name: '创建配置' }))
  await waitFor(() => expect(screen.getByRole('tab', { name: '浏览器环境' })).toHaveAttribute('data-state', 'active'))
  expect(screen.getByLabelText('浏览器时区')).toHaveFocus()
  await user.click(screen.getByRole('tab', { name: '基础信息' }))
  expect(screen.getByLabelText('名称')).toHaveValue('工作环境')
})

it('applies the default once for create and passes the selected kernel with its trigger', async () => {
  const user = userEvent.setup()
  const { onManageKernel } = renderEditor()
  await user.click(screen.getByRole('tab', { name: '内核与代理' }))
  await waitFor(() => expect(screen.getByLabelText('浏览器内核')).toHaveValue('public|146.0.1.1'))
  const trigger = screen.getByRole('button', { name: '管理内核' })
  await user.click(trigger)
  expect(onManageKernel).toHaveBeenCalledWith({ edition: 'public', version: '146.0.1.1' }, trigger)
})

it('preserves an edited null viewport and ignores the global default', async () => {
  const user = userEvent.setup()
  const { writes } = renderEditor({ initialProfile: profile, defaultKernel: otherKernel })
  await user.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(writes).toHaveLength(1))
  expect(writes[0]).toMatchObject({ method: 'PUT', body: {
    browserEdition: 'public', browserVersion: '146.0.1.1', viewportJson: null,
  } })
})

it('submits only once while saving and blocks closing', async () => {
  let resolveWrite!: (response: Response) => void
  const pending = new Promise<Response>((resolve) => { resolveWrite = resolve })
  const user = userEvent.setup()
  const { writes, onOpenChange } = renderEditor({ write: () => pending })
  await user.type(screen.getByLabelText('名称'), '工作环境')
  const submit = screen.getByRole('button', { name: '创建配置' })
  await user.dblClick(submit)
  await waitFor(() => expect(writes).toHaveLength(1))
  expect(screen.getByRole('button', { name: '正在保存…' })).toBeDisabled()
  await user.keyboard('{Escape}')
  expect(onOpenChange).not.toHaveBeenCalled()
  resolveWrite(json({ ...profile, name: '工作环境' }, 201))
  await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false))
})

it('keeps the name after a 409 conflict', async () => {
  const user = userEvent.setup()
  renderEditor({ write: () => json({ error: {
    code: 'PROFILE_NAME_CONFLICT', message: '配置名称已存在', details: {}, requestId: 'request-2',
  } }, 409) })
  await user.type(screen.getByLabelText('名称'), '重复名称')
  await user.click(screen.getByRole('button', { name: '创建配置' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('配置名称已存在')
  expect(screen.getByLabelText('名称')).toHaveValue('重复名称')
})

it('closes and announces a successful create', async () => {
  const user = userEvent.setup()
  const { onOpenChange } = renderEditor()
  await user.type(screen.getByLabelText('名称'), '工作环境')
  await user.click(screen.getByRole('button', { name: '创建配置' }))
  expect(await screen.findByText('配置已创建')).toBeInTheDocument()
  expect(onOpenChange).toHaveBeenCalledWith(false)
})
