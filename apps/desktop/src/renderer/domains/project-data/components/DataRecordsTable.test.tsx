import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { components } from '../../../shared/api/generated'
import { DataRecordsTable } from './DataRecordsTable'
import { useRecordSelection } from '../use-record-selection'
type Schema = components['schemas']
afterEach(cleanup)
const field: Schema['DataFieldView'] = { ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', fieldId: 'f' }, key: 'value', name: '业务值', type: 'string', required: false, validation: {}, writable: true, formula: false, fieldRevision: 1 }
function row(key: Schema['DataRecordKey'], cells: Schema['DataCellView'][] = []): Schema['DataRecordView'] { return { ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', recordKey: key }, values: cells, recordSlots: [], statusId: null, currentEnvironmentId: null, contentRevision: 1, statusRevision: 1, linkRevision: 1, deleted: false, createdAt: '2026-09-13T00:00:00Z', updatedAt: '2026-09-13T00:00:00Z' } }
const cell = (value: Schema['DataCellView']['value'], readable = true): Schema['DataCellView'] => ({ fieldId: 'f', value, readable, source: 'local' })
const props = { fields: [field], statuses: [], onRetry: vi.fn(), onOpen: vi.fn(), onPageChange: vi.fn() }
const page = (items: Schema['DataRecordView'][], total = items.length): Schema['DataRecordPage'] => ({ items, total, page: 1, pageSize: 2, sort: '[]' })
it('preserves typed identities and opens the exact record', async () => {
  const records = [row({ type: 'text', value: '001' }), row({ type: 'text', value: '1' }), row({ type: 'integer', value: '1' })], open = vi.fn()
  render(<DataRecordsTable {...props} page={page(records)} onOpen={open} />)
  expect(screen.getByText('文本 · 001')).toBeVisible(); expect(screen.getByText('文本 · 1')).toBeVisible(); expect(screen.getByText('整数 · 1')).toBeVisible()
  expect(screen.getByText('整数 · 1')).toHaveAccessibleName('整数 · 1')
  expect(screen.getByText('整数 · 1')).toHaveAttribute('title', '整数 · 1')
  await userEvent.setup().click(screen.getByRole('button', { name: '查看记录 整数 · 1' }))
  expect(open).toHaveBeenCalledWith(records[2])
})
it('distinguishes missing/null/empty/false and preserves date offset without machine conversion', () => {
  const date: Schema['DataDateScalar'] = { kind: 'date', precision: 'datetime', value: '2026-09-13T12:00:00.123456789123456789', offset: '+08:00' }
  const records = [[], [cell(null)], [cell('')], [cell(false)], [cell(date)]].map((values, index) => row({ type: 'text', value: String(index) }, values))
  render(<DataRecordsTable {...props} page={page(records)} />)
  expect(screen.getByText('未填写')).toBeVisible(); expect(screen.getByText('空值')).toBeVisible(); expect(screen.getByText('空字符串')).toBeVisible(); expect(screen.getByText('否')).toBeVisible()
  expect(screen.getByText(`${date.value} ${date.offset}`)).toBeVisible()
})
it('does not leak unreadable values and only renders selected columns', () => {
  const view = render(<DataRecordsTable {...props} page={page([row({ type: 'text', value: '1' }, [cell('PRIVATE', false)])])} />)
  expect(screen.getByText('不可读取')).toBeVisible(); expect(document.body.textContent).not.toContain('PRIVATE')
  view.rerender(<DataRecordsTable {...props} visibleFieldIds={[]} page={page([row({ type: 'text', value: '1' })])} />)
  expect(screen.queryByRole('columnheader', { name: '业务值' })).not.toBeInTheDocument()
})
it('uses server pagination, preserves stale data on error and blocks write actions while readonly', async () => {
  const next = vi.fn(), retry = vi.fn(), status = vi.fn(), create = vi.fn()
  render(<DataRecordsTable {...props} page={page([row({ type: 'text', value: '1' }), row({ type: 'text', value: '2' })], 4)} error="连接中断" readonly onRetry={retry} onPageChange={next} onCreate={create} onStatusChange={status} />)
  expect(screen.getByRole('alert')).toHaveTextContent('连接中断'); expect(screen.getByText('文本 · 1')).toBeVisible()
  await userEvent.setup().click(screen.getByRole('button', { name: '下一页' })); expect(next).toHaveBeenCalledWith(2)
  expect(screen.queryByRole('button', { name: '新增记录' })).not.toBeInTheDocument()
  expect(screen.getAllByRole('button', { name: /修改状态/ }).every(button => button.hasAttribute('disabled'))).toBe(true)
  await userEvent.setup().click(within(screen.getByRole('alert')).getByRole('button', { name: '重试' })); expect(retry).toHaveBeenCalledOnce()
})
it('shows loading, empty, no-match and first-load failure as distinct states', () => {
  const view = render(<DataRecordsTable {...props} loading />)
  expect(screen.getByRole('status')).toHaveTextContent('正在加载记录')
  view.rerender(<DataRecordsTable {...props} page={page([])} />); expect(screen.getByText('还没有记录')).toBeVisible()
  view.rerender(<DataRecordsTable {...props} page={page([])} hasFilters />); expect(screen.getByText('没有匹配的记录')).toBeVisible()
  view.rerender(<DataRecordsTable {...props} error="首次读取失败" />)
  expect(screen.queryByText('还没有记录')).not.toBeInTheDocument(); expect(screen.getByRole('alert')).toHaveTextContent('首次读取失败')
})
it('distinguishes unset status from a missing status definition', () => {
  const missing = { ...row({ type: 'text', value: '2' }), statusId: 'gone' }
  render(<DataRecordsTable {...props} page={page([row({ type: 'text', value: '1' }), missing])} />)
  expect(screen.getByText('未设置')).toBeVisible(); expect(screen.getByText('状态不可用')).toBeVisible()
})

it.each([0, 2])('reserves the declared column widths for %i business columns before horizontal scrolling', count => {
  const fields = Array.from({ length: count }, (_, index) => ({ ...field, ref: { ...field.ref, fieldId: `f${index}` } }))
  render(<DataRecordsTable {...props} fields={fields} page={page([row({ type: 'text', value: '1' })])} />)
  expect(screen.getByRole('columnheader', { name: '记录身份' })).toHaveAttribute('data-column-width', '112')
  expect(document.querySelector('[data-record-column="identity"]')).toHaveStyle({ width: '112px' })
  expect(screen.getByRole('table')).toHaveStyle({ minWidth: `${112 + 160 + 112 + count * 200}px` })
})

it('renders a clickable status badge and keeps the original status callback', async () => {
  const record={...row({type:'uuid',value:'12345678-1234-1234-1234-123456789abc'}),statusId:'open'},onStatusChange=vi.fn()
  render(<DataRecordsTable {...props} statuses={[{statusId:'open',name:'进行中',color:'#123456',order:0,statusRevision:1}]} page={page([record])} onStatusChange={onStatusChange}/>)
  await userEvent.click(screen.getByRole('button',{name:'修改状态 UUID · 12345678-1234-1234-1234-123456789abc'}))
  expect(screen.getByText('进行中')).toHaveAttribute('data-status-badge')
  expect(onStatusChange).toHaveBeenCalledWith(record)
})

it('offers controlled row/page selection and bulk actions without changing legacy consumers', async () => {
  const records=[row({type:'text',value:'1'}),row({type:'integer',value:'2'})],bulk=vi.fn()
  function Harness(){const selection=useRecordSelection({workspaceKey:'w',projectId:'p',tableId:'t',datasetGeneration:'g'});return <DataRecordsTable {...props} page={page(records)} selection={selection} onBulkStatus={bulk}/>}
  render(<Harness/>); expect(screen.queryByRole('toolbar')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('checkbox',{name:'选择记录 文本 · 1'})); expect(screen.getByRole('toolbar')).toHaveTextContent('已选择 1 条')
  await userEvent.click(screen.getByRole('button',{name:'批量设置状态'})); expect(bulk).toHaveBeenCalledOnce()
  await userEvent.click(screen.getByRole('checkbox',{name:'选择本页记录'})); expect(screen.getByRole('toolbar')).toHaveTextContent('已选择 2 条')
  await userEvent.click(screen.getByRole('button',{name:'清空选择'})); expect(screen.queryByRole('toolbar')).not.toBeInTheDocument()
})

it('disables every selection control while readonly, disabled, or loading',()=>{
  const selection={targets:[],count:0,error:null,isSelected:()=>false,toggle:vi.fn(),togglePage:vi.fn(),clear:vi.fn()}
  render(<DataRecordsTable {...props} page={page([row({type:'text',value:'1'})])} selection={selection} readonly disabled loading/>)
  expect(screen.getAllByRole('checkbox').every(item=>item.hasAttribute('disabled'))).toBe(true)
})
