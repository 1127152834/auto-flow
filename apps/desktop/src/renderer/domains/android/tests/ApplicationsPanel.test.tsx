import '@testing-library/jest-dom/vitest'
import { act, cleanup, render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ApplicationsPanel } from '../components/ApplicationsPanel'
import { fixtureSession } from './prototype-fixtures'

afterEach(cleanup)
const apps = {
  packages: ['org.example.notes', 'org.vendor.settings'],
  applications: [
    { packageName: 'org.example.notes', versionCode: 42, versionName: null, system: false, protected: false },
    { packageName: 'org.vendor.settings', versionCode: 7, versionName: null, system: true, protected: true },
  ],
  currentPackage: null, shellRoot: 'unknown', applicationRoot: 'unknown',
}
function setup() {
  const api = { appAction: vi.fn().mockResolvedValue(fixtureSession(true)), launch: vi.fn().mockResolvedValue(fixtureSession(true)) }
  const onSession = vi.fn(), onRefresh = vi.fn()
  render(<ApplicationsPanel apps={apps} api={api} session={fixtureSession(true)} onSession={onSession} onRefresh={onRefresh} />)
  return { api, onSession, onRefresh }
}

it('shows versions, searches packages, and disables destructive actions for system apps', async () => {
  setup()
  expect(screen.getByText(/版本 42/)).toBeVisible()
  const system = screen.getByText('org.vendor.settings').closest('article')!
  expect(within(system).getByRole('button', { name: '卸载' })).toBeDisabled()
  expect(within(system).getByRole('button', { name: '清除数据' })).toBeDisabled()
  await userEvent.type(screen.getByRole('searchbox', { name: '搜索应用' }), 'notes')
  expect(screen.queryByText('org.vendor.settings')).not.toBeInTheDocument()
})

it('requires confirmation for data loss and refreshes metadata after an unknown response without replaying the side effect', async () => {
  const { api, onRefresh } = setup()
  api.appAction.mockRejectedValueOnce(new Error('连接中断，结果未知'))
  const user = screen.getByText('org.example.notes').closest('article')!
  await userEvent.click(within(user).getByRole('button', { name: '清除数据' }))
  const dialog = await screen.findByRole('dialog')
  expect(within(dialog).getByText(/org.example.notes/)).toBeVisible()
  expect(api.appAction).not.toHaveBeenCalled()
  await userEvent.click(within(dialog).getByRole('button', { name: '确认清除数据' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('连接中断')
  await userEvent.click(screen.getByRole('button', { name: '刷新应用状态' }))
  await waitFor(() => expect(onRefresh).toHaveBeenCalledTimes(1))
  expect(api.appAction).toHaveBeenCalledTimes(1)
})

it('does not enable controls without a connected manual session', () => {
  render(<ApplicationsPanel apps={apps} session={null} onSession={vi.fn()} onRefresh={vi.fn()} />)
  for (const button of screen.getAllByRole('button')) expect(button).toBeDisabled()
})

it.each([
  ['readonly', { ...fixtureSession(false) }],
  ['closed', { ...fixtureSession(true), state: 'closed' }],
  ['stale', { ...fixtureSession(true), state: 'unknown' }],
  ['native', { ...fixtureSession(true), endpoint: 'native' }],
] as const)('fail-closes all writes for a %s session', (_label, session) => {
  setup()
  cleanup()
  render(<ApplicationsPanel apps={apps} api={{ appAction: vi.fn(), launch: vi.fn() }} session={session} onSession={vi.fn()} onRefresh={vi.fn()} />)
  for (const button of screen.getAllByRole('button')) expect(button).toBeDisabled()
})

it('keeps destructive actions disabled when app metadata is missing', () => {
  const unknownApps = { ...apps, applications: undefined }
  render(<ApplicationsPanel apps={unknownApps} api={{ appAction: vi.fn(), launch: vi.fn() }} session={fixtureSession(true)} onSession={vi.fn()} onRefresh={vi.fn()} />)
  const app = screen.getByText('org.example.notes').closest('article')!
  expect(within(app).getByRole('button', { name: '清除数据' })).toBeDisabled()
  expect(within(app).getByRole('button', { name: '卸载' })).toBeDisabled()
})

it('keeps destructive actions disabled when system or protected metadata is unknown', () => {
  const unknownMetadata = {
    ...apps,
    applications: [{ packageName: 'org.example.notes', versionCode: null, versionName: null, system: undefined, protected: undefined }],
  } as unknown as typeof apps
  render(<ApplicationsPanel apps={unknownMetadata} api={{ appAction: vi.fn(), launch: vi.fn() }} session={fixtureSession(true)} onSession={vi.fn()} onRefresh={vi.fn()} />)
  const app = screen.getByText('org.example.notes').closest('article')!
  expect(within(app).getByRole('button', { name: '清除数据' })).toBeDisabled()
  expect(within(app).getByRole('button', { name: '卸载' })).toBeDisabled()
})

it('disables an already-open destructive confirmation when the session becomes unknown', async () => {
  const api = { appAction: vi.fn(), launch: vi.fn() }
  const view = render(<ApplicationsPanel apps={apps} api={api} session={fixtureSession(true)} onSession={vi.fn()} onRefresh={vi.fn()} />)
  const app = screen.getByText('org.example.notes').closest('article')!
  await userEvent.click(within(app).getByRole('button', { name: '清除数据' }))
  expect(screen.getByRole('dialog')).toBeVisible()

  view.rerender(<ApplicationsPanel apps={apps} api={api} session={{ ...fixtureSession(true), state: 'unknown' }} onSession={vi.fn()} onRefresh={vi.fn()} />)

  expect(within(screen.getByRole('dialog')).getByRole('button', { name: '确认清除数据' })).toBeDisabled()
})

it('reconciles an unknown app operation by request id without replaying it', async () => {
  const api = {
    appAction: vi.fn().mockRejectedValueOnce(new Error('连接中断，结果未知')),
    launch: vi.fn(),
    verifyApp: vi.fn().mockResolvedValue(fixtureSession(true)),
  }
  const onSession = vi.fn(), onRefresh = vi.fn()
  render(<ApplicationsPanel apps={apps} api={api} session={fixtureSession(true)} onSession={onSession} onRefresh={onRefresh} />)
  const article = screen.getByText('org.example.notes').closest('article')!
  await userEvent.click(within(article).getByRole('button', { name: '清除数据' }))
  await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '确认清除数据' }))
  await userEvent.click(await screen.findByRole('button', { name: '按原请求核实' }))
  await waitFor(() => expect(api.verifyApp).toHaveBeenCalledWith(expect.anything(), expect.any(String), expect.any(Number)))
  expect(api.appAction).toHaveBeenCalledTimes(1)
  expect(onSession).toHaveBeenCalled()
})

