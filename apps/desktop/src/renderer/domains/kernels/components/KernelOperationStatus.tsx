import { Progress } from '../../../shared/components/ui/progress'
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
  disabled?: boolean
  onCancel?(): void | Promise<void>
  onRetry?(): void | Promise<void>
}

export function KernelOperationStatus({ operation, cancelling = false, disabled = false, onCancel, onRetry }: KernelOperationStatusProps) {
  const active = operationIsActive(operation)
  const knownProgress = operation.progress !== null
  return <div className="mt-3 rounded-control border border-line bg-surface-subtle p-3" role="status">
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="font-medium text-ink">{labels[operation.state]}</span>
      {knownProgress ? <span>{operation.progress}%</span> : active ? <span>进度未知</span> : null}
    </div>
    {active ? <Progress className="mt-2" aria-label="内核安装进度" aria-valuetext={knownProgress ? undefined : '进度未知'} value={operation.progress} /> : null}
    {operation.message ? <p className="mb-0 mt-2 text-xs text-muted">{operation.message}</p> : null}
    {operation.error ? <p role="alert" className="mb-0 mt-2 text-xs text-danger">{operation.error}</p> : null}
    {active && operation.state !== 'cancelling' && onCancel ? <Button type="button" variant="ghost" className="mt-2 h-8 px-2" disabled={disabled || cancelling} onClick={() => void onCancel()}>{cancelling ? '正在取消…' : '取消下载'}</Button> : null}
    {operation.state === 'failed' && onRetry ? <Button type="button" className="mt-2 h-8 px-3" disabled={disabled} onClick={() => void onRetry()}>重试下载</Button> : null}
  </div>
}
