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
const props = { fields: [field], statuses: [], identityMode: { mode: 'field' as const, fieldId: 'f' }, onRetry: vi.fn(), onOpen: vi.fn(), onPageChange: vi.fn() }
const page = (items: Schema['DataRecordView'][], total = items.length): Schema['DataRecordPage'] => ({ items, total, page: 1, pageSize: 2, sort: '[]' })
it('never exposes a system record UUID in visible or accessible UI', () => {
  const uuid = '11111111-2222-4333-8444-555555555555'
  render(<DataRecordsTable {...props} identityMode={{ mode: 'system' }} page={page([row({ type: 'uuid', value: uuid }, [cell('业务标题')])])} onEdit={vi.fn()} onDelete={vi.fn()} onStatusChange={vi.fn()} />)
  expect(screen.getAllByText('业务标题')).toHaveLength(2)
  expect(document.body.textContent).not.toContain(uuid)
  for (const element of document.querySelectorAll('[title],[placeholder],[aria-label],[aria-description]')) {
    for (const name of ['title', 'placeholder', 'aria-label', 'aria-description']) expect(element.getAttribute(name) ?? '').not.toContain(uuid)
  }
})
it('keeps the same UUID visible when it is user-owned field identity data', () => {
  const uuid = '11111111-2222-4333-8444-555555555555'
  render(<DataRecordsTable {...props} identityMode={{ mode: 'field', fieldId: 'f' }} page={page([row({ type: 'uuid', value: uuid }, [cell(uuid)])])} />)
  expect(screen.getAllByText(uuid)).toHaveLength(1)
  expect(screen.getAllByRole('columnheader', { name: '业务值' })).toHaveLength(1)
  expect(screen.queryByRole('columnheader', { name: '记录' })).toBeNull()
})

it('falls back to the dedicated identity column when the identity field is hidden', () => {
  render(<DataRecordsTable {...props} identityMode={{ mode: 'field', fieldId: 'f' }} visibleFieldIds={[]} page={page([row({ type: 'text', value: '001' }, [cell('隐藏值')])])} />)
  expect(screen.getAllByRole('columnheader', { name: '业务值' })).toHaveLength(1)
  expect(screen.getAllByText('001')).toHaveLength(1)
  expect(screen.queryByText('隐藏值')).toBeNull()
  expect(document.querySelector('[data-record-column="identity"]')).not.toBeNull()
})
it('preserves typed identities and opens the exact record', async () => {
  const records = [row({ type: 'text', value: '001' }, [cell('001')]), row({ type: 'text', value: '1' }, [cell('1')]), row({ type: 'integer', value: '1' }, [cell(1)])], open = vi.fn()
  render(<DataRecordsTable {...props} page={page(records)} onOpen={open} />)
  expect(screen.getByText('001')).toBeVisible(); expect(screen.getAllByText('1')).toHaveLength(2)
  await userEvent.setup().click(screen.getAllByRole('button', { name: '查看记录 1' })[1])
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
  expect(screen.getAllByRole('columnheader', { name: '业务值' })).toHaveLength(1)
})
it('uses server pagination, preserves stale data on error and blocks write actions while readonly', async () => {
  const next = vi.fn(), retry = vi.fn(), status = vi.fn(), create = vi.fn()
  render(<DataRecordsTable {...props} identityMode={{ mode: 'field', fieldId: 'other' }} page={page([row({ type: 'text', value: '1' }, [cell('1')]), row({ type: 'text', value: '2' }, [cell('2')])], 4)} error="连接中断" readonly onRetry={retry} onPageChange={next} onCreate={create} onStatusChange={status} />)
  expect(screen.getByRole('alert')).toHaveTextContent('连接中断'); expect(screen.getByText('1')).toBeVisible()
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
  expect(screen.getByRole('columnheader', { name: '字段已失效' })).toHaveAttribute('data-column-width', '112')
  expect(document.querySelector('[data-record-column="identity"]')).toHaveStyle({ width: '112px' })
  expect(screen.getByRole('table')).toHaveStyle({ minWidth: `${112 + 128 + 136 + 160 + count * 160}px` })
})

