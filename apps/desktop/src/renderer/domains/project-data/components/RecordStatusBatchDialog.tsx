import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle, AlertDialogTrigger } from '../../../shared/components/ui/alert-dialog'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '../../../shared/components/ui/dialog'
import { Select } from '../../../shared/components/ui/select'
import { DataCommandNotAccepted, DataCommandUncertain } from '../data-command'
import type { ProjectOperation, StatusBatchApi, StatusBatchPreview, StatusBatchRequest } from '../status-batch-api'
import { DataOperationStatus } from './DataOperationStatus'

type Schema = components['schemas']
type StartPending = { key: string; request?: StatusBatchRequest; retry: boolean }
type CancelPending = { key: string; operationId: string; expectedRevision: number; originalKey: string; retry: boolean }
type Stored = { key: string; request?: StatusBatchRequest; cancel?: Omit<CancelPending, 'key' | 'retry'> }
export type RecordStatusBatchDialogProps = {
  open: boolean; sessionKey: string; contextKey: string; storageScopeKey: string; disabled?: boolean; readonly?: boolean
  records?: Schema['DataRecordView'][]; targets?: Schema['RecordStatusTarget'][]; statuses: Schema['DataStatusView'][]; api: StatusBatchApi
  onClose(): void; onCompleted?(operation: ProjectOperation): void; onDirtyChange?(dirty: boolean): void; onBusyChange?(busy: boolean): void
}
const storageKey = (scope: string) => `autoflow:status-batch:${scope}`
const message = (error: unknown) => error instanceof Error ? error.message : '批量状态操作失败'
const terminal = (operation: ProjectOperation) => operation.status === 'succeeded' || operation.status === 'failed'

