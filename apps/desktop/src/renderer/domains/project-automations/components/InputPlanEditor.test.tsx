import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { choiceTestEnvironment, chooseOption } from '../../../shared/testing/choice-user'
import type { Automation } from '../types'
import { InputPlanEditor } from './InputPlanEditor'

choiceTestEnvironment()
afterEach(cleanup)
type Plan = Automation['inputPlan']
const ref = (tableId: string, fieldId: string) => ({ projectId: 'p', tableId, datasetGeneration: `g-${tableId}`, fieldId })
const record = (tableId: string, value: string) => ({ projectId: 'p', tableId, datasetGeneration: `g-${tableId}`, recordKey: { type: 'text' as const, value } })
const field = (tableId: string, fieldId: string, name: string, type: 'string' | 'number') => ({ ref: ref(tableId, fieldId), key: fieldId, name, type, required: false, validation: {}, writable: true, formula: false, fieldRevision: 1 })
const status = { statusId: 's1', name: '待处理', color: '#123456', order: 0, statusRevision: 1 }
const internal = '11111111-2222-4333-8444-555555555555'
const tables = [
  { id: 't1', name: '资料表', datasetGeneration: 'g-t1', fields: [field('t1', 'f1', '标题', 'string'), field('t1', 'f2', '页数', 'number')], statuses: [status], slotDefinitions: [{ slotId: 'slot-1', name: '归档记录', targetTableId: 't2', required: false }], records: [{ label: '记录一', ref: record('t1', 'r1') }] },
  { id: 't2', name: '归档表', datasetGeneration: 'g-t2', fields: [field('t2', 'f3', '名称', 'string')], statuses: [], slotDefinitions: [] },
]
const input = { inputId: 'i1', alias: '资料', tableId: 't1', datasetGeneration: 'g-t1', mode: 'independent' as const, required: true, fieldBindings: [], filter: { type: 'all', items: [] }, orderBy: [] }
const props = (value: Plan = { inputs: [input] }) => ({ value, onChange: vi.fn(), tables })

it('adds and removes inputs with stable UUID identities', () => {
  vi.stubGlobal('crypto', { randomUUID: () => '00000000-0000-4000-8000-000000000099' })
  const p = props(); render(<InputPlanEditor {...p}/>)
  fireEvent.click(screen.getByRole('button', { name: '添加数据输入' }))
  expect(p.onChange).toHaveBeenLastCalledWith({ inputs: [input, expect.objectContaining({ inputId: '00000000-0000-4000-8000-000000000099', tableId: 't1', datasetGeneration: 'g-t1' })] })
  fireEvent.click(screen.getByRole('button', { name: '移除输入 资料' }))
  expect(p.onChange).toHaveBeenLastCalledWith({ inputs: [] })
  vi.unstubAllGlobals()
})

it('changes an unreferenced table and clears table-scoped configuration', async () => {
  const configured = { ...input, fixedRecord: record('t1', 'r1'), fieldBindings: [{ inputFieldId: 'b1', inputFieldAlias: '标题', fieldRef: ref('t1', 'f1') }], filter: { type: 'compare', fieldId: 'f1', operator: 'eq', value: 'x' }, orderBy: [{ fieldId: 'f1', direction: 'asc' }] }
  const p = props({ inputs: [configured] }); render(<InputPlanEditor {...p}/>)
  await chooseOption(userEvent.setup(), screen.getByRole('combobox', { name: '数据表 资料' }), 't2')
  expect(p.onChange).toHaveBeenCalledWith({ inputs: [{ ...configured, tableId: 't2', datasetGeneration: 'g-t2', fieldBindings: [], filter: { type: 'all', items: [] }, orderBy: [], fixedRecord: undefined }] })
})

it('refuses table change and removal when another input relation references the input', () => {
  const related = { ...input, inputId: 'i2', alias: '关联', mode: 'related' as const, relation: { type: 'sameRecord' as const, sourceInputId: 'i1' } }
  const p = props({ inputs: [input, related] }); render(<InputPlanEditor {...p}/>)
  expect(screen.getByRole('combobox', { name: '数据表 资料' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '移除输入 资料' })).toBeDisabled()
  expect(screen.getByText('此输入正被“关联”引用，不能更换数据表或移除。')).toBeVisible()
  expect(p.onChange).not.toHaveBeenCalled()
})

