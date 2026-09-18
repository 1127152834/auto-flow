import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import type { SheetsApi } from '../sheets-api'
import { SheetsBindingWizard, parseSpreadsheetLink } from './SheetsBindingWizard'
import { SheetsConnectionPanel } from './SheetsConnectionPanel'
import { SyncOperationPanel } from './SyncOperationPanel'

afterEach(cleanup)

const client = () => new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
const wrap = (ui: React.ReactElement) => render(<QueryClientProvider client={client()}>{ui}</QueryClientProvider>)
const connection = { connectionId: 'c1', accountLabel: '运营账号', credentialState: 'available' as const, readable: true, writable: true, updatedAt: '2026-09-18T02:00:00Z' }
const field = { ref: { fieldId: 'f1', datasetGeneration: 'g', position: 0 }, name: '邮箱', type: 'string', required: false, writable: true, formula: false, validation: {} }
const inspection = { valid: true, issues: [], columns: [{ columnId: 'A', name: 'Email', formula: false }], identitySummary: { unique: true, missing: 0, duplicates: 0 }, overlaps: [] }

const report = (extra: Record<string, unknown> = {}) => ({ impactRevision: 1, target: { type: 'table', projectId: 'p', tableId: 't' }, changeDigest: 'd', expectedRevisions: {}, impacts: [], blockers: [], calculatedAt: '2026-09-18T02:00:00Z', ...extra })
const apiWith = (overrides: Partial<Record<keyof SheetsApi, unknown>> = {}) => ({
  connections: vi.fn().mockResolvedValue({ items: [connection] }), authorize: vi.fn(), connect: vi.fn(),
  previewBinding: vi.fn().mockResolvedValue(report()), previewUnbind: vi.fn().mockResolvedValue(report()), previewDisconnect: vi.fn().mockResolvedValue(report()),
  disconnect: vi.fn(), removeBinding: vi.fn(),
  readBinding: vi.fn().mockResolvedValue(null), inspect: vi.fn(), putBinding: vi.fn(), state: vi.fn(),
  operations: vi.fn(), pause: vi.fn(), resume: vi.fn(), push: vi.fn(), pull: vi.fn(), reconcile: vi.fn(), abandon: vi.fn(),
  ...overrides,
}) as unknown as SheetsApi

it('lists a real connection and never posts when the desktop handshake is cancelled', async () => {
  const api = apiWith({ authorize: vi.fn().mockResolvedValue(null) })
  wrap(<SheetsConnectionPanel api={api} scopeKey="ws:p" />)
  expect(await screen.findByText('运营账号')).toBeVisible()
  expect(screen.getByText('可读可写')).toBeVisible()
  await userEvent.type(screen.getByLabelText('Google 账号名称'), '新账号')
  await userEvent.click(screen.getByRole('button', { name: /连接 Google 账号/ }))
  await waitFor(() => expect(api.authorize).toHaveBeenCalled())
  expect(api.connect).not.toHaveBeenCalled()
})

it('asks the desktop host for the handshake and never handles a Google credential itself', async () => {
  const api = apiWith({
    authorize: vi.fn().mockResolvedValue({ authorizationToken: 'one-shot', accountLabel: '运营账号', writable: true }),
    connect: vi.fn().mockResolvedValue({ kind: 'connectSheets', status: 'succeeded' }),
  })
  wrap(<SheetsConnectionPanel api={api} scopeKey="ws:p" />)
  await userEvent.type(screen.getByLabelText('Google 账号名称'), '运营账号')
  await userEvent.click(screen.getByRole('button', { name: /连接 Google 账号/ }))
  await waitFor(() => expect(api.connect).toHaveBeenCalledWith('运营账号', 'one-shot', expect.any(String), expect.any(Function)))
})

it('derives the spreadsheet id and gid from a pasted Sheet link', () => {
  expect(parseSpreadsheetLink('https://docs.google.com/spreadsheets/d/abc_123/edit#gid=456')).toEqual({ spreadsheetId: 'abc_123', sheetId: 456 })
  expect(parseSpreadsheetLink(' bare-id ')).toEqual({ spreadsheetId: 'bare-id', sheetId: null })
})

it('blocks binding while the source check has unresolved issues and reports them', async () => {
  const api = apiWith({
    inspect: vi.fn().mockResolvedValue({
      operation: { kind: 'inspectSheets', status: 'succeeded', result: {} },
      inspection: { ...inspection, valid: false, issues: [{ code: 'SHEETS_IDENTITY_NOT_TEXT', message: '身份字段必须是文本类型。' }], identitySummary: { unique: false, missing: 2, duplicates: 0 } },
    }),
  })
  wrap(<SheetsBindingWizard open api={api} scopeKey="ws:p" contextKey="ctx" table={{ tableId: 't', name: '邮箱表', tableRevision: 7, datasetGeneration: 'g' }} fields={[field] as never} connectionId="c1"
    onClose={vi.fn()} onBound={vi.fn()} />)
  await userEvent.type(screen.getByLabelText('Spreadsheet 链接'), 'https://docs.google.com/spreadsheets/d/abc/edit#gid=0')
  await userEvent.click(screen.getByRole('button', { name: '读取工作表并检查' }))
  expect(await screen.findByText('身份字段必须是文本类型。')).toBeVisible()
  expect(screen.getByText(/身份列 存在问题（缺失 2/)).toBeVisible()
  expect(screen.getByRole('button', { name: '确认绑定' })).toBeDisabled()
  expect(api.putBinding).not.toHaveBeenCalled()
})

