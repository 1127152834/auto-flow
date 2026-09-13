import { useEffect, useRef, useState } from 'react'
import { ApiClientError } from '../../../shared/api/client'
import { Button } from '../../../shared/components/ui/button'
import type { WorkflowRunApi } from '../run-api'
import type { RunRead } from '../run-types'

export function ManualHandoffPanel({ run, api, connected, onRefresh, onStop, standalone = false }: { standalone?: boolean; run: RunRead; api: WorkflowRunApi; connected: boolean; onRefresh(): void; onStop(): void }) {
  const [now, setNow] = useState(Date.now)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const inFlight = useRef(false)
  const retry = useRef<{ action: 'open' | 'continue'; requestId: string } | null>(null)
  const handoff = run.handoff
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer) }, [])
  if (!handoff || !['waiting_manual', 'resuming'].includes(run.state)) return null
  const remaining = Math.max(0, Math.ceil((Date.parse(handoff.deadlineAt) - now) / 1000))
  const control = async (action: 'open' | 'continue') => {
    if (inFlight.current) return
    inFlight.current = true; setPending(true); setError('')
    const command = retry.current ?? { action, requestId: crypto.randomUUID() }
    retry.current = command
    try {
      await api.handoff(run.runId, handoff.handoffId, command.action, command.requestId)
      retry.current = null
    } catch (reason) { if (reason instanceof ApiClientError && reason.status >= 400 && reason.status < 500) retry.current = null; setError(reason instanceof Error ? reason.message : '操作结果未知，请刷新后按原编号重试') }
    finally { inFlight.current = false; setPending(false); onRefresh() }
  }
  const unavailable = pending || !connected || run.state === 'resuming' || remaining === 0
  return <section aria-label="人工处理安卓" className="border-b border-line bg-surface-subtle px-5 py-4">
    <div className="flex items-start justify-between gap-4"><div><h2 className="font-semibold">{run.state === 'resuming' ? '正在收回控制权' : standalone ? '手动操作' : '等待人工处理'} · {run.targetName}</h2><p className="mt-1 text-sm">{handoff.prompt}</p></div><span className="text-sm text-muted">剩余 {remaining} 秒</span></div>
    <p role="status" className="mt-2 text-sm text-muted">{handoff.state === 'closed' ? standalone ? '窗口已关闭，可以重新打开，或结束操作释放设备。' : '窗口已关闭，工作流仍在等待。' : handoff.state === 'open' ? '请在 Mac 原生窗口操作，完成后回到这里继续。' : '设备仍由当前工作流占用，其他任务不会向它输入。'}</p>
    {(error || handoff.error) && <p role="alert" className="mt-2 text-sm text-red-700">{error || handoff.error}</p>}
    <div className="mt-3 flex gap-2">
      <Button disabled={unavailable || ['starting', 'open'].includes(handoff.state) || Boolean(retry.current)} onClick={() => void control('open')}>打开操作窗口</Button>
      <Button variant="primary" disabled={unavailable || Boolean(retry.current)} onClick={() => void control('continue')}>{standalone ? '结束操作' : '完成并继续'}</Button>
      {retry.current && <Button disabled={pending || !connected} onClick={() => void control(retry.current!.action)}>按原编号重试</Button>}
      <Button disabled={!connected} onClick={onStop}>{standalone ? '停止并清理' : '停止运行'}</Button>
    </div>
  </section>
}