it('supports fixed records, record loading and explicit stable field bindings', async () => {
  const p = props(), load = vi.fn(), user = userEvent.setup(); const view = render(<InputPlanEditor {...p} onLoadRecords={load}/>)
  await chooseOption(user, screen.getByRole('combobox', { name: '输入模式 资料' }), 'fixedRecord')
  expect(p.onChange).toHaveBeenLastCalledWith({ inputs: [{ ...input, mode: 'fixedRecord', fixedRecord: null }] })
  view.rerender(<InputPlanEditor {...p} value={{ inputs: [{ ...input, mode: 'fixedRecord', fixedRecord: null }] }} onLoadRecords={load}/>)
  fireEvent.click(screen.getByRole('button', { name: '读取资料表记录' }))
  expect(load).toHaveBeenCalledWith('t1')
  view.rerender(<InputPlanEditor {...p} onLoadRecords={load}/>)
  fireEvent.click(screen.getByText('字段映射', { selector: 'summary', exact: false }))
  fireEvent.click(screen.getByRole('button', { name: '添加字段映射 资料' }))
  expect(p.onChange).toHaveBeenLastCalledWith({ inputs: [{ ...input, fieldBindings: [expect.objectContaining({ inputFieldId: expect.any(String), inputFieldAlias: '标题', fieldRef: ref('t1', 'f1') })] }] })
})

it('preserves an unavailable old related source without rewriting it', () => {
  const related = { ...input, mode: 'related' as const, relation: { type: 'sameRecord' as const, sourceInputId: 'source-old' } }
  const p = props({ inputs: [related] }); render(<InputPlanEditor {...p}/>)
  expect(screen.getByRole('combobox', { name: '输入模式 资料' })).toHaveAttribute('data-choice-value', 'related')
  expect(screen.getByText('数据输入引用暂不可用')).toBeVisible()
  expect(p.onChange).not.toHaveBeenCalled()
})

it('uses the shared structured filter and order editor and warns that execution is unavailable', () => {
  const bound = { ...input, fieldBindings: [{ inputFieldId: 'b1', inputFieldAlias: '标题', fieldRef: ref('t1', 'f1') }] }
  const p = props({ inputs: [bound] }); render(<InputPlanEditor {...p}/>)
  fireEvent.click(screen.getByText('筛选与排序', { exact: false }))
  fireEvent.click(screen.getByRole('button', { name: '添加排序' }))
  fireEvent.click(screen.getByRole('button', { name: '应用筛选' }))
  expect(p.onChange).toHaveBeenCalledWith({ inputs: [{ ...bound, orderBy: [{ fieldId: 'f1', direction: 'asc' }] }] })
  expect(screen.queryByRole('textbox', { name: /JSON/ })).toBeNull()
})

it('applies structured status filters and keeps an unapplied draft when the resource directory changes', () => {
  const bound = { ...input, fieldBindings: [{ inputFieldId: 'b1', inputFieldAlias: '标题', fieldRef: ref('t1', 'f1') }] }
  const p = props({ inputs: [bound] }), view = render(<InputPlanEditor {...p}/>)
  fireEvent.click(screen.getByText('筛选与排序', { exact: false }))
  fireEvent.click(screen.getByRole('button', { name: '添加状态条件' }))
  expect(screen.getByRole('group', { name: '状态条件' })).toBeVisible()
  view.rerender(<InputPlanEditor {...p} tables={tables.map(table => ({ ...table, fields: [...table.fields] }))}/>)
  expect(screen.getByRole('group', { name: '状态条件' })).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '应用筛选' }))
  expect(p.onChange).toHaveBeenCalledWith({ inputs: [{ ...bound, filter: { type: 'all', items: [{ type: 'status', operator: 'eq', statusId: 's1' }] } }] })
})

