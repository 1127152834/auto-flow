import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { BulkActions } from '../components/BulkActions'
import { DataMaintenance } from '../components/DataMaintenance'
import { BackupPanel } from '../components/BackupPanel'
import { ApiClientError } from '../../../shared/api/client'
import type { ManagementDevicePage } from '../management-api'

const device: ManagementDevicePage['items'][number] = { deviceId: 'd1', revision: 2, name: '设备一', runtimeState: 'ready', owner: { kind: 'none', id: null }, observedAt: null, stale: false, specSnapshot: {}, latestOperation: null, allowedActions: ['start', 'stop', 'restart', 'delete'], blockedReasons: {} }

afterEach(cleanup)

it('freezes selected revisions when submitting a bulk action', async () => {
  const bulk = vi.fn(async (body: Record<string, unknown>) => ({ id: 'b', requestId: body.requestId as string, action: 'start', deleteData: false, state: 'queued', items: [], createdAt: '' }))
  render(<BulkActions api={{ bulk }} devices={[device]} />)
  await userEvent.click(screen.getByLabelText('设备一'))
  await userEvent.click(screen.getByRole('button', { name: '提交批量操作' }))
  expect(bulk).toHaveBeenCalledWith(expect.objectContaining({ items: [{ deviceId: 'd1', expectedRevision: 2 }] }))
})

it('passes an explicit deleteData choice for bulk deletion', async () => {
  const bulk = vi.fn(async (body: Record<string, unknown>) => ({ id: 'b', requestId: body.requestId as string, action: 'delete', deleteData: Boolean(body.deleteData), state: 'queued', items: [], createdAt: '' }))
  render(<BulkActions api={{ bulk }} devices={[device]} />)
  await userEvent.click(screen.getByLabelText('设备一'))
  await userEvent.selectOptions(screen.getByLabelText('批量动作'), 'delete')
  expect(screen.getByLabelText('同时删除数据（不可恢复）')).not.toBeChecked()
  await userEvent.click(screen.getByRole('button', { name: '提交批量操作' }))
  expect(bulk).toHaveBeenCalledWith(expect.objectContaining({ action: 'delete', deleteData: false }))
  cleanup()
  render(<BulkActions api={{ bulk }} devices={[device]} />)
  await userEvent.click(screen.getByLabelText('设备一'))
  await userEvent.selectOptions(screen.getByLabelText('批量动作'), 'delete')
  await userEvent.click(screen.getByLabelText('同时删除数据（不可恢复）'))
  await userEvent.click(screen.getByRole('button', { name: '提交批量操作' }))
  expect(bulk).toHaveBeenLastCalledWith(expect.objectContaining({ action: 'delete', deleteData: true }))
})

it('does not allow unknown or stale devices into a bulk action', async () => {
  const bulk = vi.fn()
  const blocked: ManagementDevicePage['items'][number] = { ...device, deviceId: 'unknown', name: '待核实设备', runtimeState: 'unknown', stale: true }
  render(<BulkActions api={{ bulk }} devices={[blocked]} />)
  expect(screen.getByLabelText('待核实设备')).toBeDisabled()
  expect(screen.getByRole('button', { name: '提交批量操作' })).toBeDisabled()
})

it('only allows bulk selection when the target advertises the chosen action and is unowned', async () => {
  const bulk = vi.fn()
  const owned: ManagementDevicePage['items'][number] = { ...device, deviceId: 'owned', name: '占用设备', owner: { kind: 'legacyWorkflow', id: 'run-1' }, allowedActions: ['start', 'stop'] }
  const startOnly: ManagementDevicePage['items'][number] = { ...device, deviceId: 'start-only', name: '仅启动设备', allowedActions: ['start'] }
  render(<BulkActions api={{ bulk }} devices={[owned, startOnly]} />)
  expect(screen.getByLabelText('占用设备')).toBeDisabled()
  await userEvent.selectOptions(screen.getByLabelText('批量动作'), 'stop')
  expect(screen.getByLabelText('仅启动设备')).toBeDisabled()
  expect(screen.getByRole('button', { name: '提交批量操作' })).toBeDisabled()
})

