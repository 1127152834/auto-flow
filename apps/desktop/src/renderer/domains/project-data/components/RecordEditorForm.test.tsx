import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { components } from '../../../shared/api/generated'
import { choiceTestEnvironment } from '../../../shared/testing/choice-user'
import { RecordEditorForm } from './RecordEditorForm'

type Schema=components['schemas']
const field=(id:string):Schema['DataFieldView']=>({ref:{projectId:'p',tableId:'t',datasetGeneration:'g',fieldId:id},key:id,name:id,type:'string',required:false,validation:{},writable:true,formula:false,fieldRevision:1})
const cell=(fieldId:string,value:string,readable=true):Schema['DataCellView']=>({fieldId,value,readable,source:'local'})
const record=(values:Schema['DataCellView'][]):Schema['DataRecordView']=>({ref:{projectId:'p',tableId:'t',datasetGeneration:'g',recordKey:{type:'text',value:'001'}},values,recordSlots:[],statusId:null,currentEnvironmentId:null,contentRevision:1,statusRevision:1,linkRevision:1,deleted:false,createdAt:'2026-09-13T00:00:00Z',updatedAt:'2026-09-13T00:00:00Z'})
afterEach(cleanup);choiceTestEnvironment()

it('keeps dirty values across refresh and reconnect but resets only for a new session',async()=>{
  const user=userEvent.setup(),fields=[field('value')],props={id:'editor',mode:'edit' as const,fields,sessionKey:'same',onSubmit:vi.fn().mockResolvedValue(undefined)}
  const view=render(<RecordEditorForm {...props} submissionEpoch="one" initialRecord={record([cell('value','A')])}/>)
  await user.clear(screen.getByLabelText('value'));await user.type(screen.getByLabelText('value'),'draft')
  view.rerender(<RecordEditorForm {...props} submissionEpoch="two" initialRecord={record([cell('value','server')])}/>);expect(screen.getByLabelText('value')).toHaveValue('draft')
  view.rerender(<RecordEditorForm {...props} sessionKey="next" submissionEpoch="two" initialRecord={record([cell('value','B')])}/>);expect(screen.getByLabelText('value')).toHaveValue('B')
})

it('omits an untouched unreadable field and submits only the edited value',async()=>{
  const submit=vi.fn().mockResolvedValue(undefined),user=userEvent.setup(),fields=[field('visible'),field('secret')]
  render(<RecordEditorForm id="editor" mode="edit" sessionKey="same" fields={fields} initialRecord={record([cell('visible','old'),cell('secret','hidden',false)])} onSubmit={submit}/>)
  await user.clear(screen.getByLabelText('visible'));await user.type(screen.getByLabelText('visible'),'new');await user.click(screen.getByRole('button',{name:'保存修改'}))
  expect(submit).toHaveBeenCalledWith([{fieldId:'visible',value:'new'}])
})

it('locks duplicate submissions before the queued callback starts',async()=>{
  const submit=vi.fn(()=>new Promise(()=>undefined));render(<RecordEditorForm id="editor" mode="create" sessionKey="same" fields={[]} onSubmit={submit}/>)
  const form=screen.getByRole('form',{name:'新建记录表单'});act(()=>{fireEvent.submit(form);fireEvent.submit(form)});await act(async()=>{});expect(submit).toHaveBeenCalledOnce()
})

it('renders the page identity in Chinese and keeps the shared footer actions',()=>{
  render(<RecordEditorForm id="editor" mode="edit" presentation="page" sessionKey="page" fields={[field('value')]} initialRecord={record([cell('value','short')])} footerClassName="sticky-actions" onCancel={vi.fn()} onSubmit={vi.fn()}/>)
  expect(screen.getByText('记录身份：文本 · 001（只读）')).toBeVisible();expect(screen.getByLabelText('value')).toHaveProperty('tagName','INPUT')
  expect(screen.getByRole('button',{name:'取消'}).closest('footer')).toBeInTheDocument();expect(screen.getByRole('button',{name:'保存修改'}).closest('footer')).toBeInTheDocument()
})
