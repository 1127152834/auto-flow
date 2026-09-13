import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { RecordQuery } from '../record-query'
import { RecordFilterEditor } from './RecordFilterEditor'

afterEach(cleanup)
beforeEach(() => {
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  HTMLElement.prototype.hasPointerCapture = vi.fn(() => false); HTMLElement.prototype.setPointerCapture = vi.fn(); HTMLElement.prototype.releasePointerCapture = vi.fn(); HTMLElement.prototype.scrollIntoView = vi.fn()
})
const ref={projectId:'p',tableId:'t',datasetGeneration:'g'}
const fields=[{ref:{...ref,fieldId:'name'},key:'name',name:'很长的名称字段',type:'string' as const,required:false,validation:{},writable:true,formula:false,fieldRevision:1},{ref:{...ref,fieldId:'amount'},key:'amount',name:'金额',type:'number' as const,required:false,validation:{},writable:true,formula:false,fieldRevision:1}]
const statuses=[{statusId:'open',name:'进行中',color:'#123456',order:0,statusRevision:1}]
const applied:RecordQuery={filter:{type:'compare',fieldId:'name',operator:'contains',value:'old'},orderBy:[]}

it('keeps edits local, emits a plain query on apply, and cancels to the applied value', async()=>{
  const apply=vi.fn(),dirty=vi.fn(),user=userEvent.setup()
  render(<RecordFilterEditor fields={fields} statuses={statuses} appliedQuery={applied} onApply={apply} onDirtyChange={dirty}/>)
  const value=screen.getByLabelText('比较值');await user.clear(value);await user.type(value,'new')
  expect(apply).not.toHaveBeenCalled();expect(dirty).toHaveBeenCalledWith(true)
  await user.click(screen.getByRole('button',{name:'取消修改'}));expect(screen.getByLabelText('比较值')).toHaveValue('old')
  await user.clear(screen.getByLabelText('比较值'));await user.type(screen.getByLabelText('比较值'),'new');await user.click(screen.getByRole('button',{name:'应用筛选'}))
  expect(apply).toHaveBeenCalledWith({filter:{type:'compare',fieldId:'name',operator:'contains',value:'new'},orderBy:[]})
})

it('builds nested groups and warns instead of applying an empty any group', async()=>{
  const apply=vi.fn(),user=userEvent.setup()
  render(<RecordFilterEditor fields={fields} statuses={statuses} onApply={apply}/>)
  await user.click(screen.getByRole('button',{name:'添加条件组'}))
  const matches=screen.getAllByRole('combobox',{name:/匹配方式/});await user.click(matches[1]);await user.click(screen.getByRole('option',{name:'满足任一'}))
  await user.click(screen.getByRole('button',{name:'应用筛选'}))
  expect(await screen.findByRole('alert')).toHaveTextContent('不能为空');expect(apply).not.toHaveBeenCalled()
})

it('preserves a stale field reference as a repairable invalid draft', async()=>{
  const apply=vi.fn(),user=userEvent.setup(),stale:RecordQuery={filter:{type:'compare',fieldId:'gone',operator:'eq',value:'kept'},orderBy:[]}
  render(<RecordFilterEditor fields={fields} statuses={statuses} appliedQuery={stale} onApply={apply}/>)
  expect(screen.getByText('当前选项不可用，请重新选择')).toBeVisible()
  await user.click(screen.getByRole('button',{name:'应用筛选'}));expect(await screen.findByRole('alert')).toHaveTextContent('字段已失效');expect(apply).not.toHaveBeenCalled()
})

it('adds unique sorts up to the available targets and respects disabled', async()=>{
  const apply=vi.fn(),user=userEvent.setup(),view=render(<RecordFilterEditor fields={fields} statuses={statuses} onApply={apply}/>)
  await user.click(screen.getByRole('button',{name:'添加排序'}));await user.click(screen.getByRole('button',{name:'添加排序'}))
  expect(screen.getAllByLabelText(/排序字段/)).toHaveLength(2)
  await user.click(screen.getByRole('button',{name:'应用筛选'}));expect(apply.mock.calls[0][0].orderBy).toEqual([{fieldId:'name',direction:'asc'},{fieldId:'amount',direction:'asc'}])
  view.rerender(<RecordFilterEditor fields={fields} statuses={statuses} disabled onApply={apply}/>);expect(screen.getByRole('button',{name:'应用筛选'})).toBeDisabled()
})

it('accepts parent refresh while pristine and preserves an invalid dirty draft', async()=>{
  const user=userEvent.setup(),props={fields,statuses,onApply:vi.fn()}
  const view=render(<RecordFilterEditor {...props} appliedQuery={applied}/>)
  const refreshed:RecordQuery={filter:{type:'compare',fieldId:'name',operator:'contains',value:'server'},orderBy:[]}
  view.rerender(<RecordFilterEditor {...props} appliedQuery={refreshed}/>)
  expect(screen.getByLabelText('比较值')).toHaveValue('server')
  await user.clear(screen.getByLabelText('比较值'))
  view.rerender(<RecordFilterEditor {...props} appliedQuery={{...refreshed,filter:{...refreshed.filter,value:'new-server'} as RecordQuery['filter']}}/>)
  expect(screen.getByLabelText('比较值')).toHaveValue('')
})

it('can negate a status or group node instead of only a field comparison', async()=>{
  const apply=vi.fn(),user=userEvent.setup()
  render(<RecordFilterEditor fields={fields} statuses={statuses} onApply={apply}/>)
  await user.click(screen.getByRole('button',{name:'添加状态条件'}))
  const statusGroup=screen.getByText('状态条件').closest('fieldset')!
  await user.click(within(statusGroup).getByRole('button',{name:'反向此条件'}))
  await user.click(screen.getByRole('button',{name:'应用筛选'}))
  expect(apply.mock.calls[0][0].filter).toEqual({type:'all',items:[{type:'not',item:{type:'status',operator:'eq',statusId:'open'}}]})
})

it('shows a root not size error instead of silently refusing apply', async()=>{
  const apply=vi.fn(),user=userEvent.setup(),huge='文'.repeat(17_000)
  render(<RecordFilterEditor fields={fields} statuses={statuses} appliedQuery={{filter:{type:'not',item:{type:'compare',fieldId:'name',operator:'eq',value:huge}},orderBy:[]}} onApply={apply}/>)
  await user.click(screen.getByRole('button',{name:'应用筛选'}))
  expect(screen.getByRole('alert')).toHaveTextContent('64 KiB');expect(apply).not.toHaveBeenCalled()
})
