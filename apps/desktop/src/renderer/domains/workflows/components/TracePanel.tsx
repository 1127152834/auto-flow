import { useCallback, useEffect, useRef, useState } from 'react'
import { Activity, AlertTriangle, Download, Globe, ImageOff, RefreshCw, Sparkles, Terminal } from 'lucide-react'
import type { components } from '../../../shared/api/generated'
import { workflowApi } from '../api'
import { emitAssistantUiEvent } from '../api/aiAssistantSkills'
import { getStudioTransportRevision } from '../api/transport'
import { Button } from './controls/button'
import { SelectNative } from './controls/select-native'

type TracePage = components['schemas']['StudioTracePage']
type TraceEvent = components['schemas']['StudioTraceEvent']
const kinds = { '': '全部证据', execution: '节点动作', network: '网络请求', console: '控制台', exception: 'JS 异常', 'page-closed': '页面关闭', mark: '追踪标记', diagnostic: '诊断快照' }
const runStates: Record<string, string> = { starting: '正在启动', running: '运行中', completed: '运行成功', failed: '运行失败', cancelled: '已停止', interrupted: '运行中断', paused: '已暂停', stopping: '正在清理' }
const states = { pending: '等待归档', unavailable: '无可用追踪', partial: '部分采集', saved: '已归档' }
function title(event: TraceEvent) {
  if (event.kind === 'execution') return `${event.nodeLabel || event.nodeId} · ${event.phase === 'execution:node_start' ? '开始' : event.success === false ? '失败' : '完成'}`
  if (event.kind === 'network') return `${event.method} ${event.status} · ${event.url}`
  return event.message || '页面已关闭'
}

function Snapshot({ runId, artifactId, dom = false }: { runId: string; artifactId?: string | null; dom?: boolean }) {
  const [source, setSource] = useState(''), [error, setError] = useState(''), [text, setText] = useState<string | null>(null)
  useEffect(() => {
    let cancelled = false, url = ''
    const connection = getStudioTransportRevision()
    setSource(''); setError(''); setText(null)
    if (artifactId) void workflowApi.getRunArtifact(runId, artifactId).then(async result => {
      if (cancelled || connection !== getStudioTransportRevision()) return
      if (!result.success || !result.data) { setError(result.error || '快照读取失败'); return }
      if (dom) {
        if (result.data.size > 8 * 1024 * 1024 || !result.data.type.startsWith('text/html')) { setError('DOM 证据格式或大小无效'); return }
        const content = await result.data.text()
        if (!cancelled && connection === getStudioTransportRevision()) setText(content.length > 65536 ? content.slice(0, 65536) + '\n…预览限前 65,536 字符，完整文件仍在运行产物中。' : content)
        return
      }
      if (result.data.type !== 'image/png') { setError('快照格式不受支持'); return }
      url = URL.createObjectURL(result.data); setSource(url)
    })
    return () => { cancelled = true; if (url) URL.revokeObjectURL(url) }
  }, [runId, artifactId, dom])
  if (dom && text !== null) return <pre aria-label="只读 DOM 原文" className="overflow-auto whitespace-pre-wrap break-all text-xs">{text}</pre>
  return source ? <img src={source} alt="该次执行结束时的页面快照" className="h-full w-full object-contain object-top" /> :
    <div className="flex h-full min-h-24 flex-col items-center justify-center gap-2 text-xs text-muted-foreground"><ImageOff className="h-5 w-5" />{error || (artifactId ? '正在读取页面快照…' : '此条证据没有页面快照')}</div>
}

