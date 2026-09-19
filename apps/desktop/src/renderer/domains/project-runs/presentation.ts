import { ApiClientError } from '../../shared/api/client'

const apiFailureMessages: Record<string, string> = {
  VALIDATION_FAILED: '输入内容不符合要求，请检查后重试',
  REVISION_CONFLICT: '数据已被其他操作更新，请刷新后重试',
  LIFECYCLE_CONFLICT: '当前项目状态不允许执行此操作',
  RESOURCE_UNAVAILABLE: '运行所需资源当前不可用，请重新检查运行条件',
  RUN_FACTS_INCOMPLETE: '运行事实尚未完整写入，请稍后核对',
  RUN_EVENT_HISTORY_UNAVAILABLE: '运行事件记录不完整，无法继续补读',
  RUN_ARTIFACT_UNAVAILABLE: '运行截图当前不可读取',
  STATISTICS_RESULT_EXPIRED: '统计结果已过期，请刷新后重试',
}
const safeFailureMessages = new Set([
  '操作失败，请重试',
  '读取内容失败，请重试',
  '日志读取失败，请重试',
  '批次操作结果尚未确认，请核对原操作',
  ...Object.values(apiFailureMessages),
])
const staleTaskPrefix = '刷新失败，保留上次读取的任务：'

export function presentRunFailure(error: unknown, fallback = '操作失败，请重试') {
  if (typeof error === 'string') {
    if (safeFailureMessages.has(error)) return error
    if (error.startsWith(staleTaskPrefix) && safeFailureMessages.has(error.slice(staleTaskPrefix.length))) return error
    return fallback
  }
  if (!(error instanceof ApiClientError)) return fallback
  if (error.code && apiFailureMessages[error.code]) return apiFailureMessages[error.code]
  if (error.status === 401) return '本地服务认证已失效，请重新连接'
  if (error.status === 403) return '当前工作区无权执行此操作'
  if (error.status === 404) return '相关资料已不存在，请刷新后重试'
  if (error.status === 409) return '数据已发生变化，请刷新后重试'
  if (error.status === 422) return '输入内容不符合要求，请检查后重试'
  return fallback
}
