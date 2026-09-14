import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { ProjectFileSelection } from '../../../../shared/project-files'
import type { components } from '../../../shared/api/generated'
import { Modal } from '../../../shared/components/Modal'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../../shared/components/ui/alert-dialog'
import { Button } from '../../../shared/components/ui/button'
import type { ExcelApi } from '../excel-api'
import { useExcelExport } from '../use-excel-export'
import { DataOperationStatus } from './DataOperationStatus'
import { ExcelExportDialog, type ExcelExportOptions } from './ExcelExportDialog'

type Table = components['schemas']['DataTableView']; type Field = components['schemas']['DataFieldView']; type Status = components['schemas']['DataStatusView']; type Operation = components['schemas']['ProjectOperationView']
export type ExcelExportWorkflowProps = {
  open: boolean; sessionKey: string; scopeKey: string; contextKey: string; table: Table; fields: Field[]; statuses: Status[]; api: ExcelApi
  files: { chooseOutput(filename: string): Promise<ProjectFileSelection | null> }; filter: string | null; orderBy: string | null
  /** Archived projects are readonly but remain exportable; disabled means the export capability is unavailable. */
  readonly?: boolean; disabled?: boolean
  onClose(): void; onCompleted(operation: Operation): void; onDirtyChange?(dirty: boolean): void; onBusyChange?(busy: boolean): void
}

export function ExcelExportWorkflow({ open, sessionKey, scopeKey, contextKey, table, fields, statuses, api, files, filter, orderBy, disabled, onClose, onCompleted, onDirtyChange, onBusyChange }: ExcelExportWorkflowProps) {
  const blocked = disabled, exporting = useExcelExport({ api, tableId: table.tableId, scopeKey, contextKey, active: open, disabled: blocked, onCompleted })
  const [scope, setScope] = useState<ExcelExportOptions['scope']>('all'), [fieldIds, setFieldIds] = useState<string[]>(() => fields.map(field => field.ref.fieldId)), [includeStatus, setIncludeStatus] = useState(true)
  const [choosing, setChoosing] = useState(false), [leave, setLeave] = useState(false), [pickerError, setPickerError] = useState<string | null>(null), epoch = useRef(0), lock = useRef(false)
  useLayoutEffect(() => { const ticket = ++epoch.current; lock.current = false; setChoosing(false); setPickerError(null); return () => { if (epoch.current === ticket) ++epoch.current; lock.current = false } }, [scopeKey, sessionKey, contextKey, open])
  useLayoutEffect(() => { setScope('all'); setFieldIds(fields.map(field => field.ref.fieldId)); setIncludeStatus(true); setLeave(false) }, [scopeKey, sessionKey])
  const unresolved = Boolean(exporting.pending && !exporting.operation), draftDirty = scope !== 'all' || includeStatus !== true || fieldIds.length !== fields.length || fieldIds.some(id => !fields.some(field => field.ref.fieldId === id)), guarded = draftDirty || unresolved
  useEffect(() => onDirtyChange?.(guarded), [guarded, onDirtyChange]); useEffect(() => onBusyChange?.(choosing || exporting.busy), [choosing, exporting.busy, onBusyChange]); useEffect(() => () => { onDirtyChange?.(false); onBusyChange?.(false) }, [onBusyChange, onDirtyChange])
  const requestClose = () => exporting.operation ? onClose() : guarded ? setLeave(true) : onClose()
  const choose = async (options: ExcelExportOptions) => {
    if (lock.current || blocked) return
    lock.current = true; setChoosing(true); setPickerError(null); const ticket = epoch.current
    try { const selection = await files.chooseOutput(`${table.name}.xlsx`); if (!selection || ticket !== epoch.current) return; await exporting.submit({ selectionToken: selection.selectionToken, datasetGeneration: table.datasetGeneration, scope: options.scope, filter: options.scope === 'filter' ? filter : null, orderBy: options.scope === 'filter' ? orderBy : null, fieldIds: [...options.fieldIds], includeStatus: options.includeStatus }) }
    catch (cause) { if (ticket === epoch.current) setPickerError(cause instanceof Error ? cause.message : '无法选择保存位置') }
    finally { if (ticket === epoch.current) { lock.current = false; setChoosing(false) } }
  }
  const content = !exporting.pending && !exporting.operation ? <ExcelExportDialog open={open} fields={fields} statuses={statuses} scope={scope} selectedFieldIds={fieldIds} includeStatus={includeStatus} busy={choosing} disabled={blocked} error={pickerError ?? exporting.error} onScopeChange={setScope} onSelectedFieldIdsChange={setFieldIds} onIncludeStatusChange={setIncludeStatus} onClose={requestClose} onChooseOutput={choose} /> : <Modal open={open} onOpenChange={next => { if (!next) requestClose() }} title="导出 Excel" closeDisabled={exporting.busy} footer={<Button onClick={requestClose}>关闭</Button>}>
    {exporting.operation ? <DataOperationStatus operation={exporting.operation} error={exporting.error} busy={exporting.busy} onRefresh={exporting.refresh} onReconcile={exporting.operation.status === 'reconciling' ? exporting.reconcile : undefined}>{exporting.operation.status === 'reconciling' ? <p>正在核验原保存目标，不会创建第二份导出。</p> : exporting.operation.status === 'failed' ? <Button onClick={exporting.reset}>修改后开始新的导出</Button> : null}</DataOperationStatus> : <section className="grid gap-3"><p>上次导出结果尚未确认，必须先查询原请求。</p>{exporting.error ? <p role="alert">{exporting.error}</p> : null}<Button disabled={exporting.busy} onClick={exporting.refresh}>核对原导出</Button>{exporting.phase === 'notAccepted' ? <Button variant="primary" disabled={exporting.busy || blocked} onClick={exporting.retry}>按原键重试导出</Button> : null}</section>}
  </Modal>
  return <>{content}<AlertDialog open={leave} onOpenChange={setLeave}><AlertDialogContent><AlertDialogTitle>{unresolved ? '导出结果尚未确认' : '放弃导出设置？'}</AlertDialogTitle><AlertDialogDescription>{unresolved ? '原请求会保留，重新打开后必须先核对，不能创建新的导出。' : '尚未提交的导出范围和列选择会丢失。'}</AlertDialogDescription><div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button>返回</Button></AlertDialogCancel><AlertDialogAction asChild><Button variant={unresolved ? 'secondary' : 'danger'} onClick={onClose}>{unresolved ? '离开视图' : '放弃设置'}</Button></AlertDialogAction></div></AlertDialogContent></AlertDialog></>
}
