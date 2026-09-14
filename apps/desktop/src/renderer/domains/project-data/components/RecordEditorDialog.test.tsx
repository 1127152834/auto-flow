import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { components } from '../../../shared/api/generated'
import { choiceTestEnvironment, chooseOption } from '../../../shared/testing/choice-user'
import { RecordEditorDialog } from './RecordEditorDialog'

type Schema = components['schemas']
const field = (id: string, extra: Partial<Schema['DataFieldView']> = {}): Schema['DataFieldView'] => ({ ref:{projectId:'p',tableId:'t',datasetGeneration:'g',fieldId:id},key:id,name:id,type:'string',required:false,validation:{},writable:true,formula:false,fieldRevision:1,...extra })
const record = (values: Schema['DataCellView'][]): Schema['DataRecordView'] => ({ ref:{projectId:'p',tableId:'t',datasetGeneration:'g',recordKey:{type:'text',value:'001'}},values,recordSlots:[],statusId:null,currentEnvironmentId:null,contentRevision:1,statusRevision:1,linkRevision:1,deleted:false,createdAt:'2026-09-13T00:00:00Z',updatedAt:'2026-09-13T00:00:00Z' })
const cell = (fieldId:string,value:Schema['DataCellView']['value'],readable=true):Schema['DataCellView']=>({fieldId,value,readable,source:'local'})
afterEach(cleanup); choiceTestEnvironment()

it('creates from raw drafts, focuses a required error, and never adds status metadata', async () => {
  const submit=vi.fn().mockResolvedValue(undefined); const user=userEvent.setup(); const fields=[field('name',{name:'姓名',required:true}),field('note',{name:'备注'})]
  render(<RecordEditorDialog open mode="create" sessionKey="a" fields={fields} onOpenChange={vi.fn()} onSubmit={submit}/>)
  await user.click(screen.getByRole('button',{name:'创建记录'}))
  expect(await screen.findByText('请填写必填字段')).toBeVisible(); expect(screen.getByRole('combobox',{name:'姓名值状态'})).toHaveFocus()
  await chooseOption(user,screen.getByRole('combobox',{name:'姓名值状态'}),'value'); await user.type(screen.getByLabelText('姓名'),' Alice ')
  await chooseOption(user,screen.getByRole('combobox',{name:'备注值状态'}),'null'); await user.click(screen.getByRole('button',{name:'创建记录'}))
  await waitFor(()=>expect(submit).toHaveBeenCalledWith([{fieldId:'name',value:' Alice '},{fieldId:'note',value:null}]))
})

it('disables protected edit fields and submits only a real content change', async () => {
  const fields=[field('id',{name:'身份'}),field('value',{name:'内容'}),field('formula',{name:'公式',formula:true}),field('secret',{name:'秘密'})]
  const initial=record([cell('id','001'),cell('value','old'),cell('formula','x'),cell('secret','hidden',false)]); const submit=vi.fn().mockResolvedValue(undefined); const user=userEvent.setup()
  render(<RecordEditorDialog open mode="edit" sessionKey="a" fields={fields} identityFieldId="id" initialRecord={initial} onOpenChange={vi.fn()} onSubmit={submit}/>)
  expect(screen.getByText(/text.*001/)).toBeVisible(); expect(screen.getByRole('button',{name:'保存修改'})).toBeDisabled()
  for(const name of ['身份值状态','公式值状态','秘密值状态']) expect(screen.getByRole('combobox',{name})).toHaveAttribute('aria-readonly','true')
  const input=screen.getByLabelText('内容'); await user.clear(input); await user.type(input,'new'); await user.click(screen.getByRole('button',{name:'保存修改'}))
  expect(submit).toHaveBeenCalledWith([{fieldId:'value',value:'new'}])
})

