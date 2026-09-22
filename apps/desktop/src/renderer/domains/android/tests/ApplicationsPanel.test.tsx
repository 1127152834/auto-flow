import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, within, waitFor } from '@testing-library/react'
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