it('binds with the confirmed table revision and reports the created binding', async () => {
  const onBound = vi.fn()
  const binding = { connectionId: 'c1', spreadsheetId: 'abc', sheetId: 0, bindingEpoch: 1, identityStrategy: { kind: 'column', columnId: 'A' }, mapping: [{ fieldId: 'f1', columnId: 'A', direction: 'both', formula: false }], syncPaused: false }
  const api = apiWith({
    inspect: vi.fn().mockResolvedValue({ operation: { kind: 'inspectSheets', status: 'succeeded', result: {} }, inspection }),
    previewBinding: vi.fn().mockResolvedValue(report({ impactRevision: 41 })),
    putBinding: vi.fn().mockResolvedValue({ kind: 'changeSheetsBinding', status: 'succeeded', result: binding }),
  })
  wrap(<SheetsBindingWizard open api={api} scopeKey="ws:p" contextKey="ctx" table={{ tableId: 't', name: '邮箱表', tableRevision: 7, datasetGeneration: 'g' }} fields={[field] as never} connectionId="c1"
    onClose={vi.fn()} onBound={onBound} />)
  await userEvent.type(screen.getByLabelText('Spreadsheet 链接'), 'https://docs.google.com/spreadsheets/d/abc/edit#gid=0')
  await userEvent.click(screen.getByRole('button', { name: '读取工作表并检查' }))
  await userEvent.click(await screen.findByRole('button', { name: '确认绑定' }))
  await waitFor(() => expect(onBound).toHaveBeenCalledWith(binding))
  expect(api.previewBinding).toHaveBeenCalledWith('t', expect.objectContaining({ spreadsheetId: 'abc', sheetId: 0, identityStrategy: { kind: 'column', columnId: 'A' } }))
  expect(api.putBinding).toHaveBeenCalledWith('t', expect.objectContaining({ impactRevision: 41, expectedTableRevision: 7, spreadsheetId: 'abc', sheetId: 0, identityStrategy: { kind: 'column', columnId: 'A' } }), expect.any(String), expect.any(Function))
})

it('shows what a binding will do and only submits after the confirmation is accepted', async () => {
  const binding = { connectionId: 'c1', spreadsheetId: 'abc', sheetId: 0, bindingEpoch: 1, identityStrategy: { kind: 'column', columnId: 'A' }, mapping: [], syncPaused: false }
  const api = apiWith({
    inspect: vi.fn().mockResolvedValue({ operation: { kind: 'inspectSheets', status: 'succeeded', result: {} }, inspection }),
    previewBinding: vi.fn().mockResolvedValue(report({ impactRevision: 52, impacts: [{ code: 'SHEETS_DATASET_REPLACED', resource: { type: 'table', projectId: 'p', tableId: 't' }, message: '绑定会把本地数据换成来源代次，旧记录保留为历史。', blocking: false }] })),
    putBinding: vi.fn().mockResolvedValue({ kind: 'changeSheetsBinding', status: 'succeeded', result: binding }),
  })
  wrap(<SheetsBindingWizard open api={api} scopeKey="ws:p" contextKey="ctx" table={{ tableId: 't', name: '邮箱表', tableRevision: 7, datasetGeneration: 'g' }} fields={[field] as never} connectionId="c1"
    onClose={vi.fn()} onBound={vi.fn()} />)
  await userEvent.type(screen.getByLabelText('Spreadsheet 链接'), 'https://docs.google.com/spreadsheets/d/abc/edit#gid=0')
  await userEvent.click(screen.getByRole('button', { name: '读取工作表并检查' }))
  await userEvent.click(await screen.findByRole('button', { name: '确认绑定' }))
  expect(await screen.findByText('绑定会把本地数据换成来源代次，旧记录保留为历史。')).toBeVisible()
  expect(api.putBinding).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: '确认并绑定' }))
  await waitFor(() => expect(api.putBinding).toHaveBeenCalledWith('t', expect.objectContaining({ impactRevision: 52 }), expect.any(String), expect.any(Function)))
})

