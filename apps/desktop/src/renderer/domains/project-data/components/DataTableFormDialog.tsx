import { zodResolver } from '@hookform/resolvers/zod'
import { Info } from '@phosphor-icons/react'
import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { useForm } from 'react-hook-form'
import { FormField } from '../../../shared/components/FormField'
import { Modal } from '../../../shared/components/Modal'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../../shared/components/ui/alert-dialog'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Textarea } from '../../../shared/components/ui/textarea'
import { dataTableFormSchema, emptyDataTableForm, type DataTableFormValues } from '../form-schema'

export type DataTableFormDialogProps = {
  open: boolean; mode: 'create' | 'edit'; sessionKey: string; initialValues?: DataTableFormValues; submissionEpoch?: string | number
  saving?: boolean; recoveryPending?: boolean; error?: string | null; errorActions?: ReactNode; readonly?: boolean
  onOpenChange(open: boolean): void; onRequestClose?(): boolean | void | Promise<boolean | void>
  onSubmit(values: DataTableFormValues): Promise<unknown>; onRecover?(): Promise<unknown>
  onDirtyChange?(dirty: boolean): void; onSavingChange?(saving: boolean): void
}

export function DataTableFormDialog({ open, mode, sessionKey, initialValues, submissionEpoch = 0, saving = false, recoveryPending = false, error, errorActions, readonly = false, onOpenChange, onRequestClose, onSubmit, onRecover, onDirtyChange, onSavingChange }: DataTableFormDialogProps) {
  const [submitting,setSubmitting]=useState(false),[recovering,setRecovering]=useState(false),[submitError,setSubmitError]=useState<string|null>(null),[confirmClose,setConfirmClose]=useState(false)
  const busy=saving||submitting||recovering, frozen=busy||recoveryPending
  const form=useForm<DataTableFormValues>({resolver:zodResolver(dataTableFormSchema),defaultValues:initialValues??emptyDataTableForm})
  const requestEpoch=useRef(0),submitLock=useRef(false),recoverLock=useRef(false),closeLock=useRef(false),activeSession=useRef(sessionKey),activeSubmission=useRef(submissionEpoch),wasOpen=useRef(open)
  const guard=useRef({open,readonly,saving,recoveryPending}),dirtyCallback=useRef(onDirtyChange),savingCallback=useRef(onSavingChange)
  useLayoutEffect(()=>{
    const starts=activeSession.current!==sessionKey||(open&&!wasOpen.current),closed=wasOpen.current&&!open,reconnect=activeSubmission.current!==submissionEpoch
    activeSession.current=sessionKey;activeSubmission.current=submissionEpoch;wasOpen.current=open
    if(closed||reconnect){requestEpoch.current+=1;submitLock.current=false;recoverLock.current=false;closeLock.current=false;setSubmitting(false);setRecovering(false);setSubmitError(null);setConfirmClose(false)}
    if(!starts)return
    requestEpoch.current+=1;submitLock.current=false;recoverLock.current=false;closeLock.current=false
    if(open){form.reset(initialValues??emptyDataTableForm);setSubmitting(false);setRecovering(false);setSubmitError(null);setConfirmClose(false)}
  },[form,initialValues,open,sessionKey,submissionEpoch])
  useLayoutEffect(()=>{guard.current={open,readonly,saving,recoveryPending}},[open,readonly,recoveryPending,saving])
  useLayoutEffect(()=>{dirtyCallback.current=onDirtyChange;savingCallback.current=onSavingChange},[onDirtyChange,onSavingChange])
  useEffect(()=>{if(open&&activeSession.current===sessionKey&&!form.formState.isDirty)form.reset(initialValues??emptyDataTableForm)},[form,initialValues,open,sessionKey])
  useEffect(()=>onDirtyChange?.(open&&form.formState.isDirty),[form.formState.isDirty,onDirtyChange,open,sessionKey])
  useEffect(()=>onSavingChange?.(busy),[busy,onSavingChange])
  useEffect(()=>()=>{requestEpoch.current+=1;dirtyCallback.current?.(false);savingCallback.current?.(false)},[])
  const requestClose=()=>{
    if(busy||submitLock.current||recoverLock.current||closeLock.current)return
    if(form.formState.isDirty||recoveryPending){
      if(onRequestClose){const ticket=requestEpoch.current;closeLock.current=true;void Promise.resolve().then(onRequestClose).then(approved=>{if(approved===true&&ticket===requestEpoch.current&&guard.current.open&&!guard.current.saving&&!guard.current.recoveryPending&&!submitLock.current&&!recoverLock.current)onOpenChange(false)}).catch(()=>undefined).finally(()=>{if(ticket===requestEpoch.current)closeLock.current=false})}
      else if(!recoveryPending)setConfirmClose(true)
      return
    }
    onOpenChange(false)
  }
  const submit=(event:FormEvent<HTMLFormElement>)=>{
    event.preventDefault();if(submitLock.current||busy||recoveryPending||readonly)return
    submitLock.current=true;savingCallback.current?.(true);setSubmitting(true);setSubmitError(null);const ticket=requestEpoch.current
    void form.handleSubmit(async values=>{const current=guard.current;if(ticket!==requestEpoch.current||!current.open||current.readonly||current.saving||current.recoveryPending)return;await onSubmit(dataTableFormSchema.parse(values))},errors=>{if(ticket===requestEpoch.current)form.setFocus(errors.name?'name':'description')})()
      .catch(caught=>{if(ticket===requestEpoch.current)setSubmitError(caught instanceof Error?caught.message:'保存数据表失败')})
      .finally(()=>{if(ticket===requestEpoch.current){submitLock.current=false;setSubmitting(false);savingCallback.current?.(guard.current.saving)}})
  }
  const recover=()=>{
    if(!onRecover||recoverLock.current||busy)return
    recoverLock.current=true;savingCallback.current?.(true);setRecovering(true);setSubmitError(null);const ticket=requestEpoch.current
    void onRecover().catch(caught=>{if(ticket===requestEpoch.current)setSubmitError(caught instanceof Error?caught.message:'核对保存结果失败')}).finally(()=>{if(ticket===requestEpoch.current){recoverLock.current=false;setRecovering(false);savingCallback.current?.(guard.current.saving)}})
  }
  return <>
    <Modal open={open} onOpenChange={next=>{if(!next)requestClose()}} closeDisabled={busy} size="small" className="max-w-[32.5rem] [&_[data-slot=dialog-title]]:text-[28px]" title={mode==='create'?'新建数据表':'编辑数据表'} description={mode==='create'?'先给数据一个用途，来源可以稍后配置。':'修改数据表名称和用途说明。'} footer={<><Button type="button" variant="ghost" disabled={busy} onClick={requestClose}>取消</Button>{recoveryPending?<Button type="button" variant="primary" disabled={busy||!onRecover} onClick={recover}>{recovering?'正在核对…':'核对保存结果'}</Button>:<Button type="submit" form="data-table-form" variant="primary" disabled={busy||readonly}>{busy?'正在保存…':mode==='create'?'创建数据表':'保存修改'}</Button>}</>}>
      <form id="data-table-form" className="grid gap-5" onSubmit={submit}>
        {error||submitError?<div role="alert" className="m-0 rounded-control border border-clay/30 bg-clay/10 p-3 text-sm text-ink"><p className="m-0">{submitError??error}</p>{errorActions?<div className="mt-3">{errorActions}</div>:null}</div>:null}
        <div className="grid gap-2"><label className="text-sm font-medium text-ink" htmlFor="data-table-name">数据表名称 <span aria-hidden="true" className="text-clay">*</span></label><Input id="data-table-name" aria-label="数据表名称" autoFocus maxLength={120} readOnly={frozen||readonly} aria-invalid={form.formState.errors.name?true:undefined} aria-describedby={form.formState.errors.name?'data-table-name-error':undefined} {...form.register('name')}/>{form.formState.errors.name?<p id="data-table-name-error" role="alert" className="text-xs text-clay">{form.formState.errors.name.message}</p>:null}</div>
        <FormField label="用途说明（可选）" htmlFor="data-table-description" error={form.formState.errors.description?.message} hint="最多 1000 个字符"><Textarea rows={4} maxLength={1000} readOnly={frozen||readonly} {...form.register('description')}/></FormField>
        <p className="m-0 flex items-start gap-2 border-t border-line pt-4 text-sm text-muted"><Info className="mt-0.5 shrink-0"/>创建后即可维护本地记录，后续可按需配置数据来源。</p>
      </form>
    </Modal>
    <AlertDialog open={open&&confirmClose} onOpenChange={next=>{if(!busy||next)setConfirmClose(next)}}><AlertDialogContent><AlertDialogTitle>放弃未保存的修改？</AlertDialogTitle><AlertDialogDescription>关闭后，本次对数据表的修改将不会保存。</AlertDialogDescription><div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button autoFocus disabled={busy}>继续编辑</Button></AlertDialogCancel><AlertDialogAction asChild><Button variant="danger" disabled={busy} onClick={()=>{if(busy)return;setConfirmClose(false);form.reset(initialValues??emptyDataTableForm);onOpenChange(false)}}>放弃修改</Button></AlertDialogAction></div></AlertDialogContent></AlertDialog>
  </>
}
