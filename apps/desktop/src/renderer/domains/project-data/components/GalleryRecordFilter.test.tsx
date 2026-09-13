import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { recordQueryDraft, type FilterDraft, type RecordQuery } from '../record-query'
import { GalleryRecordFilter } from './GalleryRecordFilter'

afterEach(cleanup)
beforeEach(()=>{vi.stubGlobal('ResizeObserver',class{observe(){} unobserve(){} disconnect(){}});HTMLElement.prototype.hasPointerCapture=vi.fn(()=>false);HTMLElement.prototype.setPointerCapture=vi.fn();HTMLElement.prototype.releasePointerCapture=vi.fn();HTMLElement.prototype.scrollIntoView=vi.fn()})
const ref={projectId:'p',tableId:'t',datasetGeneration:'g'}
const fields=[{ref:{...ref,fieldId:'name'},key:'name',name:'标题',type:'string' as const,required:false,validation:{},writable:true,formula:false,fieldRevision:1}]
const statuses=[{statusId:'open',name:'待核对',color:'#123456',order:0,statusRevision:1}]
const renderFilter=(filter:FilterDraft,onChange=vi.fn())=>render(<GalleryRecordFilter fields={fields} statuses={statuses} filter={filter} onChange={onChange}/>)

it('keeps an empty simple query empty until the user chooses a condition',async()=>{
  const user=userEvent.setup(),onChange=vi.fn();renderFilter({type:'all',items:[]},onChange)
  expect(screen.getByText('字段条件')).toBeVisible();expect(screen.getByText('业务状态')).toBeVisible();expect(onChange).not.toHaveBeenCalled()
  await user.click(screen.getByRole('combobox',{name:'字段'}));await user.click(screen.getByRole('option',{name:'标题'}))
  expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({type:'compare',fieldId:'name'}))
})

it('edits a representable compare and status as two simple AND conditions',()=>{
  const query:RecordQuery={filter:{type:'all',items:[{type:'compare',fieldId:'name',operator:'contains',value:'温室'},{type:'status',operator:'eq',statusId:'open'}]},orderBy:[]}
  renderFilter(recordQueryDraft(query).filter)
  expect(screen.getByRole('combobox',{name:'字段'})).toHaveTextContent('标题')
  expect(screen.getByRole('combobox',{name:'字段运算符'})).toHaveTextContent('包含')
  expect(screen.getByLabelText('比较值')).toHaveValue('温室')
  expect(screen.getByRole('combobox',{name:'业务状态'})).toHaveTextContent('待核对')
  expect(screen.getByText('两项条件同时满足时显示；业务状态仅属于本项目。')).toBeVisible()
})

it('opens complex trees in advanced mode and refuses a lossy simple switch',async()=>{
  const complex:FilterDraft={type:'any',items:[{type:'not',item:{type:'status',operator:'eq',statusId:'open'}}]};renderFilter(complex)
  expect(screen.getByText('条件组')).toBeVisible()
  const simple=screen.getByRole('button',{name:'使用简单条件'});expect(simple).toBeDisabled()
  expect(screen.getByText('请先在高级条件中调整为一个字段条件和一个业务状态条件。')).toBeVisible()
  expect(within(screen.getByRole('region',{name:'高级条件编辑器'})).getByText('条件组')).toBeVisible()
})
