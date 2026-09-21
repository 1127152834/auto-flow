// Source: WebRPA@5ccb900e; see SOURCE.md for provenance and adaptation boundaries.
import { useEffect, useState } from 'react'
import { Button } from '../controls/button'
import { useScheduledTaskStore, type ScheduledTask } from '../../hooks/stores/scheduledTaskStore'
import { CheckCircle2, XCircle, Clock, Trash2, RefreshCw, X } from 'lucide-react'
import { useConfirm } from '../controls/confirm-dialog'
import { DialogPortal } from '../controls/dialog-portal'

interface TaskLogsDialogProps {
  task: ScheduledTask
  open: boolean
  onClose: () => void
}

export function TaskLogsDialog({ task, open, onClose }: TaskLogsDialogProps) {
  const { logs, fetchTaskLogs, clearTaskLogs } = useScheduledTaskStore()
  const [loading, setLoading] = useState(false)
  const { confirm: showConfirm, ConfirmDialog } = useConfirm()

  useEffect(() => {
    if (open) {
      loadLogs()
    }
  }, [open, task.id])

  const loadLogs = async () => {
    setLoading(true)
    try {
      await fetchTaskLogs(task.id)
    } finally {
      setLoading(false)
    }
  }

  const handleClearLogs = async () => {
    const confirmed = await showConfirm(
      `确定要清空任务"${task.name}"的所有执行日志吗？此操作无法撤销。`,
      {
        title: '清空日志',
        confirmText: '清空',
        cancelText: '取消',
        type: 'warning'
      }
    )

    if (confirmed) {
      await clearTaskLogs(task.id)
    }
  }

  const formatDateTime = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  const formatDuration = (seconds?: number) => {
    if (seconds === undefined || seconds === null) return '-'
    if (seconds < 60) return `${seconds.toFixed(1)}秒`
    const minutes = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${minutes}分${secs}秒`
  }

  const getTriggerTypeLabel = (type: string) => {
    switch (type) {
      case 'time': return '时间触发'
      case 'hotkey': return '热键触发'
      case 'startup': return '启动触发'
      case 'manual': return '手动执行'
      case 'webhook': return 'Webhook触发'
      case 'repeat': return '重复执行'
      default: return type
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'success':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-medium">
            <CheckCircle2 className="w-3 h-3" />
            成功
          </span>
        )
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-medium">
            <XCircle className="w-3 h-3" />
            失败
          </span>
        )
      case 'running':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-medium">
            <Clock className="w-3 h-3 animate-spin" />
            执行中
          </span>
        )
      case 'queued':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 bg-amber-100 text-amber-700 rounded text-xs font-medium">
            <Clock className="w-3 h-3" />
            等待执行
          </span>
        )
      case 'stopped':
        return <span className="text-gray-500 text-xs">已停止</span>
      default:
        return <span className="text-gray-500 text-xs">{status}</span>
    }
  }

  if (!open) return null

  return (
    <DialogPortal>
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 animate-fade-in" style={{ zIndex: 2147483646 }} onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col animate-scale-in" onClick={(e) => e.stopPropagation()}>
        {/* 头部 */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-900">执行日志 - {task.name}</h2>
          <div className="flex items-center gap-2">
            <Button
              variant="tonal-success"
              size="sm"
              onClick={loadLogs}
              disabled={loading}
              className="gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              刷新
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleClearLogs}
              disabled={logs.length === 0}
              className="gap-2 text-red-600 hover:text-red-700"
            >
              <Trash2 className="w-4 h-4" />
              清空日志
            </Button>
            <Button variant="tonal-danger" size="icon" onClick={onClose} title="关闭">

              <X className="w-4 h-4" />

            </Button>
          </div>
        </div>

        {/* 内容 */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading && logs.length === 0 ? (
            <div className="flex items-center justify-center h-64 text-gray-500">
              加载中...
            </div>
          ) : logs.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-gray-500">
              <Clock className="w-16 h-16 mb-4 text-gray-300" />
              <p>暂无执行日志</p>
            </div>
          ) : (
            <div className="space-y-3">
              {logs.map(log => (
                <div
                  key={log.id}
                  className="border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors"
                >
                  {/* 头部 */}
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        {getStatusBadge(log.status)}
                        <span className="text-xs text-gray-500">
                          {getTriggerTypeLabel(log.trigger_type)}
                        </span>
                      </div>
                      {log.start_time && (
                        <div className="text-sm text-gray-600">
                          开始时间: {formatDateTime(log.start_time)}
                        </div>
                      )}
                      {log.end_time && (
                        <div className="text-sm text-gray-600">
                          结束时间: {formatDateTime(log.end_time)}
                        </div>
                      )}
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-medium text-gray-900">
                        耗时: {formatDuration(log.duration)}
                      </div>
                    </div>
                  </div>

                  {/* 执行统计 */}
                  <div className="grid grid-cols-3 gap-3 mb-3">
                    <div className="bg-gray-50 rounded p-2 text-center">
                      <div className="text-xs text-gray-600">执行节点</div>
                      <div className="text-lg font-semibold text-gray-900">
                        {log.executed_nodes}
                      </div>
                    </div>
                    <div className="bg-red-50 rounded p-2 text-center">
                      <div className="text-xs text-red-600">失败节点</div>
                      <div className="text-lg font-semibold text-red-700">
                        {log.failed_nodes}
                      </div>
                    </div>
                    <div className="bg-blue-50 rounded p-2 text-center">
                      <div className="text-xs text-blue-600">收集数据</div>
                      <div className="text-lg font-semibold text-blue-700">
                        {log.collected_data_count}
                      </div>
                    </div>
                  </div>

                  {/* 错误信息 */}
                  {log.error && (
                    <div className="bg-red-50 border border-red-200 rounded p-3 mb-3">
                      <div className="text-xs font-medium text-red-700 mb-1">
                        错误信息:
                      </div>
                      <div className="text-sm text-red-600 font-mono break-words">
                        {log.error}
                      </div>
                    </div>
                  )}

                  {/* 工作流完整日志 */}
                  {log.workflow_logs && log.workflow_logs.length > 0 && (
                    <div className="mt-3">
                      <details className="group">
                        <summary className="cursor-pointer text-sm font-medium text-gray-700 hover:text-blue-600 select-none outline-none">
                          查看完整执行日志 ({log.workflow_logs.length} 条)
                        </summary>
                        <div className="mt-2 bg-gray-900 rounded p-3 max-h-60 overflow-y-auto">
                          {log.workflow_logs.map((wlog: any, idx: number) => (
                            <div key={idx} className="mb-1 last:mb-0 text-xs font-mono break-words flex gap-2">
                              <span className="text-gray-500 shrink-0">
                                {new Date(wlog.timestamp).toLocaleTimeString()}
                              </span>
                              <span className={`
                                ${wlog.level === 'error' ? 'text-red-400' : ''}
                                ${wlog.level === 'warning' ? 'text-yellow-400' : ''}
                                ${wlog.level === 'success' ? 'text-green-400' : ''}
                                ${wlog.level === 'info' ? 'text-blue-300' : ''}
                                ${!['error', 'warning', 'success', 'info'].includes(wlog.level) ? 'text-gray-300' : ''}
                              `}>
                                {wlog.message}
                              </span>
                            </div>
                          ))}
                        </div>
                      </details>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      <ConfirmDialog />
    </div>
    </DialogPortal>
  )
}
