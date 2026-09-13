import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { components } from '../../../shared/api/generated'
import { emptyRecordQuery, RecordQueryError, type RecordQuery } from '../record-query'
import { composeRecordQuery, RecordQueryToolbar } from './RecordQueryToolbar'

type Schema = components['schemas']
afterEach(cleanup)
beforeEach(() => {
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  HTMLElement.prototype.hasPointerCapture = vi.fn(() => false); HTMLElement.prototype.setPointerCapture = vi.fn(); HTMLElement.prototype.releasePointerCapture = vi.fn(); HTMLElement.prototype.scrollIntoView = vi.fn()
})
const ref={projectId:'p',tableId:'t',datasetGeneration:'g'}
const fields:Schema['DataFieldView'][]=[
  {ref:{...ref,fieldId:'name'},key:'name',name:'名称',type:'string',required:false,validation:{},writable:true,formula:false,fieldRevision:1},
  {ref:{...ref,fieldId:'amount'},key:'amount',name:'金额',type:'number',required:false,validation:{},writable:true,formula:false,fieldRevision:1},
]
const statuses:Schema['DataStatusView'][]=[{statusId:'open',name:'进行中',color:'#123456',order:0,statusRevision:1}]
const query:RecordQuery={filter:{type:'all',items:[{type:'compare',fieldId:'amount',operator:'eq',value:0}]},orderBy:[{systemField:'createdAt',direction:'desc'}]}
const props={fields,statuses,query,visibleFieldIds:null,quickSearch:{fieldId:'name',keyword:''},selectionCount:0,onClearSelection:vi.fn(),onCreate:vi.fn(),onBatchStatus:vi.fn(),onExport:vi.fn(),onApplyQuery:vi.fn(),onApplyColumns:vi.fn(),onApplySearch:vi.fn(),resetKey:'g'}

it('composes non-empty text search with the full validated advanced query',()=>{
  expect(composeRecordQuery(fields,query,{fieldId:'name',keyword:'x'})).toEqual({filter:{type:'all',items:[{type:'compare',fieldId:'amount',operator:'eq',value:0},{type:'compare',fieldId:'name',operator:'contains',value:'x'}]},orderBy:query.orderBy})
  expect(composeRecordQuery(fields,{filter:{type:'status',operator:'eq',statusId:'open'},orderBy:[]},{fieldId:'name',keyword:''}).filter).toEqual({type:'status',operator:'eq',statusId:'open'})
  expect(()=>composeRecordQuery(fields,emptyRecordQuery(),{fieldId:'amount',keyword:'x'})).toThrow(RecordQueryError)
})

it('selects the first asynchronously loaded text field and follows applied search only while pristine',async()=>{
  const user=userEvent.setup()
  const view=render(<RecordQueryToolbar {...props} fields={fields.slice(1)} quickSearch={{fieldId:null,keyword:''}}/>)
  view.rerender(<RecordQueryToolbar {...props} fields={fields} quickSearch={{fieldId:null,keyword:''}}/>)
  expect(screen.getByLabelText('搜索字段')).toHaveAttribute('data-choice-value','name')
  view.rerender(<RecordQueryToolbar {...props} quickSearch={{fieldId:'name',keyword:'server'}}/>)
  expect(screen.getByRole('searchbox')).toHaveValue('server')
  await user.type(screen.getByRole('searchbox'),' local')
  view.rerender(<RecordQueryToolbar {...props} quickSearch={{fieldId:'name',keyword:'new server'}}/>)
  expect(screen.getByRole('searchbox')).toHaveValue('server local')
})

it('shows column names and clearing search submits only an empty quick search',async()=>{
  const user=userEvent.setup(),onApplySearch=vi.fn()
  render(<RecordQueryToolbar {...props} quickSearch={{fieldId:'name',keyword:'needle'}} onApplySearch={onApplySearch}/>)
  await user.click(screen.getByRole('button',{name:'显示列'})); expect(within(screen.getByLabelText('显示列')).getByText('名称')).toBeVisible()
  await user.click(screen.getByRole('button',{name:'清除文本搜索'})); expect(onApplySearch).toHaveBeenCalledWith({fieldId:'name',keyword:''})
  expect(query.filter).toEqual({type:'all',items:[{type:'compare',fieldId:'amount',operator:'eq',value:0}]})
})

