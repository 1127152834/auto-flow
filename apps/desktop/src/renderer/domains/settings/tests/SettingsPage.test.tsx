import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import type { DesktopSettingsSnapshot, SettingsBridge } from '../../../../shared/settings'
import { SettingsPage } from '../pages/SettingsPage'
import { DiagnosticDialog } from '../components/DiagnosticDialog'

afterEach(cleanup)
const snapshot: DesktopSettingsSnapshot = {
  preferences: { zoom: 100, motion: 'system' },
  workspace: { path: '/Users/demo/AutoFlow/workspace', previousPath: '/Users/demo/old', paths: { workspace: '/Users/demo/AutoFlow/workspace', database: '/Users/demo/AutoFlow/workspace/data/autoflow.sqlite3', profiles: '/Users/demo/AutoFlow/workspace/workspace/profiles', kernels: '/Users/demo/AutoFlow/workspace/data/kernels', logs: '/Users/demo/AutoFlow/workspace/logs' }, blocked: false, blockers: [], recovery: null, needsSelection: false },
  service: { state: 'ready', apiVersion: 'v1', baseUrl: 'http://127.0.0.1:4500', message: null },
  runtime: { appVersion: '0.1.0', electronVersion: '41', chromeVersion: '140', nodeVersion: '24', platform: 'macos', arch: 'arm64', backendVersion: '0.1.0', pythonVersion: '3.11', sqliteVersion: '3.50' },
  operation: 'idle',
}

function bridge(overrides: Partial<SettingsBridge> = {}): SettingsBridge {
  return {
    getSettings: vi.fn(async () => ({ ok: true as const, value: snapshot })),
    setPreferences: vi.fn(async value => ({ ok: true as const, value })),
    chooseWorkspace: vi.fn(async () => ({ ok: true as const, value: { id: 'choice', path: '/Users/demo/new', kind: 'existing' as const } })),
    confirmWorkspace: vi.fn(async () => ({ ok: true as const, value: { ...snapshot, workspace: { ...snapshot.workspace, path: '/Users/demo/new' } } })),
    openSettingsDirectory: vi.fn(async () => ({ ok: true as const, value: { opened: true as const } })),
    previewDiagnostics: vi.fn(async includeLogs => ({ ok: true as const, value: { id: includeLogs ? 'logs' : 'basic', filename: 'autoflow-diagnostics.json', content: includeLogs ? '{"events":[]}' : '{"service":"ready"}' } })),
    saveDiagnostics: vi.fn(async () => ({ ok: true as const, value: { saved: false } })),
    quitApplication: vi.fn(async () => ({ ok: true as const, value: { quitting: true as const } })),
    ...overrides,
  }
}

it('renders real service information and persists preferences', async () => {
  const api = bridge()
  const user = userEvent.setup()
  render(<SettingsPage bridge={api} restartService={vi.fn()} />)
  expect(await screen.findByText('运行正常')).toBeInTheDocument()
  expect(screen.getByText('v1')).toBeInTheDocument()
  await user.selectOptions(screen.getByLabelText('界面缩放'), '110')
  expect(api.setPreferences).toHaveBeenCalledWith({ zoom: 110, motion: 'system' })
})

it('confirms a selected workspace and reports the service change', async () => {
  const api = bridge()
  const changed = vi.fn()
  const user = userEvent.setup()
  render(<SettingsPage bridge={api} restartService={vi.fn()} onServiceChanged={changed} />)
  await screen.findByText('运行正常')
  await user.click(screen.getByRole('tab', { name: '工作区' }))
  await user.click(screen.getByRole('button', { name: '切换工作区' }))
  const dialog = await screen.findByRole('dialog', { name: '切换工作区' })
  expect(within(dialog).getByText('/Users/demo/new')).toBeInTheDocument()
  expect(within(dialog).getByRole('button', { name: '取消' })).toHaveFocus()
  await user.click(within(dialog).getByRole('button', { name: '确认切换' }))
  await waitFor(() => expect(api.confirmWorkspace).toHaveBeenCalledWith('choice'))
  expect(changed).toHaveBeenCalledOnce()
})

it('keeps diagnostics local, logs opt-in, and preserves preview on save cancel', async () => {
  const api = bridge()
  const user = userEvent.setup()
  render(<SettingsPage bridge={api} restartService={vi.fn()} />)
  await screen.findByText('运行正常')
  await user.click(screen.getByRole('tab', { name: '关于' }))
  await user.click(screen.getByRole('button', { name: '导出诊断信息' }))
  const dialog = await screen.findByRole('dialog', { name: '导出诊断信息' })
  expect(within(dialog).getByText(/不会自动上传/)).toBeInTheDocument()
  expect(within(dialog).getByRole('checkbox', { name: '添加最近日志' })).not.toBeChecked()
  expect(await within(dialog).findByText('{"service":"ready"}')).toBeInTheDocument()
  await user.click(within(dialog).getByRole('button', { name: '选择保存位置' }))
  expect(api.saveDiagnostics).toHaveBeenCalledWith('basic')
  expect(dialog).toBeInTheDocument()
})

