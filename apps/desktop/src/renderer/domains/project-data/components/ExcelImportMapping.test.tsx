import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { choiceTestEnvironment, chooseOption } from '../../../shared/testing/choice-user'
import { ExcelImportMapping, createExcelImportMappingDraft } from './ExcelImportMapping'

const sheet = { sheetId: 's1', name: '客户', headers: ['姓名', '编号'], sample: [['张三', '001']], rowCount: 20, ignoredEmptyRowCount: 2, formulaRowCount: [], identityCandidates: [1], issues: [] }
const fields = [{ key: 'name', name: '客户名称', type: 'string', required: false, validation: {}, ref: { fieldId: 'f1' }, writable: true, formula: false, fieldRevision: 1 }]
afterEach(cleanup)
choiceTestEnvironment()

it('edits new fields and emits the real DataFieldWrite shape', async () => {
  const change = vi.fn(), next = vi.fn()
  const draft = createExcelImportMappingDraft(sheet as never)
  render(<ExcelImportMapping sheet={sheet as never} mode="create" value={draft} onChange={change} onContinue={next} />)
  const names = screen.getAllByLabelText('字段名称')
  fireEvent.change(names[0], { target: { value: '联系人' } })
  expect(change.mock.calls.at(-1)?.[0].columns[0].target.definition).toMatchObject({ key: 'column_1', name: '联系人', type: 'string', required: false, validation: {} })
})

it('supports existing and ignored columns only where allowed', async () => {
  const change = vi.fn()
  const draft = createExcelImportMappingDraft(sheet as never)
  const view = render(<ExcelImportMapping sheet={sheet as never} mode="replace" existingFields={fields as never} value={draft} onChange={change} onContinue={vi.fn()} />)
  await chooseOption(userEvent.setup(), screen.getAllByRole('combobox', { name: '列映射' })[0], 'existing:f1')
  expect(change.mock.calls.at(-1)?.[0].columns[0]).toMatchObject({ target: { kind: 'existing', fieldId: 'f1' } })
  view.rerender(<ExcelImportMapping sheet={sheet as never} mode="create" existingFields={fields as never} value={draft} onChange={change} onContinue={vi.fn()} />)
  expect(screen.getAllByRole('combobox', { name: '列映射' })[0]).not.toHaveTextContent('客户名称')
})

it('blocks ignored identity and duplicate field targets', async () => {
  const next = vi.fn(), change = vi.fn()
  const draft = { ...createExcelImportMappingDraft(sheet as never), identity: { mode: 'column' as const, columnIndex: 1 } }
  render(<ExcelImportMapping sheet={sheet as never} mode="replace" existingFields={fields as never} value={draft} onChange={change} onContinue={next} />)
  expect(screen.getByText(/身份列必须保持字段映射/)).not.toBeNull()
  screen.getAllByRole('combobox', { name: '列映射' })[1].focus(); await userEvent.keyboard('{ArrowDown}')
  expect(screen.getAllByRole('option').find(option => option.getAttribute('data-choice-value') === 'ignore')).toHaveAttribute('data-disabled')
  cleanup()
  const invalid = { ...draft, columns: [draft.columns[0], { columnIndex: 1, target: null }] }
  render(<ExcelImportMapping sheet={sheet as never} mode="replace" existingFields={fields as never} value={invalid} onChange={change} onContinue={next} />)
  expect(screen.getByRole('alert')).toHaveTextContent('身份列不能忽略')
  expect(screen.getByRole('button', { name: '继续导入' })).toBeDisabled()
})

it('rejects duplicate targets, keys and invalid constraints', () => {
  const base = createExcelImportMappingDraft(sheet as never)
  const duplicate = { ...base, columns: base.columns.map(column => column.target?.kind === 'new' ? { ...column, target: { ...column.target, definition: { ...column.target.definition, key: 'same', validation: { minLength: 5, maxLength: 2 } } } } : column) }
  render(<ExcelImportMapping sheet={sheet as never} mode="create" value={duplicate} onChange={vi.fn()} onContinue={vi.fn()} />)
  expect(screen.getAllByRole('alert').map(node => node.textContent).join(' ')).toContain('新字段键不能重复')
  expect(screen.getAllByRole('alert').map(node => node.textContent).join(' ')).toContain('定义或约束无效')
})
