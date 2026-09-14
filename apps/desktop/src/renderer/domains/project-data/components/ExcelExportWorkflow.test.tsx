// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { choiceTestEnvironment, chooseOption } from '../../../shared/testing/choice-user'
import { DataCommandUncertain } from '../data-command'
import { ExcelExportWorkflow } from './ExcelExportWorkflow'

const field = (id: string, name: string) => ({ key: id, name, type: 'string', required: false, validation: {}, ref: { fieldId: id }, writable: true, formula: false, fieldRevision: 1 })
const fields = [field('f1', '姓名'), field('f2', '年龄')], statuses = [{ statusId: 's', name: '待办', color: '#fff', order: 0, statusRevision: 1 }]
const table = { projectId: 'p', tableId: 't', name: '客户', description: '', sourceKind: 'local', datasetGeneration: 'g1', tableRevision: 3, identity: { mode: 'system' }, slotDefinitions: [], recordCount: 2, syncSummary: {}, createdAt: '', updatedAt: '' }
const selection = { selectionToken: 'output', displayName: '客户.xlsx', kind: 'xlsx-output', expiresAt: '2099-01-01T00:00:00Z' }
const accepted = { operationId: 'o', idempotencyKey: 'k', kind: 'exportXlsx', status: 'accepted', statusRevision: 1, resource: { type: 'table', projectId: 'p', tableId: 't' }, result: null, error: null, createdAt: '', updatedAt: '', completedAt: null }
beforeEach(() => { const values = new Map<string, string>(); vi.stubGlobal('localStorage', { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key), clear: () => values.clear() }) }); afterEach(() => { cleanup(); vi.unstubAllGlobals() }); choiceTestEnvironment()

it('freezes filter, order, fields, status and dataset version after output selection', async () => {
  const api = { startExport: vi.fn().mockResolvedValue(accepted), lookupExport: vi.fn(), reconcileExport: vi.fn(), lookupReconcile: vi.fn() }
  render(<ExcelExportWorkflow open sessionKey="s" scopeKey="w:p:t:s" contextKey="i1" table={table as never} fields={fields as never} statuses={statuses as never} api={api as never} files={{ chooseOutput: vi.fn().mockResolvedValue(selection as never) }} filter="name:张" orderBy="name" onClose={vi.fn()} onCompleted={vi.fn()} />)
  await chooseOption(userEvent.setup(), screen.getByRole('combobox', { name: '导出范围' }), 'filter')
  await userEvent.click(screen.getByRole('checkbox', { name: '年龄' })); await userEvent.click(screen.getByRole('button', { name: '选择保存位置' }))
  expect(api.startExport).toHaveBeenCalledWith('t', { selectionToken: 'output', datasetGeneration: 'g1', scope: 'filter', filter: 'name:张', orderBy: 'name', fieldIds: ['f1'], includeStatus: true }, expect.any(String), expect.any(Function))
})

it('keeps an unknown export guarded and restores it by lookup without choosing another path', async () => {
  const api = { startExport: vi.fn().mockRejectedValue(new DataCommandUncertain('lost')), lookupExport: vi.fn().mockRejectedValue(new DataCommandUncertain('offline')), reconcileExport: vi.fn(), lookupReconcile: vi.fn() }, choose = vi.fn().mockResolvedValue(selection), dirty = vi.fn()
  render(<ExcelExportWorkflow open sessionKey="s" scopeKey="w:p:t:s" contextKey="i1" table={table as never} fields={fields as never} statuses={statuses as never} api={api as never} files={{ chooseOutput: choose }} filter={null} orderBy={null} onClose={vi.fn()} onCompleted={vi.fn()} onDirtyChange={dirty} />)
  await userEvent.click(screen.getByRole('button', { name: '选择保存位置' })); await screen.findByText('上次导出结果尚未确认，必须先查询原请求。')
  expect(choose).toHaveBeenCalledTimes(1); expect(dirty).toHaveBeenLastCalledWith(true)
  await waitFor(() => expect(api.lookupExport).toHaveBeenCalled()); expect(choose).toHaveBeenCalledTimes(1)
})