it('creates only backward related sources and supports field and slot identities', async () => {
  const second = { ...input, inputId: 'i2', alias: '归档', tableId: 't2', datasetGeneration: 'g-t2' }
  const p = props({ inputs: [input, second] }), user = userEvent.setup(), view = render(<InputPlanEditor {...p}/>)
  const modes = screen.getAllByRole('combobox', { name: /输入模式/ })
  expect(within(screen.getAllByRole('article')[0]).getByRole('combobox', { name: /输入模式/ })).toHaveAttribute('data-choice-value', 'independent')
  await chooseOption(user, modes[1], 'related')
  expect(p.onChange).toHaveBeenLastCalledWith({ inputs: [input, { ...second, mode: 'related', relation: { type: 'fieldEquals', sourceInputId: 'i1', sourceFieldRef: ref('t1', 'f1'), targetFieldRef: ref('t2', 'f3') } }] })
  const related = { ...second, mode: 'related' as const, relation: { type: 'fieldEquals' as const, sourceInputId: 'i1', sourceFieldRef: ref('t1', 'f1'), targetFieldRef: ref('t2', 'f3') } }
  view.rerender(<InputPlanEditor {...p} value={{ inputs: [input, related] }}/>)
  await chooseOption(user, screen.getByRole('combobox', { name: '关联方式 归档' }), 'recordSlot')
  expect(p.onChange).toHaveBeenLastCalledWith({ inputs: [input, { ...related, relation: { type: 'recordSlot', sourceInputId: 'i1', slotId: 'slot-1' } }] })
})

it('allows same-record relations only within the same table generation', async () => {
  const sameTable = { ...input, inputId: 'i2', alias: '同表资料' }
  const p = props({ inputs: [input, sameTable] }), user = userEvent.setup()
  render(<InputPlanEditor {...p}/>)
  await chooseOption(user, screen.getAllByRole('combobox', { name: /输入模式/ })[1], 'related')
  expect(p.onChange).toHaveBeenLastCalledWith({ inputs: [input, { ...sameTable, mode: 'related', relation: { type: 'sameRecord', sourceInputId: 'i1' } }] })
})

it('reports an unapplied filter draft as invalid without writing the plan', () => {
  const bound = { ...input, fieldBindings: [{ inputFieldId: 'b1', inputFieldAlias: '标题', fieldRef: ref('t1', 'f1') }] }
  const p = props({ inputs: [bound] }), draft = vi.fn()
  render(<InputPlanEditor {...p} resetKey="one" onDraftStateChange={draft}/>)

  fireEvent.click(screen.getByText('筛选与排序', { exact: false }))
  fireEvent.click(screen.getByRole('button', { name: '添加状态条件' }))

  expect(p.onChange).not.toHaveBeenCalled()
  expect(draft).toHaveBeenLastCalledWith({ dirty: true, valid: false })
  const warning = screen.getByText('筛选或排序有尚未应用的修改，请先应用或取消。')
  expect(warning.parentElement).toHaveAttribute('aria-invalid', 'true')
  expect(warning.parentElement).toHaveAttribute('tabindex', '-1')
})

it('resetKey discards the inner filter draft and reports a clean state', async () => {
  const bound = { ...input, fieldBindings: [{ inputFieldId: 'b1', inputFieldAlias: '标题', fieldRef: ref('t1', 'f1') }] }
  const p = props({ inputs: [bound] }), draft = vi.fn()
  const view = render(<InputPlanEditor {...p} resetKey="one" onDraftStateChange={draft}/>)
  fireEvent.click(screen.getByText('筛选与排序', { exact: false }))
  fireEvent.click(screen.getByRole('button', { name: '添加状态条件' }))
  expect(screen.getByRole('group', { name: '状态条件' })).toBeVisible()

  view.rerender(<InputPlanEditor {...p} resetKey="two" onDraftStateChange={draft}/>)

  expect(screen.queryByRole('group', { name: '状态条件' })).not.toBeInTheDocument()
  expect(screen.queryByText(/尚未应用的修改/)).not.toBeInTheDocument()
  await vi.waitFor(() => expect(draft).toHaveBeenLastCalledWith({ dirty: false, valid: true }))
})

it('exposes unknown input error paths through a focusable item alert', () => {
  render(<InputPlanEditor {...props()} errors={{ 'i1.relation.targetFieldRef': '目标字段已经失效' }}/>)

  const alert = screen.getByRole('alert', { name: '' })
  expect(alert).toHaveTextContent('目标字段已经失效')
  expect(alert.closest('article')).toHaveAttribute('aria-invalid', 'true')
  expect(alert.closest('article')).toHaveAttribute('tabindex', '-1')
})

