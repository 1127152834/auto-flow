import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { ProjectFileSelection } from '../../../../shared/project-files'
import type { components } from '../../../shared/api/generated'
import { Modal } from '../../../shared/components/Modal'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../../shared/components/ui/alert-dialog'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import type { ExcelApi, ExcelReplaceImpact } from '../excel-api'
import { useExcelImport } from '../use-excel-import'
import { useExcelInspection } from '../use-excel-inspection'
import { DataOperationStatus } from './DataOperationStatus'
import { ExcelImportMapping, createExcelImportMappingDraft, type ExcelImportMappingDraft } from './ExcelImportMapping'
import { ExcelInspectionPanel } from './ExcelInspectionPanel'

type Field = components['schemas']['DataFieldView']; type Table = components['schemas']['DataTableView']; type Operation = components['schemas']['ProjectOperationView']
type MappingResult = { mapping: components['schemas']['ExcelMapping'][]; identity: components['schemas']['SystemExcelIdentity'] | components['schemas']['ColumnExcelIdentity'] }
export type ExcelImportWizardProps = {
  open: boolean; mode: 'create' | 'replace'; sessionKey: string; scopeKey: string; contextKey: string; api: ExcelApi
  files: { chooseInput(): Promise<ProjectFileSelection | null> }; table?: Table; existingFields?: Field[]; readonly?: boolean; disabled?: boolean
  onClose(): void; onCompleted(operation: Operation): void; onDirtyChange?(dirty: boolean): void; onBusyChange?(busy: boolean): void
}

