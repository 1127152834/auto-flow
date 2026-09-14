import type { ApiResponse, ExecutionLogPage, WorkflowRunPage } from '../api'
import { getStudioTransportRevision } from '../api/transport'

const levels = new Set(['debug', 'info', 'success', 'warning', 'error'])
const finiteInteger = (value: unknown, minimum = 0) => Number.isSafeInteger(value) && Number(value) >= minimum
const text = (value: unknown) => typeof value === 'string'

export async function checkedExecutionLogPage(request: Promise<ApiResponse<unknown>>, expectedRunId: string): Promise<ApiResponse<ExecutionLogPage>> {
  const revision = getStudioTransportRevision()
  const result = await request
  if (revision !== getStudioTransportRevision()) return { success: false, error: '服务连接已变更，旧运行日志未应用' }
  const page = result.data as ExecutionLogPage | undefined
  const valid = result.success && page && page.runId === expectedRunId && text(page.workflowId)
    && finiteInteger(page.total) && (page.nextCursor === null || page.nextCursor === undefined || finiteInteger(page.nextCursor, 1))
    && Array.isArray(page.items) && page.items.length <= page.total
    && page.items.every((item, index) => text(item.id) && !!item.id.trim() && text(item.timestamp)
      && levels.has(item.level) && text(item.message) && finiteInteger(item.sequence, 1)
      && (index === 0 || item.sequence > page.items[index - 1].sequence))
  return valid ? { ...result, data: page } : { success: false, httpStatus: result.httpStatus, error: result.error || '运行日志响应无效' }
}

export async function checkedWorkflowRunPage(request: Promise<ApiResponse<unknown>>): Promise<ApiResponse<WorkflowRunPage>> {
  const revision = getStudioTransportRevision()
  const result = await request
  if (revision !== getStudioTransportRevision()) return { success: false, error: '服务连接已变更，旧运行历史未应用' }
  const page = result.data as WorkflowRunPage | undefined
  const valid = result.success && page && finiteInteger(page.total)
    && (page.nextCursor === null || page.nextCursor === undefined || finiteInteger(page.nextCursor, 1))
    && Array.isArray(page.items) && page.items.length <= page.total
    && page.items.every(item => text(item.runId) && !!item.runId.trim() && text(item.workflowId)
      && !!item.workflowId.trim() && text(item.documentId) && !!item.documentId.trim()
      && text(item.startedAt) && finiteInteger(item.logCount))
  return valid ? { ...result, data: page } : { success: false, httpStatus: result.httpStatus, error: result.error || '运行历史响应无效' }
}