it('keeps a failed batch retryable with the original request and reports unknown outcomes', async () => {
  const bulk = vi.fn()
    .mockRejectedValueOnce(new Error('批次连接中断'))
    .mockResolvedValueOnce({ id: 'b', requestId: 'r', action: 'start', deleteData: false, state: 'needs_verification', items: [{ state: 'accepted' }], createdAt: '' })
  const bulkAction = vi.fn(async () => ({ id: 'b', requestId: 'r', action: 'start', deleteData: false, state: 'succeeded', items: [{ state: 'succeeded' }], createdAt: '' }))
  render(<BulkActions api={{ bulk, bulkAction }} devices={[device]} />)
  await userEvent.click(screen.getByLabelText('设备一'))
  await userEvent.click(screen.getByRole('button', { name: '提交批量操作' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('批次连接中断')
  await userEvent.click(screen.getByRole('button', { name: '重试批量操作' }))
  await vi.waitFor(() => expect(bulk).toHaveBeenCalledTimes(2))
  expect(bulk.mock.calls[0][0]).toEqual(bulk.mock.calls[1][0])
  expect(await screen.findByRole('alert')).toHaveTextContent('批次结果未知')
  await userEvent.click(screen.getByRole('button', { name: '核实批次' }))
  await vi.waitFor(() => expect(bulkAction).toHaveBeenCalledWith('b', expect.objectContaining({ action: 'verify' })))
  expect(await screen.findByRole('status')).toHaveTextContent('succeeded')
})

it('summarizes failed batch items and retries them with an idempotent action request', async () => {
  const bulk = vi.fn(async () => ({ id: 'b', requestId: 'create-r', action: 'start', deleteData: false, state: 'partially_failed', items: [{ deviceId: 'd1', name: '设备一', state: 'failed', operationId: 'op-1' }], createdAt: '' }))
  const bulkAction = vi.fn()
    .mockRejectedValueOnce(new Error('批次重试连接中断'))
    .mockResolvedValueOnce({ id: 'b', requestId: 'create-r', action: 'start', deleteData: false, state: 'running', items: [{ deviceId: 'd1', name: '设备一', state: 'queued', retryOf: 'op-1' }], createdAt: '' })
  render(<BulkActions api={{ bulk, bulkAction }} devices={[device]} />)
  await userEvent.click(screen.getByLabelText('设备一'))
  await userEvent.click(screen.getByRole('button', { name: '提交批量操作' }))

  expect(await screen.findByLabelText('批次结果')).toHaveTextContent('重试自 op-1')
  await userEvent.click(screen.getByRole('button', { name: '重试失败项' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('批次重试连接中断')
  await userEvent.click(screen.getByRole('button', { name: '重试失败项' }))
  await vi.waitFor(() => expect(bulkAction).toHaveBeenCalledTimes(2))
  expect(bulkAction.mock.calls[0][1]).toEqual(expect.objectContaining({ action: 'retryFailed' }))
  expect(bulkAction.mock.calls[0][1].requestId).toBe(bulkAction.mock.calls[1][1].requestId)
})

it('requires a preview before cleanup execution', async () => {
  const cleanupPreview = vi.fn(async () => ({ items: [{ id: 'v1', kind: 'backup', references: ['d1'], size: 128, reversible: false, fingerprint: 'fingerprint' }], confirmationDigest: 'digest' }))
  const cleanup = vi.fn(async () => ({ items: [], state: 'accepted' }))
  const diagnostics = vi.fn(async () => ({ id: 'd', requestId: 'r', state: 'ready', payload: {}, createdAt: '' }))
  render(<QueryClientProvider client={new QueryClient()}><DataMaintenance api={{ cleanupPreview, cleanup, diagnostics }} resourceIds={['v1']} /></QueryClientProvider>)
  expect(screen.queryByRole('button', { name: /确认清理/ })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '预览清理' }))
  expect(await screen.findByRole('button', { name: '确认清理 1 项' })).toBeVisible()
  expect(screen.getByLabelText('清理预览')).toHaveTextContent('对象：v1 · 备份')
  expect(screen.getByLabelText('清理预览')).toHaveTextContent('引用：d1')
  expect(screen.getByLabelText('清理预览')).toHaveTextContent('不可逆')
  expect(screen.getByLabelText('清理预览')).toHaveTextContent('指纹：fingerprint')
})

it('keeps diagnostic contents out of the renderer and saves by controlled id', async () => {
  const diagnostics = vi.fn(async () => ({ id: 'diag-1', requestId: 'diag-1', state: 'ready', payload: { secret: 'redacted' }, createdAt: '', expiresAt: '' }))
  const saveDiagnostic = vi.fn(async () => ({ ok: true as const, value: { saved: true, path: '/tmp/android.json' } }))
  render(<QueryClientProvider client={new QueryClient()}><DataMaintenance api={{ cleanupPreview: vi.fn(), cleanup: vi.fn(), diagnostics }} saveDiagnostic={saveDiagnostic} resourceIds={['v1']} /></QueryClientProvider>)
  await userEvent.click(screen.getByRole('button', { name: '生成脱敏诊断' }))
  expect(await screen.findByRole('status')).toHaveTextContent('诊断已生成，内容已脱敏')
  expect(screen.queryByText('redacted')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '保存诊断' }))
  expect(saveDiagnostic).toHaveBeenCalledWith('diag-1')
})

it('clears a stale cleanup preview when refreshing it fails', async () => {
  let fail = false
  const cleanupPreview = vi.fn(async () => {
    if (fail) throw new Error('清理目录暂不可用')
    return { items: [{ id: 'v1' }], confirmationDigest: 'digest' }
  })
  const cleanup = vi.fn(async () => ({ items: [], state: 'accepted' }))
  const diagnostics = vi.fn(async () => ({ id: 'd', requestId: 'r', state: 'ready', payload: {}, createdAt: '' }))
  render(<QueryClientProvider client={new QueryClient()}><DataMaintenance api={{ cleanupPreview, cleanup, diagnostics }} resourceIds={['v1']} /></QueryClientProvider>)
  await userEvent.click(screen.getByRole('button', { name: '预览清理' }))
  expect(await screen.findByRole('button', { name: '确认清理 1 项' })).toBeVisible()
  fail = true
  await userEvent.click(screen.getByRole('button', { name: '预览清理' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('清理目录暂不可用')
  expect(screen.queryByRole('button', { name: /确认清理/ })).not.toBeInTheDocument()
})

it('surfaces cleanup conflicts and requires a fresh preview', async () => {
  const cleanupPreview = vi.fn(async () => ({ items: [{ id: 'v1' }], confirmationDigest: 'digest' }))
  const cleanup = vi.fn(async () => { throw new ApiClientError('清理预览已变化', 409, 'ANDROID_CLEANUP_CHANGED') })
  const diagnostics = vi.fn(async () => ({ id: 'd', requestId: 'r', state: 'ready', payload: {}, createdAt: '' }))
  render(<QueryClientProvider client={new QueryClient()}><DataMaintenance api={{ cleanupPreview, cleanup, diagnostics }} resourceIds={['v1']} /></QueryClientProvider>)
  await userEvent.click(screen.getByRole('button', { name: '预览清理' }))
  await userEvent.click(await screen.findByRole('button', { name: '确认清理 1 项' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('清理预览已变化，请重新预览后确认')
  expect(screen.queryByRole('button', { name: /确认清理/ })).not.toBeInTheDocument()
})

it('keeps backup request retryable and refreshes after restore', async () => {
  const backupRecord = { id: 'b1', deviceId: 'd1', bytes: 3, imageId: 'img', sha256: 'digest', formatVersion: 1, state: 'ready', createdAt: '' }
  const backup = vi.fn()
    .mockRejectedValueOnce(new Error('连接中断'))
    .mockResolvedValueOnce(backupRecord)
  const restoreBackup = vi.fn(async () => ({ deviceId: 'd2', operationId: 'op-1', requestId: 'restore-r', targetId: 'd2', backupId: 'b1', state: 'restored' }))
  const operationByRequest = vi.fn(async () => ({ operationId: 'op-1', requestId: 'r', targetId: 'd1', action: 'backup', state: 'succeeded', stageCode: 'complete', stageLabel: '已完成', attempt: 1, createdAt: '' }))
  const backups = vi.fn(async () => [backupRecord])
  const api = { backup, restoreBackup, backups, operationByRequest }
  render(<QueryClientProvider client={new QueryClient()}><BackupPanel api={api} deviceId="d1" revision={2} runtimeState="stopped" control="idle" hasControlSession={false} stale={false} /></QueryClientProvider>)
  await userEvent.click(screen.getByRole('button', { name: '创建停机备份' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('连接中断')
  await userEvent.click(screen.getByRole('button', { name: '核实原请求' }))
  await vi.waitFor(() => expect(operationByRequest).toHaveBeenCalled())
  await userEvent.click(screen.getByRole('button', { name: '恢复为新实例' }))
  await vi.waitFor(() => expect(restoreBackup).toHaveBeenCalledTimes(1))
  expect(backups).toHaveBeenCalledTimes(3)
})

it.each([
  { runtimeState: 'ready', control: 'idle', hasControlSession: false, stale: false },
  { runtimeState: 'unknown', control: 'idle', hasControlSession: false, stale: false },
  { runtimeState: 'stopped', control: 'manual', hasControlSession: false, stale: false },
  { runtimeState: 'stopped', control: 'idle', hasControlSession: true, stale: false },
  { runtimeState: 'retained', control: 'idle', hasControlSession: false, stale: true },
])('blocks backup unless stopped, current and free of control: %o', async (state) => {
  const api = { backups: vi.fn(async () => []), backup: vi.fn(), restoreBackup: vi.fn(), operationByRequest: vi.fn() }
  render(<QueryClientProvider client={new QueryClient()}><BackupPanel api={api} deviceId="d1" revision={2} {...state} /></QueryClientProvider>)
  const button = screen.getByRole('button', { name: '创建停机备份' })
  expect(button).toBeDisabled()
  await userEvent.click(button)
  expect(api.backup).not.toHaveBeenCalled()
})

it.each(['accepted', 'running', 'needs_verification'])('keeps a %s cleanup result pending until the original request is verified', async (state) => {
  const cleanupPreview = vi.fn(async () => ({ items: [{ id: 'v1' }], previewId: 'preview-1', confirmationDigest: 'digest' }))
  const cleanup = vi.fn(async (body: { requestId: string }) => ({ items: [], state, requestId: body.requestId, previewId: 'preview-1' }))
  const diagnostics = vi.fn()
  const operationByRequest = vi.fn(async () => ({ operationId: 'cleanup-op', requestId: 'r', targetId: 'cleanup', action: 'cleanup', state: 'needs_verification', stageCode: 'verify', stageLabel: '待核实', attempt: 1, createdAt: '' }))
  const verify = vi.fn(async () => ({ operationId: 'cleanup-op', requestId: 'r', targetId: 'cleanup', action: 'cleanup', state: 'succeeded', stageCode: 'verified', stageLabel: '已核实', attempt: 1, createdAt: '' }))
  render(<DataMaintenance api={{ cleanupPreview, cleanup, diagnostics, operationByRequest, verify }} resourceIds={['v1']} />)
  await userEvent.click(screen.getByRole('button', { name: '预览清理' }))
  await userEvent.click(await screen.findByRole('button', { name: '确认清理 1 项' }))
  expect(screen.queryByText('清理已完成')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '核实原清理请求' })).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '核实原清理请求' }))
  expect(operationByRequest).toHaveBeenCalledWith(cleanup.mock.calls[0][0].requestId)
  expect(verify).toHaveBeenCalledWith('cleanup-op', { requestId: cleanup.mock.calls[0][0].requestId })
  expect(await screen.findByText('清理已完成')).toBeVisible()
  expect(cleanup).toHaveBeenCalledTimes(1)
})

const temporary = { id: 'orphan:partial', kind: 'backup-orphan', purpose: 'unregistered-backup', revision: 1, references: [], workspaceId: 'workspace', ownership: {}, size: 12, irreversibleImpact: '永久删除', summary: {}, fingerprint: 'file-revision', reversible: false }

it('discovers module temporary files and previews only explicitly selected objects', async () => {
  const cleanupResources = vi.fn(async () => ({ items: [temporary, { ...temporary, id: 'keep' }] }))
  const cleanupPreview = vi.fn(async () => ({ items: [temporary], confirmationDigest: 'digest' }))
  render(<DataMaintenance api={{ cleanupResources, cleanupPreview, cleanup: vi.fn(), diagnostics: vi.fn() }} resourceIds={['keep']} />)
  const choice = await screen.findByRole('checkbox', { name: /orphan:partial/ })
  expect(choice).not.toBeChecked()
  expect(screen.getByRole('button', { name: '预览清理' })).toBeDisabled()
  await userEvent.click(choice)
  await userEvent.click(screen.getByRole('button', { name: '预览清理' }))
  expect(cleanupPreview).toHaveBeenCalledWith(['orphan:partial'])
  expect(screen.getByLabelText('清理预览')).toHaveTextContent('未登记备份')
})

it('does not reuse selected objects or a preview after inventory refresh fails', async () => {
  const cleanupResources = vi.fn().mockResolvedValueOnce({ items: [temporary] }).mockRejectedValueOnce(new Error('目录读取失败'))
  const cleanupPreview = vi.fn(async () => ({ items: [temporary], confirmationDigest: 'digest' }))
  render(<DataMaintenance api={{ cleanupResources, cleanupPreview, cleanup: vi.fn(), diagnostics: vi.fn() }} resourceIds={[]} />)
  await userEvent.click(await screen.findByRole('checkbox', { name: /orphan:partial/ }))
  await userEvent.click(screen.getByRole('button', { name: '预览清理' }))
  await userEvent.click(screen.getByRole('button', { name: '刷新清理对象' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('目录读取失败')
  expect(screen.queryByRole('button', { name: /确认清理/ })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '预览清理' })).toBeDisabled()
})

it('reports a malformed inventory without crashing the management page', async () => {
  const cleanupResources = vi.fn().mockResolvedValue({})
  render(<DataMaintenance api={{ cleanupResources, cleanupPreview: vi.fn(), cleanup: vi.fn(), diagnostics: vi.fn() }} resourceIds={[]} />)
  expect(await screen.findByRole('alert')).toHaveTextContent('清理对象响应无效')
  expect(screen.getByRole('button', { name: '预览清理' })).toBeDisabled()
})

it('shows readable source references and irreversible impact in the frozen preview', async () => {
  const item = { ...temporary, references: [{ kind: 'device', id: 'source-id', name: '源实例' }] }
  const cleanupPreview = vi.fn(async () => ({ items: [item], confirmationDigest: 'digest' }))
  render(<DataMaintenance api={{ cleanupPreview, cleanup: vi.fn(), diagnostics: vi.fn() }} resourceIds={['orphan:partial']} />)
  await userEvent.click(screen.getByRole('button', { name: '预览清理' }))
  expect(await screen.findByLabelText('清理预览')).toHaveTextContent('源实例')
  expect(screen.getByLabelText('清理预览')).toHaveTextContent('永久删除')
  expect(screen.getByLabelText('清理预览')).not.toHaveTextContent('[object Object]')
})