it('uses a decorative remainder column when there are no business columns', () => {
  render(<DataRecordsTable {...props} fields={[]} page={page([row({ type: 'text', value: '1' })])} />)
  expect(document.querySelector('col[data-record-column="remainder"]')).toBeInTheDocument()
  expect(document.querySelectorAll('[data-record-remainder]')).toHaveLength(2)
  expect(Array.from(document.querySelectorAll('[data-record-remainder]')).every(node => node.getAttribute('aria-hidden') === 'true')).toBe(true)
})

it('renders a clickable status badge and keeps the original status callback', async () => {
  const record={...row({type:'uuid',value:'12345678-1234-1234-1234-123456789abc'}),statusId:'open'},onStatusChange=vi.fn()
  render(<DataRecordsTable {...props} statuses={[{statusId:'open',name:'进行中',color:'#123456',order:0,statusRevision:1}]} page={page([record])} onStatusChange={onStatusChange}/>)
  await userEvent.click(screen.getByRole('button',{name:'修改状态 12345678-1234-1234-1234-123456789abc'}))
  expect(screen.getByText('进行中')).toHaveAttribute('data-status-badge')
  expect(onStatusChange).toHaveBeenCalledWith(record)
})

it('offers controlled row/page selection and bulk actions without changing legacy consumers', async () => {
  const records=[row({type:'text',value:'1'}),row({type:'integer',value:'2'})],bulk=vi.fn()
  function Harness(){const selection=useRecordSelection({workspaceKey:'w',projectId:'p',tableId:'t',datasetGeneration:'g'});return <DataRecordsTable {...props} page={page(records)} selection={selection} onBulkStatus={bulk}/>}
  render(<Harness/>); expect(screen.queryByRole('toolbar')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('checkbox',{name:'选择记录 1'})); expect(screen.getByRole('toolbar')).toHaveTextContent('已选择 1 条')
  await userEvent.click(screen.getByRole('button',{name:'批量设置状态'})); expect(bulk).toHaveBeenCalledOnce()
  await userEvent.click(screen.getByRole('checkbox',{name:'选择本页记录'})); expect(screen.getByRole('toolbar')).toHaveTextContent('已选择 2 条')
  await userEvent.click(screen.getByRole('button',{name:'清空选择'})); expect(screen.queryByRole('toolbar')).not.toBeInTheDocument()
})

it('disables every selection control while readonly, disabled, or loading',()=>{
  const selection={targets:[],count:0,error:null,isSelected:()=>false,toggle:vi.fn(),togglePage:vi.fn(),clear:vi.fn()}
  render(<DataRecordsTable {...props} page={page([row({type:'text',value:'1'})])} selection={selection} readonly disabled loading/>)
  expect(screen.getAllByRole('checkbox').every(item=>item.hasAttribute('disabled'))).toBe(true)
})
it('keeps original view, edit and more actions separate with the exact typed record',async()=>{
 const item=row({type:'text',value:'001'}),open=vi.fn(),edit=vi.fn(),remove=vi.fn();
 render(<DataRecordsTable {...props} page={page([item])} onOpen={open} onEdit={edit} onDelete={remove}/>);
 await userEvent.click(screen.getByRole('button',{name:'编辑记录 001'}));expect(edit).toHaveBeenCalledWith(item);expect(open).not.toHaveBeenCalled();
 await userEvent.click(screen.getByRole('button',{name:'更多记录 001操作'}));await userEvent.click(screen.getByRole('menuitem',{name:'删除记录'}));expect(remove).toHaveBeenCalledWith(item);expect(open).not.toHaveBeenCalled();
 expect(screen.getByRole('columnheader',{name:'最近修改'})).toBeVisible();
})

it.each(['loading', 'disabled'] as const)('blocks an already open delete menu when %s changes',async state=>{
 const item=row({type:'text',value:'001'}),remove=vi.fn();
 const view=render(<DataRecordsTable {...props} page={page([item])} onDelete={remove}/>);
 await userEvent.click(screen.getByRole('button',{name:'更多记录 001操作'}));
 view.rerender(<DataRecordsTable {...props} page={page([item])} onDelete={remove} {...{[state]:true}}/>);
 expect(screen.getByRole('menuitem',{name:'删除记录'})).toHaveAttribute('aria-disabled','true');
 await userEvent.click(screen.getByRole('menuitem',{name:'删除记录'}));expect(remove).not.toHaveBeenCalled();
})
