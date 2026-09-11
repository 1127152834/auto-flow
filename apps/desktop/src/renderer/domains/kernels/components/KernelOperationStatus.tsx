import type { KernelOperation } from '../../../shared/api/types'
import { Button } from '../../../shared/components/ui/button'

const labels: Record<KernelOperation['state'], string> = {
  queued: '准备下载',
  downloading: '下载中',
  verifying: '正在校验',
  extracting: '正在安装',
  cancelling: '正在取消',
  cancelled: '下载已取消',
  completed: '安装完成',
  failed: '安装失败',
}

const activeStates = new Set<KernelOperation['state']>(['queued', 'downloading', 'verifying', 'extracting', 'cancelling'])

export function operationIsActive(operation: KernelOperation): boolean {
  return activeStates.has(operation.state)
}

export type KernelOperationStatusProps = {
  operation: KernelOperation
  cancelling?: boolean
  onCancel?(): void | Promise<void>
  onRetry?(): void | Promise<void>
}

export function KernelOperationStatus({ operation, cancelling = false, onCancel, onRetry }: KernelOperationStatusProps) {
  const active = operationIsActive(operation)
  const knownProgress = operation.progress !== null
  return <div className="mt-3 rounded-control border border-line bg-surface-subtle p-3" role="status">
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="font-medium text-ink">{labels[operation.state]}</span>
      {knownProgress ? <span>{operation.progress}%</span> : active ? <span>进度未知</span> : null}
    </div>
    {active ? <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line" role="progressbar" aria-label="内核安装进度" {...(knownProgress ? { 'aria-valuenow': operation.progress as number, 'aria-valuemin': 0, 'aria-valuemax': 100 } : { 'aria-valuetext': '进度未知' })}>
      <div className={knownProgress ? 'h-full rounded-full bg-clay transition-[width] duration-300' : 'h-full w-1/3 animate-pulse rounded-full bg-clay'} style={knownProgress ? { width: `${operation.progress}%` } : undefined} />
    </div> : null}
    {operation.message ? <p className="mb-0 mt-2 text-xs text-muted">{operation.message}</p> : null}
    {operation.error ? <p role="alert" className="mb-0 mt-2 text-xs text-red-700">{operation.error}</p> : null}
    {active && operation.state !== 'cancelling' && onCancel ? <Button type="button" variant="ghost" className="mt-2 h-8 px-2" disabled={cancelling} onClick={() => void onCancel()}>{cancelling ? '正在取消…' : '取消下载'}</Button> : null}
    {operation.state === 'failed' && onRetry ? <Button type="button" className="mt-2 h-8 px-3" onClick={() => void onRetry()}>重试下载</Button> : null}
  </div>
}
