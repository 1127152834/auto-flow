import { useWorkflowStore } from '../editor-store'
import { runProjectOnce, hasPendingProjectRun } from '../run-project-once'
import { useEffect, useRef, useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '../../../shared/components/ui/dialog'
import { inputReference, useProjectInputs, type DebugInputs, type DebugSelection, type InputObject } from '../project-inputs'

type View = 'definition' | 'debug' | 'task'
const text = (value: unknown) => value === undefined ? '未提供' : value === null ? '空值' : typeof value === 'object' ? JSON.stringify(value) : String(value)
const types: Record<string, string> = { string: '文本', number: '数字', boolean: '布尔', date: '日期' }
export function ProjectInputPanel() {
  const { automation, fields, tables, statuses, debug, task, taskDefinition, busy, error, notice, preview, choose } = useProjectInputs()
  const running = useWorkflowStore(state => state.executionStatus === 'running')
  const [view, setView] = useState<View>('definition'), [selected, setSelected] = useState<string | null>(null)
  const [picker, setPicker] = useState(false), [copyError, setCopyError] = useState('')
  if (!automation) return <div className="p-5 text-sm" role="status">{error || (busy ? '正在读取自动化输入…' : '从项目自动化打开工作流，即可查看项目输入。')}{error && <Button size="sm" onClick={() => void useProjectInputs.getState().load().catch(() => {})}>重新读取输入定义</Button>}</div>
  const definition = view === 'task' ? taskDefinition ?? { inputPlan: { inputs: [] }, parameterSchema: [] } : automation
  const inputId = selected ?? definition.inputPlan.inputs[0]?.inputId ?? 'parameters'
  const input = definition.inputPlan.inputs.find(item => item.inputId === inputId)
  const snapshots = (view === 'task' ? task?.inputSnapshot.inputs : debug?.inputs) as InputObject[] | undefined
  const object = snapshots?.find(item => item.inputId === inputId)
  const parameters = view === 'task' ? task?.inputSnapshot.parameters : Object.fromEntries(automation.parameterSchema.map(parameter => [parameter.parameterId, parameter.defaultValue]))
  const copy = (reference: string) => { void navigator.clipboard.writeText(`{${reference}}`).then(() => setCopyError('字段引用已复制'), () => setCopyError('无法访问剪贴板，请从节点变量选择器插入')) }
  return <section aria-label="项目数据" className="flex h-full min-h-0 flex-col overflow-auto p-4 text-sm">
    <header className="mb-4 flex flex-wrap items-center justify-between gap-3"><div><strong>项目数据 · {automation.name}</strong><p className="mb-0 text-xs text-muted">{view === 'task' ? task ? `本次任务 #${task.task.taskOrdinal} · ${task.task.status}` : '尚未执行任务' : '输入与参数由当前自动化配置'}</p></div><div className="flex gap-2"><Button size="sm" disabled={busy || running || hasPendingProjectRun()} onClick={() => void useProjectInputs.getState().load().catch(() => {})}>刷新输入定义</Button>{([['definition', '输入定义'], ['debug', '调试输入'], ['task', '本次任务']] as const).map(([id, title]) => <Button size="sm" key={id} aria-pressed={view === id} onClick={() => { setView(id); if (id === 'debug' && !debug && !busy) void preview() }}>{title}</Button>)}</div></header>
    {error && <div role="alert" className="text-danger">{error}{hasPendingProjectRun() && <Button size="sm" onClick={() => void runProjectOnce().catch(() => {})}>核验本次运行</Button>}</div>}
    {notice && <p role="status">{notice}</p>}
    {copyError && <p role="status">{copyError}</p>}
    <div className="grid min-h-56 flex-1 grid-cols-[12rem_minmax(0,1fr)] rounded-control border border-line">
      <nav aria-label="输入对象" className="border-r border-line p-3"><p className="text-xs text-muted">输入对象</p>{definition.inputPlan.inputs.map(item => <button type="button" key={item.inputId} aria-pressed={inputId === item.inputId} onClick={() => setSelected(item.inputId)} className={`mb-1 block w-full rounded-control p-3 text-left ${inputId === item.inputId ? 'bg-clay-soft text-clay' : ''}`}>{item.alias}<small className="ml-2 text-muted">{item.required ? '必需' : '可选'}</small></button>)}<button type="button" className={`mt-3 w-full border-t border-line p-3 text-left ${!input ? 'bg-clay-soft text-clay' : ''}`} onClick={() => setSelected('parameters')}>固定参数</button></nav>
      <div className="min-w-0 p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3"><strong>{input?.alias ?? '固定参数'}</strong>{view === 'debug' && input && <div className="flex gap-2"><Button size="sm" disabled={busy || input.mode === 'fixedRecord'} onClick={() => setPicker(true)}>选择数据</Button>{!input.required && <Button size="sm" disabled={busy} onClick={() => void choose(inputId, null)}>本次不提供</Button>}</div>}</div>
        {input && <p className="text-xs text-muted">来源：{tables.find(table => table.tableId === input.tableId)?.name ?? "项目数据表"} · 条件：{conditionText(input.filter, fields, statuses)}</p>}
        {input && view !== 'definition' && <p className="text-xs text-muted">{object?.recordRef ? `记录：${object.recordRef.recordKey.value} · ${view === 'debug' ? '尚未领取' : '任务原始输入'}` : view === 'task' && !task ? '尚未执行任务' : '本次未提供'}{input.mode === 'fixedRecord' ? ' · 固定记录' : ''}</p>}
        <dl className="divide-y divide-line">{input ? input.fieldBindings.map(binding => {
          const field = fields.find(item => item.ref.fieldId === binding.fieldRef.fieldId)
          const value = object?.values?.find(cell => cell.fieldId === binding.fieldRef.fieldId)?.value
          return <div key={binding.inputFieldId} className="grid grid-cols-[minmax(8rem,1fr)_5rem_minmax(8rem,2fr)_auto] items-center gap-3 py-3"><dt>{binding.inputFieldAlias}</dt><dd className="text-xs text-muted">{types[field?.type ?? ''] ?? field?.type ?? '未知类型'}</dd><dd className="break-all">{view === 'definition' ? field?.name ?? '字段已失效' : /password|密码/i.test(binding.inputFieldAlias) && value != null ? '••••••••' : text(value)}</dd><dd><Button size="sm" variant="ghost" aria-label={`复制 ${binding.inputFieldAlias} 引用`} onClick={() => copy(inputReference(inputId, binding.inputFieldId))}>复制引用</Button></dd></div>
        }) : definition.parameterSchema.map(parameter => <div key={parameter.parameterId} className="grid grid-cols-[1fr_5rem_2fr_auto] items-center gap-3 py-3"><dt>{parameter.name}</dt><dd className="text-xs text-muted">{types[parameter.type]}</dd><dd>{text(parameters?.[parameter.parameterId])}</dd><dd><Button size="sm" variant="ghost" onClick={() => copy(`PROJECT_PARAMETERS['${parameter.parameterId}']`)}>复制引用</Button></dd></div>)}</dl>
        {input && <p className="mt-4 text-xs text-muted">{view === 'definition' ? `已映射 ${input.fieldBindings.length} 个字段；筛选、排序和来源在自动化「输入与参数」中维护。` : '原始输入保持不变；修改项目记录请使用数据节点。'}</p>}
        {view === 'task' && task && <details className="mt-4 rounded-control border border-line p-3"><summary>本任务写入记录 · {task.dataWrites?.length ?? 0}</summary>{task.dataWrites?.map((write, index) => <div key={index} className="border-t border-line py-2"><strong>{write.nodeName ?? write.nodeId ?? '数据操作'}</strong><p>{write.beforeSummary ?? write.previousStatus ?? ''} → {write.afterSummary ?? write.nextStatus ?? write.detail ?? ''}</p><span>{write.outcome === 'succeeded' ? '已保存' : write.outcome}</span></div>)}</details>}
        {view === 'debug' && <div className="mt-4 flex items-center gap-3"><Button size="sm" disabled={busy} onClick={() => void preview()}>重新选择默认数据</Button><span className="text-xs text-muted">{busy ? '正在读取…' : debug?.selectionStatus === 'ready' ? '完整输入组已就绪，运行时重新校验并领取' : '尚未取得完整输入组'}</span></div>}
      </div>
    </div>
    <p className="mb-0 mt-3 text-xs text-muted">真实单任务调试 · 修改会保存到项目数据</p>
    {input && <CandidatePicker key={inputId} open={picker} onOpenChange={setPicker} inputId={inputId} title={input.alias} onChoose={async value => { await choose(inputId, value); setPicker(false) }} />}
  </section>
}
function CandidatePicker({ open, onOpenChange, inputId, title, onChoose }: { open: boolean; onOpenChange(open: boolean): void; inputId: string; title: string; onChoose(value: DebugSelection[string]): Promise<void> }) {
  const [search, setSearch] = useState(''), [query, setQuery] = useState(''), [cursors, setCursors] = useState<(string | null)[]>([null]), [refresh, setRefresh] = useState(0)
  const [page, setPage] = useState<DebugInputs | null>(null), [error, setError] = useState(''), [busy, setBusy] = useState(false), [selected, setSelected] = useState<number | null>(null)
  const { automation, fields, statuses } = useProjectInputs()
  const input = automation?.inputPlan.inputs.find(item => item.inputId === inputId)
  const version = useRef(0), cursor = cursors[cursors.length - 1]
  useEffect(() => {
    const request = ++version.current
    if (!open) return
    setBusy(true); setError(''); setSelected(null); setPage(null)
    void useProjectInputs.getState().candidates(inputId, cursor, query).then(value => { if (version.current === request) { setPage(value); const current = useProjectInputs.getState().debug?.selection[inputId]; const index = value.items.findIndex(item => JSON.stringify(item.selection) === JSON.stringify(current)); setSelected(index >= 0 ? index : null) } }, failure => { if (version.current === request) setError(String(failure)) }).finally(() => { if (version.current === request) setBusy(false) })
    return () => { version.current++ }
  }, [open, inputId, cursor, query, refresh])
  return <Dialog open={open} onOpenChange={onOpenChange} busy={busy}><DialogContent className="w-[min(92vw,56rem)] max-w-4xl"><header><DialogTitle>选择{title}数据</DialogTitle><DialogDescription>仅显示符合自动化条件的候选；每次选择一条，运行时重新校验。</DialogDescription></header>
    {input && <p className="text-sm text-muted">条件：{conditionText(input.filter, fields, statuses)}</p>}
    <form className="flex gap-2" onSubmit={event => { event.preventDefault(); setCursors([null]); setQuery(search); setRefresh(value => value + 1) }}><input aria-label="搜索候选数据" className="min-w-0 flex-1 rounded-control border border-line px-3" value={search} onChange={event => setSearch(event.target.value)} /><Button type="submit" disabled={busy}>搜索</Button><Button disabled={busy} onClick={() => setRefresh(value => value + 1)}>刷新</Button></form>
    {error && <p role="alert">{error}</p>}{busy ? <p role="status">正在读取…</p> : <div className="max-h-80 overflow-auto"><table className="w-full text-left text-sm"><thead><tr><th>选择</th><th>记录</th><th>字段值</th><th>可选状态</th></tr></thead><tbody>{page?.items.map((raw, index) => { const item = raw as unknown as InputObject & { selectable: boolean; reason?: string; selection: DebugSelection[string] }; return <tr key={index} className="border-t border-line"><td className="p-3"><input type="radio" name="debug-record" aria-label={`选择记录 ${item.recordRef?.recordKey.value}`} disabled={!item.selectable} checked={selected === index} onChange={() => setSelected(index)} /></td><td>{item.recordRef?.recordKey.value}</td><td>{item.values?.map(cell => /password|密码/i.test(cell.fieldName) ? '••••••••' : text(cell.value)).join(' · ')}</td><td>{item.reason ?? '可选择'}</td></tr> })}</tbody></table>{!page?.items.length && <p>本页没有可展示的候选数据</p>}</div>}
    <footer className="flex justify-end gap-2"><Button disabled={busy || cursors.length === 1} onClick={() => setCursors(value => value.slice(0, -1))}>上一页</Button><Button disabled={busy || !page?.nextCursor} onClick={() => setCursors(value => [...value, page!.nextCursor])}>下一页</Button><Button onClick={() => onOpenChange(false)}>取消</Button><Button disabled={busy || selected === null} onClick={() => { if (selected === null || !page) return; setBusy(true); void onChoose(page.items[selected].selection as DebugSelection[string]).finally(() => setBusy(false)) }}>使用此条</Button></footer>
  </DialogContent></Dialog>
}

function conditionText(value: unknown, fields: ReturnType<typeof useProjectInputs.getState>['fields'], statuses: ReturnType<typeof useProjectInputs.getState>['statuses']): string {
  const filter = value as { type?: string; items?: unknown[]; item?: unknown; fieldId?: string; statusId?: string; operator?: string; value?: unknown }
  if (!filter || (filter.type === 'all' && !filter.items?.length)) return '全部记录'
  if (filter.type === 'all' || filter.type === 'any') return `(${filter.items?.map(item => conditionText(item, fields, statuses)).join(filter.type === 'all' ? ' 且 ' : ' 或 ')})`
  if (filter.type === 'not') return `不满足 ${conditionText(filter.item, fields, statuses)}`
  const operators: Record<string, string> = { eq: '=', neq: '≠', gt: '>', gte: '≥', lt: '<', lte: '≤', contains: '包含', startsWith: '开头为', isNull: '为空', isNotNull: '非空' }
  const name = filter.type === 'status' ? '业务状态' : fields.find(field => field.ref.fieldId === filter.fieldId)?.name ?? '字段已失效'
  const valueText = filter.operator === 'isNull' || filter.operator === 'isNotNull' ? '' : filter.type === 'status' ? statuses.find(status => status.statusId === filter.statusId)?.name ?? '状态已失效' : text(filter.value)
  return `${name} ${operators[filter.operator ?? ''] ?? ''} ${valueText}`
}