it('preserves dirty input on same-session refresh and ignores a late failure after session change', async () => {
  let reject!: (reason:unknown)=>void; const pending=new Promise<void>((_,r)=>{reject=r}); const fields=[field('value',{name:'内容'})]; const user=userEvent.setup()
  const props={open:true,mode:'edit' as const,fields,sessionKey:'a',onOpenChange:vi.fn(),onSubmit:()=>pending}
  const view=render(<RecordEditorDialog {...props} initialRecord={record([cell('value','A')])}/>)
  const input=screen.getByLabelText('内容'); await user.clear(input); await user.type(input,'draft')
  view.rerender(<RecordEditorDialog {...props} initialRecord={record([cell('value','server')])}/>); expect(input).toHaveValue('draft')
  await user.click(screen.getByRole('button',{name:'保存修改'})); view.rerender(<RecordEditorDialog {...props} sessionKey="b" initialRecord={record([cell('value','B')])}/>)
  reject(new Error('旧失败')); await Promise.resolve(); await Promise.resolve(); expect(screen.getByLabelText('内容')).toHaveValue('B'); expect(screen.queryByText('旧失败')).not.toBeInTheDocument()
})

it('guards dirty close, reports dirty cleanup, and locks every close path while saving', async () => {
  const dirty=vi.fn(),close=vi.fn(),user=userEvent.setup(); const props={open:true,mode:'create' as const,sessionKey:'a',fields:[field('x',{name:'内容'})],onOpenChange:close,onSubmit:vi.fn(),onDirtyChange:dirty}
  const view=render(<RecordEditorDialog {...props}/>); await chooseOption(user,screen.getByRole('combobox',{name:'内容值状态'}),'value'); await user.type(screen.getByLabelText('内容'),'draft'); await waitFor(()=>expect(dirty).toHaveBeenLastCalledWith(true))
  await user.click(screen.getByRole('button',{name:'取消'})); expect(screen.getByRole('alertdialog')).toBeVisible(); view.rerender(<RecordEditorDialog {...props} saving/>); expect(screen.getByRole('button',{name:'放弃修改'})).toBeDisabled(); await user.keyboard('{Escape}'); expect(close).not.toHaveBeenCalled()
  view.rerender(<RecordEditorDialog {...props} open={false}/>); await waitFor(()=>expect(dirty).toHaveBeenLastCalledWith(false)); view.unmount(); expect(dirty).toHaveBeenLastCalledWith(false)
})

it('allows an empty system-identity record and keeps parent ownership of closing', async () => {
  const submit=vi.fn().mockResolvedValue(undefined),close=vi.fn(),user=userEvent.setup()
  render(<RecordEditorDialog open mode="create" sessionKey="empty" fields={[]} onOpenChange={close} onSubmit={submit}/>)
  await user.click(screen.getByRole('button',{name:'创建记录'})); expect(submit).toHaveBeenCalledWith([]); expect(close).not.toHaveBeenCalled()
})

it('freezes the record baseline while dirty so untouched remote cells are not submitted', async () => {
  const fields=[field('first'),field('second')], submit=vi.fn().mockResolvedValue(undefined), user=userEvent.setup()
  const props={open:true,mode:'edit' as const,sessionKey:'same',fields,onOpenChange:vi.fn(),onSubmit:submit}
  const view=render(<RecordEditorDialog {...props} initialRecord={record([cell('first','a'),cell('second','b')])}/>)
  await user.clear(screen.getByLabelText('first')); await user.type(screen.getByLabelText('first'),'mine')
  view.rerender(<RecordEditorDialog {...props} initialRecord={record([cell('first','a'),cell('second','remote')])}/>)
  await user.click(screen.getByRole('button',{name:'保存修改'})); expect(submit).toHaveBeenCalledWith([{fieldId:'first',value:'mine'}])
})

it('checks session and open state before a queued command begins', async () => {
  const submit=vi.fn().mockResolvedValue(undefined), props={open:true,mode:'create' as const,fields:[],onOpenChange:vi.fn(),onSubmit:submit}
  const view=render(<RecordEditorDialog {...props} sessionKey="A"/>); fireEvent.submit(document.querySelector('#record-editor-form')!)
  view.rerender(<RecordEditorDialog {...props} sessionKey="B"/>); await act(async()=>{}); expect(submit).not.toHaveBeenCalled()
  fireEvent.submit(document.querySelector('#record-editor-form')!); view.rerender(<RecordEditorDialog {...props} open={false} sessionKey="B"/>); await act(async()=>{}); expect(submit).not.toHaveBeenCalled()
})

