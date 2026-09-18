import { useLayoutEffect, useState } from 'react'
import type { components } from '../../../shared/api/generated'
import { Modal } from '../../../shared/components/Modal'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableRow, TableScroll } from '../../../shared/components/ui/table'
import { safeProjectError } from '../../projects/presentation-error'
import type { SheetsApi, SheetsBinding, SheetsImpact, SheetsInspection } from '../sheets-api'
import { SheetsConnectionPanel } from './SheetsConnectionPanel'

type Field = components['schemas']['DataFieldView']
type MappingEntry = components['schemas']['SheetsMappingEntry']

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
export const columnLetter = (index: number): string => {
  let value = index, name = ''
  do { name = LETTERS[value % 26] + name; value = Math.floor(value / 26) - 1 } while (value >= 0)
  return name
}
const columnIndex = (letter: string) => letter.toUpperCase().split('').reduce((total, char) => total * 26 + (char.charCodeAt(0) - 64), 0) - 1

/** Accepts a pasted Sheets URL or a bare spreadsheet id, plus the gid in the URL fragment. */
export function parseSpreadsheetLink(value: string): { spreadsheetId: string; sheetId: number | null } {
  const text = value.trim()
  const match = text.match(/\/spreadsheets\/d\/([A-Za-z0-9_-]+)/)
  const gid = text.match(/[#&?]gid=(\d+)/)
  return { spreadsheetId: match ? match[1] : text, sheetId: gid ? Number(gid[1]) : null }
}

const seed = (fields: Field[], columns: string[]): MappingEntry[] => fields.slice(0, 200).map((field, index) => ({
  fieldId: field.ref.fieldId,
  columnId: columns[index] ?? columnLetter(index),
  direction: field.formula || !field.writable ? 'read' : 'both',
  formula: Boolean(field.formula),
}))

export type SheetsBindingWizardProps = {
  open: boolean
  api: SheetsApi
  scopeKey: string
  contextKey: string
  table: { tableId: string; name: string; tableRevision: number; datasetGeneration: string }
  fields: Field[]
  connectionId?: string | null
  readonly?: boolean
  disabled?: boolean
  onClose(): void
  onBound(binding: SheetsBinding): void
  onDirtyChange?(dirty: boolean): void
}

/** 选择文件 → 工作表 → 字段与身份映射 → 校验与影响 → 提交 → 结果, in the frozen contract's order. */
export function SheetsBindingWizard({ open, api, scopeKey, contextKey, table, fields, connectionId, readonly, disabled, onClose, onBound, onDirtyChange }: SheetsBindingWizardProps) {
  const blocked = Boolean(readonly || disabled)
  const [connection, setConnection] = useState<string | null>(connectionId ?? null)
  const [link, setLink] = useState(''), [sheetValue, setSheetValue] = useState('')
  const [mapping, setMapping] = useState<MappingEntry[] | null>(null)
  const [identityColumn, setIdentityColumn] = useState<string | null>(null)
  const [inspection, setInspection] = useState<SheetsInspection | null>(null)
  const [impacts, setImpacts] = useState<SheetsImpact[]>([])
  const [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null)

  useLayoutEffect(() => {
    if (!open) return
    setConnection(connectionId ?? null); setLink(''); setSheetValue(''); setMapping(null); setIdentityColumn(null); setInspection(null); setImpacts([]); setError(null)
  }, [open, contextKey, scopeKey, table.tableId, table.datasetGeneration, connectionId])

  const parsed = parseSpreadsheetLink(link)
  const sheetId = sheetValue.trim() === '' ? parsed.sheetId : Number(sheetValue.trim())
  const sheetIdValid = sheetId !== null && Number.isInteger(sheetId) && sheetId >= 0
  const target = { connectionId: connection ?? '', spreadsheetId: parsed.spreadsheetId, sheetId: sheetId ?? 0 }
  const ready = Boolean(connection && parsed.spreadsheetId && sheetIdValid)

  const draft = (): MappingEntry[] => mapping ?? seed(fields, inspection?.columns.map(column => column.columnId) ?? [])
  const options = inspection ? inspection.columns.map(column => ({ columnId: column.columnId, name: column.name })) : []

  const inspect = async () => {
    if (!ready || busy) return
    setBusy(true); setError(null)
    try {
      const entries = draft()
      const identity = identityColumn ?? entries.find(entry => fields.find(field => field.ref.fieldId === entry.fieldId)?.type === 'string')?.columnId ?? entries[0].columnId
      const outcome = await api.inspect(table.tableId, { ...target, identityStrategy: { kind: 'column', columnId: identity }, mapping: entries }, crypto.randomUUID(), () => true)
      if (outcome.operation.status === 'failed') { setError(safeProjectError(outcome.operation.error ?? new Error('来源检查失败'))); return }
      setMapping(entries); setIdentityColumn(identity)
      setInspection(outcome.inspection ?? (outcome.operation.result && 'inspection' in outcome.operation.result ? outcome.operation.result.inspection as SheetsInspection : null))
      onDirtyChange?.(true)
    } catch (cause) { setError(safeProjectError(cause)) } finally { setBusy(false) }
  }

  const bind = async (confirmed: boolean) => {
    if (!ready || busy || !inspection) return
    const entries = draft()
    if (!identityColumn) { setError('请指定用于识别记录身份的来源列。'); return }
    const change = {
      ...target,
      identityStrategy: { kind: 'column' as const, columnId: identityColumn },
      mapping: entries,
    }
    setBusy(true); setError(null)
    try {
      // The writer re-derives these facts inside its own transaction, so the
      // confirmation has to be issued right before the command is sent; a
      // stale one is refused instead of silently overwriting newer data.
      const report = await api.previewBinding(table.tableId, change)
      if (report.blockers.length > 0) {
        setImpacts([])
        setError(report.blockers.map(blocker => blocker.message).join(' '))
        return
      }
      if (report.impacts.length > 0 && !confirmed) {
        // 校验与影响：先让用户看到这次绑定会做什么，再提交。
        setImpacts(report.impacts)
        return
      }
      const operation = await api.putBinding(table.tableId, {
        ...change, impactRevision: report.impactRevision, expectedTableRevision: table.tableRevision,
      }, crypto.randomUUID(), () => true)
      if (operation.status === 'failed') { setError(safeProjectError(operation.error ?? new Error('绑定未建立'))); return }
      const result = operation.result
      // The frozen `changeSheetsBinding` result is the binding itself.
      if (!result || !('spreadsheetId' in result)) { setError('绑定结果暂时无法读取，请重新载入来源设置。'); return }
      setImpacts([])
      onDirtyChange?.(false)
      onBound(result)
    } catch (cause) { setError(safeProjectError(cause)) } finally { setBusy(false) }
  }

  const blocking = inspection ? inspection.issues.filter(issue => issue.code !== 'SHEETS_COLUMN_MISSING') : []

  return <Modal open={open} onOpenChange={next => { if (!next) onClose() }} title={`绑定 Google Sheets · ${table.name}`} description="本地表与一张工作表建立映射；来源文件不会被修改。" size="large" closeDisabled={busy}>
    <div className="grid gap-5">
      <SheetsConnectionPanel api={api} scopeKey={scopeKey} readonly={readonly} disabled={disabled} selectedId={connection} onSelect={setConnection} />
      <section className="grid gap-3" aria-label="选择工作表">
        <h4 className="text-lg font-semibold">选择工作表</h4>
        <label className="grid gap-1 text-sm"><span>Spreadsheet 链接或 ID</span><Input aria-label="Spreadsheet 链接" value={link} disabled={blocked || busy} placeholder="https://docs.google.com/spreadsheets/d/…" onChange={event => setLink(event.target.value)} /></label>
        <label className="grid max-w-56 gap-1 text-sm"><span>工作表 gid（链接里的 gid=）</span><Input aria-label="工作表 gid" value={sheetValue} disabled={blocked || busy} placeholder={parsed.sheetId === null ? '例如 0' : String(parsed.sheetId)} onChange={event => setSheetValue(event.target.value)} /></label>
        <div className="flex flex-wrap items-center gap-3">
          <Button size="sm" disabled={blocked || busy || !ready} onClick={() => void inspect()}>{inspection ? '按当前映射重新检查' : '读取工作表并检查'}</Button>
          {sheetIdValid ? <p className="m-0 text-sm text-muted">将检查 Spreadsheet <code className="break-all">{parsed.spreadsheetId || '—'}</code> 的工作表 {sheetId}</p> : null}
        </div>
      </section>
      {error ? <p role="alert" className="m-0 text-sm text-danger">{error}</p> : null}
      {inspection ? <>
        <section className="grid gap-3" aria-label="来源检查结果">
          <h4 className="text-lg font-semibold">来源检查</h4>
          <p className="m-0 text-sm">表头 {inspection.columns.length} 列；身份列 {inspection.identitySummary.unique ? '唯一' : '存在问题'}（缺失 {inspection.identitySummary.missing}，重复 {inspection.identitySummary.duplicates}）。</p>
          {inspection.issues.length > 0 ? <ul className="m-0 grid gap-1 pl-5 text-sm text-warning">{inspection.issues.map((issue, index) => <li key={`${issue.code}-${index}`}>{issue.message}</li>)}</ul> : <p className="m-0 text-sm text-success">没有发现问题。</p>}
          {inspection.overlaps.length > 0 ? <ul className="m-0 grid gap-1 pl-5 text-sm text-clay">{inspection.overlaps.map(overlap => <li key={overlap.tableId}>来源列 {overlap.columnIds.join('、')} 同时被另一张表（{overlap.tableId}）使用。</li>)}</ul> : null}
        </section>
        <section className="grid gap-3" aria-label="字段映射">
          <h4 className="text-lg font-semibold">字段与身份映射</h4>
          <label className="grid max-w-72 gap-1 text-sm"><span>身份列（必须映射到文本字段）</span>
            <select aria-label="身份列" className="h-9 rounded-control border border-line bg-surface px-2" value={identityColumn ?? ''} disabled={blocked} onChange={event => setIdentityColumn(event.target.value)}>
              <option value="">请选择</option>
              {draft().map(entry => <option key={entry.columnId} value={entry.columnId}>{entry.columnId} · {options.find(option => option.columnId === entry.columnId)?.name ?? '无表头'}</option>)}
            </select>
          </label>
          <TableScroll label="字段映射" className="rounded-control border border-line">
            <Table data-variant="compact" aria-label="字段映射">
              <TableHead><TableRow><TableCell>本地字段</TableCell><TableCell>来源列</TableCell><TableCell>方向</TableCell><TableCell>公式</TableCell></TableRow></TableHead>
              <TableBody>
                {draft().map(entry => {
                  const field = fields.find(item => item.ref.fieldId === entry.fieldId)
                  return <TableRow key={entry.fieldId}>
                    <TableCell className="font-medium">{field?.name ?? '字段已失效'}{field?.required ? <span className="ml-1 text-clay">必填</span> : null}</TableCell>
                    <TableCell>
                      <select aria-label={`${field?.name ?? entry.fieldId} 的来源列`} className="h-8 rounded-control border border-line bg-surface px-2" value={entry.columnId} disabled={blocked}
                        onChange={event => setMapping(draft().map(item => item.fieldId === entry.fieldId ? { ...item, columnId: event.target.value } : item))}>
                        {[...new Set([...options.map(option => option.columnId), entry.columnId])].sort((left, right) => columnIndex(left) - columnIndex(right)).map(value =>
                          <option key={value} value={value}>{value}{options.find(option => option.columnId === value) ? ` · ${options.find(option => option.columnId === value)!.name}` : ''}</option>)}
                      </select>
                    </TableCell>
                    <TableCell>
                      <select aria-label={`${field?.name ?? entry.fieldId} 的方向`} className="h-8 rounded-control border border-line bg-surface px-2" value={entry.direction} disabled={blocked}
                        onChange={event => setMapping(draft().map(item => item.fieldId === entry.fieldId ? { ...item, direction: event.target.value as MappingEntry['direction'] } : item))}>
                        <option value="both">双向</option><option value="read">只读来源</option><option value="write">只写来源</option>
                      </select>
                    </TableCell>
                    <TableCell>{entry.formula ? '公式列' : '普通值'}</TableCell>
                  </TableRow>
                })}
              </TableBody>
            </Table>
          </TableScroll>
          <p className="m-0 text-sm text-muted">身份列会保留 “001” 与 “1” 的区别，必须是文本字段。绑定后本地数据整体换代次，业务状态与记录关联不会继承。</p>
          {blocking.length > 0 ? <p role="alert" className="m-0 text-sm text-danger">还有 {blocking.length} 项检查未通过，修正映射后重新检查再绑定。</p> : null}
          {impacts.length > 0 ? <section className="grid gap-1 rounded-control border border-clay bg-surface p-3" aria-label="绑定影响">
            <h5 className="m-0 text-sm font-semibold">确认这次绑定会做什么</h5>
            <ul className="m-0 grid gap-1 pl-5 text-sm text-muted">{impacts.map((impact, index) => <li key={`${impact.code}-${index}`}>{impact.message}</li>)}</ul>
          </section> : null}
          <div className="flex flex-wrap gap-3">
            {impacts.length > 0
              ? <><Button variant="primary" disabled={blocked || busy} onClick={() => void bind(true)}>确认并绑定</Button>
                <Button disabled={busy} onClick={() => setImpacts([])}>返回修改</Button></>
              : <Button variant="primary" disabled={blocked || busy || blocking.length > 0 || !identityColumn} onClick={() => void bind(false)}>确认绑定</Button>}
            <Button disabled={busy} onClick={onClose}>取消</Button>
          </div>
        </section>
      </> : null}
    </div>
  </Modal>
}