export function TracePanel({ runId }: { runId: string }) {
  const [page, setPage] = useState<TracePage | null>(null)
  const [kind, setKind] = useState(''), [cursor, setCursor] = useState(0), [selected, setSelected] = useState<string | null>(null)
  const [loading, setLoading] = useState(false), [error, setError] = useState(''), [downloading, setDownloading] = useState(false)
  const [showDom, setShowDom] = useState(false)
  const [compare, setCompare] = useState(false), [detailsShown, setDetailsShown] = useState(false)
  const request = useRef(0), downloadRequest = useRef(0)
  const load = useCallback(async () => {
    const token = ++request.current, connection = getStudioTransportRevision()
    setLoading(true); setError('')
    const result = await workflowApi.getRunTrace(runId, cursor, kind)
    if (token !== request.current || connection !== getStudioTransportRevision()) return
    setLoading(false)
    if (!result.success || !result.data) { setError(result.error || 'Trace 读取失败'); return }
    setPage(result.data)
    setSelected(previous => result.data!.events.some(row => row.id === previous) ? previous : result.data!.events.find(row => row.snapshotId)?.id || result.data!.events[0]?.id || null)
  }, [runId, cursor, kind])
  useEffect(() => {
    setPage(null); setSelected(null); setCompare(false); setShowDom(false)
    void load()
    const refresh = () => { setPage(null); setDownloading(false); downloadRequest.current++; void load() }
    window.addEventListener('studio:transport-changed', refresh)
    window.addEventListener('studio:connection-restored', refresh)
    return () => {
      request.current++; downloadRequest.current++
      window.removeEventListener('studio:transport-changed', refresh)
      window.removeEventListener('studio:connection-restored', refresh)
    }
  }, [load])
  useEffect(() => {
    if (page?.status !== 'pending') return
    const timer = window.setTimeout(() => void load(), 2000)
    return () => window.clearTimeout(timer)
  }, [page, load])
  const event = page?.events.find(row => row.id === selected)
  const previous = event && page?.events.slice(0, page.events.indexOf(event)).findLast(row => row.snapshotId && row.pageId === event.pageId)
  const download = async () => {
    if (!page?.archiveId || downloading) return
    const token = ++downloadRequest.current, connection = getStudioTransportRevision()
    setDownloading(true); setError('')
    const result = await workflowApi.getRunArtifact(runId, page.archiveId)
    if (token !== downloadRequest.current || connection !== getStudioTransportRevision()) return
    setDownloading(false)
    if (!result.success || !result.data) { setError(result.error || '归档下载失败'); return }
    const url = URL.createObjectURL(result.data), link = document.createElement('a')
    link.href = url; link.download = `trace-${runId}.zip`; link.click(); URL.revokeObjectURL(url)
  }
  return <section aria-label="浏览器追踪" className="flex min-h-0 flex-1 flex-col text-xs">
    <div className="flex flex-wrap items-center gap-3 border-b px-3 py-2">
      <Activity className="h-4 w-4 text-primary" /><strong>Trace 时间线</strong>
      <span className="text-muted-foreground">{page ? `${runStates[page.runStatus] || page.runStatus} / ${states[page.status]}` : '正在读取'} · 本地证据</span>
      <SelectNative aria-label="证据类型" value={kind} onChange={e => { setKind(e.target.value); setCursor(0) }} className="h-7 w-32">
        {Object.entries(kinds).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </SelectNative>
      <Button size="sm" variant="ghost" disabled={loading} onClick={() => void load()}><RefreshCw className="mr-1 h-3 w-3" />刷新</Button>
      <Button size="sm" variant="outline" disabled={!page?.archiveId || downloading} onClick={() => void download()}><Download className="mr-1 h-3 w-3" />下载原始追踪</Button>
      <Button size="sm" variant="outline" disabled={!page?.traceId} onClick={() => {
        const prompt = `请诊断运行 ${runId} 的浏览器追踪${event ? `，重点检查证据 ${event.id}` : ''}。先用 get_trace_summary 核实采集范围，再按需读取证据，引用证据 ID 并区分观察和推测。`
        if (!emitAssistantUiEvent('ask_ai', { prompt, autoSend: false })) setError('小助手面板尚未连接')
      }}><Sparkles className="mr-1 h-3 w-3" />交给小助手</Button>
    </div>
    {error && <p role="alert" className="px-3 py-2 text-destructive">{error}</p>}
    {page?.status === 'pending' && <p role="status" className="p-4 text-muted-foreground">浏览器会话结束后展示已归档证据。停止时会先尝试保存追踪，再清理浏览器。</p>}
    {page?.status === 'unavailable' && <p className="p-4 text-muted-foreground">本次运行没有可读取的 Trace。可能是历史运行、未启动浏览器或采集异常；没有用当前页面替代历史证据。</p>}
    {!!page?.gaps.length && <details className="border-b bg-amber-50 px-3 py-1.5 text-amber-900"><summary className="cursor-pointer"><AlertTriangle className="mr-1 inline h-3 w-3" />采集范围说明 · {page.gaps.length} 项</summary>{page.gaps.map(gap => <p key={gap} className="py-1">{gap}</p>)}</details>}
    {!!page?.events.length && <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-[minmax(180px,26%)_minmax(240px,1fr)_minmax(180px,25%)] overflow-auto">
      <div aria-label="追踪事件" className={`min-h-0 overflow-auto border-r ${detailsShown ? 'hidden md:block' : ''}`}>
        {page.events.map(row => <button key={row.id} onClick={() => { setSelected(row.id); setCompare(false); setShowDom(false); setDetailsShown(true) }} aria-pressed={selected === row.id} className={`flex w-full gap-2 border-b px-3 py-2.5 text-left ${selected === row.id ? 'bg-primary/10 text-primary' : 'hover:bg-muted'}`}>
          {row.kind === 'network' ? <Globe className="mt-1 h-3 w-3 shrink-0" /> : row.kind === 'execution' ? <Activity className="mt-1 h-3 w-3 shrink-0" /> : <Terminal className="mt-1 h-3 w-3 shrink-0" />}
          <span className="min-w-0"><span className="block truncate">{title(row)}</span><span className="mt-1 block text-[10px] text-muted-foreground">+{(row.timeMs / 1000).toFixed(3)} s · {row.pageId || '无页面归属'}</span></span>
        </button>)}
      </div>
      <div className={`min-h-0 flex-col bg-muted/20 ${detailsShown ? 'flex' : 'hidden md:flex'}`}>
        <button onClick={() => setDetailsShown(false)} className="border-b p-2 text-left md:hidden">返回事件列表</button>
        <div className="flex items-center justify-between border-b px-3 py-2"><span>只读页面证据</span>{event?.domId && <button onClick={() => { setShowDom(!showDom); setCompare(false) }}>{showDom ? '查看截图' : '查看 DOM 原文'}</button>}<button disabled={showDom || !previous || !event?.snapshotId} onClick={() => setCompare(!compare)} className="disabled:opacity-40">{compare ? '单张查看' : '对比上一张同页快照'}</button></div>
        <div className={`grid min-h-0 flex-1 gap-2 p-3 ${compare ? 'grid-cols-2' : ''}`}>
          {compare && <Snapshot key={previous?.id} runId={runId} artifactId={previous?.snapshotId} />}
          <Snapshot key={event?.id} runId={runId} dom={showDom} artifactId={showDom ? event?.domId : event?.snapshotId} />
        </div>
      </div>
      <aside aria-label="证据详情" className={`min-h-0 overflow-auto border-l p-3 ${detailsShown ? '' : 'hidden md:block'}`}>
        <strong>证据详情</strong>
        {event && <dl className="mt-3 space-y-3 break-words">
          <div><dt className="text-muted-foreground">证据 ID</dt><dd>{event.id}</dd></div>
          {event.executionId && <div><dt className="text-muted-foreground">执行标识</dt><dd>{event.executionId}</dd></div>}
          <div><dt className="text-muted-foreground">记录时间</dt><dd>{event.timestamp}</dd></div>
          <div><dt className="text-muted-foreground">内容</dt><dd className="whitespace-pre-wrap">{title(event)}{event.truncated && '（摘要已截断）'}</dd></div>
          {event.description && <div><dt className="text-muted-foreground">说明</dt><dd>{event.description}</dd></div>}
          {event.correlation && <div><dt className="text-muted-foreground">业务关联</dt><dd>{event.correlation}</dd></div>}
          {event.gaps?.map(gap => <div key={gap} className="text-amber-800">{gap}</div>)}
          {event.attribution && <div className="text-muted-foreground">后台页面事件；未推断属于某个节点。</div>}
          {event.executionContext != null && <div><dt className="text-muted-foreground">执行上下文</dt><dd><pre className="whitespace-pre-wrap">{JSON.stringify(event.executionContext, null, 2)}</pre></dd></div>}
        </dl>}
      </aside>
    </div>}
    {page && page.total > 0 && <div className="flex items-center gap-3 border-t px-3 py-1.5 text-muted-foreground"><span>{cursor + 1}–{cursor + page.events.length} / {page.total} 条</span><button disabled={loading || cursor === 0} onClick={() => setCursor(Math.max(0, cursor - 100))}>上一页</button><button disabled={loading || page.nextCursor == null} onClick={() => setCursor(page.nextCursor!)}>下一页</button><span className="ml-auto">页面内容不在面板中执行 · 原始归档仅主动下载</span></div>}
  </section>
}
