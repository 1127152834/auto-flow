import { useCallback, useEffect, useRef, useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { useWorkflowDebug } from '../hooks/useWorkflowDebug'
import { isRunActive, parseDebugValues, type DebugCommand, type DebugVariables, type RunRead } from '../run-types'
import type { WorkflowRunApi } from '../run-api'

export function DebugPanel({ run, api, connected, refresh, stop }: { run: RunRead; api: WorkflowRunApi; connected: boolean; refresh(): void; stop(): void }) {
  const control = useWorkflowDebug(api, run, connected, refresh)
  const [variables, setVariables] = useState<DebugVariables | null>(null)
  const [checkpoint, setCheckpoint] = useState('')
  const [patch, setPatch] = useState('{}')
  const [error, setError] = useState('')
  const [detail, setDetail] = useState('')
  const [page, setPage] = useState('')
  const [pageAlias, setPageAlias] = useState('')
  const [url, setUrl] = useState('')
  const generation = useRef(0)
  const paused = run.state === 'paused'
  const inspect = paused || run.state === 'failed_paused'
  const busy = Boolean(control.pending) || !connected
  const point = typeof run.debug?.checkpointId === 'string' ? run.debug.checkpointId : ''
  const pause = String(run.debug?.pauseId ?? '')
  useEffect(() => { setPatch('{}'); setCheckpoint(''); setDetail(''); setError('') }, [pause])
  useEffect(() => {
    const current = ++generation.current
    setVariables(null); setDetail('')
    if (connected) void api.variables(run.runId, checkpoint || point).then(value => { if (generation.current === current) setVariables(value) }).catch(e => { if (generation.current === current) setError(String(e)) })
    return () => { generation.current++ }
  }, [api, checkpoint, connected, point, run.runId])
  const load = useCallback(async (offset = 0, after = 0) => {
    const current = generation.current
    try {
      const result = await api.variables(run.runId, checkpoint || point, offset, after)
      if (generation.current !== current) return
      setVariables(previous => ({ ...result, items: offset ? [...(previous?.items ?? []), ...result.items].slice(-200) : result.items, diagnosticArtifacts: after ? [...(previous?.diagnosticArtifacts ?? []), ...(result.diagnosticArtifacts ?? [])].slice(-200) : result.diagnosticArtifacts }))
    } catch (e) { if (generation.current === current) setError(String(e)) }
  }, [api, checkpoint, point, run.runId])
  const send = (action: DebugCommand['action'], extras: Partial<DebugCommand> = {}) => {
    if (['step', 'resume'].includes(action) && patch.trim() !== '{}') { setError('请先应用或放弃尚未提交的变量修改'); return }
    setError(''); void control.send(action, extras)
  }
  const apply = () => {
    try { const values = parseDebugValues(patch); send('variables', { values }) }
    catch (e) { setError(String(e)) }
  }
  useEffect(() => { if (control.response?.state === 'applied' && control.appliedAction === 'variables') setPatch('{}') }, [control.response, control.appliedAction])
  const openValue = async (id: string) => { const current = generation.current; try { const text = await (await api.artifact(run.runId, id)).text(); if (generation.current === current) setDetail(text.slice(0, 65536)) } catch (e) { if (generation.current === current) setError(String(e)) } }
  const pages = (control.response?.data?.pages ?? []) as { pageId: string; title: string; url: string }[]
  const breakpoints = (run.debug?.breakpoints ?? []) as string[]
  return <section aria-label="调试工作台" className="flex h-full min-h-0 flex-col gap-3 bg-surface px-5 py-3 text-xs">
    <div className="flex shrink-0 flex-wrap items-center gap-2 bg-surface"><strong>{run.state === 'failed_paused' ? '失败现场 · 只读检查' : '调试控制'}</strong><Button disabled={busy || run.state !== 'running'} onClick={() => send('pause')}>暂停</Button><Button disabled={busy || !paused} onClick={() => send('resume')}>继续</Button><Button disabled={busy || !paused} onClick={() => send('step')}>单步</Button><Button disabled={!connected || !isRunActive(run)} onClick={stop}>结束调试</Button><span>待执行：{String(run.debug?.pendingNodeId ?? '—')} · {({ start: '起点暂停', step: '单步完成', pause: '请求暂停', breakpoint: '断点命中', target: '已到达目标', failure: '执行失败' } as Record<string, string>)[String(run.debug?.pauseReason)] ?? ''} · 累计暂停 {Number(run.debug?.pauseDurationMs ?? 0)} ms</span></div>
    <div className="min-h-0 flex-1 space-y-3 overflow-auto">
    {Array.isArray(run.debug?.loopPath) && run.debug.loopPath.length ? <p>循环位置：{(run.debug.loopPath as { loopNodeId: string; iteration: number }[]).map(p => `${run.document.nodes.find(n => n.id === p.loopNodeId)?.label || p.loopNodeId} 第 ${p.iteration} 轮`).join(' / ')}</p> : null}
    {control.error || error ? <p role="alert" className="text-red-700">{control.error || error}</p> : null}
    {control.pending ? <p role="status">正在确认调试命令；不会重复发送单步</p> : null}
    <details><summary>本次运行断点（绑定启动快照）</summary><div className="flex flex-wrap gap-3 py-2">{run.document.nodes.map(node => <label key={node.id}><input type="checkbox" disabled={busy || !isRunActive(run) || run.state === 'failed_paused'} checked={breakpoints.includes(node.id)} onChange={e => send('breakpoints', { breakpoints: e.target.checked ? [...breakpoints, node.id] : breakpoints.filter(id => id !== node.id) })} /> {node.label || node.type}</label>)}</div></details>
    {inspect ? <div className="flex flex-wrap items-center gap-2"><Button disabled={busy} onClick={() => send('pages')}>刷新标签页</Button><Select className="w-52" aria-label="调试目标页" value={page} onChange={e => setPage(e.target.value)}><option value="">选择目标标签页</option>{pages.map(p => <option key={p.pageId} value={p.pageId}>{p.title || p.url}</option>)}</Select><Input className="w-72" aria-label="调试导航地址" placeholder="https://…" value={url} onChange={e => setUrl(e.target.value)} /><Input aria-label="调试页面别名" placeholder="页面别名（可选）" value={pageAlias} onChange={e => setPageAlias(e.target.value)} /><Button disabled={busy || !page} onClick={() => send('page', { pageId: page, url: url || null, pageAlias: pageAlias || null, focus: true })}>选择／导航并聚焦</Button></div> : null}
    <div className="grid grid-cols-2 gap-4"><div><h3 className="mb-2 font-semibold">{checkpoint ? '历史变量（只读）' : '当前变量'}</h3><Button disabled={!checkpoint} onClick={() => setCheckpoint('')}>返回当前检查点</Button>{variables?.items.map(item => <button key={String(item.name)} className="block w-full truncate border-b border-line py-1 text-left" onClick={() => void openValue(String(item.artifactId))}>{String(item.name)} · {item.scope ? `循环 ${String(item.scope)} / 只读` : '流程级'} · {({ str: '字符串', int: '数字', float: '数字', bool: '布尔', list: '列表', dict: '对象', NoneType: 'null' } as Record<string, string>)[String(item.type)] || String(item.type)} · {String(item.preview)} · 来源 {({ manual: '人工修改', node: '节点输出', scope: '循环绑定', initial: '声明初值' } as Record<string, string>)[String(item.source)] ?? String(item.source ?? '声明初值')}</button>)}{variables?.nextOffset != null ? <Button onClick={() => void load(variables.nextOffset!)}>更多变量</Button> : null}
    {!variables?.checkpointId ? <p>此运行尚未记录变量检查点</p> : null}
    {paused && !checkpoint ? <><label className="mt-2 block">原子修改运行变量（JSON）<textarea aria-label="修改运行变量" className="mt-1 h-16 w-full rounded border border-line bg-canvas p-2 font-mono" value={patch} onChange={e => setPatch(e.target.value)} /></label><Button disabled={busy || patch.trim() === '{}'} onClick={apply}>应用变量修改</Button><Button onClick={() => setPatch('{}')}>放弃变量修改</Button></> : null}</div><div><h3 className="font-semibold">变量检查点与变化</h3><div className="max-h-40 overflow-auto">{variables?.diagnosticArtifacts?.map(item => <div key={String(item.id)} className="flex gap-2 py-1"><button onClick={() => void openValue(String(item.id))}>#{String(item.eventSeq)} · {run.document.nodes.find(n => n.id === item.nodeId)?.label || '流程'} · {item.diagnosticKind === 'checkpoint' ? '变量检查点' : '变量变化'}</button>{item.diagnosticKind === 'checkpoint' ? <button className="shrink-0 text-clay" onClick={() => setCheckpoint(String(item.id))}>查看检查点</button> : null}</div>)}</div>{variables?.nextCursor != null ? <Button onClick={() => void load(0, variables.nextCursor!)}>更多诊断</Button> : null}</div></div>
    {detail ? <details open><summary>诊断 JSON（最多展示 64 KiB，完整内容可通过导出读取）</summary><pre className="max-h-48 overflow-auto whitespace-pre-wrap break-all bg-canvas p-3">{detail}</pre></details> : null}
    </div>
  </section>
}