it('offers filter and sort fields only after they are explicitly bound', () => {
  const view = render(<InputPlanEditor {...props()}/>)
  expect(screen.getByText('筛选与排序', { exact: false })).toHaveTextContent('未设置条件')
  fireEvent.click(screen.getByText('筛选与排序', { exact: false }))
  expect(screen.getByText('字段筛选和字段排序需要先添加字段映射；状态条件和系统字段排序仍可使用。')).toBeVisible()

  const bound = { ...input, fieldBindings: [{ inputFieldId: 'b1', inputFieldAlias: '页数', fieldRef: ref('t1', 'f2') }] }
  view.rerender(<InputPlanEditor {...props({ inputs: [bound] })}/>)
  fireEvent.click(screen.getByRole('button', { name: '添加排序' }))
  expect(screen.getByRole('combobox', { name: '排序字段 1' })).toHaveAttribute('data-choice-value', 'field:f2')
})

it('keeps status filters and system-field sorting available without bindings', () => {
  const p = props()
  render(<InputPlanEditor {...p}/>)

  fireEvent.click(screen.getByText('筛选与排序', { exact: false }))
  fireEvent.click(screen.getByRole('button', { name: '添加状态条件' }))
  fireEvent.click(screen.getByRole('button', { name: '添加排序' }))
  expect(screen.getByRole('group', { name: '状态条件' })).toBeVisible()
  expect(screen.getByRole('combobox', { name: '排序字段 1' })).toHaveAttribute('data-choice-value', 'system:status')
  fireEvent.click(screen.getByRole('button', { name: '应用筛选' }))
  expect(p.onChange).toHaveBeenCalledWith({ inputs: [{ ...input, filter: { type: 'all', items: [{ type: 'status', operator: 'eq', statusId: 's1' }] }, orderBy: [{ systemField: 'status', direction: 'asc' }] }] })
})

it('uses semantic labels for unavailable table, record, input, field and slot references', async () => {
  const missingRef = { projectId: 'p', tableId: 't1', datasetGeneration: 'g-t1', fieldId: internal }
  const related = {
    ...input,
    inputId: 'i2',
    alias: '关联资料',
    mode: 'related' as const,
    relation: { type: 'fieldEquals' as const, sourceInputId: internal, sourceFieldRef: missingRef, targetFieldRef: missingRef },
    fieldBindings: [{ inputFieldId: 'binding', inputFieldAlias: '旧字段', fieldRef: missingRef }],
  }
  const fixed = { ...input, mode: 'fixedRecord' as const, fixedRecord: { ...record('t1', internal), recordKey: { type: 'uuid' as const, value: internal } } }
  render(<InputPlanEditor {...props({ inputs: [fixed, related] })} />)
  expect(screen.getByRole('combobox', { name: '固定记录 资料' })).toHaveTextContent('记录已失效')
  expect(screen.getByRole('combobox', { name: '来源输入 关联资料' })).toHaveTextContent('数据输入引用暂不可用')
  expect(screen.getByRole('combobox', { name: '来源字段 关联资料' })).toHaveTextContent('字段已失效')
  expect(screen.getByRole('combobox', { name: '目标字段 关联资料' })).toHaveTextContent('字段已失效')
  expect(screen.getByRole('combobox', { name: '映射字段 旧字段' })).toHaveTextContent('字段已失效')
  expect(document.body.textContent).not.toContain(internal)
})

it('uses a semantic label when the saved table is unavailable', () => {
  render(<InputPlanEditor {...props({ inputs: [{ ...input, tableId: internal, datasetGeneration: 'old' }] })} />)
  expect(screen.getByRole('combobox', { name: '数据表 资料' })).toHaveTextContent('数据表已失效')
  expect(document.body.textContent).not.toContain(internal)
})

it('uses a semantic label when a saved record slot is unavailable', () => {
  const related = { ...input, inputId: 'i2', alias: '归档', tableId: 't2', datasetGeneration: 'g-t2', mode: 'related' as const, relation: { type: 'recordSlot' as const, sourceInputId: 'i1', slotId: internal } }
  render(<InputPlanEditor {...props({ inputs: [input, related] })} />)
  expect(screen.getByRole('combobox', { name: '记录槽 归档' })).toHaveTextContent('记录槽已失效')
  expect(document.body.textContent).not.toContain(internal)
})