it.each([
  ['ANDROID_APP_OPERATION_FAILED', 422, true],
  ['ANDROID_OPERATION_UNKNOWN', 503, false],
] as const)('releases the write lock only for a conclusive verification failure: %s', async (code, status, unlocked) => {
  const { ApiClientError } = await import('../../../shared/api/client')
  const api = {
    appAction: vi.fn().mockRejectedValue(new Error('response lost')),
    launch: vi.fn(),
    verifyApp: vi.fn().mockRejectedValue(new ApiClientError('核验结果', status, code)),
  }
  render(<ApplicationsPanel apps={apps} api={api} session={fixtureSession(true)} onSession={vi.fn()} onRefresh={vi.fn()} />)
  const article = screen.getByText('org.example.notes').closest('article')!
  await userEvent.click(within(article).getByRole('button', { name: '停止' }))
  await userEvent.click(await screen.findByRole('button', { name: '按原请求核实' }))
  await screen.findByText('核验结果')
  expect(within(article).getByRole('button', { name: '启动' }).hasAttribute('disabled')).toBe(!unlocked)
  expect(api.appAction).toHaveBeenCalledTimes(1)
})


it.each(['generation', 'closed', 'unmount'])('ignores a verification response after the control changes: %s', async (change) => {
  let finish!: (session: ReturnType<typeof fixtureSession>) => void
  const api = { appAction: vi.fn().mockRejectedValue(new Error('lost')), launch: vi.fn(),
    verifyApp: vi.fn(() => new Promise<ReturnType<typeof fixtureSession>>((resolve) => { finish = resolve })) }
  const onSession = vi.fn()
  const session = fixtureSession(true)
  const view = render(<ApplicationsPanel apps={apps} api={api} session={session} onSession={onSession} onRefresh={vi.fn()} />)
  await userEvent.click(within(screen.getByText('org.example.notes').closest('article')!).getByRole('button', { name: '停止' }))
  await userEvent.click(await screen.findByRole('button', { name: '按原请求核实' }))
  if (change === 'unmount') view.unmount()
  else view.rerender(<ApplicationsPanel apps={apps} api={api} session={change === 'closed' ? { ...session, state: 'closed' } : { ...session, generation: session.generation + 1 }} onSession={onSession} onRefresh={vi.fn()} />)
  await act(async () => { finish(session) })
  expect(onSession).not.toHaveBeenCalled()
})

it('ignores an application action response after the session closes', async () => {
  let finish!: (session: ReturnType<typeof fixtureSession>) => void
  const api = { appAction: vi.fn(() => new Promise<ReturnType<typeof fixtureSession>>((resolve) => { finish = resolve })), launch: vi.fn() }
  const session = fixtureSession(true)
  const onSession = vi.fn()
  const view = render(<ApplicationsPanel apps={apps} api={api} session={session} onSession={onSession} onRefresh={vi.fn()} />)
  await userEvent.click(within(screen.getByText('org.example.notes').closest('article')!).getByRole('button', { name: '停止' }))
  view.rerender(<ApplicationsPanel apps={apps} api={api} session={{ ...session, state: 'closed' }} onSession={onSession} onRefresh={vi.fn()} />)
  await act(async () => { finish(session) })
  expect(onSession).not.toHaveBeenCalled()
})
