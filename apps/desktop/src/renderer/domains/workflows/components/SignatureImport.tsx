import { useState } from 'react'
import type { components } from '../../../shared/api/generated'
import { apiRequest } from '../api'
import { getStudioOpenContext } from '../api/config'
import { importCandidates, type ImportCandidate } from '../lib/signatureKeys'
import { Button } from './controls/button'
import { SIGNATURE_TYPE_LABELS } from './signatureTypes'

type Schema = components['schemas']
export interface ImportGroup { key: string; name: string; fieldKeys: string[] }
export type ImportTarget = { groupKey: string } | { newName: string }
const NEW_GROUP = '__new__'
const root = (projectId: string) => `/v1/projects/${encodeURIComponent(projectId)}`

/** Pick fields from a project data table to turn into flow inputs; only offered inside a project. */
export function SignatureImport({ groups, disabled, onApply }: { groups: ImportGroup[]; disabled: boolean; onApply(target: ImportTarget, items: ImportCandidate[]): void }) {
  const projectId = getStudioOpenContext().projectId
  const [open, setOpen] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState('')
  const [tables, setTables] = useState<Schema['DataTableView'][]>([]), [tableId, setTableId] = useState('')
  const [fields, setFields] = useState<Schema['DataFieldView'][] | null>(null)
  const [target, setTarget] = useState(groups[0]?.key ?? NEW_GROUP), [picked, setPicked] = useState<Set<string>>(new Set())
  if (!projectId) return null
  const table = tables.find(item => item.tableId === tableId)
  const existing = target === NEW_GROUP ? [] : groups.find(group => group.key === target)?.fieldKeys ?? []
  const candidates = fields ? importCandidates(fields, existing) : []
  const fail = (what: string, cause: unknown) => setError(`${what}：${cause instanceof Error ? cause.message : String(cause)}。请检查项目是否可访问后重试。`)

  const start = async () => {
    setOpen(true); setError(''); setBusy(true)
    try {
      const result = await apiRequest<Schema['DataTablePage']>(`${root(projectId)}/tables?pageSize=100&page=1`)
      if (!result.success || !result.data) throw new Error(result.error || '服务没有返回数据表')
      setTables(result.data.items)
    } catch (cause) { fail('读取数据表失败', cause) } finally { setBusy(false) }
  }
  const choose = async (id: string) => {
    setTableId(id); setFields(null); setPicked(new Set()); setError('')
    if (!id) return
    setBusy(true)
    try {
      const result = await apiRequest<Schema['DataFieldDirectory']>(`${root(projectId)}/tables/${encodeURIComponent(id)}/fields`)
      if (!result.success || !result.data) throw new Error(result.error || '服务没有返回字段')
      setFields(result.data.items)
      setPicked(new Set(result.data.items.map(field => field.key)))
    } catch (cause) { fail('读取数据表字段失败', cause) } finally { setBusy(false) }
  }
  const apply = () => {
    const chosen = candidates.filter((item, index) => !item.exists && picked.has(fields![index].key))
    if (!chosen.length) return
    onApply(target === NEW_GROUP ? { newName: table?.name ?? '新分组' } : { groupKey: target }, chosen)
    setOpen(false); setFields(null); setTableId(''); setPicked(new Set())
  }
  if (!open) return <Button size="sm" variant="outline" disabled={disabled} onClick={() => void start()}>从数据表导入</Button>
  const select = 'h-8 w-full rounded-control border bg-[hsl(var(--card))] px-2 text-[13px]'
  return <section aria-label="从数据表导入" className="space-y-3 rounded-control border p-3">
    <div className="flex items-center justify-between"><strong className="text-[13px]">从数据表导入</strong><Button size="sm" variant="ghost" onClick={() => setOpen(false)}>收起</Button></div>
    {error && <p role="alert" className="text-xs text-danger">{error}</p>}
    <div className="grid grid-cols-2 gap-3">
      <label className="space-y-1 text-xs font-medium">数据表<select className={select} value={tableId} disabled={busy} onChange={event => void choose(event.target.value)}><option value="">请选择数据表</option>{tables.map(item => <option key={item.tableId} value={item.tableId}>{item.name}</option>)}</select></label>
      <label className="space-y-1 text-xs font-medium">导入到分组<select className={select} value={target} onChange={event => setTarget(event.target.value)}>{groups.map(group => <option key={group.key} value={group.key}>{group.name}</option>)}<option value={NEW_GROUP}>新建分组（用数据表名称）</option></select></label>
    </div>
    {busy && <p role="status" className="text-xs text-muted-foreground">正在读取…</p>}
    {fields && (candidates.length ? <ul aria-label="可导入的字段" className="space-y-1">{candidates.map((item, index) => {
      const source = fields[index]
      return <li key={source.key}><label className="flex items-center gap-2 text-[13px]"><input type="checkbox" disabled={item.exists} checked={!item.exists && picked.has(source.key)} onChange={event => setPicked(current => { const next = new Set(current); if (event.target.checked) next.add(source.key); else next.delete(source.key); return next })} />
        <span>{item.name}</span><span className="text-xs text-muted-foreground">{SIGNATURE_TYPE_LABELS[item.type] ?? item.type}{item.required ? ' · 必填' : ''}{item.exists ? ' · 已存在，不重复导入' : ''}</span></label></li>
    })}</ul> : <p className="text-xs text-muted-foreground">这张数据表还没有字段。</p>)}
    <div className="flex justify-end"><Button size="sm" disabled={!fields || !candidates.some((item, index) => !item.exists && picked.has(fields[index].key))} onClick={apply}>导入所选字段</Button></div>
  </section>
}