export function ExcelImportWizard({ open, mode, sessionKey, scopeKey, contextKey, api, files, table, existingFields = [], readonly, disabled, onClose, onCompleted, onDirtyChange, onBusyChange }: ExcelImportWizardProps) {
  const blocked = disabled || readonly, inspection = useExcelInspection({ api, chooseInput: files.chooseInput, scopeKey, contextKey, active: open, disabled: blocked })
  const importing = useExcelImport({ api, scopeKey, contextKey, active: open, disabled: blocked, onCompleted })
  const [sheetId, setSheetId] = useState<string | null>(null), [mapping, setMapping] = useState<ExcelImportMappingDraft | null>(null), [review, setReview] = useState(false)
  const [name, setName] = useState(''), [description, setDescription] = useState(''), [impact, setImpact] = useState<ExcelReplaceImpact | null>(null), [impactError, setImpactError] = useState<string | null>(null)
  const [dirtyClose, setDirtyClose] = useState(false), epoch = useRef(0), inspectionId = useRef<string | null>(null)
  useLayoutEffect(() => { epoch.current += 1; setImpact(null); setImpactError(null); if (mode === 'replace') setReview(false); return () => { epoch.current += 1 } }, [scopeKey, sessionKey, contextKey, open, mode, table?.datasetGeneration, table?.tableRevision])
  useLayoutEffect(() => { setSheetId(null); setMapping(null); setReview(false); setImpact(null); setImpactError(null); setName(''); setDescription(''); setDirtyClose(false); inspectionId.current = null }, [scopeKey, sessionKey])
  useEffect(() => { const next = inspection.inspection?.inspectionId; if (!next || next === inspectionId.current) return; inspectionId.current = next; setSheetId(null); setMapping(null); setReview(false) }, [inspection.inspection])
  const selected = inspection.inspection?.sheets.find(sheet => sheet.sheetId === sheetId) ?? null
  const unresolved = Boolean(importing.pending && !importing.operation), dirty = Boolean(mapping || name || description || unresolved)
  useEffect(() => onDirtyChange?.(dirty), [dirty, onDirtyChange])
  useEffect(() => onBusyChange?.(inspection.busy || importing.busy), [importing.busy, inspection.busy, onBusyChange])
  useEffect(() => () => { onDirtyChange?.(false); onBusyChange?.(false) }, [onBusyChange, onDirtyChange])
  const choose = inspection.choose
  const requestClose = () => importing.operation ? onClose() : dirty ? setDirtyClose(true) : onClose()
  const toReview = async (value: MappingResult) => {
    if (!inspection.inspection || !selected) return
    const ticket = ++epoch.current
    setImpact(null); setImpactError(null)
    setMapping({ columns: value.mapping, identity: value.identity }); setReview(true)
    if (mode === 'replace' && table) { try { const value = await api.replaceImpact(table.tableId); if (ticket === epoch.current) setImpact(value) } catch (cause) { if (ticket === epoch.current) setImpactError(cause instanceof Error ? cause.message : '无法评估替换影响') } }
  }
  const submit = () => {
    if (!inspection.inspection || !selected || !mapping) return
    const common = { inspectionId: inspection.inspection.inspectionId, fingerprint: inspection.inspection.fingerprint, sheetId: selected.sheetId, mapping: mapping.columns.filter((column): column is components['schemas']['ExcelMapping'] => column.target !== null), identity: mapping.identity }
    if (mode === 'create') void importing.submit({ mode, request: { ...common, name: name.trim(), description: description.trim() } })
    else if (table && impact) void importing.submit({ mode, tableId: table.tableId, request: { ...common, expectedDatasetGeneration: table.datasetGeneration, expectedTableRevision: table.tableRevision, impactRevision: impact.impactRevision } })
  }
  const footer = importing.operation || importing.pending ? undefined : <Button onClick={requestClose}>关闭</Button>
  return <><Modal open={open} onOpenChange={next => { if (!next) requestClose() }} title={mode === 'create' ? '从 Excel 新建数据表' : '用 Excel 替换数据表'} closeDisabled={inspection.busy || importing.busy} size="large" footer={footer}>
    {importing.operation ? <DataOperationStatus operation={importing.operation} error={importing.error} busy={importing.busy} onRefresh={importing.refresh}>{importing.operation.status === 'succeeded' && importing.operation.result && 'importedRecordCount' in importing.operation.result ? <><p>已导入 {importing.operation.result.importedRecordCount} 条记录。</p><Button onClick={onClose}>完成</Button></> : importing.operation.status === 'failed' ? <Button onClick={importing.reset}>修改后开始新的导入</Button> : null}</DataOperationStatus>
      : importing.pending ? <section className="grid gap-3"><p>已保存导入请求，正在核对原操作。</p>{importing.error ? <p role="alert">{importing.error}</p> : null}<Button disabled={importing.busy} onClick={importing.refresh}>核对导入结果</Button>{importing.phase === 'notAccepted' ? <Button variant="primary" disabled={importing.busy} onClick={() => void importing.submit(importing.pending!.body)}>按原键重试提交</Button> : null}</section>
        : !inspection.inspection ? <section className="grid gap-4"><ExcelInspectionPanel inspection={null} selectedSheetId={null} checking={inspection.busy} disabled={blocked} onChoose={choose} onSelectSheet={() => {}} onContinue={() => {}} />{inspection.phase === 'unknown' || inspection.phase === 'notAccepted' ? <><p>正在核对上次文件检查。</p><Button disabled={inspection.busy} onClick={inspection.refresh}>核对检查结果</Button>{inspection.phase === 'notAccepted' ? <Button variant="primary" disabled={blocked || inspection.busy} onClick={inspection.submit}>按原键重试检查</Button> : null}</> : inspection.selection ? <Button variant="primary" disabled={blocked || inspection.busy} onClick={inspection.submit}>检查文件</Button> : null}{inspection.operation ? <DataOperationStatus operation={inspection.operation} error={inspection.error} busy={inspection.busy} onRefresh={inspection.refresh} /> : inspection.error ? <p role="alert">{inspection.error}</p> : null}</section>
          : !mapping || !review ? <>{!mapping ? <ExcelInspectionPanel inspection={inspection.inspection} selectedSheetId={sheetId} disabled={blocked} onChoose={choose} onSelectSheet={value => { setSheetId(value); setMapping(null) }} onContinue={sheet => { setSheetId(sheet.sheetId); setMapping(createExcelImportMappingDraft(sheet)) }} /> : null}{selected && mapping ? <><ExcelImportMapping sheet={selected} mode={mode} existingFields={existingFields} value={mapping} disabled={blocked} onChange={setMapping} onContinue={toReview} /><Button onClick={() => { setMapping(null); setReview(false) }}>返回选择工作表</Button></> : null}</>
            : <section className="grid gap-4"><h3 className="font-medium">确认导入</h3>{mode === 'create' ? <><label className="grid gap-1">数据表名称<Input aria-label="数据表名称" value={name} onChange={event => setName(event.target.value)} disabled={blocked} /></label><label className="grid gap-1">描述<Input aria-label="数据表描述" value={description} onChange={event => setDescription(event.target.value)} disabled={blocked} /></label></> : <><p>将替换“{table?.name}”的全部记录。原业务状态和记录关联不会继承。</p>{impact ? <p>{impact.recordCount} 条原记录将被替换。</p> : <p role={impactError ? 'alert' : 'status'}>{impactError ?? '正在评估替换影响…'}</p>}{impact?.blockers.map(blocker => <p role="alert" key={blocker}>{blocker}</p>)}</>}<p>将导入 {selected?.rowCount ?? 0} 条记录，映射 {mapping.columns.filter(column => column.target).length} 列。</p>{importing.error ? <p role="alert">{importing.error}</p> : null}<Button variant="primary" disabled={blocked || (mode === 'create' ? !name.trim() : !impact || impact.blockers.length > 0)} onClick={submit}>确认并开始导入</Button><Button onClick={() => { epoch.current += 1; setImpact(null); setImpactError(null); setReview(false) }}>返回映射</Button></section>}
  </Modal><AlertDialog open={dirtyClose} onOpenChange={setDirtyClose}><AlertDialogContent><AlertDialogTitle>{unresolved ? '导入结果尚未确认' : '放弃未提交的导入草稿？'}</AlertDialogTitle><AlertDialogDescription>{unresolved ? '原请求身份会保留，重新打开后必须先核对该请求，不能创建新的导入。' : '字段映射和尚未提交的设置会丢失。'}</AlertDialogDescription><div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button>继续编辑</Button></AlertDialogCancel><AlertDialogAction asChild><Button variant={unresolved ? 'secondary' : 'danger'} onClick={onClose}>{unresolved ? '离开视图' : '放弃草稿'}</Button></AlertDialogAction></div></AlertDialogContent></AlertDialog></>
}