it('uses a synchronous lock against duplicate form submissions', async () => {
  const submit=vi.fn(()=>new Promise(()=>undefined)); render(<RecordEditorDialog open mode="create" sessionKey="duplicate" fields={[]} onOpenChange={vi.fn()} onSubmit={submit}/>)
  const form=document.querySelector('#record-editor-form')!; act(()=>{fireEvent.submit(form);fireEvent.submit(form)}); await act(async()=>{}); expect(submit).toHaveBeenCalledOnce()
})

it('treats a canonical numeric spelling change as unchanged but invalid input as dirty', async () => {
  const dirty=vi.fn(),user=userEvent.setup(); render(<RecordEditorDialog open mode="edit" sessionKey="number" fields={[field('n',{name:'数字',type:'number'})]} initialRecord={record([cell('n',1)])} onOpenChange={vi.fn()} onSubmit={vi.fn()} onDirtyChange={dirty}/>)
  await user.type(screen.getByLabelText('数字'),'.0'); expect(screen.getByRole('button',{name:'保存修改'})).toBeDisabled()
  await user.clear(screen.getByLabelText('数字')); await waitFor(()=>expect(dirty).toHaveBeenLastCalledWith(true)); await user.click(screen.getByRole('button',{name:'保存修改'})); expect(await screen.findByText('请输入有效数字')).toBeVisible()
})

it('hides discard confirmation and invalidates failures when the parent closes', async () => {
  let reject!:(reason:unknown)=>void; const submit=()=>new Promise<void>((_,fail)=>{reject=fail}); const user=userEvent.setup()
  const props={mode:'edit' as const,sessionKey:'close',fields:[field('x')],initialRecord:record([cell('x','a')]),onOpenChange:vi.fn(),onSubmit:submit}
  const view=render(<RecordEditorDialog open {...props}/>); await user.type(screen.getByLabelText('x'),'dirty'); await user.click(screen.getByRole('button',{name:'取消'})); expect(await screen.findByRole('alertdialog')).toBeVisible()
  view.rerender(<RecordEditorDialog open={false} {...props}/>); expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  view.rerender(<RecordEditorDialog open {...props}/>); await user.type(screen.getByLabelText('x'),'more'); await user.click(screen.getByRole('button',{name:'保存修改'})); view.rerender(<RecordEditorDialog open={false} {...props}/>); await act(async()=>reject(new Error('迟到失败')))
  view.rerender(<RecordEditorDialog open {...props}/>); expect(screen.queryByText('迟到失败')).not.toBeInTheDocument()
})

it.each(['readonly','saving'] as const)('does not start a queued command after committed %s becomes true', async guard => {
  const submit=vi.fn().mockResolvedValue(undefined), props={open:true,mode:'create' as const,sessionKey:guard,fields:[],onOpenChange:vi.fn(),onSubmit:submit}
  const view=render(<RecordEditorDialog {...props}/>); fireEvent.submit(document.querySelector('#record-editor-form')!)
  view.rerender(<RecordEditorDialog {...props} {...{[guard]:true}}/>); await act(async()=>{}); expect(submit).not.toHaveBeenCalled()
})

