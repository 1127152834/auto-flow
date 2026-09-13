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
  expect(screen.getByRole('textbox',{name:'记录身份'})).toHaveValue('文本 · 001');expect(screen.getByRole('textbox',{name:'记录身份'})).toHaveAttribute('readonly');expect(screen.getByText('只读')).toBeVisible();expect(screen.getByLabelText('value')).toHaveProperty('tagName','INPUT')
  expect(screen.getByRole('button',{name:'取消'}).closest('footer')).toBeInTheDocument();expect(screen.getByRole('button',{name:'保存修改'}).closest('footer')).toBeInTheDocument()
})

it('shows submitted recovery values without replacing the record baseline or leaking identity',async()=>{
  const user=userEvent.setup(),submit=vi.fn().mockResolvedValue(undefined),fields=[field('identity'),field('value')],initial=record([cell('identity','001'),cell('value','before')])
  const props={id:'editor',mode:'edit' as const,sessionKey:'recovery',fields,initialRecord:initial,identityFieldId:'identity',initialSubmittedValues:[{fieldId:'identity',value:'leak'},{fieldId:'value',value:'submitted'}] as Schema['DataCellWrite'][],onSubmit:submit}
  const view=render(<RecordEditorForm {...props} recoveryPending/>);expect(screen.getByLabelText('identity')).toHaveValue('001');expect(screen.getByLabelText('value')).toHaveValue('submitted')
  view.rerender(<RecordEditorForm {...props} initialSubmittedValues={[{fieldId:'value',value:'later'}]} recoveryPending/>);expect(screen.getByLabelText('value')).toHaveValue('submitted')
  view.rerender(<RecordEditorForm {...props}/>);await user.click(screen.getByRole('button',{name:'保存修改'}));expect(submit).toHaveBeenCalledWith([{fieldId:'value',value:'submitted'}])
})

it('keeps an unchanged submitted recovery value across a same-session record refresh',()=>{
  const fields=[field('value')],submitted=[{fieldId:'value',value:'before'}] as Schema['DataCellWrite'][],props={id:'editor',mode:'edit' as const,sessionKey:'recovery-same',fields,initialSubmittedValues:submitted,recoveryPending:true,onSubmit:vi.fn()}
  const view=render(<RecordEditorForm {...props} initialRecord={record([cell('value','before')])}/>);view.rerender(<RecordEditorForm {...props} initialRecord={record([cell('value','server-refresh')])}/>)
  expect(screen.getByLabelText('value')).toHaveValue('before')
})

it('restores a submitted field identity while creating a record',()=>{
  render(<RecordEditorForm id="editor" mode="create" sessionKey="create-recovery" fields={[field('identity')]} identityFieldId="identity" initialSubmittedValues={[{fieldId:'identity',value:'new-key'}]} recoveryPending onSubmit={vi.fn()}/>)
  expect(screen.getByLabelText('identity')).toHaveValue('new-key')
})

it('reports submitted dirty fields and all invalid fields without changing dirty callback semantics',()=>{
  const required={...field('required'),required:true},number={...field('number'),type:'number' as const}
  const summary=vi.fn()
  const view=render(<RecordEditorForm id="editor" mode="create" sessionKey="summary" fields={[required,number]} initialSubmittedValues={[{fieldId:'required',value:''},{fieldId:'number',value:0}]} onDraftSummaryChange={summary} onSubmit={vi.fn()}/>)
  expect(summary).toHaveBeenLastCalledWith({dirtyFields:['required','number'],invalidFields:['required']})
  view.rerender(<RecordEditorForm id="editor" mode="create" sessionKey="summary" fields={[required,number]} initialSubmittedValues={[{fieldId:'required',value:''},{fieldId:'number',value:0}]} onDraftSummaryChange={summary} onSubmit={vi.fn()}/>)
})

it('renders page identity and field rows without a separate identity card',()=>{
  render(<RecordEditorForm id="editor" mode="create" presentation="page" sessionKey="page-create" fields={[{...field('title'),required:true}]} onSubmit={vi.fn()}/>)
  expect(screen.getByText('保存时自动生成')).toBeVisible()
  expect(document.querySelector('[data-record-field-label]')).toHaveTextContent('title*')
  expect(screen.queryByText(/^记录身份：/)).not.toBeInTheDocument()
  expect(screen.getByLabelText('title').closest('[data-record-field-layout]')).toHaveClass('lg:grid-cols-[250px_minmax(0,1fr)]')
})

it('shows every field error from the shared record validation and focuses the first',async()=>{
  const user=userEvent.setup(),required={...field('required'),required:true},number={...field('number'),type:'number' as const}
  render(<RecordEditorForm id="editor" mode="create" presentation="page" sessionKey="errors" fields={[required,number]} initialSubmittedValues={[{fieldId:'number',value:1}]} onSubmit={vi.fn()}/>)
  await user.clear(screen.getByLabelText('number'));await user.type(screen.getByLabelText('number'),'bad')
  await user.click(screen.getByRole('button',{name:'创建记录'}))
  const summary=screen.getByText('还有 2 个字段需要修正，其他输入已保留。')
  expect(summary).toBeVisible()
  expect(summary.compareDocumentPosition(screen.getByText('保存时自动生成'))&Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(screen.getAllByRole('alert').map(node=>node.textContent)).toEqual(expect.arrayContaining(['请填写必填字段','请输入有效数字']))
  expect(screen.getByLabelText('required')).toHaveFocus()
  expect(screen.getByText('请填写必填字段',{selector:'p[aria-hidden="true"]'})).toHaveClass('text-danger','text-sm')
  expect(screen.getByText('请填写必填字段',{selector:'p[aria-hidden="true"]'}).querySelector('svg')).toBeTruthy()
})

it('reports visible validation errors, disables ordinary save, and clears after correction',async()=>{
  const user=userEvent.setup(),validation=vi.fn()
  render(<RecordEditorForm id="editor" mode="create" presentation="page" sessionKey="validation" fields={[{...field('required'),required:true}]} onValidationErrorChange={validation} onSubmit={vi.fn()}/>)
  expect(validation).toHaveBeenLastCalledWith(false)
  await user.click(screen.getByRole('button',{name:'创建记录'}))
  expect(validation).toHaveBeenLastCalledWith(true);expect(screen.getByRole('button',{name:'创建记录'})).toBeDisabled()
  await user.type(screen.getByLabelText('required'),'fixed')
  expect(validation).toHaveBeenLastCalledWith(false);expect(screen.getByRole('button',{name:'创建记录'})).toBeEnabled()
})