it('disables restart and workspace changes while occupied', async () => {
  const api = bridge({ getSettings: vi.fn(async () => ({ ok: true as const, value: { ...snapshot, workspace: { ...snapshot.workspace, blocked: true, blockers: ['内核安装'] } } })) })
  const user = userEvent.setup()
  render(<SettingsPage bridge={api} restartService={vi.fn()} />)
  expect(await screen.findByRole('button', { name: '重启服务' })).toBeDisabled()
  await user.click(screen.getByRole('tab', { name: '工作区' }))
  expect(screen.getByRole('button', { name: '切换工作区' })).toBeDisabled()
  expect(screen.getByText(/内核安装/)).toBeInTheDocument()
})

it('keeps operation errors visible across polling and lets the user dismiss them', async () => {
  const api = bridge({ setPreferences: vi.fn(async () => ({ ok: false as const, error: { code: 'WRITE_FAILED', message: '偏好保存失败' } })) })
  const user = userEvent.setup()
  render(<SettingsPage bridge={api} restartService={vi.fn()} />)
  await screen.findByText('运行正常')
  await user.selectOptions(screen.getByLabelText('界面缩放'), '110')
  expect(await screen.findByRole('alert')).toHaveTextContent('偏好保存失败')
  await new Promise(resolve => window.setTimeout(resolve, 1100))
  expect(screen.getByRole('alert')).toHaveTextContent('偏好保存失败')
  await user.click(within(screen.getByRole('alert')).getByRole('button', { name: '关闭' }))
  expect(screen.queryByText('偏好保存失败')).not.toBeInTheDocument()
})

it('does not let polling overwrite a preference while its save is pending', async () => {
  let resolveSave!: (value: Awaited<ReturnType<SettingsBridge['setPreferences']>>) => void
  const api = bridge({ setPreferences: vi.fn((): ReturnType<SettingsBridge['setPreferences']> => new Promise(resolve => { resolveSave = resolve })) })
  const user = userEvent.setup()
  render(<SettingsPage bridge={api} restartService={vi.fn()} />)
  const zoom = await screen.findByLabelText('界面缩放')
  await user.selectOptions(zoom, '110')
  await new Promise(resolve => window.setTimeout(resolve, 1100))
  expect(zoom).toHaveValue('110')
  resolveSave({ ok: true, value: { zoom: 110, motion: 'system' } })
  await waitFor(() => expect(zoom).toBeEnabled())
})

it('moves a consumed workspace choice to a visible result state', async () => {
  const confirmWorkspace = vi.fn(async () => ({ ok: false as const, error: { code: 'SWITCH_FAILED', message: '切换失败，已恢复原工作区' } }))
  const api = bridge({ confirmWorkspace })
  const user = userEvent.setup()
  render(<SettingsPage bridge={api} restartService={vi.fn()} />)
  await screen.findByText('运行正常')
  await user.click(screen.getByRole('tab', { name: '工作区' }))
  await user.click(screen.getByRole('button', { name: '切换工作区' }))
  await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '确认切换' }))
  const result = await screen.findByRole('dialog', { name: '工作区切换未完成' })
  expect(within(result).getByRole('alert')).toHaveTextContent('已恢复原工作区')
  expect(within(result).queryByRole('button', { name: '确认切换' })).not.toBeInTheDocument()
  expect(confirmWorkspace).toHaveBeenCalledOnce()
})

it('opens required workspace selection and ignores a stale diagnostic preview', async () => {
  const required = bridge({ getSettings: vi.fn(async () => ({ ok: true as const, value: { ...snapshot, workspace: { ...snapshot.workspace, needsSelection: true } } })) })
  const { unmount } = render(<SettingsPage bridge={required} restartService={vi.fn()} />)
  expect(await screen.findByRole('tab', { name: '工作区', selected: true })).toBeInTheDocument()
  unmount()

  let resolvePreview!: (value: Awaited<ReturnType<SettingsBridge['previewDiagnostics']>>) => void
  const pending = bridge({ previewDiagnostics: vi.fn((): ReturnType<SettingsBridge['previewDiagnostics']> => new Promise(resolve => { resolvePreview = resolve })) })
  const view = render(<DiagnosticDialog open bridge={pending} onOpenChange={vi.fn()} />)
  const checkbox = await screen.findByRole('checkbox', { name: '添加最近日志' })
  expect(checkbox).toBeDisabled()
  view.rerender(<DiagnosticDialog open={false} bridge={pending} onOpenChange={vi.fn()} />)
  resolvePreview({ ok: true, value: { id: 'stale', filename: 'stale.json', content: 'stale preview' } })
  await waitFor(() => expect(screen.queryByText('stale preview')).not.toBeInTheDocument())
})