it('focuses and aria-describes the exact value, offset, and presence controls', async () => {
  const user=userEvent.setup(), number=field('n',{name:'数字',type:'number'}), date=field('d',{name:'时间',type:'date'})
  const initial=record([cell('n',1),cell('d',{kind:'date',precision:'datetime',value:'2026-09-13T10:30:00',offset:'+08:00'})])
  const view=render(<RecordEditorDialog open mode="edit" sessionKey="errors" fields={[number,date]} initialRecord={initial} onOpenChange={vi.fn()} onSubmit={vi.fn()}/>)
  await user.clear(screen.getByLabelText('数字')); await user.click(screen.getByRole('button',{name:'保存修改'}))
  const numberInput=screen.getByLabelText('数字'); expect(numberInput).toHaveFocus(); expect(numberInput).toHaveAccessibleDescription('请输入有效数字')
  await user.type(numberInput,'1'); const offset=screen.getByLabelText('时间时区偏移'); await user.clear(offset); await user.type(offset,'+00:99'); await user.click(screen.getByRole('button',{name:'保存修改'}))
  expect(offset).toHaveFocus(); expect(offset).toHaveAccessibleDescription(expect.stringContaining('请输入有效时区偏移'))
  view.rerender(<RecordEditorDialog open mode="create" sessionKey="required" fields={[field('required',{name:'必填',required:true})]} onOpenChange={vi.fn()} onSubmit={vi.fn()}/>)
  await user.click(screen.getByRole('button',{name:'创建记录'})); const presence=screen.getByRole('combobox',{name:'必填值状态'}); expect(presence).toHaveFocus(); expect(presence).toHaveAccessibleDescription('请填写必填字段')
  await chooseOption(user,presence,'value'); await user.click(screen.getByRole('button',{name:'创建记录'})); const requiredInput=screen.getByLabelText('必填'); expect(requiredInput).toHaveFocus(); expect(requiredInput).toHaveAccessibleDescription('请填写必填字段')
})

it('keeps a dirty draft and permits lookup-only recovery after reconnect', async () => {
  const recover=vi.fn().mockResolvedValue(undefined), submit=vi.fn(), user=userEvent.setup()
  const props={open:true,mode:'create' as const,sessionKey:'same',submissionEpoch:'i1',fields:[field('x',{name:'内容'})],onOpenChange:vi.fn(),onSubmit:submit,onRecover:recover}
  const view=render(<RecordEditorDialog {...props}/>)
  await chooseOption(user,screen.getByRole('combobox',{name:'内容值状态'}),'value'); await user.type(screen.getByLabelText('内容'),'draft')
  view.rerender(<RecordEditorDialog {...props} submissionEpoch="i2" recoveryPending readonly error="结果未知" errorActions={<button>重试原请求</button>}/>)
  expect(screen.getByLabelText('内容')).toHaveValue('draft'); expect(screen.getByRole('combobox',{name:'内容值状态'})).toHaveAttribute('aria-readonly','true')
  expect(screen.getByRole('button',{name:'重试原请求'})).toBeVisible(); await user.click(screen.getByRole('button',{name:'核对保存结果'}))
  expect(recover).toHaveBeenCalledOnce(); expect(submit).not.toHaveBeenCalled()
})

it('revokes a pending close approval when a newer submit fails', async () => {
  let approve!: (approved: boolean) => void
  const close=vi.fn(), requestClose=vi.fn(()=>new Promise<boolean>(resolve=>{approve=resolve})), submit=vi.fn().mockRejectedValue(new Error('new submission failed'))
  render(<RecordEditorDialog open mode="create" sessionKey="close-submit" fields={[]} onOpenChange={close} onRequestClose={requestClose} onSubmit={submit}/>)
  await userEvent.click(screen.getByRole('button',{name:'取消'})); await userEvent.click(screen.getByRole('button',{name:'创建记录'})); await screen.findByText('new submission failed')
  await act(async()=>approve(true)); expect(close).not.toHaveBeenCalled()
})

it('revokes a pending close approval before a newer submit fails validation', async () => {
  let approve!: (approved: boolean) => void
  const close=vi.fn(), requestClose=vi.fn(()=>new Promise<boolean>(resolve=>{approve=resolve}))
  render(<RecordEditorDialog open mode="create" sessionKey="close-invalid-submit" fields={[field('required',{required:true})]} onOpenChange={close} onRequestClose={requestClose} onSubmit={vi.fn()}/>)
  await userEvent.click(screen.getByRole('button',{name:'取消'})); await userEvent.click(screen.getByRole('button',{name:'创建记录'})); expect(await screen.findByText('请填写必填字段')).toBeVisible()
  await act(async()=>approve(true)); expect(close).not.toHaveBeenCalled()
})

