import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { FieldEditorDialog } from './FieldEditorDialog'

afterEach(cleanup)
beforeEach(() => {
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  HTMLElement.prototype.hasPointerCapture = vi.fn(() => false)
  HTMLElement.prototype.setPointerCapture = vi.fn()
  HTMLElement.prototype.releasePointerCapture = vi.fn()
  HTMLElement.prototype.scrollIntoView = vi.fn()
})
const field = { ref: { projectId:'00000000-0000-0000-0000-000000000001', tableId:'00000000-0000-0000-0000-000000000002', datasetGeneration:'00000000-0000-0000-0000-000000000003', fieldId:'00000000-0000-0000-0000-000000000004' }, key:'email', name:'Email', type:'string' as const, required:false, writable:true, formula:false, validation:{}, fieldRevision:1 }
const impact = { impactRevision: 9, target:{ type:'field' as const, fieldRef:field.ref }, changeDigest:'x', expectedRevisions:{ tableRevision:1, fieldRevision:1 }, impacts:[{ code:'FIELD_RECORD_VALIDATION', resource:{ type:'field' as const, fieldRef:field.ref }, message:'已检查', blocking:false }], blockers:[], calculatedAt:new Date().toISOString() }

it('creates a required field with an explicit default and keeps parent control', async () => {
  const submit=vi.fn().mockResolvedValue(undefined), close=vi.fn(), user=userEvent.setup()
  render(<FieldEditorDialog open mode="create" sessionKey="w:p:t:create" onOpenChange={close} onSubmit={submit} />)
  await user.type(screen.getByLabelText('字段名称'),' Email '); await user.type(screen.getByLabelText('字段键'),' email ')
  await user.click(screen.getByText('必填'))
  await user.click(screen.getByLabelText('现有记录默认值值状态')); await user.click(screen.getByRole('option',{name:'填写值'}))
  await user.type(screen.getByLabelText('现有记录默认值'),' a@b ')
  await user.click(screen.getByRole('button',{name:'创建字段'}))
  await waitFor(()=>expect(submit).toHaveBeenCalledWith({ definition:{ key:'email',name:'Email',type:'string',required:true,validation:{} }, existingRecordDefault:' a@b ' }))
  expect(close).not.toHaveBeenCalled()
})

it('allows a required field to omit the existing-record default', async () => {
  const submit=vi.fn().mockResolvedValue(undefined), user=userEvent.setup()
  render(<FieldEditorDialog open mode="create" sessionKey="required-empty" onOpenChange={vi.fn()} onSubmit={submit} />)
  await user.type(screen.getByLabelText('字段名称'),'Required'); await user.type(screen.getByLabelText('字段键'),'required'); await user.click(screen.getByText('必填'))
  await user.click(screen.getByRole('button',{name:'创建字段'}))
  await waitFor(()=>expect(submit).toHaveBeenCalledWith({definition:expect.objectContaining({required:true})}))
  expect(screen.getByText(/非空表/)).toBeVisible()
})

