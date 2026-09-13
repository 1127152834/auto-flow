import { useEffect, useRef, useState } from 'react'
import { DebugPanel } from './DebugPanel'
import { RunLogs } from './RunLogs'
import { ArtifactPanel } from './ArtifactPanel'
import { Button } from '../../../shared/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../../shared/components/ui/tabs'
import type { WorkflowRunApi } from '../run-api'
import { runStateLabel, type RunEvent, type RunRead, type RunSummary } from '../run-types'

type Props = {
  run: RunRead | null; events: RunEvent[]; history: RunSummary[]; nextOffset: number | null
  sameDocument: boolean; connected: boolean; message: string | null; api: WorkflowRunApi
  onDebugRefresh?(): void; onDebugStop?(): void
  onSelect(id: string): void; onLocate(id: string): void; onMore(): void
}

export function RunPanel({ run, events, history, nextOffset, sameDocument, connected, message, api, onSelect, onLocate, onMore, onDebugRefresh, onDebugStop }: Props) {
  const [logLimit, setLogLimit] = useState(200)
  const [tab, setTab] = useState('logs')
  const [collapsed, setCollapsed] = useState(false)
  const [follow, setFollow] = useState(true)
  const logs = useRef<HTMLDivElement>(null)
  const debugRunId = run?.mode === 'debug' ? run.runId : null
  useEffect(() => { if (debugRunId) setTab('debug') }, [debugRunId])
  useEffect(() => { if (follow && logs.current) logs.current.scrollTop = logs.current.scrollHeight }, [events.at(-1)?.seq, follow, collapsed, tab])
  const totalMs = run?.finishedAt ? Math.max(0, Date.parse(run.finishedAt) - Date.parse(run.startedAt)) : null
  const nodeName = (id: string) => { const node = run?.document.nodes.find(item => item.id === id); return node?.label || node?.type || id }
  return <section className={`flex shrink-0 flex-col border-t border-line bg-surface ${collapsed ? '' : tab === 'debug' ? 'h-[330px] min-h-[160px]' : 'h-[230px] min-h-[160px]'}`} aria-label="运行记录">
    <Tabs value={tab} onValueChange={setTab} className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center gap-4 px-4"><TabsList>{run?.mode === 'debug' ? <TabsTrigger value="debug">调试／变量</TabsTrigger> : null}<TabsTrigger value="logs">运行日志</TabsTrigger><TabsTrigger value="diagnostics">搜索／导出</TabsTrigger><TabsTrigger value="results">只读结果 {run?.artifactCount || ''}</TabsTrigger><TabsTrigger value="history">最近运行</TabsTrigger></TabsList>{run ? <span className="truncate text-xs text-muted">{run.name} · {runStateLabel[run.state]} · 已调度 {run.executionCount ?? run.completedNodeIds.length} 次 · {new Date(run.startedAt).toLocaleString()}{totalMs !== null ? ` · 总时长 ${(totalMs / 1000).toFixed(1)} 秒` : ''}</span> : null}{!collapsed && tab === 'logs' ? <label className="ml-auto flex shrink-0 items-center gap-1.5 text-xs text-muted"><input type="checkbox" checked={follow} onChange={event => setFollow(event.target.checked)} />跟随最新</label> : null}<Button variant="ghost" className="ml-auto h-8 shrink-0 text-xs" aria-expanded={!collapsed} onClick={() => setCollapsed(value => !value)}>{collapsed ? '展开运行记录' : '收起运行记录'}</Button></div>
      <div hidden={collapsed} className={collapsed ? 'hidden' : 'contents'}>
      {message ? <p role="alert" className="px-5 py-1 text-xs text-red-700">{message}</p> : null}
      {run && !sameDocument ? <p className="px-5 py-1 text-xs text-amber-800">画布与本次运行快照不同，已暂停节点标记和定位。撤销至相同内容后可恢复。</p> : null}
      <TabsContent value="logs" className="m-0 min-h-0 flex-1 overflow-hidden"><div ref={logs} aria-label="日志内容" onScroll={event => { const area = event.currentTarget; setFollow(area.scrollHeight - area.scrollTop - area.clientHeight <= 24) }} className="h-full overflow-auto px-5 py-2">
        {events.length > logLimit ? <Button variant="ghost" onClick={() => { setFollow(false); setLogLimit(n => n + 200) }}>显示更早日志（剩余 {events.length - logLimit} 条）</Button> : null}
        {!run ? <p className="py-5 text-sm text-muted">运行当前草稿后，真实执行日志会显示在这里。</p> : !events.length ? <p role="status" className="py-3 text-xs text-muted">{connected ? '正在读取运行日志…' : '连接中断，已保留本次运行；恢复后补读日志。'}</p> : <ol className="space-y-1.5 font-mono text-xs">{events.slice(-logLimit).map(event => <li key={`${event.runId}:${event.seq}`} className={`flex items-start gap-3 ${event.level === 'error' ? 'text-red-700' : event.level === 'warning' ? 'text-amber-800' : 'text-muted'}`}><time className="shrink-0">{new Date(event.timestamp).toLocaleTimeString()}</time><span className="shrink-0">{{ info: '信息', warning: '警告', error: '错误' }[event.level]}</span>{event.nodeId ? <button type="button" className="max-w-40 shrink-0 truncate text-clay underline decoration-dotted disabled:text-muted disabled:no-underline" disabled={!sameDocument} onClick={() => onLocate(event.nodeId!)} title={nodeName(event.nodeId)}>{nodeName(event.nodeId)}</button> : null}<span className="whitespace-pre-wrap break-all">{event.loopPath?.length ? `[${event.loopPath.map(p => `${nodeName(p.loopNodeId)} 第 ${p.iteration} 轮`).join(' / ')}] ` : ''}{event.branch ? `[${event.branch}] ` : ''}{event.message}{event.durationMs !== null ? ` · ${event.durationMs} ms` : ''}</span></li>)}</ol>}
        {run?.error ? <p role="alert" className="mt-2 text-xs text-red-700">{run.error.message}</p> : null}
      </div></TabsContent>
      <TabsContent value="debug" forceMount className="m-0 min-h-0 flex-1 overflow-auto data-[state=inactive]:hidden">{run?.mode === 'debug' ? <DebugPanel key={run.runId} run={run} api={api} connected={connected} refresh={onDebugRefresh ?? noop} stop={onDebugStop ?? noop} /> : null}</TabsContent>
      <TabsContent value="diagnostics" className="m-0 min-h-0 flex-1 overflow-auto px-5 py-2">{run ? <RunLogs run={run} api={api} connected={connected} sameDocument={sameDocument} onLocate={onLocate} /> : <p>暂无运行</p>}</TabsContent>
      <TabsContent value="results" className="m-0 min-h-0 flex-1 overflow-auto px-5 py-2">{run ? <ArtifactPanel key={run.runId} run={run} api={api} connected={connected} /> : <p className="py-5 text-sm text-muted">本次运行尚无提取数据或截图。</p>}</TabsContent>
      <TabsContent value="history" className="m-0 min-h-0 flex-1 overflow-auto px-5 py-2">{history.length ? <ul className="space-y-1">{history.map(item => <li key={item.runId}><button type="button" className="flex w-full items-center justify-between rounded-control px-3 py-2 text-left text-xs hover:bg-surface-hover disabled:opacity-50" disabled={!connected} aria-pressed={run?.runId === item.runId} onClick={() => { onSelect(item.runId); setTab('logs') }}><span>{item.name} · {item.profileName}</span><span>{runStateLabel[item.state]} · {new Date(item.startedAt).toLocaleString()}</span></button></li>)}</ul> : <p className="py-5 text-sm text-muted">当前工作区暂无运行记录。</p>}{nextOffset !== null ? <Button variant="ghost" disabled={!connected} onClick={onMore}>加载更早运行</Button> : null}</TabsContent>
      </div>
    </Tabs>
  </section>
}

function noop() {}
