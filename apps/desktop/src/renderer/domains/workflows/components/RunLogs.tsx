import { useEffect, useRef, useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import type { WorkflowRunApi } from '../run-api'
import type { RunEvent, RunRead } from '../run-types'

export function RunLogs({ run, api, connected, sameDocument, onLocate }: { run: RunRead; api: WorkflowRunApi; connected: boolean; sameDocument: boolean; onLocate(id: string): void }) {
  const [filters, setFilters] = useState({ q: '', level: '', nodeId: '', executionId: '' })
  const [items, setItems] = useState<RunEvent[]>([])
  const [cursor, setCursor] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [follow, setFollow] = useState(true)
  const generation = useRef(0)
  useEffect(() => {
    generation.current++; setCursor(null); setError('')
    if (!connected) return
    let alive = true
    const timer = window.setTimeout(() => void api.logs(run.runId, filters, 0, follow).then(page => { if (alive) { setItems(page.items); setCursor(page.hasMore ? page.nextSeq : null) } }).catch(e => { if (alive) setError(String(e)) }), 200)
    return () => { generation.current++; alive = false; window.clearTimeout(timer) }
  }, [api, connected, filters, run.runId, follow, follow ? run.latestSeq : 0])
  const more = async () => {
    if (cursor === null || busy) return
    setBusy(true)
    const current = generation.current
    try { const page = await api.logs(run.runId, filters, cursor); if (generation.current !== current) return; setItems(previous => [...previous, ...page.items].slice(-400)); setCursor(page.hasMore ? page.nextSeq : null) }
    catch (e) { if (generation.current === current) setError(String(e)) } finally { setBusy(false) }
  }
  const download = async (kind: 'logs' | 'results' | 'diagnostics') => {
    setBusy(true)
    try { if (window.autoflow?.exportWorkflow) { const context = await window.autoflow.getRuntimeContext(); await window.autoflow.exportWorkflow({ workspaceKey: context.workspaceKey, runId: run.runId, kind, throughSeq: run.latestSeq, filters }); return } const blob = await api.export(run.runId, kind, run.latestSeq, filters); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = `${run.runId}-${kind}.${kind === 'results' ? 'zip' : kind === 'logs' ? 'jsonl' : 'json'}`; link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000) }
    catch (e) { setError(String(e)) } finally { setBusy(false) }
  }
  return <div className="space-y-2" aria-label="运行日志筛选与导出"><div className="flex flex-wrap gap-2"><Input aria-label="日志关键词" placeholder="搜索全部持久化日志" value={filters.q} onChange={e => setFilters({ ...filters, q: e.target.value })} /><Select aria-label="日志级别" value={filters.level} onChange={e => setFilters({ ...filters, level: e.target.value })}><option value="">全部级别</option><option value="info">信息</option><option value="warning">警告</option><option value="error">错误</option></Select><Select aria-label="日志节点" value={filters.nodeId} onChange={e => setFilters({ ...filters, nodeId: e.target.value })}><option value="">全部节点</option>{run.document.nodes.map(node => <option key={node.id} value={node.id}>{node.label || node.type}</option>)}</Select><Input aria-label="日志执行标识" value={filters.executionId} placeholder="executionId" onChange={e => setFilters({ ...filters, executionId: e.target.value })} /><label><input type="checkbox" checked={follow} onChange={e => setFollow(e.target.checked)} />跟随最新（取消后从首条分页查看）</label>{(['logs', 'results', 'diagnostics'] as const).map(kind => <Button key={kind} disabled={busy || !connected} onClick={() => void download(kind)}>{{ logs: '导出筛选日志', results: '导出结果 ZIP', diagnostics: '导出变量诊断' }[kind]}</Button>)}</div>
    {error ? <p role="alert">{error}</p> : null}<ol className="space-y-1 font-mono text-xs">{items.map(item => <li key={item.seq} className={item.level === 'error' ? 'text-red-700' : 'text-muted'}><time>{new Date(item.timestamp).toLocaleTimeString()}</time> · {item.level} · {item.nodeId ? <button disabled={!sameDocument} className="text-clay underline disabled:no-underline" onClick={() => onLocate(item.nodeId!)}>{run.document.nodes.find(n => n.id === item.nodeId)?.label || item.nodeId}</button> : null} {item.loopPath?.map(p => `[${p.loopNodeId} 第 ${p.iteration} 轮]`).join(' ')} {item.message} {item.durationMs != null ? `· ${item.durationMs} ms` : ''}</li>)}</ol>{cursor !== null ? <Button disabled={busy} onClick={() => void more()}>下一页日志</Button> : null}
  </div>
}
