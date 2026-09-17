import '@testing-library/jest-dom/vitest'
import { act, cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { choiceTestEnvironment, chooseOption } from '../../../shared/testing/choice-user'
import { DataCommandUncertain } from '../data-command'
import { ExcelImportWizard } from './ExcelImportWizard'

beforeEach(() => { const values = new Map<string, string>(); vi.stubGlobal('localStorage', { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key), clear: () => values.clear() }) }); afterEach(() => { cleanup(); vi.unstubAllGlobals() })
choiceTestEnvironment()
const selection = { selectionToken: 'token', displayName: '客户.xlsx', kind: 'excel-input', expiresAt: '2099-01-01T00:00:00Z' }
const inspection = { inspectionId: 'i', fingerprint: 'f', filename: '客户.xlsx', expiresAt: '2099-01-01T00:00:00Z', issues: [], sheets: [{ sheetId: 's', name: '客户', headers: ['姓名'], sample: [['张三']], rowCount: 1, ignoredEmptyRowCount: 0, formulaRowCount: [0], identityCandidates: [0], issues: [] }] }
const inspectOperation = { operationId: 'inspect', operationKey: 'ik', kind: 'inspectExcel', status: 'succeeded', resource: { type: 'project', projectId: 'p' }, operationRevision: 1, result: inspection, error: null, createdAt: '', updatedAt: '' }

it('runs choose, inspect, mapping and create review without page integration', async () => {
  const api = { inspect: vi.fn().mockResolvedValue(inspectOperation), lookupInspection: vi.fn().mockResolvedValue(inspectOperation), startImport: vi.fn(), replace: vi.fn(), lookupImport: vi.fn(), replaceImpact: vi.fn() }
  const props = { open: true, mode: 'create' as const, sessionKey: 'new', scopeKey: 'w:p', contextKey: 'i:p', api: api as never, files: { chooseInput: vi.fn().mockResolvedValue(selection as never) }, onClose: vi.fn(), onCompleted: vi.fn() }
  const view = render(<ExcelImportWizard {...props} />)
  await userEvent.click(screen.getByRole('button', { name: '选择 Excel 文件' }))
  await userEvent.click(await screen.findByRole('button', { name: '检查文件' }))
  await chooseOption(userEvent.setup(), await screen.findByRole('combobox', { name: '工作表' }), 's'); await userEvent.click(screen.getByRole('button', { name: '继续字段映射' }))
  view.rerender(<ExcelImportWizard {...props} contextKey="i2:p" />)
  expect(await screen.findByText('字段映射')).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '继续导入' }))
  expect(screen.getByText('确认导入')).toBeVisible()
  expect(screen.getByLabelText('数据表名称')).toBeVisible()
})

it('warns before closing a dirty unsubmitted mapping', async () => {
  const api = { inspect: vi.fn().mockResolvedValue(inspectOperation), lookupInspection: vi.fn(), startImport: vi.fn(), replace: vi.fn(), lookupImport: vi.fn(), replaceImpact: vi.fn() }
  const close = vi.fn()
  render(<ExcelImportWizard open mode="create" sessionKey="new" scopeKey="w:p" contextKey="i:p" api={api as never} files={{ chooseInput: vi.fn().mockResolvedValue(selection as never) }} onClose={close} onCompleted={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: '选择 Excel 文件' })); await userEvent.click(await screen.findByRole('button', { name: '检查文件' })); await chooseOption(userEvent.setup(), await screen.findByRole('combobox', { name: '工作表' }), 's'); await userEvent.click(screen.getByRole('button', { name: '继续字段映射' }))
  await userEvent.click(screen.getAllByRole('button', { name: '关闭' }).at(-1)!)
  expect(screen.getByText('放弃未提交的导入草稿？')).toBeVisible(); expect(close).not.toHaveBeenCalled()
})

it('offers lookup instead of a new inspection while the original result is unknown', async () => {
  localStorage.setItem('autoflow:excel-inspection:w:p', JSON.stringify({ key: 'original', selection }))
  const api = { inspect: vi.fn(), lookupInspection: vi.fn(() => new Promise(() => {})), startImport: vi.fn(), replace: vi.fn(), lookupImport: vi.fn(), replaceImpact: vi.fn() }
  render(<ExcelImportWizard open mode="create" sessionKey="new" scopeKey="w:p" contextKey="i:p" api={api as never} files={{ chooseInput: vi.fn() }} onClose={vi.fn()} onCompleted={vi.fn()} />)
  expect(await screen.findByText('正在核对上次文件检查。')).toBeVisible()
  expect(screen.getByRole('button', { name: '核对检查结果' })).toBeDisabled()
  expect(screen.queryByRole('button', { name: '检查文件' })).toBeNull()
})

