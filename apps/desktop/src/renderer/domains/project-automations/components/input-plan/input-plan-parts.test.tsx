import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { choiceTestEnvironment, chooseOption } from '../../../../shared/testing/choice-user'
import { findInternalIds } from '../../../../shared/testing/internal-id-scan'
import { FieldBindingSection } from './FieldBindingSection'
import { InputMatchPreview, InputMatchStatus } from './InputMatchPreview'
import { RelationGraph, relationEdges } from './RelationGraph'
import type { InputDefinition, InputTableOption } from './types'

choiceTestEnvironment()
afterEach(cleanup)
const ref = (tableId: string, fieldId: string) => ({ projectId: 'p', tableId, datasetGeneration: `g-${tableId}`, fieldId })
const field = (tableId: string, fieldId: string, name: string, type: 'string' | 'number') => ({ ref: ref(tableId, fieldId), key: fieldId, name, type, required: false, validation: {}, writable: true, formula: false, fieldRevision: 1 })
const tables = [
  { id: 't1', name: '资料表', datasetGeneration: 'g-t1', fields: [field('t1', 'f1', '标题', 'string'), field('t1', 'f2', '页数', 'string')], statuses: [], slotDefinitions: [] },
  { id: 't2', name: '归档表', datasetGeneration: 'g-t2', fields: [field('t2', 'f3', '名称', 'string')], statuses: [], slotDefinitions: [] },
] as unknown as InputTableOption[]
const input = { inputId: '11111111-2222-4333-8444-555555555555', alias: '资料', tableId: 't1', datasetGeneration: 'g-t1', mode: 'independent', required: true, fieldBindings: [], filter: { type: 'all', items: [] }, orderBy: [], signatureInput: 'doc' } as unknown as InputDefinition
const group = { key: 'doc', name: '文档', fields: [
  { key: 'title', name: '标题', type: 'string' as const, required: true, sensitive: false },
  { key: 'pages', name: '页数', type: 'number' as const, required: false, sensitive: false },
] }

it('marks an unbound required signature field red with an inline hint and binds on selection', async () => {
  const onChange = vi.fn()
  render(<FieldBindingSection input={input} table={tables[0]} group={group} disabled={false} onChange={onChange}/>)
  const panel = screen.getByRole('group', { name: '流程字段对应 资料' })
  expect(within(panel).getByRole('alert')).toHaveTextContent('请选择对应的表字段')
  expect(within(panel).getByRole('combobox', { name: '对应表字段 标题' })).toHaveAttribute('aria-invalid', 'true')
  expect(within(panel).getByText('文本 · 必填')).toBeVisible()
  await chooseOption(userEvent.setup(), screen.getByRole('combobox', { name: '对应表字段 标题' }), 'f1')
  expect(onChange).toHaveBeenCalledWith({ ...input, fieldBindings: [expect.objectContaining({ fieldRef: ref('t1', 'f1'), signatureField: 'title', inputFieldAlias: '标题' })] })
  expect(findInternalIds(document.body)).toEqual([])
})

it('warns about an incompatible type but keeps the person choice', () => {
  const bound = { ...input, fieldBindings: [{ inputFieldId: 'b', inputFieldAlias: '页数', fieldRef: ref('t1', 'f2'), signatureField: 'pages' }] }
  render(<FieldBindingSection input={bound} table={tables[0]} group={group} disabled={false} onChange={vi.fn()}/>)
  expect(screen.getByText('类型不一致：流程需要数字，所选字段是文本')).toBeVisible()
})

it('auto-matches only unbound fields and leaves manual bindings alone', () => {
  const onChange = vi.fn()
  const manual = { ...input, fieldBindings: [{ inputFieldId: 'b', inputFieldAlias: '手动', fieldRef: ref('t1', 'f2'), signatureField: 'pages' }] }
  render(<FieldBindingSection input={manual} table={tables[0]} group={group} disabled={false} onChange={onChange}/>)
  fireEvent.click(screen.getByRole('button', { name: '按名称自动匹配' }))
  expect(onChange).toHaveBeenCalledWith({ ...manual, fieldBindings: [manual.fieldBindings[0], expect.objectContaining({ fieldRef: ref('t1', 'f1'), signatureField: 'title' })] })
})

it('shows matched and unprocessed counts with the sample rows', () => {
  const item = { inputId: 'i', alias: '资料', outcome: 'counted', matchedCount: 12, unprocessedCount: 5, sample: [{ 标题: 'A', 密码: '已隐藏' }, { 标题: 'B', 密码: null }] } as never
  render(<InputMatchPreview item={item}/>)
  expect(screen.getByTestId('input-match')).toHaveTextContent('当前条件匹配 12 行，其中未处理 5 行')
  const table = screen.getByRole('table', { name: '样例行' })
  expect(within(table).getAllByRole('columnheader').map(cell => cell.textContent)).toEqual(['标题', '密码'])
  expect(within(table).getAllByRole('row')).toHaveLength(3)
  expect(within(table).getByText('已隐藏')).toBeVisible()
})

