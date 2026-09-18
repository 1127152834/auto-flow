import type { ProjectRoute } from '../types'

export type ResourceLocator = { type: string; [key: string]: unknown }

const labels: Record<string, string> = {
  project: '项目',
  automation: '自动化',
  batch: '运行批次',
  task: '任务',
  table: '数据表',
  record: '记录',
  field: '字段',
  status: '业务状态',
  sheets: '表格连接',
  sync: '表格同步',
}

export function resourceLabel(type: string) {
  return labels[type] ?? '对象'
}

/** Stable identity of a locator, used to keep two panels from repeating one object. */
export function resourceKey(locator: ResourceLocator) {
  const identifiers = ['batchId', 'taskId', 'automationId', 'tableId', 'recordKey', 'fieldId', 'statusId', 'syncOperationId']
  const id = identifiers.map(name => locator[name]).find(value => typeof value === 'string' || typeof value === 'number')
  return `${locator.type}:${id === undefined ? '' : String(id)}`
}

/** Map an overview resource locator onto a workspace route; null when unreachable. */
export function resourceRoute(locator: ResourceLocator): ProjectRoute | null {
  const tableId = typeof locator.tableId === 'string' ? locator.tableId : undefined
  if (locator.type === 'batch' && typeof locator.batchId === 'string') return { tab: 'runs', batchId: locator.batchId }
  if (locator.type === 'task' && typeof locator.taskId === 'string') return { tab: 'runs', taskId: locator.taskId }
  if (locator.type === 'automation' && typeof locator.automationId === 'string') return { tab: 'automations', automationId: locator.automationId }
  if (['table', 'record', 'field', 'status'].includes(locator.type) && tableId) return { tab: 'data', tableId }
  return null
}
