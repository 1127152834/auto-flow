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

it('requires confirmation for data loss and retains the same request after an unknown response', async () => {
  const { api, onRefresh } = setup()
  api.appAction.mockRejectedValueOnce(new Error('连接中断，结果未知'))
  const user = screen.getByText('org.example.notes').closest('article')!
  await userEvent.click(within(user).getByRole('button', { name: '清除数据' }))
  const dialog = await screen.findByRole('dialog')
  expect(within(dialog).getByText(/org.example.notes/)).toBeVisible()
  expect(api.appAction).not.toHaveBeenCalled()
  await userEvent.click(within(dialog).getByRole('button', { name: '确认清除数据' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('连接中断')
  await userEvent.click(screen.getByRole('button', { name: '按原请求核实' }))
  await waitFor(() => expect(onRefresh).toHaveBeenCalledTimes(1))
  expect(api.appAction.mock.calls[0]).toEqual(api.appAction.mock.calls[1])
  expect(api.appAction).toHaveBeenCalledWith(expect.objectContaining({ generation: 1 }), 'clearData', 'org.example.notes', expect.any(String))
})

it('does not enable controls without a connected manual session', () => {
  render(<ApplicationsPanel apps={apps} session={null} onSession={vi.fn()} onRefresh={vi.fn()} />)
  for (const button of screen.getAllByRole('button')) expect(button).toBeDisabled()
})
