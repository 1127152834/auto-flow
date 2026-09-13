import { useEffect, useRef, useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Textarea } from '../../../shared/components/ui/textarea'
import { ApiClientError } from '../../../shared/api/client'
import type { InspectionApi, InspectionPick, InspectionResult, InspectionSession } from '../inspection-api'
import type { WorkflowNode, WorkflowVariable } from '../types'

type Props = { api: InspectionApi; session: InspectionSession | null; node: WorkflowNode; documentId: string; variables: WorkflowVariable[]; disabled: boolean; commit(): void; apply(patch: Record<string, unknown>): void }
export function SelectorTools({ api, session, node, documentId, variables, disabled, commit, apply }: Props) {
  const [pick, setPick] = useState<InspectionPick | null>(null)
  const [test, setTest] = useState<InspectionResult | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const framePath = Array.isArray(node.config.framePath) ? node.config.framePath.map(String) : []
  const page = session?.pages.find(item => item.pageId === session.targetPageId)
  const key = JSON.stringify([documentId, node.id, node.config.selector, framePath, variables, session?.sessionId, page?.pageId, page?.revision])
  const latest = useRef(key); latest.current = key
  const generation = useRef(0)
  const request = useRef<{ id: string; sessionId: string; pageId: string; key: string } | null>(null)
  const visibleKey = useRef('')
  const allowed = !disabled && session?.state === 'ready' && Boolean(page)
  useEffect(() => {
    generation.current++
    const previous = request.current
    request.current = null
    if (previous) void api.cancel(previous.sessionId, previous.id).catch(() => undefined)
    return () => { generation.current++ }
  }, [key, api])
  useEffect(() => {
    if (!pick || pick.state !== 'pending' || !request.current) return
    const captured = request.current
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      try {
        const value = await api.getPick(captured.sessionId, captured.id)
        if (!cancelled && latest.current === captured.key && request.current?.id === captured.id) {
          visibleKey.current = captured.key; setPick(value)
          if (value.state !== 'pending') return
        }
      } catch (error) {
        if (!cancelled && latest.current === captured.key) setMessage(error instanceof Error ? error.message : '拾取连接中断，请恢复连接')
      }
      if (!cancelled) timer = setTimeout(() => void poll(), 500)
    }
    timer = setTimeout(() => void poll(), 500)
    return () => { cancelled = true; clearTimeout(timer) }
  }, [pick, api])
  useEffect(() => () => {
    const pending = request.current
    if (pending) void api.cancel(pending.sessionId, pending.id).catch(() => undefined)
  }, [api])
  const startPick = async () => {
    if (!allowed || !session || !page || busy) return
    commit()
    const captured = { id: crypto.randomUUID(), sessionId: session.sessionId, pageId: page.pageId, key }
    request.current = captured; visibleKey.current = key
    const token = ++generation.current
    setBusy(true); setMessage(null); setTest(null)
    setPick({ requestId: captured.id, pageId: page.pageId, pageRevision: page.revision, state: 'pending', result: null, error: null })
    try {
      const value = await api.pick(captured.sessionId, captured.id, captured.pageId)
      if (latest.current === key && token === generation.current) setPick(value)
    } catch (error) {
      if (latest.current === key && token === generation.current) {
        setMessage(error instanceof Error ? error.message : '拾取请求响应未知，正在查询原请求')
        if (error instanceof ApiClientError && error.status >= 400 && error.status < 500) setPick(null)
      }
    } finally { setBusy(false) }
  }
  const cancel = async () => {
    const pending = request.current
    if (!pending) return
    try {
      const value = await api.cancel(pending.sessionId, pending.id)
      if (latest.current === pending.key) setPick(value)
    } catch (error) { setMessage(error instanceof Error ? error.message : '取消失败，请重试') }
  }
  const testSelector = async () => {
    if (!allowed || !session || !page || busy) return
    commit()
    const token = ++generation.current
    visibleKey.current = key; setBusy(true); setMessage(null); setTest(null); setPick(null)
    try {
      const value = await api.test(session.sessionId, { pageId: page.pageId, selector: String(node.config.selector ?? ''), framePath, variables })
      if (latest.current === key && token === generation.current && value.pageRevision === page.revision) setTest(value)
    } catch (error) { if (latest.current === key && token === generation.current) setMessage(error instanceof Error ? error.message : '定位测试失败') }
    finally { setBusy(false) }
  }
  const applyResult = async () => {
    const binding = request.current
    if (!binding || !allowed || busy) return
    setBusy(true)
    try {
      const verified = await api.getPick(binding.sessionId, binding.id)
      if (latest.current !== binding.key) return
      if (verified.state !== 'selected' || !verified.result || verified.pageRevision !== page?.revision) { setPick(verified); setMessage('页面或拾取结果已变化，请重新拾取'); return }
      commit(); apply({ selector: verified.result.selector, framePath: verified.result.framePath }); setPick(null)
    } catch (error) { if (latest.current === binding.key) setMessage(error instanceof Error ? error.message : '无法确认拾取结果，请重试') }
    finally { setBusy(false) }
  }
  const current = visibleKey.current === key
  return <div className="space-y-2" aria-label="元素定位工具">
    <label className="block text-xs text-muted" htmlFor={`frames-${node.id}`}>框架路径（每行一层，留空为主页面）</label>
    <Textarea id={`frames-${node.id}`} rows={2} disabled={disabled} value={framePath.join('\n')} onChange={event => apply({ framePath: event.target.value === '' ? [] : event.target.value.split('\n') })} />
    <div className="flex flex-wrap gap-2"><Button disabled={!allowed || busy || current && pick?.state === 'pending'} onClick={() => void startPick()}>拾取元素</Button><Button disabled={!allowed || busy} onClick={() => void testSelector()}>测试定位</Button>{current && pick?.state === 'pending' ? <Button disabled={disabled} onClick={() => void cancel()}>取消拾取</Button> : null}</div>
    {!allowed ? <p className="text-xs text-muted">请先打开拾取浏览器并选择目标标签页。</p> : null}
    {current && message ? <p role="alert" className="text-xs text-red-700">{message}</p> : null}
    {current && pick?.state === 'pending' ? <p role="status" className="text-xs text-muted">在浏览器中点击元素，Esc 取消。</p> : null}
    {current && pick?.error ? <p role="alert" className="text-xs text-red-700">{pick.error}</p> : null}
    {current && pick?.state === 'selected' && pick.result ? <div className="space-y-2 rounded-control border border-line p-2 text-xs" aria-label="拾取结果预览"><p>{pick.result.tag} · {pick.result.text}</p><code className="block break-all">{pick.result.selector}</code>{pick.result.framePath.length ? <p className="break-all">框架：{pick.result.framePath.join(' → ')}</p> : null}{pick.result.positional ? <p className="text-amber-800">此定位依赖页面结构，页面调整后需重新测试。</p> : null}<Button disabled={!allowed || busy} onClick={() => void applyResult()}>应用到节点</Button></div> : null}
    {current && test ? <div role="status" className="space-y-1 rounded-control border border-line p-2 text-xs"><p>匹配 {test.count} 个元素{test.first ? ` · 首个${test.first.visible ? '可见' : '不可见'}` : ''}</p>{test.first ? <p>{test.first.tag} · {test.first.text}</p> : null}{test.count > 1 ? <p className="text-amber-800">实际执行选择第一个匹配元素。</p> : null}{test.truncated ? <p>仅高亮前 100 个匹配中的可见元素。</p> : null}</div> : null}
    {!current && (pick || test) ? <p className="text-xs text-muted">页面或定位配置已变化，请重新拾取或测试。</p> : null}
  </div>
}
