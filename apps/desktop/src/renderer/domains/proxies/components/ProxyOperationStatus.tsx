import { CircleNotch } from '@phosphor-icons/react'
import type { RemoteOperation } from '../api'
import { Button } from '../../../shared/components/ui/button'

export function ProxyOperationStatus({ operation, busy, onReconcile, onAcknowledge }: {operation?: RemoteOperation; busy: boolean; onReconcile: () => void; onAcknowledge: () => void}) {
  if (!operation) return null
  const label: Record<string,string> = {change_ip:'更换 IP', relocate:'切换地点', save_rotation:'保存轮换计划', clear_rotation:'关闭轮换计划'}
  const running = operation.status === 'queued' || operation.status === 'running'
  return <div role="status" className="grid gap-2 rounded-control border border-line bg-surface-subtle p-4 text-sm">
    <span className="text-xs text-muted">{label[operation.kind] ?? '远程操作'}</span>
    <span className="flex items-center gap-2">{running && <CircleNotch className="animate-spin" aria-hidden="true" />}{running ? '操作已受理，正在等待远程结果…' : operation.status === 'unknown' ? '结果尚未确认' : operation.status === 'succeeded' ? '最近操作已确认完成' : '最近操作未完成'}</span>
    {running && <p className="text-xs text-muted">可关闭详情，后台会继续核实。不要重复提交。</p>}
    {!running && operation.error && <p className="text-muted">{operation.error.message}</p>}
    {operation.status === 'unknown' && <><p className="text-xs text-muted">请求可能已经生效。重新核实只读取远程状态，不会再次执行操作。</p><div className="flex flex-wrap gap-2"><Button disabled={busy} onClick={onReconcile}>重新核实</Button><Button disabled={busy} onClick={onAcknowledge}>处理未知结果</Button></div></>}
  </div>
}