it('reports an unknown import as guarded and confirms leaving without losing its identity', async () => {
  localStorage.setItem('autoflow:excel-import:w:p', JSON.stringify({ key: 'original', body: { mode: 'create', request: { name: '客户', description: '', inspectionId: 'i', fingerprint: 'f', sheetId: 's', mapping: [], identity: { mode: 'system' } } } }))
  const api = { inspect: vi.fn(), lookupInspection: vi.fn(), startImport: vi.fn(), replace: vi.fn(), lookupImport: vi.fn().mockRejectedValue(new DataCommandUncertain('offline')), replaceImpact: vi.fn() }
  const dirty = vi.fn(), close = vi.fn()
  render(<ExcelImportWizard open mode="create" sessionKey="new" scopeKey="w:p" contextKey="i:p" api={api as never} files={{ chooseInput: vi.fn() }} onClose={close} onCompleted={vi.fn()} onDirtyChange={dirty} />)
  await screen.findByText('已保存导入请求，正在核对原操作。'); expect(dirty).toHaveBeenLastCalledWith(true)
  await userEvent.click(await screen.findByRole('button', { name: '关闭' }))
  expect(screen.getByText('导入结果尚未确认')).toBeVisible(); expect(close).not.toHaveBeenCalled()
  expect(JSON.parse(localStorage.getItem('autoflow:excel-import:w:p')!).key).toBe('original')
})
// @vitest-environment jsdom

it('revokes the previous replacement impact while checking a revised mapping', async () => {
  let rejectImpact!: (error: Error) => void
  const api = { inspect: vi.fn().mockResolvedValue(inspectOperation), lookupInspection: vi.fn(), startImport: vi.fn(), replace: vi.fn(), lookupImport: vi.fn(), replaceImpact: vi.fn().mockResolvedValueOnce({ impactRevision: 'first', recordCount: 1, blockers: [] }).mockImplementationOnce(() => new Promise((_, reject) => { rejectImpact = reject })) }
  render(<ExcelImportWizard open mode="replace" sessionKey="replace" scopeKey="w:p:t" contextKey="i:p:t" table={{ tableId: 't', name: '客户', datasetGeneration: 'g', tableRevision: 1 } as never} api={api as never} files={{ chooseInput: vi.fn().mockResolvedValue(selection as never) }} onClose={vi.fn()} onCompleted={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: '选择 Excel 文件' }))
  await userEvent.click(await screen.findByRole('button', { name: '检查文件' }))
  await chooseOption(userEvent.setup(), await screen.findByRole('combobox', { name: '工作表' }), 's')
  await userEvent.click(screen.getByRole('button', { name: '继续字段映射' }))
  await userEvent.click(screen.getByRole('button', { name: '继续导入' }))
  expect(await screen.findByText('1 条原记录将被替换。')).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '返回映射' }))
  await userEvent.click(screen.getByRole('button', { name: '继续导入' }))
  expect(screen.getByRole('button', { name: '确认并开始导入' })).toBeDisabled()
  await act(async () => rejectImpact(new Error('影响检查失败')))
  expect(await screen.findByRole('alert')).toHaveTextContent('操作失败，请重试')
  expect(screen.getByRole('button', { name: '确认并开始导入' })).toBeDisabled()
  expect(api.replace).not.toHaveBeenCalled()
})

it('ignores an older impact response after returning to mapping and starting another review', async () => {
  let finishOld!: (value: unknown) => void
  const api = { inspect: vi.fn().mockResolvedValue(inspectOperation), lookupInspection: vi.fn(), startImport: vi.fn(), replace: vi.fn(), lookupImport: vi.fn(), replaceImpact: vi.fn().mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve })).mockResolvedValueOnce({ impactRevision: 'new', recordCount: 2, blockers: ['数据已变化，请重新检查'] }) }
  render(<ExcelImportWizard open mode="replace" sessionKey="replace" scopeKey="w:p:t" contextKey="i:p:t" table={{ tableId: 't', name: '客户', datasetGeneration: 'g', tableRevision: 1 } as never} api={api as never} files={{ chooseInput: vi.fn().mockResolvedValue(selection as never) }} onClose={vi.fn()} onCompleted={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: '选择 Excel 文件' }))
  await userEvent.click(await screen.findByRole('button', { name: '检查文件' }))
  await chooseOption(userEvent.setup(), await screen.findByRole('combobox', { name: '工作表' }), 's')
  await userEvent.click(screen.getByRole('button', { name: '继续字段映射' }))
  await userEvent.click(screen.getByRole('button', { name: '继续导入' }))
  await userEvent.click(screen.getByRole('button', { name: '返回映射' }))
  await userEvent.click(screen.getByRole('button', { name: '继续导入' }))
  await screen.findByText('2 条原记录将被替换。')
  await act(async () => finishOld({ impactRevision: 'old', recordCount: 1, blockers: [] }))
  expect(screen.getByText('2 条原记录将被替换。')).toBeVisible()
  expect(screen.getByRole('button', { name: '确认并开始导入' })).toBeDisabled()
  expect(screen.getByRole('alert')).toHaveTextContent('当前数据暂不能替换，请刷新后重试')
})
