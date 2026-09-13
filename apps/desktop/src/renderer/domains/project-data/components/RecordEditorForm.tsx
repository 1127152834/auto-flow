import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { createRecordDraft, recordValues, RecordDraftError, type RecordDraft } from '../record-draft'
import type { ScalarDraftControl } from '../scalar-draft'
import { ScalarValueEditor } from './ScalarValueEditor'

type Schema = components['schemas']
type Field = Schema['DataFieldView']
type RecordView = Schema['DataRecordView']
type CellWrite = Schema['DataCellWrite']
type FormContext = { fields: Field[]; initialRecord?: RecordView; identityFieldId?: string }
export type RecordEditorFormProps = {
  id: string; mode: 'create' | 'edit'; sessionKey: string; fields: Field[]; initialRecord?: RecordView; identityFieldId?: string; submissionEpoch?: string | number
  saving?: boolean; recoveryPending?: boolean; readonly?: boolean; error?: string | null; errorActions?: ReactNode; footerClassName?: string
  externalActions?: boolean
  onCancel?(): void; onSubmitAttempt?(): void; onSubmit(values: CellWrite[]): Promise<unknown>; onRecover?(): Promise<unknown>; onDirtyChange?(dirty: boolean): void; onSavingChange?(saving: boolean): void
}

const equalDraft = (left: RecordDraft, right: RecordDraft) => JSON.stringify(left) === JSON.stringify(right)