it('asks before discarding edited settings when the dialog is dismissed', async () => {
  const api = { startExport: vi.fn(), lookupExport: vi.fn(), reconcileExport: vi.fn(), lookupReconcile: vi.fn() }, onClose = vi.fn()
  render(<ExcelExportWorkflow open sessionKey="s" scopeKey="w:p:t:s" contextKey="i1" table={table as never} fields={fields as never} statuses={statuses as never} api={api as never} files={{ chooseOutput: vi.fn() }} filter="active" orderBy={null} onClose={onClose} onCompleted={vi.fn()} />)
  await chooseOption(userEvent.setup(), screen.getByRole('combobox', { name: '导出范围' }), 'filter')
  await userEvent.keyboard('{Escape}')
  expect(await screen.findByText('放弃导出设置？')).toBeInTheDocument()
  expect(onClose).not.toHaveBeenCalled()
})

it('shows an output picker failure without losing the draft', async () => {
  const api = { startExport: vi.fn(), lookupExport: vi.fn(), reconcileExport: vi.fn(), lookupReconcile: vi.fn() }
  render(<ExcelExportWorkflow open sessionKey="s" scopeKey="w:p:t:s" contextKey="i1" table={table as never} fields={fields as never} statuses={statuses as never} api={api as never} files={{ chooseOutput: vi.fn().mockRejectedValue(new Error('保存对话框不可用')) }} filter={null} orderBy={null} onClose={vi.fn()} onCompleted={vi.fn()} />)
  await userEvent.click(screen.getByRole('checkbox', { name: '年龄' }))
  await userEvent.click(screen.getByRole('button', { name: '选择保存位置' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('保存对话框不可用')
  expect(screen.getByRole('checkbox', { name: '年龄' })).not.toBeChecked()
  expect(api.startExport).not.toHaveBeenCalled()
})

it('does not submit a late output selection after unmount', async () => {
  let resolveSelection!: (value: typeof selection) => void
  const choosing = new Promise<typeof selection>(resolve => { resolveSelection = resolve })
  const api = { startExport: vi.fn(), lookupExport: vi.fn(), reconcileExport: vi.fn(), lookupReconcile: vi.fn() }
  const view = render(<ExcelExportWorkflow open sessionKey="s" scopeKey="w:p:t:s" contextKey="i1" table={table as never} fields={fields as never} statuses={statuses as never} api={api as never} files={{ chooseOutput: vi.fn().mockReturnValue(choosing) }} filter={null} orderBy={null} onClose={vi.fn()} onCompleted={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: '选择保存位置' }))
  view.unmount(); resolveSelection(selection); await Promise.resolve()
  expect(api.startExport).not.toHaveBeenCalled()
})

it('allows a readonly archived project to choose a file and export', async () => {
  const api = { startExport: vi.fn().mockResolvedValue(accepted), lookupExport: vi.fn(), reconcileExport: vi.fn(), lookupReconcile: vi.fn() }, chooseOutput = vi.fn().mockResolvedValue(selection)
  render(<ExcelExportWorkflow open readonly sessionKey="s" scopeKey="w:p:t:s" contextKey="i1" table={table as never} fields={fields as never} statuses={statuses as never} api={api as never} files={{ chooseOutput }} filter={null} orderBy={null} onClose={vi.fn()} onCompleted={vi.fn()} />)
  const choose = screen.getByRole('button', { name: '选择保存位置' })
  expect(choose).not.toBeDisabled(); await userEvent.click(choose)
  expect(chooseOutput).toHaveBeenCalledOnce(); expect(api.startExport).toHaveBeenCalledOnce()
})

it('blocks export when the capability is disabled', async () => {
  const api = { startExport: vi.fn(), lookupExport: vi.fn(), reconcileExport: vi.fn(), lookupReconcile: vi.fn() }, chooseOutput = vi.fn()
  render(<ExcelExportWorkflow open disabled sessionKey="s" scopeKey="w:p:t:s" contextKey="i1" table={table as never} fields={fields as never} statuses={statuses as never} api={api as never} files={{ chooseOutput }} filter={null} orderBy={null} onClose={vi.fn()} onCompleted={vi.fn()} />)
  expect(screen.getByRole('button', { name: '选择保存位置' })).toBeDisabled()
  expect(chooseOutput).not.toHaveBeenCalled(); expect(api.startExport).not.toHaveBeenCalled()
})
