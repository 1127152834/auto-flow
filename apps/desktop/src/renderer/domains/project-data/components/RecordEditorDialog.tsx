import { useEffect, useRef, useState } from 'react'
import { Modal } from '../../../shared/components/Modal'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../../shared/components/ui/alert-dialog'
import { Button } from '../../../shared/components/ui/button'
import { RecordEditorForm, type RecordEditorFormProps } from './RecordEditorForm'

export type RecordEditorDialogProps = Omit<RecordEditorFormProps, 'id' | 'onCancel'> & {
  open: boolean
  onOpenChange(open: boolean): void
  onRequestClose?(): boolean | void | Promise<boolean | void>
}

export function RecordEditorDialog({ open, onOpenChange, onRequestClose, saving=false, recoveryPending=false, readonly=false, onDirtyChange, onSavingChange, ...props }: RecordEditorDialogProps) {
  const [dirty,setDirty]=useState(false),[formSaving,setFormSaving]=useState(false),[confirmClose,setConfirmClose]=useState(false)
  const closeLock=useRef(false),requestEpoch=useRef(0),guard=useRef({open,saving,recoveryPending})
  const busy=saving||formSaving
  useEffect(()=>{guard.current={open,saving,recoveryPending};if(!open){requestEpoch.current++;closeLock.current=false;setConfirmClose(false)}},[open,recoveryPending,saving])
  useEffect(()=>()=>{requestEpoch.current++},[])
  const requestClose=()=>{
    if(busy||closeLock.current)return
    if(onRequestClose){const ticket=requestEpoch.current;closeLock.current=true;void Promise.resolve().then(onRequestClose).then(approved=>{const current=guard.current;if(approved===true&&ticket===requestEpoch.current&&current.open&&!current.saving&&!current.recoveryPending)onOpenChange(false)}).catch(()=>undefined).finally(()=>{if(ticket===requestEpoch.current)closeLock.current=false});return}
    if(dirty||recoveryPending){if(!recoveryPending)setConfirmClose(true);return}
    onOpenChange(false)
  }
  return <>
    <Modal open={open} onOpenChange={next=>{if(!next)requestClose()}} closeDisabled={busy} variant="form" size="large" title={props.mode==='create'?'新建记录':'编辑记录'} description="填写记录的业务字段值。" bodyClassName="grid gap-5">
      <RecordEditorForm {...props} id="record-editor-form" saving={saving} recoveryPending={recoveryPending} readonly={readonly} onCancel={requestClose} onDirtyChange={value=>{setDirty(value);onDirtyChange?.(open&&value)}} onSavingChange={value=>{if(value){requestEpoch.current++;closeLock.current=false}setFormSaving(value);onSavingChange?.(value)}} />
    </Modal>
    <AlertDialog open={confirmClose} onOpenChange={next=>{if(!busy||next)setConfirmClose(next)}}><AlertDialogContent><AlertDialogTitle>放弃未保存的修改？</AlertDialogTitle><AlertDialogDescription>关闭后，本次记录修改不会保存。</AlertDialogDescription><div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button autoFocus disabled={busy}>继续编辑</Button></AlertDialogCancel><AlertDialogAction asChild><Button variant="danger" disabled={busy} onClick={()=>{if(busy)return;setConfirmClose(false);onOpenChange(false)}}>放弃修改</Button></AlertDialogAction></div></AlertDialogContent></AlertDialog>
  </>
}