export function RecordStatusBatchDialog({ open, sessionKey, contextKey, storageScopeKey, records = [], targets, statuses, api, disabled, readonly, onClose, onCompleted, onDirtyChange, onBusyChange }: RecordStatusBatchDialogProps) {
  const [statusId, setStatusId] = useState<string | null>(null), [preview, setPreview] = useState<StatusBatchPreview | null>(null), [frozen, setFrozen] = useState<StatusBatchRequest | null>(null)
  const [operation, setOperation] = useState<ProjectOperation | null>(null), [startPending, setStartPending] = useState<StartPending | null>(null), [cancelPending, setCancelPending] = useState<CancelPending | null>(null)
  const [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null)
  const epoch = `${contextKey}:${storageScopeKey}:${sessionKey}:${open}`, currentEpoch = useRef(''), lock = useRef(false), abort = useRef<AbortController | null>(null), delivered = useRef<string | null>(null)
  const selectedTargets = useMemo(() => targets ? structuredClone(targets) : records.map(record => ({ recordRef: structuredClone(record.ref), expectedStatusRevision: record.statusRevision })), [records, targets])
  const request = useMemo<StatusBatchRequest>(() => ({ statusId, targets: selectedTargets, blockSize: 100 }), [selectedTargets, sessionKey, statusId])
  const allowed = () => open && !disabled && !readonly
  const current = (ticket: string) => () => currentEpoch.current === ticket
  const persist = (value: Stored) => localStorage.setItem(storageKey(storageScopeKey), JSON.stringify(value))
  useLayoutEffect(() => { currentEpoch.current = epoch; return () => { currentEpoch.current = ''; abort.current?.abort() } }, [epoch])
  useEffect(() => onDirtyChange?.(Boolean(startPending || cancelPending)), [cancelPending, onDirtyChange, startPending])
  useEffect(() => onBusyChange?.(busy), [busy, onBusyChange])
  useEffect(() => () => { onDirtyChange?.(false); onBusyChange?.(false) }, [onBusyChange, onDirtyChange])

  useEffect(() => {
    abort.current?.abort(); lock.current = false; setBusy(false); setPreview(null); setFrozen(null); setOperation(null); setStartPending(null); setCancelPending(null); setError(null); delivered.current = null
    if (!open) return
    let raw: string | null
    try { raw = localStorage.getItem(storageKey(storageScopeKey)) } catch (cause) { setError(message(cause)); return }
    if (!raw) return
    let saved: Stored
    try { saved = JSON.parse(raw) as Stored } catch { saved = { key: raw } }
    const ticket = epoch
    if (saved.cancel) setCancelPending({ key: saved.key, ...saved.cancel, retry: false }); else setStartPending({ key: saved.key, request: saved.request, retry: false })
    const lookup = saved.cancel ? api.lookupCancel(saved.key, current(ticket)).then(() => api.lookup(saved.cancel!.originalKey, current(ticket))) : api.lookup(saved.key, current(ticket))
    void lookup.then(value => { if (current(ticket)() && value) { setStartPending(null); setCancelPending(null); setOperation(value) } }).catch(cause => { if (!current(ticket)()) return; if (cause instanceof DataCommandNotAccepted) { if (saved.cancel) setCancelPending({ key: saved.key, ...saved.cancel, retry: true }); else setStartPending({ key: saved.key, request: saved.request, retry: true }) }; setError(message(cause)) })
  }, [api, epoch, open, storageScopeKey])
  useEffect(() => {
    if (!open || !operation || terminal(operation)) return
    const ticket = epoch, timer = setTimeout(() => { void api.lookup(operation.idempotencyKey, current(ticket)).then(value => { if (current(ticket)() && value) setOperation(value) }).catch(cause => { if (current(ticket)()) setError(message(cause)) }) }, 500)
    return () => clearTimeout(timer)
  }, [api, epoch, open, operation])
  useEffect(() => {
    if (!operation || operation.status !== 'succeeded' || delivered.current === operation.operationId || !onCompleted) return
    delivered.current = operation.operationId; try { localStorage.removeItem(storageKey(storageScopeKey)) } catch { /* result delivery is authoritative */ }; setStartPending(null); setCancelPending(null); onCompleted(operation)
  }, [onCompleted, operation, storageScopeKey])

  const inspect = async () => {
    if (lock.current || !allowed() || selectedTargets.length === 0 || selectedTargets.length > 1000 || startPending) return
    const ticket = epoch, controller = new AbortController(), body = structuredClone(request); abort.current?.abort(); abort.current = controller; lock.current = true; setBusy(true); setError(null)
    try { const value = await api.preview(body, controller.signal); if (current(ticket)()) { setFrozen(body); setPreview(value) } } catch (cause) { if (current(ticket)() && !controller.signal.aborted) setError(message(cause)) } finally { if (current(ticket)()) { lock.current = false; setBusy(false) } }
  }
  const start = async () => {
    const body = startPending?.request ?? frozen; if (!body || lock.current || !allowed() || startPending && !startPending.retry) return
    const ticket = epoch, key = startPending?.key ?? crypto.randomUUID(); lock.current = true; setBusy(true); setError(null)
    let persisted = false
    try { persist({ key, request: body }); persisted = true; setStartPending({ key, request: body, retry: false }); const value = await api.start(structuredClone(body), key, current(ticket)); if (current(ticket)()) { setStartPending(null); setOperation(value) } }
    catch (cause) { if (current(ticket)()) { if (!persisted || !(cause instanceof DataCommandUncertain || cause instanceof DataCommandNotAccepted)) { if (persisted) try { localStorage.removeItem(storageKey(storageScopeKey)) } catch { /* the original error is more useful */ }; setStartPending(null) } else setStartPending({ key, request: body, retry: cause instanceof DataCommandNotAccepted }); setError(message(cause)) } }
    finally { if (current(ticket)()) { lock.current = false; setBusy(false) } }
  }
  const recoverStart = async () => {
    if (!startPending || lock.current) return; const ticket = epoch; lock.current = true; setBusy(true); setError(null)
    try { const value = await api.lookup(startPending.key, current(ticket)); if (current(ticket)()) { setStartPending(null); setOperation(value) } } catch (cause) { if (current(ticket)()) { setStartPending({ ...startPending, retry: cause instanceof DataCommandNotAccepted }); setError(message(cause)) } } finally { if (current(ticket)()) { lock.current = false; setBusy(false) } }
  }
  const refresh = async () => {
    if (!operation || lock.current) return; const ticket = epoch; lock.current = true; setBusy(true); setError(null)
    try { const value = await api.lookup(operation.idempotencyKey, current(ticket)); if (current(ticket)()) setOperation(value) } catch (cause) { if (current(ticket)()) setError(message(cause)) } finally { if (current(ticket)()) { lock.current = false; setBusy(false) } }
  }
  const stop = async () => {
    if ((!operation && !cancelPending) || lock.current || !allowed() || operation && terminal(operation)) return
    const operationId = cancelPending?.operationId ?? operation!.operationId, expectedRevision = cancelPending?.expectedRevision ?? operation!.statusRevision, originalKey = cancelPending?.originalKey ?? operation!.idempotencyKey, key = cancelPending?.key ?? crypto.randomUUID(), ticket = epoch
    lock.current = true; setBusy(true); setError(null)
    let persisted = false
    try { persist({ key, cancel: { operationId, expectedRevision, originalKey } }); persisted = true; setCancelPending({ key, operationId, expectedRevision, originalKey, retry: false }); await api.cancel(operationId, expectedRevision, key, current(ticket)); const value = await api.lookup(originalKey, current(ticket)); if (current(ticket)()) { setCancelPending(null); setOperation(value) } }
    catch (cause) { if (current(ticket)()) { if (!persisted) setCancelPending(null); else if (cause instanceof DataCommandUncertain || cause instanceof DataCommandNotAccepted) setCancelPending({ key, operationId, expectedRevision, originalKey, retry: cause instanceof DataCommandNotAccepted }); else { try { persist({ key: originalKey }); setCancelPending(null) } catch (storageCause) { setCancelPending({ key, operationId, expectedRevision, originalKey, retry: false }); setError(message(storageCause)); return } }; setError(message(cause)) } }
    finally { if (current(ticket)()) { lock.current = false; setBusy(false) } }
  }
  const recoverCancel = async () => {
    if (!cancelPending || lock.current) return; const ticket = epoch; lock.current = true; setBusy(true); setError(null)
    try { await api.lookupCancel(cancelPending.key, current(ticket)); const value = await api.lookup(cancelPending.originalKey, current(ticket)); if (current(ticket)()) { setCancelPending(null); setOperation(value) } } catch (cause) { if (current(ticket)()) { setCancelPending({ ...cancelPending, retry: cause instanceof DataCommandNotAccepted }); setError(message(cause)) } } finally { if (current(ticket)()) { lock.current = false; setBusy(false) } }
  }
  const startNew = () => { if (!operation || !terminal(operation)) return; try { localStorage.removeItem(storageKey(storageScopeKey)) } catch (cause) { setError(message(cause)); return }; setOperation(null); setStartPending(null); setCancelPending(null); setPreview(null); setFrozen(null); setError(null) }
  const blockers = preview?.blocks.flatMap(block => block.blockers) ?? [], writeBlocked = Boolean(disabled || readonly)
  return <Dialog open={open} onOpenChange={next => { if (!next) onClose() }}><DialogContent busy={busy}><DialogTitle>批量设置业务状态</DialogTitle><DialogDescription>已选择 {selectedTargets.length} 条记录，提交后按每块 100 条处理。</DialogDescription>
    {operation ? <DataOperationStatus operation={operation} error={error ?? (operation.error && typeof operation.error.message === 'string' ? operation.error.message : null)} busy={busy} onRefresh={refresh}>
      {operation.result && 'blocks' in operation.result ? <ul>{operation.result.blocks.flatMap(block => block.blockers).map((item, index) => <li key={index}>{item.message}</li>)}</ul> : null}
      {terminal(operation) ? operation.status === 'failed' ? <Button onClick={startNew}>开始新的批量操作</Button> : null : cancelPending ? <Button disabled={busy || (cancelPending.retry && writeBlocked)} onClick={() => void (cancelPending.retry ? stop() : recoverCancel())}>{cancelPending.retry ? '按原键重试停止' : '核对停止结果'}</Button> : <AlertDialog><AlertDialogTrigger asChild><Button disabled={writeBlocked}>停止后续处理</Button></AlertDialogTrigger><AlertDialogContent><AlertDialogTitle>停止后续处理？</AlertDialogTitle><AlertDialogDescription>已经提交的修改不会回滚，只关闭尚未开始的块。</AlertDialogDescription><div className="flex gap-2"><AlertDialogCancel asChild><Button variant="ghost">返回</Button></AlertDialogCancel><AlertDialogAction asChild><Button disabled={writeBlocked} onClick={() => void stop()}>确认停止</Button></AlertDialogAction></div></AlertDialogContent></AlertDialog>}
    </DataOperationStatus> : <><Select aria-label="目标状态" value={statusId} placeholder="清空状态" options={statuses.map(item => ({ value: item.statusId, label: item.name }))} onValueChange={value => { setStatusId(value); setPreview(null); setFrozen(null) }} disabled={disabled} readOnly={readonly} />
      {preview ? <section><p>预检完成，共 {frozen?.targets.length ?? 0} 条</p>{blockers.map((item, index) => <p role="alert" key={index}>{item.message}</p>)}</section> : null}{selectedTargets.length > 1000 ? <p role="alert">一次最多处理 1000 条记录，请缩小选择范围。</p> : null}{error ? <p role="alert">{error}</p> : null}
      <div className="flex gap-2"><Button variant="ghost" onClick={onClose}>关闭</Button><Button onClick={inspect} disabled={busy || writeBlocked || selectedTargets.length === 0 || selectedTargets.length > 1000 || Boolean(startPending)}>预检批量状态</Button>{preview && !startPending ? <Button onClick={() => void start()} disabled={busy || writeBlocked}>确认开始</Button> : null}{startPending ? <Button onClick={() => void (startPending.retry ? start() : recoverStart())} disabled={busy || (startPending.retry && writeBlocked)}>{startPending.retry ? '按原键重试' : '核对原操作'}</Button> : null}</div>
    </>}
  </DialogContent></Dialog>
}