export function RecordEditorForm({ id, mode, sessionKey, fields, initialRecord, identityFieldId, submissionEpoch=0, saving=false, recoveryPending=false, readonly=false, error, errorActions, footerClassName, externalActions=false, onCancel, onSubmitAttempt, onSubmit, onRecover, onDirtyChange, onSavingChange }: RecordEditorFormProps) {
  const [drafts,setDrafts]=useState(()=>createRecordDraft(fields,initialRecord)),[context,setContext]=useState<FormContext>(()=>({fields,initialRecord,identityFieldId}))
  const [fieldErrors,setFieldErrors]=useState<Record<string,{message:string;control:ScalarDraftControl}>>({}),[submitError,setSubmitError]=useState<string|null>(null)
  const [submitting,setSubmitting]=useState(false),[recovering,setRecovering]=useState(false)
  const baseline=useRef(drafts),activeSession=useRef(sessionKey),activeSubmission=useRef(submissionEpoch),requestEpoch=useRef(0),submitLock=useRef(false),recoverLock=useRef(false)
  const guardRef=useRef({readonly,saving,recoveryPending}),lastInitial=useRef(initialRecord),lastFields=useRef(fields),dirtyCallback=useRef(onDirtyChange),savingCallback=useRef(onSavingChange)
  const fieldContainers=useRef(new Map<string,HTMLDivElement>())
  const hasChanges=mode==='create'?!equalDraft(drafts,baseline.current):(()=>{try{return recordValues(context.fields,drafts,context.initialRecord,context.identityFieldId).length>0}catch{return true}})()
  const busy=saving||submitting||recovering,frozen=busy||recoveryPending

  useLayoutEffect(()=>{
    const newSession=activeSession.current!==sessionKey,reconnect=activeSubmission.current!==submissionEpoch,refreshed=lastInitial.current!==initialRecord||lastFields.current!==fields
    activeSession.current=sessionKey;activeSubmission.current=submissionEpoch;lastInitial.current=initialRecord;lastFields.current=fields
    if(reconnect){requestEpoch.current++;submitLock.current=false;recoverLock.current=false;setSubmitting(false);setRecovering(false);setFieldErrors({});setSubmitError(null)}
    if(newSession){requestEpoch.current++;submitLock.current=false;recoverLock.current=false;setSubmitting(false);setRecovering(false);const next=createRecordDraft(fields,initialRecord);baseline.current=next;setDrafts(next);setContext({fields,initialRecord,identityFieldId});setFieldErrors({});setSubmitError(null);return}
    if(refreshed&&!hasChanges){const next=createRecordDraft(fields,initialRecord);baseline.current=next;setDrafts(next);setContext({fields,initialRecord,identityFieldId});setFieldErrors({})}
  },[fields,hasChanges,identityFieldId,initialRecord,sessionKey,submissionEpoch])
  useLayoutEffect(()=>{dirtyCallback.current=onDirtyChange;savingCallback.current=onSavingChange;guardRef.current={readonly,saving,recoveryPending}},[onDirtyChange,onSavingChange,readonly,recoveryPending,saving])
  useEffect(()=>{onDirtyChange?.(hasChanges)},[hasChanges,onDirtyChange,sessionKey])
  useEffect(()=>{onSavingChange?.(busy)},[busy,onSavingChange])
  useEffect(()=>()=>{requestEpoch.current++;dirtyCallback.current?.(false);savingCallback.current?.(false)},[])

  const focusField=(fieldId:string,control:ScalarDraftControl)=>{const suffix=control==='presence'?'-presence':control==='offset'?'-offset':'';fieldContainers.current.get(fieldId)?.querySelector<HTMLElement>(`#${id}-${fieldId}${suffix}`)?.focus()}
  const submit=(event:FormEvent<HTMLFormElement>)=>{
    event.preventDefault();if((event.nativeEvent as SubmitEvent).submitter instanceof HTMLElement&&(event.nativeEvent as SubmitEvent).submitter?.dataset.recordAction==='recover'){recover();return}if(submitLock.current||busy||recoveryPending||readonly||(mode==='edit'&&!hasChanges))return
    onSubmitAttempt?.();requestEpoch.current++;submitLock.current=true;const ticket=requestEpoch.current,target=context;let values:CellWrite[]
    try{values=recordValues(target.fields,drafts,target.initialRecord,target.identityFieldId)}catch(caught){submitLock.current=false;if(caught instanceof RecordDraftError){setFieldErrors({[caught.fieldId]:{message:caught.message,control:caught.control}});focusField(caught.fieldId,caught.control)}else setSubmitError(caught instanceof Error?caught.message:'记录值无效');return}
    if(mode==='edit'&&!values.length){submitLock.current=false;return}
    savingCallback.current?.(true);setFieldErrors({});setSubmitError(null);setSubmitting(true);const snapshot=values.map(value=>({...value}))
    void Promise.resolve().then(()=>{const guard=guardRef.current;if(ticket!==requestEpoch.current||guard.readonly||guard.saving||guard.recoveryPending)return;return onSubmit(snapshot)}).catch(caught=>{if(ticket===requestEpoch.current)setSubmitError(caught instanceof Error?caught.message:'保存记录失败')}).finally(()=>{if(ticket===requestEpoch.current){submitLock.current=false;setSubmitting(false);savingCallback.current?.(guardRef.current.saving)}})
  }
  const recover=()=>{if(!onRecover||recoverLock.current||busy)return;requestEpoch.current++;recoverLock.current=true;savingCallback.current?.(true);setRecovering(true);setSubmitError(null);const ticket=requestEpoch.current;void onRecover().catch(caught=>{if(ticket===requestEpoch.current)setSubmitError(caught instanceof Error?caught.message:'核对保存结果失败')}).finally(()=>{if(ticket===requestEpoch.current){recoverLock.current=false;setRecovering(false);savingCallback.current?.(guardRef.current.saving)}})}

  return <form id={id} aria-label={mode==='create'?'新建记录表单':'编辑记录表单'} className="grid min-w-0 gap-5" noValidate onSubmit={submit}>
    {context.initialRecord?<p className="m-0 break-all rounded-control border border-line bg-surface px-3 py-2 text-sm text-muted">记录身份：{context.initialRecord.ref.recordKey.type} · {context.initialRecord.ref.recordKey.value}</p>:null}
    {error||submitError?<div role="alert" className="m-0 rounded-control border border-clay/30 bg-clay/10 p-3 text-sm text-ink"><p className="m-0">{submitError??error}</p>{errorActions?<div className="mt-3">{errorActions}</div>:null}</div>:null}
    {!context.fields.length?<p className="text-sm text-muted">当前表没有业务字段，将创建一条系统身份记录。</p>:null}
    {context.fields.map(field=>{const fieldId=field.ref.fieldId,cell=context.initialRecord?.values.find(value=>value.fieldId===fieldId);const protectedReason=field.formula?'公式字段由系统计算':!field.writable?'此字段只读':cell?.readable===false?'此值不可读取，因此不能编辑':mode==='edit'&&fieldId===context.identityFieldId?'记录身份字段不能在编辑时修改':null;return <div key={fieldId} ref={node=>{if(node)fieldContainers.current.set(fieldId,node);else fieldContainers.current.delete(fieldId)}} className="grid min-w-0 gap-2"><ScalarValueEditor id={`${id}-${fieldId}`} label={field.name} type={field.type} draft={drafts[fieldId]??createRecordDraft([field])[fieldId]} allowMissing={!field.required} presenceDisplay="contextual" disabled={frozen} readOnly={readonly||Boolean(protectedReason)} error={fieldErrors[fieldId]?.message} errorTarget={fieldErrors[fieldId]?.control} onChange={draft=>{setDrafts(current=>({...current,[fieldId]:draft}));setFieldErrors(current=>{const next={...current};delete next[fieldId];return next})}}/>{protectedReason?<p className="text-xs text-muted">{protectedReason}</p>:null}</div>})}
    {externalActions?null:<footer className={footerClassName??'flex justify-end gap-2'}>{onCancel?<Button type="button" variant="ghost" disabled={busy} onClick={onCancel}>取消</Button>:null}{recoveryPending?<Button type="button" variant="primary" disabled={busy||!onRecover} onClick={recover}>{recovering?'正在核对…':'核对保存结果'}</Button>:<Button type="submit" variant="primary" disabled={busy||readonly||(mode==='edit'&&!hasChanges)}>{busy?'正在保存…':mode==='create'?'创建记录':'保存修改'}</Button>}</footer>}
  </form>
}