it('focuses a validation alert when the current schema invalidates a filter draft',async()=>{
  const user=userEvent.setup(),view=render(<RecordQueryToolbar {...props}/>)
  await user.click(screen.getByRole('button',{name:'筛选'})); view.rerender(<RecordQueryToolbar {...props} fields={[fields[0]]}/>)
  await user.click(within(screen.getByLabelText('记录筛选')).getByRole('button',{name:'应用筛选'}))
  expect(screen.getByRole('alert')).toHaveFocus()
})

it('keeps filter drafts local and applies only the filter part',async()=>{
  const user=userEvent.setup(),onApplyQuery=vi.fn()
  render(<RecordQueryToolbar {...props} onApplyQuery={onApplyQuery}/>)
  expect(screen.queryByLabelText('记录筛选')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button',{name:'筛选'}))
  const panel=screen.getByLabelText('记录筛选'); await user.click(within(panel).getByRole('button',{name:'添加状态条件'}))
  await user.click(within(panel).getByRole('button',{name:'取消'})); expect(onApplyQuery).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button',{name:'筛选'})); await user.click(within(screen.getByLabelText('记录筛选')).getByRole('button',{name:'添加状态条件'}))
  await user.click(within(screen.getByLabelText('记录筛选')).getByRole('button',{name:'应用筛选'}))
  expect(onApplyQuery).toHaveBeenCalledWith({filter:{type:'all',items:[{type:'compare',fieldId:'amount',operator:'eq',value:0},{type:'status',operator:'eq',statusId:'open'}]},orderBy:query.orderBy})
})

it('switches mutually exclusive panels, discards drafts, and skips unchanged callbacks',async()=>{
  const user=userEvent.setup(),onApplyQuery=vi.fn(),onApplyColumns=vi.fn()
  render(<RecordQueryToolbar {...props} onApplyQuery={onApplyQuery} onApplyColumns={onApplyColumns}/>)
  await user.click(screen.getByRole('button',{name:'排序'})); await user.click(within(screen.getByLabelText('记录排序')).getByRole('button',{name:'删除排序'}))
  await user.click(screen.getByRole('button',{name:'显示列'})); expect(screen.queryByLabelText('记录排序')).not.toBeInTheDocument()
  await user.click(within(screen.getByLabelText('显示列')).getByRole('button',{name:'取消'}))
  await user.click(screen.getByRole('button',{name:'排序'})); expect(within(screen.getByLabelText('记录排序')).getByLabelText('排序字段 1')).toBeInTheDocument()
  await user.click(within(screen.getByLabelText('记录排序')).getByRole('button',{name:'应用排序'})); expect(onApplyQuery).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button',{name:'显示列'})); await user.click(within(screen.getByLabelText('显示列')).getByRole('button',{name:'应用显示列'})); expect(onApplyColumns).not.toHaveBeenCalled()
})

it('searches only on submit and disables search when no text field exists',async()=>{
  const user=userEvent.setup(),onApplySearch=vi.fn(),view=render(<RecordQueryToolbar {...props} onApplySearch={onApplySearch}/>)
  const input=screen.getByRole('searchbox'); await user.type(input,'needle'); expect(onApplySearch).not.toHaveBeenCalled(); await user.keyboard('{Enter}')
  expect(onApplySearch).toHaveBeenCalledWith({fieldId:'name',keyword:'needle'})
  view.rerender(<RecordQueryToolbar {...props} fields={fields.slice(1)} quickSearch={{fieldId:null,keyword:''}} onApplySearch={onApplySearch}/>)
  expect(screen.getByRole('searchbox')).toBeDisabled(); expect(screen.getByText('没有可搜索的文本字段')).toBeVisible()
})

it('keeps a rejected apply open, focuses its error, resets drafts, and exposes record actions',async()=>{
  const user=userEvent.setup(),onApplyQuery=vi.fn(()=>false),clear=vi.fn(),batch=vi.fn(),view=render(<RecordQueryToolbar {...props} selectionCount={2} onClearSelection={clear} onBatchStatus={batch} onApplyQuery={onApplyQuery}/>)
  expect(screen.getByText('已选择 2 条')).toBeVisible(); await user.click(screen.getByRole('button',{name:'清空选择'})); expect(clear).toHaveBeenCalled()
  await user.click(screen.getByRole('button',{name:'批量设置状态'})); expect(batch).toHaveBeenCalled()
  await user.click(screen.getByRole('button',{name:'排序'})); await user.click(within(screen.getByLabelText('记录排序')).getByRole('button',{name:'删除排序'})); await user.click(within(screen.getByLabelText('记录排序')).getByRole('button',{name:'应用排序'}))
  const alert=screen.getByRole('alert'); expect(alert).toHaveFocus(); expect(screen.getByLabelText('记录排序')).toBeVisible()
  view.rerender(<RecordQueryToolbar {...props} resetKey="next" onApplyQuery={onApplyQuery}/>); expect(screen.queryByLabelText('记录排序')).not.toBeInTheDocument()
})

it('hides create in readonly mode and keeps batch status disabled',()=>{
  render(<RecordQueryToolbar {...props} readonly selectionCount={2}/>)
  expect(screen.queryByRole('button',{name:'新增记录'})).not.toBeInTheDocument()
  expect(screen.getByRole('button',{name:'批量设置状态'})).toBeDisabled()
  expect(screen.getByRole('button',{name:'导出 Excel'})).toBeEnabled()
})

it('clears a failed search error when edited and adopts the next successful trimmed search',async()=>{
  const user=userEvent.setup(),onApplySearch=vi.fn().mockReturnValueOnce(false).mockReturnValueOnce(true)
  render(<RecordQueryToolbar {...props} onApplySearch={onApplySearch}/>)
  const input=screen.getByRole('searchbox'); await user.type(input,'  first  '); await user.keyboard('{Enter}')
  expect(screen.getByRole('alert')).toBeVisible(); expect(input).toHaveValue('  first  ')
  await user.type(input,' next'); expect(screen.queryByRole('alert')).not.toBeInTheDocument(); await user.keyboard('{Enter}')
  expect(onApplySearch).toHaveBeenLastCalledWith({fieldId:'name',keyword:'first   next'}); expect(input).toHaveValue('first   next'); expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

it('clears a previous search error after a successful explicit clear',async()=>{
  const user=userEvent.setup(),onApplySearch=vi.fn().mockReturnValueOnce(false).mockReturnValueOnce(undefined)
  render(<RecordQueryToolbar {...props} quickSearch={{fieldId:'name',keyword:'applied'}} onApplySearch={onApplySearch}/>)
  await user.type(screen.getByRole('searchbox'),' failed'); await user.keyboard('{Enter}'); expect(screen.getByRole('alert')).toBeVisible()
  await user.click(screen.getByRole('button',{name:'清除文本搜索'})); expect(onApplySearch).toHaveBeenLastCalledWith({fieldId:'name',keyword:''}); expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

it('disables only export for an invalid effective query',async()=>{
  const user=userEvent.setup()
  render(<RecordQueryToolbar {...props} exportDisabled/>)
  expect(screen.getByRole('button',{name:'导出 Excel'})).toBeDisabled()
  expect(screen.getByRole('button',{name:'筛选'})).toBeEnabled(); await user.click(screen.getByRole('button',{name:'筛选'})); expect(screen.getByLabelText('记录筛选')).toBeVisible()
})

it('renders and focuses the parent query error instead of a generic message',()=>{
  render(<RecordQueryToolbar {...props} queryError="所选字段已失效，请修正筛选"/>)
  const alert=screen.getByRole('alert'); expect(alert).toHaveTextContent('所选字段已失效，请修正筛选'); expect(alert).toHaveFocus(); expect(alert).not.toHaveTextContent('应用失败')
})