it('previews edit, displays blockers, invalidates impact after draft changes', async () => {
  const preview=vi.fn().mockResolvedValue(impact), submit=vi.fn(), user=userEvent.setup()
  render(<FieldEditorDialog open mode="edit" sessionKey="w:p:t:f:s" initialField={field} onOpenChange={vi.fn()} onPreview={preview} onSubmit={submit} />)
  await user.clear(screen.getByLabelText('字段名称')); await user.type(screen.getByLabelText('字段名称'),'Address')
  await user.click(screen.getByRole('button',{name:'预检影响'})); expect(await screen.findByText('将检查现有记录是否符合新的字段规则')).toBeVisible()
  await user.clear(screen.getByLabelText('字段键')); await user.type(screen.getByLabelText('字段键'),'address')
  expect(screen.queryByText('将检查现有记录是否符合新的字段规则')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button',{name:'预检影响'})); await screen.findByText('将检查现有记录是否符合新的字段规则')
  await user.click(screen.getByRole('button',{name:'确认修改'}))
  await waitFor(()=>expect(submit).toHaveBeenCalledWith(expect.objectContaining({impactRevision:9})))
})

it('blocks confirmation and preserves dirty values through same-session refresh', async () => {
  const blocked={...impact,blockers:[{code:'FIELD_READ_ONLY',resource:{type:'field' as const,fieldRef:field.ref},state:'blocked',message:'不能修改'}]}
  const user=userEvent.setup(), preview=vi.fn().mockResolvedValue(blocked), submit=vi.fn(), dirty=vi.fn()
  const props={open:true,mode:'edit' as const,sessionKey:'same',initialField:field,onOpenChange:vi.fn(),onPreview:preview,onSubmit:submit,onDirtyChange:dirty}
  const view=render(<FieldEditorDialog {...props}/>)
  await user.clear(screen.getByLabelText('字段名称')); await user.type(screen.getByLabelText('字段名称'),'Draft')
  view.rerender(<FieldEditorDialog {...props} initialField={{...field,name:'Server'}} />)
  expect(screen.getByLabelText('字段名称')).toHaveValue('Draft')
  await user.click(screen.getByRole('button',{name:'预检影响'})); expect(await screen.findByText('操作失败，请重试')).toBeVisible()
  expect(screen.getByRole('button',{name:'确认修改'})).toBeDisabled(); expect(submit).not.toHaveBeenCalled(); expect(dirty).toHaveBeenCalledWith(true)
  fireEvent.submit(document.querySelector('#field-editor-form')!)
  expect(submit).not.toHaveBeenCalled()
})

it('locks protected fields and dirty close while saving', async () => {
  const close=vi.fn()
  const view=render(<FieldEditorDialog open mode="edit" sessionKey="x" initialField={{...field,formula:true,writable:false}} onOpenChange={close} onSubmit={vi.fn()} />)
  expect(screen.getByLabelText('字段名称')).toHaveAttribute('readonly')
  view.rerender(<FieldEditorDialog open mode="edit" sessionKey="x" initialField={field} saving onOpenChange={close} onSubmit={vi.fn()} />)
  expect(screen.getByRole('button',{name:'处理中…'})).toBeDisabled()
})

it('refreshes a pristine edit but never overwrites a dirty draft', async () => {
  const props={open:true,mode:'edit' as const,sessionKey:'same',initialField:field,onOpenChange:vi.fn(),onSubmit:vi.fn()}
  const view=render(<FieldEditorDialog {...props}/>)
  view.rerender(<FieldEditorDialog {...props} initialField={{...field,name:'Server'}} />)
  await waitFor(()=>expect(screen.getByLabelText('字段名称')).toHaveValue('Server'))
  await userEvent.setup().type(screen.getByLabelText('字段名称'),' draft')
  view.rerender(<FieldEditorDialog {...props} initialField={{...field,name:'New server'}} />)
  expect(screen.getByLabelText('字段名称')).toHaveValue('Server draft')
})

it('ignores a preview completing after the committed session changes', async () => {
  let finish!: (value: typeof impact) => void
  const preview=vi.fn(() => new Promise<typeof impact>(resolve => { finish=resolve })), user=userEvent.setup()
  const props={open:true,mode:'edit' as const,initialField:field,onOpenChange:vi.fn(),onPreview:preview,onSubmit:vi.fn()}
  const view=render(<FieldEditorDialog {...props} sessionKey="A" />)
  await user.type(screen.getByLabelText('字段名称'),' x'); await user.click(screen.getByRole('button',{name:'预检影响'}))
  view.rerender(<FieldEditorDialog {...props} sessionKey="B" initialField={{...field,name:'Second'}} />)
  finish(impact)
  await waitFor(()=>expect(screen.getByLabelText('字段名称')).toHaveValue('Second'))
  expect(screen.queryByText('已检查')).not.toBeInTheDocument()
})

it('does not submit a validated old session after a committed session switch', async () => {
  const submitA=vi.fn(), submitB=vi.fn()
  const props={open:true,mode:'create' as const,onOpenChange:vi.fn()}
  const view=render(<FieldEditorDialog {...props} sessionKey="A" onSubmit={submitA} />)
  fireEvent.change(screen.getByLabelText('字段名称'),{target:{value:'First'}}); fireEvent.change(screen.getByLabelText('字段键'),{target:{value:'first'}})
  fireEvent.submit(document.querySelector('#field-editor-form')!)
  view.rerender(<FieldEditorDialog {...props} sessionKey="B" onSubmit={submitB} />)
  await Promise.resolve(); await Promise.resolve()
  expect(submitA).not.toHaveBeenCalled(); expect(submitB).not.toHaveBeenCalled()
})

it('uses normalized definitions to detect an unchanged edit', async () => {
  const preview=vi.fn(), user=userEvent.setup()
  render(<FieldEditorDialog open mode="edit" sessionKey="normalized" initialField={field} onOpenChange={vi.fn()} onPreview={preview} onSubmit={vi.fn()} />)
  await user.type(screen.getByLabelText('字段名称'),' ')
  expect(screen.getByRole('button',{name:'预检影响'})).toBeDisabled()
  fireEvent.submit(document.querySelector('#field-editor-form')!); expect(preview).not.toHaveBeenCalled()
})

it('lets an invalid dirty edit reach the resolver and show its error', async () => {
  const preview=vi.fn(), user=userEvent.setup()
  render(<FieldEditorDialog open mode="edit" sessionKey="invalid" initialField={field} onOpenChange={vi.fn()} onPreview={preview} onSubmit={vi.fn()} />)
  await user.clear(screen.getByLabelText('字段名称'))
  expect(screen.getByRole('button',{name:'预检影响'})).toBeEnabled()
  await user.click(screen.getByRole('button',{name:'预检影响'}))
  expect(await screen.findByText('请输入字段名称')).toBeVisible(); expect(preview).not.toHaveBeenCalled()
})

it('requires confirmation to close a dirty form and does nothing for an unchanged edit', async () => {
  const close=vi.fn(), preview=vi.fn(), user=userEvent.setup()
  render(<FieldEditorDialog open mode="edit" sessionKey="close" initialField={field} onOpenChange={close} onPreview={preview} onSubmit={vi.fn()} />)
  expect(screen.getByRole('button',{name:'预检影响'})).toBeDisabled()
  await user.type(screen.getByLabelText('字段名称'),' x'); await user.click(screen.getByRole('button',{name:'取消'}))
  expect(await screen.findByText('放弃未保存的修改？')).toBeVisible(); expect(close).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button',{name:'继续编辑'})); expect(screen.queryByText('放弃未保存的修改？')).not.toBeInTheDocument()
})

it('removes a dirty confirmation when the parent closes the dialog', async () => {
  const user=userEvent.setup(), props={mode:'edit' as const,sessionKey:'parent-close',initialField:field,onOpenChange:vi.fn(),onSubmit:vi.fn()}
  const view=render(<FieldEditorDialog open {...props} />)
  await user.type(screen.getByLabelText('字段名称'),' changed'); await user.click(screen.getByRole('button',{name:'取消'})); await screen.findByRole('alertdialog')
  view.rerender(<FieldEditorDialog open={false} {...props} />)
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
})

it('keeps failed create input and clears dirty state when the dialog closes', async () => {
  const submit=vi.fn().mockRejectedValue(new Error('保存失败')), dirty=vi.fn(), user=userEvent.setup()
  const props={mode:'create' as const,sessionKey:'create-fail',onOpenChange:vi.fn(),onSubmit:submit,onDirtyChange:dirty}
  const view=render(<FieldEditorDialog open {...props} />)
  await user.type(screen.getByLabelText('字段名称'),'Draft'); await user.type(screen.getByLabelText('字段键'),'draft')
  await user.click(screen.getByRole('button',{name:'创建字段'}))
  expect(await screen.findByRole('alert')).toHaveTextContent('操作失败，请重试'); expect(screen.getByLabelText('字段名称')).toHaveValue('Draft')
  view.rerender(<FieldEditorDialog open={false} {...props} />)
  expect(dirty).toHaveBeenLastCalledWith(false)
})

it('revokes an old preview on reconnect while preserving the definition draft', async () => {
  let finish!:(value:typeof impact)=>void
  const preview=vi.fn(()=>new Promise<typeof impact>(resolve=>{finish=resolve})), user=userEvent.setup()
  const props={open:true,mode:'edit' as const,sessionKey:'same',submissionEpoch:'i1',initialField:field,onOpenChange:vi.fn(),onPreview:preview,onSubmit:vi.fn()}
  const view=render(<FieldEditorDialog {...props}/>); await user.type(screen.getByLabelText('字段名称'),' draft'); await user.click(screen.getByRole('button',{name:'预检影响'}))
  view.rerender(<FieldEditorDialog {...props} submissionEpoch="i2" recoveryPending onRecover={vi.fn().mockResolvedValue(undefined)}/>)
  finish(impact); await Promise.resolve(); await Promise.resolve()
  expect(screen.getByLabelText('字段名称')).toHaveValue('Email draft'); expect(screen.queryByText('已检查')).not.toBeInTheDocument(); expect(screen.getByRole('button',{name:'核对保存结果'})).toBeVisible()
})

it('allows readonly recovery and reports local saving lifecycle', async () => {
  let finish!:()=>void
  const recover=vi.fn(()=>new Promise<void>(resolve=>{finish=resolve})), savingChange=vi.fn()
  render(<FieldEditorDialog open mode="edit" sessionKey="recover" initialField={field} readonly recoveryPending onOpenChange={vi.fn()} onSubmit={vi.fn()} onRecover={recover} onSavingChange={savingChange}/>)
  await userEvent.click(screen.getByRole('button',{name:'核对保存结果'})); expect(recover).toHaveBeenCalledOnce(); expect(savingChange).toHaveBeenLastCalledWith(true)
  finish(); await waitFor(()=>expect(savingChange).toHaveBeenLastCalledWith(false))
})

it('revokes a pending close approval when a newer submit fails', async () => {
  let approve!: (approved: boolean) => void
  const close=vi.fn(), requestClose=vi.fn(()=>new Promise<boolean>(resolve=>{approve=resolve})), submit=vi.fn().mockRejectedValue(new Error('new submission failed'))
  render(<FieldEditorDialog open mode="create" sessionKey="close-submit" onOpenChange={close} onRequestClose={requestClose} onSubmit={submit}/>)
  fireEvent.change(screen.getByLabelText('字段名称'),{target:{value:'Name'}}); fireEvent.change(screen.getByLabelText('字段键'),{target:{value:'name'}})
  await userEvent.click(screen.getByRole('button',{name:'取消'})); await userEvent.click(screen.getByRole('button',{name:'创建字段'})); await screen.findByText('操作失败，请重试')
  await act(async()=>approve(true)); expect(close).not.toHaveBeenCalled()
})

it('clears a pending recovery lock when a new session starts', async () => {
  let finish!:()=>void
  const recover=vi.fn(()=>new Promise<void>(resolve=>{finish=resolve})), props={open:true,mode:'create' as const,onOpenChange:vi.fn(),onSubmit:vi.fn(),onRecover:recover}
  const view=render(<FieldEditorDialog {...props} sessionKey="old" recoveryPending/>); await userEvent.click(screen.getByRole('button',{name:'核对保存结果'}))
  view.rerender(<FieldEditorDialog {...props} sessionKey="new"/>); expect(screen.getByRole('button',{name:'取消'})).toBeEnabled(); await act(async()=>finish())
})