it('gives business wording for no match, dependent and invalid outcomes', () => {
  const base = { inputId: 'i', alias: '资料', unprocessedCount: null, sample: [] }
  const view = render(<InputMatchPreview item={{ ...base, outcome: 'counted', matchedCount: 0 } as never}/>)
  expect(screen.getByText('没有符合条件的行，请检查筛选条件。')).toBeVisible()
  view.rerender(<InputMatchPreview item={{ ...base, outcome: 'dependsOnOtherInput', matchedCount: null } as never}/>)
  expect(screen.getByText(/没有单独的匹配行数/)).toBeVisible()
  view.rerender(<InputMatchPreview item={{ ...base, outcome: 'filterInvalid', matchedCount: null } as never}/>)
  expect(screen.getByText(/筛选条件无法使用/)).toBeVisible()
})

it('reports a failed check with its reason and a retry', () => {
  const retry = vi.fn()
  render(<InputMatchStatus state={{ status: 'error', error: '服务暂不可用', retry }}/>)
  expect(screen.getByRole('alert')).toHaveTextContent('服务暂不可用')
  fireEvent.click(screen.getByRole('button', { name: '重新检查' }))
  expect(retry).toHaveBeenCalled()
})

it('draws related inputs as labelled links and selects the link target', () => {
  const second = { ...input, inputId: 'i2', alias: '归档', tableId: 't2', datasetGeneration: 'g-t2', mode: 'related', relation: { type: 'fieldEquals', sourceInputId: input.inputId, sourceFieldRef: ref('t1', 'f1'), targetFieldRef: ref('t2', 'f3') } } as unknown as InputDefinition
  expect(relationEdges([input, second], tables)).toEqual([{ inputId: 'i2', sourceId: input.inputId, label: '标题 = 名称', sourceField: '标题', targetField: '名称' }])
  const onSelect = vi.fn()
  const { container } = render(<RelationGraph inputs={[input, second]} tables={tables} onSelect={onSelect}/>)
  expect(screen.getByText('标题 = 名称')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /关联：标题 = 名称/ }))
  expect(onSelect).toHaveBeenCalledWith('i2')
  expect(findInternalIds(container)).toEqual([])
})

it('renders nothing when no input is related', () => {
  const { container } = render(<RelationGraph inputs={[input]} tables={tables} onSelect={vi.fn()}/>)
  expect(container).toBeEmptyDOMElement()
})

const pair = (): InputDefinition[] => {
  const second = { ...input, inputId: 'i2', alias: '归档', tableId: 't2', datasetGeneration: 'g-t2', mode: 'related', relation: { type: 'fieldEquals', sourceInputId: input.inputId, sourceFieldRef: ref('t1', 'f1'), targetFieldRef: ref('t2', 'f3') } } as unknown as InputDefinition
  return [input, second]
}

it('exposes the graph as a group with a text list of every link that jumps to the same editor', () => {
  const onSelect = vi.fn()
  render(<RelationGraph inputs={pair()} tables={tables} onSelect={onSelect}/>)
  expect(screen.getByRole('group', { name: '输入关联图' })).toBeInTheDocument()
  expect(screen.queryByRole('img')).toBeNull()
  const list = screen.getByRole('list', { name: '关联列表' })
  fireEvent.click(within(list).getByRole('button', { name: '资料·标题 ↔ 归档·名称' }))
  expect(onSelect).toHaveBeenCalledWith('i2')
})

it('bows links between the same two inputs at different heights and clips long names', () => {
  const [a, b] = pair()
  const back = { ...a, mode: 'related', relation: { type: 'sameRecord', sourceInputId: 'i2' }, alias: '一个非常非常非常长的输入名称需要截断显示' } as unknown as InputDefinition
  const { container } = render(<RelationGraph inputs={[back, b]} tables={tables} onSelect={vi.fn()}/>)
  const paths = Array.from(container.querySelectorAll('svg path[stroke="currentColor"]')).map(path => path.getAttribute('d'))
  expect(paths).toHaveLength(2)
  expect(new Set(paths).size).toBe(2)
  const name = screen.getAllByText(/一个非常非常非常长/).find(node => node.tagName.toLowerCase() === 'text')!
  expect(name.textContent).toContain('截断显示')
  expect(name.closest('[clip-path]')).not.toBeNull()
})

it('keeps the pre-check reason intact without doubled punctuation', () => {
  render(<InputMatchStatus state={{ status: 'error', error: '数据表读取超时。', retry: vi.fn() }}/>)
  expect(screen.getByRole('alert').textContent).toContain('数据表读取超时。已填写')
  expect(screen.getByRole('alert').textContent).not.toContain('。。')
})

it('shows a validation-class pre-check answer as a quiet hint, not a warning', () => {
  render(<InputMatchStatus state={{ status: 'error', error: '请选择数据表', quiet: true, retry: vi.fn() }}/>)
  expect(screen.queryByRole('alert')).toBeNull()
  expect(screen.getByRole('status')).toHaveTextContent('补全后会自动检查')
  expect(screen.getByRole('status')).toHaveTextContent('请选择数据表')
})

it('never shows an internal key as a sample column header', () => {
  const bound = { ...input, fieldBindings: [{ inputFieldId: 'b', inputFieldAlias: '', fieldRef: ref('t1', 'f1'), signatureField: 'title' }] }
  const item = { inputId: 'i', alias: '资料', outcome: 'counted', matchedCount: 2, unprocessedCount: null, sample: [{ '': 'A' }, { '': 'B' }] } as never
  const view = render(<InputMatchPreview item={item} input={bound} table={tables[0]}/>)
  expect(screen.getByRole('columnheader')).toHaveTextContent('标题')
  view.rerender(<InputMatchPreview item={item}/>)
  expect(screen.getByRole('columnheader')).toHaveTextContent('第 1 列')
})