it('clears a pending recovery lock when a new session starts', async () => {
  let finish!:()=>void
  const recover=vi.fn(()=>new Promise<void>(resolve=>{finish=resolve})), props={open:true,mode:'create' as const,fields:[],onOpenChange:vi.fn(),onSubmit:vi.fn(),onRecover:recover}
  const view=render(<RecordEditorDialog {...props} sessionKey="old" recoveryPending/>); await userEvent.click(screen.getByRole('button',{name:'核对保存结果'}))
  view.rerender(<RecordEditorDialog {...props} sessionKey="new"/>); expect(screen.getByRole('button',{name:'取消'})).toBeEnabled(); await act(async()=>finish())
})

it('rechecks guards after an asynchronous close approval', async () => {
  let approve!:(allowed:boolean)=>void
  const close=vi.fn(), requestClose=vi.fn(()=>new Promise<boolean>(resolve=>{approve=resolve})), props={open:true,mode:'create' as const,sessionKey:'close-guard',fields:[],onOpenChange:close,onRequestClose:requestClose,onSubmit:vi.fn()}
  const view=render(<RecordEditorDialog {...props}/>); await userEvent.click(screen.getByRole('button',{name:'取消'})); expect(requestClose).toHaveBeenCalledOnce()
  view.rerender(<RecordEditorDialog {...props} saving/>); approve(true); await act(async()=>{})
  expect(close).not.toHaveBeenCalled()
})

it('revokes an asynchronous close approval when the record session changes', async()=>{
  let approve!:(allowed:boolean)=>void;const close=vi.fn(),requestClose=vi.fn(()=>new Promise<boolean>(resolve=>{approve=resolve})),props={open:true,mode:'create' as const,fields:[],onOpenChange:close,onRequestClose:requestClose,onSubmit:vi.fn()}
  const view=render(<RecordEditorDialog {...props} sessionKey="A" submissionEpoch="one"/>);await userEvent.click(screen.getByRole('button',{name:'取消'}))
  view.rerender(<RecordEditorDialog {...props} sessionKey="B" submissionEpoch="two"/>);await act(async()=>approve(true));expect(close).not.toHaveBeenCalled()
})

it('removes an open discard confirmation when recovery becomes pending',async()=>{
  const user=userEvent.setup(),props={open:true,mode:'edit' as const,sessionKey:'A',fields:[field('x')],initialRecord:record([cell('x','a')]),onOpenChange:vi.fn(),onSubmit:vi.fn()}
  const view=render(<RecordEditorDialog {...props}/>);await user.type(screen.getByLabelText('x'),'dirty');await user.click(screen.getByRole('button',{name:'取消'}));expect(screen.getByRole('alertdialog')).toBeVisible()
  view.rerender(<RecordEditorDialog {...props} recoveryPending/>);expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
})

it('removes an open discard confirmation when the record session changes',async()=>{
  const user=userEvent.setup(),props={open:true,mode:'edit' as const,fields:[field('x')],onOpenChange:vi.fn(),onSubmit:vi.fn()}
  const view=render(<RecordEditorDialog {...props} sessionKey="A" submissionEpoch="one" initialRecord={record([cell('x','a')])}/>);await user.type(screen.getByLabelText('x'),'dirty');await user.click(screen.getByRole('button',{name:'取消'}));expect(screen.getByRole('alertdialog')).toBeVisible()
  view.rerender(<RecordEditorDialog {...props} sessionKey="B" submissionEpoch="two" initialRecord={record([cell('x','b')])}/>);expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
})

it('keeps legacy dialog actions in the modal footer',()=>{
  render(<RecordEditorDialog open mode="create" sessionKey="fixed-footer" fields={[]} onOpenChange={vi.fn()} onSubmit={vi.fn()}/>)
  expect(screen.getByRole('button',{name:'取消'}).closest('footer')).toBeInTheDocument()
  expect(screen.getByRole('button',{name:'创建记录'}).closest('footer')).toBe(screen.getByRole('button',{name:'取消'}).closest('footer'))
})
