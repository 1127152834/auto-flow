import { useEffect, useRef, useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../../shared/components/ui/tabs'
import type { WorkflowRunApi } from '../run-api'
import { runStateLabel, type RunArtifact, type RunEvent, type RunRead, type RunSummary } from '../run-types'

type Props = {
  run: RunRead | null; events: RunEvent[]; history: RunSummary[]; nextOffset: number | null
  sameDocument: boolean; connected: boolean; message: string | null; api: WorkflowRunApi
  onSelect(id: string): void; onLocate(id: string): void; onMore(): void
}

export function RunPanel({ run, events, history, nextOffset, sameDocument, connected, message, api, onSelect, onLocate, onMore }: Props) {
  const [tab, setTab] = useState('logs')
  const [collapsed, setCollapsed] = useState(false)
  const [follow, setFollow] = useState(true)
  const logs = useRef<HTMLDivElement>(null)
  useEffect(() => { if (follow && logs.current) logs.current.scrollTop = logs.current.scrollHeight }, [events.length, follow, collapsed, tab])
  const nodeName = (id: string) => { const node = run?.document.nodes.find(item => item.id === id); return node?.label || node?.type || id }
  return <section className={`flex shrink-0 flex-col border-t border-line bg-surface ${collapsed ? '' : 'h-[230px] min-h-[160px]'}`} aria-label="运行记录">
    <Tabs value={tab} onValueChange={setTab} className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center gap-4 px-4"><TabsList><TabsTrigger value="logs">运行日志</TabsTrigger><TabsTrigger value="results">只读结果 {run?.artifacts.length || ''}</TabsTrigger><TabsTrigger value="history">最近运行</TabsTrigger></TabsList>{run ? <span className="truncate text-xs text-muted">{run.name} · {runStateLabel[run.state]} · {new Date(run.startedAt).toLocaleString()}</span> : null}{!collapsed && tab === 'logs' ? <label className="ml-auto flex shrink-0 items-center gap-1.5 text-xs text-muted"><input type="checkbox" checked={follow} onChange={event => setFollow(event.target.checked)} />跟随最新</label> : null}<Button variant="ghost" className="ml-auto h-8 shrink-0 text-xs" aria-expanded={!collapsed} onClick={() => setCollapsed(value => !value)}>{collapsed ? '展开运行记录' : '收起运行记录'}</Button></div>
      {!collapsed ? <>
      {message ? <p role="alert" className="px-5 py-1 text-xs text-red-700">{message}</p> : null}
      {run && !sameDocument ? <p className="px-5 py-1 text-xs text-amber-800">画布与本次运行快照不同，已暂停节点标记和定位。撤销至相同内容后可恢复。</p> : null}
      <TabsContent value="logs" className="m-0 min-h-0 flex-1 overflow-hidden"><div ref={logs} aria-label="日志内容" onScroll={event => { const area = event.currentTarget; setFollow(area.scrollHeight - area.scrollTop - area.clientHeight <= 24) }} className="h-full overflow-auto px-5 py-2">
        {!run ? <p className="py-5 text-sm text-muted">运行当前草稿后，真实执行日志会显示在这里。</p> : !events.length ? <p role="status" className="py-3 text-xs text-muted">{connected ? '正在读取运行日志…' : '连接中断，已保留本次运行；恢复后补读日志。'}</p> : <ol className="space-y-1.5 font-mono text-xs">{events.map(event => <li key={`${event.runId}:${event.seq}`} className={`flex items-start gap-3 ${event.level === 'error' ? 'text-red-700' : event.level === 'warning' ? 'text-amber-800' : 'text-muted'}`}><time className="shrink-0">{new Date(event.timestamp).toLocaleTimeString()}</time><span className="shrink-0">{{ info: '信息', warning: '警告', error: '错误' }[event.level]}</span>{event.nodeId ? <button type="button" className="max-w-40 shrink-0 truncate text-clay underline decoration-dotted disabled:text-muted disabled:no-underline" disabled={!sameDocument} onClick={() => onLocate(event.nodeId!)} title={nodeName(event.nodeId)}>{nodeName(event.nodeId)}</button> : null}<span className="whitespace-pre-wrap break-all">{event.message}{event.durationMs !== null ? ` · ${event.durationMs} ms` : ''}</span></li>)}</ol>}
        {run?.error ? <p role="alert" className="mt-2 text-xs text-red-700">{run.error.message}</p> : null}
      </div></TabsContent>
      <TabsContent value="results" className="m-0 min-h-0 flex-1 overflow-auto px-5 py-2">{run?.artifacts.length ? <div className="flex gap-4">{run.artifacts.map(artifact => <ArtifactResult key={`${run.runId}:${artifact.id}`} runId={run.runId} artifact={artifact} api={api} connected={connected} />)}</div> : <p className="py-5 text-sm text-muted">本次运行尚无提取数据或截图。</p>}</TabsContent>
      <TabsContent value="history" className="m-0 min-h-0 flex-1 overflow-auto px-5 py-2">{history.length ? <ul className="space-y-1">{history.map(item => <li key={item.runId}><button type="button" className="flex w-full items-center justify-between rounded-control px-3 py-2 text-left text-xs hover:bg-surface-hover disabled:opacity-50" disabled={!connected} aria-pressed={run?.runId === item.runId} onClick={() => { onSelect(item.runId); setTab('logs') }}><span>{item.name} · {item.profileName}</span><span>{runStateLabel[item.state]} · {new Date(item.startedAt).toLocaleString()}</span></button></li>)}</ul> : <p className="py-5 text-sm text-muted">当前工作区暂无运行记录。</p>}{nextOffset !== null ? <Button variant="ghost" disabled={!connected} onClick={onMore}>加载更早运行</Button> : null}</TabsContent>
      </> : null}
    </Tabs>
  </section>
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
  return <article className="min-w-72 max-w-2xl flex-1 rounded-control border border-line p-3"><h3 className="text-xs font-semibold">{artifact.name}</h3><p className="mt-1 break-all text-[11px] text-muted">{artifact.outputPath || artifact.relativePath}</p><p className="mt-1 line-clamp-2 break-all text-xs text-muted">{artifact.preview}</p><Button className="mt-2 h-8 text-xs" disabled={!connected && !expanded} aria-expanded={expanded} onClick={() => { setResult({}); setExpanded(value => !value) }}>{expanded ? '收起结果' : artifact.kind === 'image' ? '查看截图' : '查看完整结果'}</Button>{expanded ? result.error ? <p role="alert" className="mt-2 text-xs text-red-700">{result.error}</p> : result.url ? <img src={result.url} alt={artifact.name} className="mt-2 max-h-48 max-w-full object-contain" /> : result.text !== undefined ? <pre tabIndex={0} aria-label={artifact.name} className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-all text-xs">{result.text}</pre> : <p role="status" className="mt-2 text-xs text-muted">{connected ? '正在读取产物…' : '恢复连接后读取产物'}</p> : null}</article>
}
