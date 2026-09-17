import { TableStatus } from '../../../shared/components/ui/table-status'

export type BatchStatusValue = 'accepted' | 'running' | 'blocked' | 'draining' | 'stopping' | 'reconciling' | 'completed' | 'stopped' | 'failed' | 'interrupted'
const labels: Record<BatchStatusValue, string> = { accepted: '已接受', running: '运行中', blocked: '等待资源', draining: '正在收尾', stopping: '正在停止', reconciling: '正在核对', completed: '已完成', stopped: '已停止', failed: '失败', interrupted: '已中断' }
export function BatchStatus({ status }: { status: BatchStatusValue }) {
  const tone = status === 'completed' ? 'success' : status === 'failed' || status === 'interrupted' ? 'danger' : status === 'blocked' || status === 'stopping' ? 'warning' : 'neutral'
  return <TableStatus tone={tone}>{labels[status]}</TableStatus>
}