it('keeps the previous binding when the impact preview reports a blocker', async () => {
  const api = apiWith({
    inspect: vi.fn().mockResolvedValue({ operation: { kind: 'inspectSheets', status: 'succeeded', result: {} }, inspection }),
    previewBinding: vi.fn().mockResolvedValue(report({ blockers: [{ code: 'SHEETS_BINDING_CONFLICT', resource: { type: 'table', projectId: 'p', tableId: 't' }, state: 'blocked', message: '该工作表已被另一张表绑定。' }] })),
  })
  wrap(<SheetsBindingWizard open api={api} scopeKey="ws:p" contextKey="ctx" table={{ tableId: 't', name: '邮箱表', tableRevision: 7, datasetGeneration: 'g' }} fields={[field] as never} connectionId="c1"
    onClose={vi.fn()} onBound={vi.fn()} />)
  await userEvent.type(screen.getByLabelText('Spreadsheet 链接'), 'https://docs.google.com/spreadsheets/d/abc/edit#gid=0')
  await userEvent.click(screen.getByRole('button', { name: '读取工作表并检查' }))
  await userEvent.click(await screen.findByRole('button', { name: '确认绑定' }))
  expect(await screen.findByText('该工作表已被另一张表绑定。')).toBeVisible()
  expect(api.putBinding).not.toHaveBeenCalled()
})

it('previews a disconnect and only submits the revision the report issued', async () => {
  const api = apiWith({
    previewDisconnect: vi.fn().mockResolvedValue(report({ impactRevision: 12, impacts: [{ code: 'SHEETS_CREDENTIAL_REMOVED', resource: { type: 'sheetsConnection', projectId: 'p', connectionId: 'c1' }, message: '本机保存的 Google 凭据会被删除，需要重新授权才能再次连接。', blocking: false }] })),
    disconnect: vi.fn().mockResolvedValue({ kind: 'disconnectSheets', status: 'succeeded', result: { connectionId: 'c1', mode: 'forgetCredential', disconnected: true } }),
  })
  wrap(<SheetsConnectionPanel api={api} scopeKey="ws:p" />)
  await screen.findByText('运营账号')
  expect(api.disconnect).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: '删除凭据…' }))
  expect(await screen.findByText('本机保存的 Google 凭据会被删除，需要重新授权才能再次连接。')).toBeVisible()
  expect(api.previewDisconnect).toHaveBeenCalledWith('c1', 'forgetCredential')
  await userEvent.click(screen.getByRole('button', { name: '断开并删除本机凭据' }))
  await waitFor(() => expect(api.disconnect).toHaveBeenCalledWith('c1', { impactRevision: 12, mode: 'forgetCredential' }, expect.any(String), expect.any(Function)))
})

it('keeps an in-use connection instead of disconnecting it', async () => {
  const api = apiWith({
    previewDisconnect: vi.fn().mockResolvedValue(report({ blockers: [{ code: 'SHEETS_CONNECTION_IN_USE', resource: { type: 'table', projectId: 'p', tableId: 't' }, state: 'blocked', message: '仍有数据表绑定使用该连接，请先解除绑定。' }] })),
  })
  wrap(<SheetsConnectionPanel api={api} scopeKey="ws:p" />)
  await screen.findByText('运营账号')
  await userEvent.click(screen.getByRole('button', { name: '断开…' }))
  expect(await screen.findByText('仍有数据表绑定使用该连接，请先解除绑定。')).toBeVisible()
  expect(api.disconnect).not.toHaveBeenCalled()
  expect(screen.queryByRole('button', { name: '断开连接' })).toBeNull()
})

it('says the table has no binding instead of pretending sync is idle', async () => {
  const api = apiWith()
  wrap(<SyncOperationPanel api={api} tableId="t" scopeKey="ws:p" tableRevision={3} binding={null} />)
  expect(await screen.findByText(/尚未绑定工作表/)).toBeVisible()
})

it('offers reconciliation for an unknown send and never pushes again on its own', async () => {
  const api = apiWith({
    state: vi.fn().mockResolvedValue({ summary: { status: 'unknown', pendingCount: 0, unknownCount: 1, lastConfirmedAt: null }, binding: { connectionId: 'c1', spreadsheetId: 'abc', sheetId: 0, bindingEpoch: 2, identityStrategy: { kind: 'column', columnId: 'A' }, mapping: [], syncPaused: false } }),
    operations: vi.fn().mockResolvedValue({ items: [{ syncOperationId: 's1', projectId: 'p', tableId: 't', kind: 'push', bindingEpoch: 2, status: 'unknown', statusRevision: 4, createdAt: '2026-09-18T02:00:00Z', updatedAt: '2026-09-18T02:00:00Z' }], page: 1, pageSize: 50, total: 1 }),
    reconcile: vi.fn().mockResolvedValue({ kind: 'reconcileSync', status: 'succeeded', result: {} }),
  })
  wrap(<SyncOperationPanel api={api} tableId="t" scopeKey="ws:p" tableRevision={3} binding={null} />)
  // Both the summary line and the operation row report the unknown send.
  expect((await screen.findAllByText('结果未知')).length).toBeGreaterThan(1)
  expect(screen.getByText(/不会自动重发/)).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: /核对结果/ }))
  await waitFor(() => expect(api.reconcile).toHaveBeenCalledWith('t', 's1', 4, expect.any(String), expect.any(Function)))
  expect(api.push).not.toHaveBeenCalled()
})
