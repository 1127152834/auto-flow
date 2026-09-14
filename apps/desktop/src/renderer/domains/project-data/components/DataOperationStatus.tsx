import type { ReactNode } from 'react'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'

type Operation = components['schemas']['ProjectOperationView']
export function DataOperationStatus({ operation, error, busy = false, onRefresh, onReconcile, onStop, children }: {
  operation: Operation; error?: string | null; busy?: boolean
  onRefresh?(): void; onReconcile?(): void; onStop?(): void; children?: ReactNode
}) {
  const result = operation.result
  const batch = result && 'blocks' in result ? result : null
  const terminal = operation.status === 'succeeded' || operation.status === 'failed'
  const title = operation.status === 'succeeded' ? '操作已完成'
    : operation.status === 'failed' ? batch?.cancelled ? '后续处理已停止' : '操作未全部完成'
      : operation.status === 'reconciling' ? '正在核对已有结果'
        : operation.status === 'accepted' ? '已接受，等待处理' : '正在处理'
  const filename = result && 'filename' in result && typeof result.filename === 'string' ? result.filename : null
  const recordCount = result && 'recordCount' in result && typeof result.recordCount === 'number' ? result.recordCount : null
  return <section className="grid gap-3 rounded-control border border-line bg-surface p-4" aria-label="数据操作进度">
    <p role="status" aria-live="polite" className="m-0 text-sm font-medium">{title}</p>
    {batch ? <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm"><span>已修改 {batch.changedCount} 条</span><span>冲突 {batch.conflictCount} 条</span><span>未执行 {batch.notStartedCount} 条</span></div> : null}
    {operation.status === 'succeeded' && filename && recordCount !== null ? <p className="m-0 break-all text-sm">{filename} · {recordCount} 条记录</p> : null}
    {!terminal ? <p className="m-0 text-xs text-muted">关闭此视图不会取消已接受的操作，返回后可继续核对结果。</p> : null}
    {error ? <p role="alert" className="m-0 text-sm text-danger">{error}</p> : null}
    {children}
    <div className="flex flex-wrap gap-2">
      {onRefresh ? <Button size="sm" variant="ghost" disabled={busy} onClick={onRefresh}>刷新结果</Button> : null}
      {onReconcile ? <Button size="sm" disabled={busy} onClick={onReconcile}>核对文件结果</Button> : null}
      {!terminal && onStop ? <Button size="sm" variant="ghost" disabled={busy} onClick={onStop}>停止后续处理</Button> : null}
    </div>
  </section>
}
