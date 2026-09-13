import { useEffect, useRef, useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import type { WorkflowRunApi } from '../run-api'
import type { RunArtifact, RunRead } from '../run-types'

export function ArtifactPanel({ run, api, connected }: { run: RunRead; api: WorkflowRunApi; connected: boolean }) {
  const [nodeId, setNodeId] = useState('')
  const [executionId, setExecutionId] = useState('')
  const [items, setItems] = useState(run.artifacts)
  const [cursor, setCursor] = useState(run.nextArtifactCursor ?? null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const epoch = useRef(0)
  useEffect(() => {
    const current = ++epoch.current
    if (!connected) return
    setBusy(true)
    void api.artifacts(run.runId, 0, nodeId, executionId).then(page => {
      if (current !== epoch.current) return
      setItems(page.items); setCursor(page.nextCursor ?? null); setError('')
    }).catch(e => { if (current === epoch.current) setError(e instanceof Error ? e.message : '无法读取产物') }).finally(() => { if (current === epoch.current) setBusy(false) })
    return () => { epoch.current += 1 }
  }, [api, connected, executionId, nodeId, run.runId])
  // Live first-page updates do not discard pages the user already loaded.
  const visible = !nodeId && !executionId ? [...new Map([...run.artifacts, ...items].map(item => [item.id, item])).values()] : items
  const next = cursor ?? (!nodeId && !executionId && visible.length < run.artifactCount ? visible.at(-1)?.ordinal ?? 0 : null)
  const more = async () => {
    if (busy || next === null) return
    const current = epoch.current
    setBusy(true)
    try { const page = await api.artifacts(run.runId, next, nodeId, executionId); if (current === epoch.current) { setItems(previous => [...new Map([...previous, ...page.items].map(item => [item.id, item])).values()]); setCursor(page.nextCursor ?? null) } }
    catch (e) { if (current === epoch.current) setError(e instanceof Error ? e.message : '无法读取产物') }
    finally { if (current === epoch.current) setBusy(false) }
  }
  return <div className="space-y-2" aria-label="运行产物列表">
    <div className="flex items-center gap-2"><Select aria-label="按产物节点筛选" value={nodeId} onChange={event => setNodeId(event.target.value)}><option value="">全部节点</option>{run.document.nodes.filter(n => ['get_element_info', 'screenshot', 'android_screenshot'].includes(n.type)).map(n => <option key={n.id} value={n.id}>{n.label || n.type}</option>)}</Select><Input aria-label="按执行标识筛选" placeholder="executionId" value={executionId} onChange={event => setExecutionId(event.target.value)} /><span className="shrink-0 text-xs text-muted">共 {run.artifactCount} 项</span></div>
    {error ? <p role="alert">{error}</p> : null}
    <div className="flex flex-wrap gap-3">{visible.map(item => <ArtifactResult key={item.id} runId={run.runId} artifact={item} api={api} connected={connected} />)}</div>
    {!visible.length ? <p className="py-3 text-xs text-muted">{busy ? '正在读取产物…' : '暂无匹配产物'}</p> : null}
    {next !== null ? <Button disabled={busy || !connected} onClick={() => void more()}>加载更多产物</Button> : null}
  </div>
}

function ArtifactResult({ runId, artifact, api, connected }: { runId: string; artifact: RunArtifact; api: WorkflowRunApi; connected: boolean }) {
  const [result, setResult] = useState<{ url?: string; text?: string; error?: string }>({})
  const [expanded, setExpanded] = useState(false)
  useEffect(() => {
    if (!connected || !expanded) return
    const controller = new AbortController()
    let url: string | undefined
    void api.artifact(runId, artifact.id, controller.signal).then(async blob => {
      if (controller.signal.aborted) return
      if (artifact.kind === 'image') { url = URL.createObjectURL(blob); setResult({ url }) }
      else { const text = await blob.text(); if (!controller.signal.aborted) setResult({ text }) }
    }).catch(error => { if (!controller.signal.aborted) setResult({ error: error instanceof Error ? error.message : '产物读取失败' }) })
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url) }
  }, [api, artifact.id, artifact.kind, connected, expanded, runId])
  return <article className="min-w-72 max-w-2xl flex-1 rounded-control border border-line p-3"><h3 className="text-xs font-semibold">{artifact.name}</h3><p className="text-[11px] text-muted">{artifact.loopPath?.map(p => `第 ${p.iteration} 轮`).join(' / ') || '单次执行'} · {artifact.executionId ?? '历史记录'}</p><p className="mt-1 break-all text-[11px] text-muted">{artifact.outputPath || artifact.relativePath}</p><p className="mt-1 line-clamp-2 break-all text-xs text-muted">{artifact.preview}</p><Button className="mt-2 h-8 text-xs" disabled={!connected && !expanded} aria-expanded={expanded} onClick={() => { setResult({}); setExpanded(value => !value) }}>{expanded ? '收起结果' : artifact.kind === 'image' ? '查看截图' : '查看完整结果'}</Button>{expanded ? result.error ? <p role="alert" className="mt-2 text-xs text-red-700">{result.error}</p> : result.url ? <img src={result.url} alt={artifact.name} className="mt-2 max-h-48 max-w-full object-contain" /> : result.text !== undefined ? <pre tabIndex={0} aria-label={artifact.name} className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-all text-xs">{result.text}</pre> : <p role="status" className="mt-2 text-xs text-muted">{connected ? '正在读取产物…' : '恢复连接后读取产物'}</p> : null}</article>
}
